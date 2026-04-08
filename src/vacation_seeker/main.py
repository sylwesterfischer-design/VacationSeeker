from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

from .config import Settings
from .db import add_watch, connect, init_schema, list_enabled_watches
from .pipeline import run_once
from .run_audit import log_end, log_start, configure_run_logger
from .run_context import RunContext
from .scheduler import run_scheduler


def report_filename_for_destination(destination: str) -> str:
    """Bezpieczna nazwa pliku raportu lokalizacyjnego, np. report_Zakynthos.html."""
    s = (destination or "").strip()
    if not s:
        return "report_location.html"
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s)
    safe = safe.strip(" .") or "location"
    return f"report_{safe}.html"


def _resolve_report_output_path(settings: Settings, args: argparse.Namespace) -> str:
    """Ustal sciezke raportu: domyslnie report.html, chyba ze --report-filename lub --location-report."""
    if args.report_filename:
        filename = args.report_filename
    elif getattr(args, "location_report", False):
        filename = report_filename_for_destination(args.destination or "")
    else:
        filename = Path(settings.report_path).name
    if args.target_folder:
        return str(Path(args.target_folder) / filename)
    base = Path(settings.report_path).parent
    return str(base / filename)


def main() -> None:
    parser = argparse.ArgumentParser(description="VacationSeeker")
    parser.add_argument("command", choices=["run-once", "schedule", "add-watch", "list-watches"])
    parser.add_argument("--target-folder", default=None, help="Folder docelowy dla raportu HTML")
    parser.add_argument(
        "--report-filename",
        default=None,
        help="Nazwa pliku HTML w folderze docelowym (nadpisuje domyslne report.html)",
    )
    parser.add_argument(
        "--location-report",
        action="store_true",
        help="Zapisz jako report_<kierunek>.html zamiast nadpisywac report.html (wymaga --destination)",
    )
    parser.add_argument("--refresh-minutes", type=int, default=None, help="Nadpisanie interwalu schedulera")
    parser.add_argument("--destination", default=None, help="Nazwa kraju/miasta do watcha")
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--children-ages", default="12,14", help="Wiek dzieci, np. 12,14")
    parser.add_argument("--drop-ratio", type=float, default=0.5, help="Prog spadku vs mediana, np. 0.5 = 50%%")
    parser.add_argument("--max-total-pln", type=float, default=None, help="Maksymalny koszt calkowity rodziny")
    parser.add_argument("--email", default=None, help="Adres email dla alertow")
    parser.add_argument("--departure-from", default=None, help="Data odlotu od (YYYY-MM-DD)")
    parser.add_argument("--departure-to", default=None, help="Data odlotu do (YYYY-MM-DD)")
    parser.add_argument("--return-from", default=None, help="Data powrotu od (YYYY-MM-DD)")
    parser.add_argument("--return-to", default=None, help="Data powrotu do (YYYY-MM-DD)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Bez zapisu do DB/HTML/maili/webhook — tylko zbieranie i podsumowanie [dry-run] na stderr",
    )
    parser.add_argument(
        "--verbose-items",
        action="store_true",
        help="Log każdego kolektora (source_name -> liczba raw) na stderr / w pliku logu",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Wyłącz pasek tqdm / procenty kolektorów",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Plik logu UTF-8 (append): START/END run_id, traceback przy wyjątku",
    )
    args = parser.parse_args()

    settings = Settings()
    if args.target_folder or args.report_filename or args.location_report:
        settings.report_path = _resolve_report_output_path(settings, args)
    if args.refresh_minutes is not None:
        settings.refresh_minutes = max(1, args.refresh_minutes)
    if args.departure_from:
        settings.report_departure_from = args.departure_from
    if args.departure_to:
        settings.report_departure_to = args.departure_to
    if args.destination:
        settings.report_destination = args.destination
    if args.return_from:
        settings.report_return_from = args.return_from
    if args.return_to:
        settings.report_return_to = args.return_to
    settings.report_adults = max(1, args.adults)
    settings.report_children_ages = args.children_ages
    if args.command == "run-once":
        run_id = str(uuid.uuid4())
        ctx = RunContext(
            run_id=run_id,
            argv=sys.argv.copy(),
            dry_run=args.dry_run,
            verbose_items=args.verbose_items,
            no_progress=args.no_progress,
        )
        if args.log_file:
            ctx.logger = configure_run_logger(Path(args.log_file), run_id)
        log_start(ctx.logger, run_id, ctx.argv)
        try:
            _, alerts, summary = run_once(settings, ctx)
            if ctx.dry_run:
                print(f"OK. Dry-run. Alerts (nie wyslane): {len(alerts)}")
            else:
                print(f"OK. Report: {settings.report_path}")
                print(f"Alerts: {len(alerts)}")
            log_end(ctx.logger, run_id, "ok", 0)
        except Exception as exc:
            log_end(ctx.logger, run_id, "exception", 1, exc)
            raise
    elif args.command == "schedule":
        print(f"Scheduler started. Every {settings.refresh_minutes} minutes.")
        run_scheduler(settings)
    elif args.command == "add-watch":
        if not args.destination:
            raise SystemExit("Brak --destination, np. --destination Irlandia")
        conn = connect(settings.db_path)
        init_schema(conn)
        target_email = args.email or settings.default_alert_email
        if not target_email:
            raise SystemExit("Brak adresu email. Podaj --email albo VACATION_ALERT_EMAIL.")
        watch_id = add_watch(
            conn=conn,
            destination_query=args.destination,
            adults=max(1, args.adults),
            children_ages=args.children_ages,
            target_email=target_email,
            drop_ratio=max(0.01, min(args.drop_ratio, 0.95)),
            max_total_pln=args.max_total_pln,
            departure_from=args.departure_from,
            departure_to=args.departure_to,
        )
        conn.close()
        print(
            f"Dodano/zaaktualizowano watch #{watch_id}: {args.destination} | email: {target_email} | "
            f"od={args.departure_from} do={args.departure_to}"
        )
    else:
        conn = connect(settings.db_path)
        init_schema(conn)
        watches = list_enabled_watches(conn)
        if not watches:
            print("Brak aktywnych watchy.")
        for w in watches:
            print(
                f"#{w.id} | {w.destination_query} | dorosli={w.adults} | dzieci={w.children_ages} | "
                f"email={w.target_email} | prog={w.drop_ratio * 100:.0f}% | max={w.max_total_pln} | "
                f"od={w.departure_from} do={w.departure_to}"
            )
        conn.close()


if __name__ == "__main__":
    main()

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from collections import Counter

from .aggregator import rank, RankedResult
from .alerts import build_price_drop_alerts, send_webhook_alerts
from .availability_validator import filter_available_offers
from .collectors.extra_feeds import default_extra_collectors
from .collectors.live_sources import RainbowLastMinuteCollector, TuiLastMinuteCollector, WakacyjniPiraciRssCollector
from .collectors.mock_sources import MockCollector
from .config import Settings
from .db import (
    already_sent_watch_event,
    connect,
    init_schema,
    list_enabled_watches,
    latest_price_by_hash,
    save_offers,
    save_watch_event,
)
from .emailer import send_email
from .flight_fallback_links import FlightFallbackContext, parse_children_ages
from .models import Offer
from .normalizer import normalize
from .presenter_html import render_html
from .scorer import apply_scoring
from .run_context import RunContext, RunSummary
from .top_tier_email import maybe_send_top_tier_email
from .watcher import evaluate_watch


def _collect_with_progress(
    collectors: list,
    ctx: RunContext | None,
) -> tuple[list, dict[str, int], int]:
    """Zwraca (raw_offers, collected_counts, collectors_failed)."""
    raw_offers: list = []
    collected_counts: dict[str, int] = {}
    failed = 0
    n = len(collectors)
    use_manual = False
    seq = collectors
    if ctx is not None and not ctx.no_progress:
        try:
            from tqdm import tqdm

            seq = tqdm(collectors, desc="Collectors", file=sys.stderr, unit="src")
        except ImportError:
            use_manual = True
            seq = collectors

    for i, c in enumerate(seq):
        if ctx is not None and not ctx.no_progress and use_manual:
            sys.stderr.write(f"\rCollectors {i + 1}/{n} ({100 * (i + 1) / max(1, n):.0f}%)")
            sys.stderr.flush()
        try:
            chunk = c.collect()
            raw_offers.extend(chunk)
            collected_counts[c.source_name] = len(chunk)
            if ctx and ctx.verbose_items:
                msg = f"[item] {c.source_name} -> {len(chunk)} raw"
                if ctx.logger:
                    ctx.logger.info(msg)
                print(msg, file=sys.stderr)
        except Exception:
            collected_counts[c.source_name] = 0
            failed += 1
            if ctx and ctx.logger:
                ctx.logger.exception("collector failed: %s", c.source_name)
            elif ctx and ctx.verbose_items:
                print(f"[item] {c.source_name} -> EXCEPTION (see logger)", file=sys.stderr)
    if use_manual and ctx is not None and not ctx.no_progress:
        sys.stderr.write("\n")
    return raw_offers, collected_counts, failed


def run_once(settings: Settings, ctx: RunContext | None = None) -> tuple[RankedResult, list[str], RunSummary]:
    summary = RunSummary(dry_run=bool(ctx and ctx.dry_run))
    conn = connect(settings.db_path)
    init_schema(conn)
    previous_prices = latest_price_by_hash(conn)

    collectors = [
        WakacyjniPiraciRssCollector(),
        TuiLastMinuteCollector(),
        RainbowLastMinuteCollector(),
        *default_extra_collectors(),
    ]
    summary.collectors_total = len(collectors)
    raw_offers, collected_counts, coll_failed = _collect_with_progress(collectors, ctx)
    summary.collectors_failed = coll_failed
    before_validation_counts = _count_by_source(raw_offers)
    if not raw_offers and settings.use_mock_fallback:
        raw_offers = MockCollector().collect()
        collected_counts["mock_feed"] = len(raw_offers)
        before_validation_counts = _count_by_source(raw_offers)
    summary.raw_offers_scanned = len(raw_offers)
    after_validation_counts = before_validation_counts
    if settings.validate_offer_links:
        raw_offers = filter_available_offers(
            raw_offers,
            timeout_seconds=settings.validation_timeout_seconds,
            show_progress=ctx is not None and not ctx.no_progress,
        )
        after_validation_counts = _count_by_source(raw_offers)
    summary.after_validation = len(raw_offers)
    _print_source_telemetry(collected_counts, before_validation_counts, after_validation_counts, settings.validate_offer_links)

    offers = [normalize(r) for r in raw_offers]
    offers = apply_scoring(offers)
    summary.offers_normalized = len(offers)

    if not (ctx and ctx.dry_run):
        save_offers(conn, offers)
        summary.db_saved = True
    report_offers = _filter_report_offers(offers, settings)
    report_near, report_far = _split_offers_by_departure_horizon(report_offers, settings.report_horizon_months)
    summary.report_near_count = len(report_near)
    ranked = rank(report_near)

    alerts = build_price_drop_alerts(offers, previous_prices)
    if not (ctx and ctx.dry_run):
        send_webhook_alerts(settings.webhook_url, alerts)
        summary.webhook_sent = bool(settings.webhook_url)
    data_mode = _detect_data_mode(raw_offers)
    family_size = settings.report_adults + _children_count(settings.report_children_ages)
    alt_tips = _alternative_date_tips(offers, settings, family_size)

    best_highlight = None
    if report_near:
        best_highlight = min(report_near, key=lambda o: o.total_trip_cost_pln)

    flight_fallback: FlightFallbackContext | None = None
    if (
        not report_offers
        and settings.report_destination
        and settings.report_departure_from
        and settings.report_return_to
    ):
        flight_fallback = FlightFallbackContext(
            destination_label=settings.report_destination,
            departure_date=settings.report_departure_from,
            return_date=settings.report_return_to,
            origin_iata=settings.origin_airport_iata,
            adults=max(1, settings.report_adults),
            children_ages=parse_children_ages(settings.report_children_ages),
        )

    if not (ctx and ctx.dry_run):
        render_html(
            ranked,
            alerts,
            settings.report_path,
            report_near,
            data_mode,
            family_size,
            alt_tips,
            best_offer_highlight=best_highlight,
            flight_fallback=flight_fallback,
            offers_beyond_horizon=report_far,
            horizon_months=settings.report_horizon_months,
        )
        summary.html_written = True
        maybe_send_top_tier_email(conn, settings, report_near)
        summary.watch_emails_sent = _run_watches(conn, settings, offers)
    conn.close()
    if ctx and ctx.dry_run:
        sys.stdout.flush()
        _print_dry_run_summary(summary, settings)
    return ranked, alerts, summary


def _print_dry_run_summary(summary: RunSummary, settings: Settings) -> None:
    print(
        "[dry-run] scanned_raw=%d after_validation=%d normalized=%d report_near=%d | "
        "saved_db=%s html=%s webhook=%s | collectors_failed=%d"
        % (
            summary.raw_offers_scanned,
            summary.after_validation,
            summary.offers_normalized,
            summary.report_near_count,
            summary.db_saved,
            summary.html_written,
            summary.webhook_sent,
            summary.collectors_failed,
        ),
        file=sys.stderr,
    )
    print(f"[dry-run] report_path_would_be={settings.report_path}", file=sys.stderr)


def _run_watches(conn, settings: Settings, offers) -> int:
    sent_n = 0
    watches = list_enabled_watches(conn)
    for watch in watches:
        hit = evaluate_watch(watch, offers)
        if hit is None:
            continue
        if already_sent_watch_event(conn, hit.watch_id, hit.offer_id_hash):
            continue

        sent = send_email(settings, watch.target_email, hit.subject, hit.body)
        if sent:
            save_watch_event(conn, hit.watch_id, hit.offer_id_hash)
            sent_n += 1
    return sent_n


def _filter_report_offers(offers, settings: Settings):
    filtered = offers
    if settings.report_destination:
        q = settings.report_destination.lower()
        filtered = [
            o
            for o in filtered
            if q in o.destination_country.lower() or q in o.destination_city_or_region.lower()
        ]
    if settings.report_departure_from:
        frm = datetime.strptime(settings.report_departure_from, "%Y-%m-%d").date()
        filtered = [o for o in filtered if datetime.strptime(o.departure_date, "%Y-%m-%d").date() >= frm]
    if settings.report_departure_to:
        to = datetime.strptime(settings.report_departure_to, "%Y-%m-%d").date()
        filtered = [o for o in filtered if datetime.strptime(o.departure_date, "%Y-%m-%d").date() <= to]
    if settings.report_return_from:
        frm = datetime.strptime(settings.report_return_from, "%Y-%m-%d").date()
        filtered = [o for o in filtered if datetime.strptime(o.return_date, "%Y-%m-%d").date() >= frm]
    if settings.report_return_to:
        to = datetime.strptime(settings.report_return_to, "%Y-%m-%d").date()
        filtered = [o for o in filtered if datetime.strptime(o.return_date, "%Y-%m-%d").date() <= to]
    return filtered


def _split_offers_by_departure_horizon(
    offers: list[Offer],
    horizon_months: int,
) -> tuple[list[Offer], list[Offer]]:
    """
    Główne tabele raportu: wylot <= dziś + ~horizon_months miesięcy.
    Późniejsze terminy (np. za rok) trafiają do osobnej sekcji HTML.
    """
    if not offers:
        return [], []
    today = date.today()
    cutoff = today + timedelta(days=int(30.5 * horizon_months))
    near: list[Offer] = []
    far: list[Offer] = []
    for o in offers:
        try:
            d = datetime.strptime(o.departure_date, "%Y-%m-%d").date()
        except ValueError:
            near.append(o)
            continue
        if d <= cutoff:
            near.append(o)
        else:
            far.append(o)
    far.sort(key=lambda x: (x.departure_date, x.hotel_name))
    return near, far


def _detect_data_mode(raw_offers) -> str:
    if not raw_offers:
        return "NO_DATA"
    sources = {o.source_name for o in raw_offers}
    if sources == {"mock_feed"}:
        return "MOCK_ONLY"
    if "mock_feed" in sources:
        return "LIVE_PLUS_MOCK_FALLBACK"
    return "LIVE"


def _children_count(children_ages: str) -> int:
    if not children_ages:
        return 0
    return len([x for x in children_ages.split(",") if x.strip()])


def _count_by_source(raw_offers) -> dict[str, int]:
    if not raw_offers:
        return {}
    ctr = Counter(o.source_name for o in raw_offers)
    return dict(ctr)


def _print_source_telemetry(
    collected_counts: dict[str, int],
    before_validation_counts: dict[str, int],
    after_validation_counts: dict[str, int],
    validation_enabled: bool,
) -> None:
    sources = sorted(set(collected_counts) | set(before_validation_counts) | set(after_validation_counts))
    if not sources:
        print("[telemetry] Brak ofert ze wszystkich zrodel.")
        return
    print("[telemetry] Oferty per zrodlo:")
    for src in sources:
        collected = collected_counts.get(src, 0)
        before = before_validation_counts.get(src, 0)
        if validation_enabled:
            after = after_validation_counts.get(src, 0)
            dropped = max(0, before - after)
            print(
                f"[telemetry] {src}: collected={collected}, before_validation={before}, "
                f"after_validation={after}, dropped_by_validation={dropped}"
            )
        else:
            print(f"[telemetry] {src}: collected={collected}, offers={before}")


def _alternative_date_tips(offers, settings: Settings, family_size: int) -> list[str]:
    if not settings.report_destination or not settings.report_departure_from or not settings.report_return_to:
        return []
    try:
        dep = datetime.strptime(settings.report_departure_from, "%Y-%m-%d").date()
        ret = datetime.strptime(settings.report_return_to, "%Y-%m-%d").date()
    except ValueError:
        return []
    q = settings.report_destination.lower()
    candidates = [
        o
        for o in offers
        if (q in o.destination_country.lower() or q in o.destination_city_or_region.lower())
    ]
    if not candidates:
        return []

    def _best_for_window(d_from, d_to, r_from, r_to):
        scoped = [
            o
            for o in candidates
            if d_from <= datetime.strptime(o.departure_date, "%Y-%m-%d").date() <= d_to
            and r_from <= datetime.strptime(o.return_date, "%Y-%m-%d").date() <= r_to
        ]
        if not scoped:
            return None
        return min(scoped, key=lambda o: o.total_trip_cost_pln * family_size)

    base = _best_for_window(dep, dep, ret, ret)
    prev = _best_for_window(dep - timedelta(days=1), dep - timedelta(days=1), ret - timedelta(days=1), ret - timedelta(days=1))
    nxt = _best_for_window(dep + timedelta(days=1), dep + timedelta(days=1), ret + timedelta(days=1), ret + timedelta(days=1))

    tips: list[str] = []
    base_cost = (base.total_trip_cost_pln * family_size) if base else None
    for label, opt in [("1 dzien wczesniej", prev), ("1 dzien pozniej", nxt)]:
        if not opt:
            tips.append(f"{label}: brak oferty porownawczej.")
            continue
        opt_cost = opt.total_trip_cost_pln * family_size
        if base_cost is None:
            tips.append(f"{label}: {opt_cost:.0f} PLN (brak oferty bazowej do porownania).")
        elif opt_cost < base_cost:
            tips.append(f"{label}: TANIEJ o {base_cost - opt_cost:.0f} PLN (koszt rodziny: {opt_cost:.0f} PLN).")
        elif opt_cost > base_cost:
            tips.append(f"{label}: DROZEJ o {opt_cost - base_cost:.0f} PLN (koszt rodziny: {opt_cost:.0f} PLN).")
        else:
            tips.append(f"{label}: taki sam koszt ({opt_cost:.0f} PLN).")
    return tips


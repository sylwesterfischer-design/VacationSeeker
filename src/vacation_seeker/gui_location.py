"""
GUI do raportu lokalizacyjnego: lokalizacja (tekst), zakres dat wylotu i powrotu, osoby.
Uruchomienie: py -3 -m src.vacation_seeker.gui_location
Albo: run_raport_location_gui.bat
"""

from __future__ import annotations

import threading
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .config import Settings
from .main import report_filename_for_destination
from .pipeline import run_once
from .run_context import RunContext


ACCENT = "#ff6b00"
BG = "#f0f0f0"
CARD = "#ffffff"


class LocationReportApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("VacationSeeker — raport lokalizacyjny")
        self.configure(bg=BG)
        self.minsize(520, 620)
        self._build()

    def _build(self) -> None:
        pad = {"padx": 16, "pady": 8}
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            outer,
            text="Wpisz parametry wyszukiwania",
            font=("Segoe UI", 14, "bold"),
            bg=BG,
            fg="#222",
        ).pack(anchor="w", **pad)

        # Kierunek
        card1 = tk.Frame(outer, bg=CARD, highlightbackground="#ddd", highlightthickness=1)
        card1.pack(fill=tk.X, **pad)
        tk.Label(card1, text="📍 Kierunek", font=("Segoe UI", 10), bg=CARD, fg="#555").pack(anchor="w", padx=12, pady=(10, 0))
        self.var_destination = tk.StringVar(value="Zakynthos")
        e_dest = tk.Entry(card1, textvariable=self.var_destination, font=("Segoe UI", 12), relief=tk.FLAT, highlightthickness=1, highlightbackground="#ccc")
        e_dest.pack(fill=tk.X, padx=12, pady=(4, 12))

        # Zakres wylotu + zakres powrotu (Settings.report_*_from / *_to)
        card2 = tk.Frame(outer, bg=CARD, highlightbackground="#ddd", highlightthickness=1)
        card2.pack(fill=tk.X, **pad)
        tk.Label(
            card2,
            text="Terminy — zakresy (YYYY-MM-DD)",
            font=("Segoe UI", 10, "bold"),
            bg=CARD,
        ).pack(anchor="w", padx=12, pady=(10, 4))

        row_df = tk.Frame(card2, bg=CARD)
        row_df.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(row_df, text="Wylot od", bg=CARD, width=14, anchor="w").pack(side=tk.LEFT)
        self.var_dep_from = tk.StringVar(value="2026-06-20")
        tk.Entry(row_df, textvariable=self.var_dep_from, width=14, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=4)
        tk.Label(row_df, text="do", bg=CARD).pack(side=tk.LEFT, padx=4)
        self.var_dep_to = tk.StringVar(value="2026-06-30")
        tk.Entry(row_df, textvariable=self.var_dep_to, width=14, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=4)

        row_rf = tk.Frame(card2, bg=CARD)
        row_rf.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(row_rf, text="Powrót od", bg=CARD, width=14, anchor="w").pack(side=tk.LEFT)
        self.var_ret_from = tk.StringVar(value="2026-07-01")
        tk.Entry(row_rf, textvariable=self.var_ret_from, width=14, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=4)
        tk.Label(row_rf, text="do", bg=CARD).pack(side=tk.LEFT, padx=4)
        self.var_ret_to = tk.StringVar(value="2026-07-10")
        tk.Entry(row_rf, textvariable=self.var_ret_to, width=14, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=4)

        tk.Label(
            card2,
            text="Oferty muszą mieścić się w obu zakresach (wylot i powrót).",
            font=("Segoe UI", 8),
            fg="#666",
            bg=CARD,
        ).pack(anchor="w", padx=12, pady=(0, 12))

        # Osoby
        card3 = tk.Frame(outer, bg=CARD, highlightbackground="#ddd", highlightthickness=1)
        card3.pack(fill=tk.BOTH, expand=True, **pad)
        tk.Label(card3, text="Osoby", font=("Segoe UI", 11, "bold"), bg=CARD).pack(anchor="w", padx=12, pady=(10, 4))

        row_a = tk.Frame(card3, bg=CARD)
        row_a.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(row_a, text="Dorośli", bg=CARD).pack(side=tk.LEFT)
        self.spin_adults = tk.Spinbox(row_a, from_=1, to=9, width=4, font=("Segoe UI", 11))
        self.spin_adults.delete(0, tk.END)
        self.spin_adults.insert(0, "2")
        self.spin_adults.pack(side=tk.LEFT, padx=8)

        self.frame_children = tk.Frame(card3, bg=CARD)
        self.frame_children.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self._child_rows: list[tuple[tk.Frame, tk.Spinbox]] = []
        for age in (12, 14):
            self._add_child_row(age)

        btn_add = tk.Button(
            card3,
            text="+ Dodaj dziecko",
            command=lambda: self._add_child_row(10),
            bg="#e8e8e8",
            relief=tk.GROOVE,
            font=("Segoe UI", 10),
        )
        btn_add.pack(anchor="w", padx=12, pady=(0, 12))

        # Folder docelowy
        row_t = tk.Frame(outer, bg=BG)
        row_t.pack(fill=tk.X, **pad)
        tk.Label(row_t, text="Folder raportu:", bg=BG).pack(side=tk.LEFT)
        self.var_target = tk.StringVar(value=str(Path.cwd() / "target"))
        tk.Entry(row_t, textvariable=self.var_target, width=42).pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        tk.Button(row_t, text="…", width=3, command=self._pick_folder).pack(side=tk.LEFT)

        self.lbl_status = tk.Label(outer, text="", bg=BG, fg="#444", font=("Segoe UI", 9))
        self.lbl_status.pack(anchor="w", padx=16)

        self.btn_run = tk.Button(
            outer,
            text="Generuj raport lokalizacyjny",
            command=self._on_run,
            bg=ACCENT,
            fg="white",
            activebackground="#e65f00",
            activeforeground="white",
            font=("Segoe UI", 12, "bold"),
            relief=tk.FLAT,
            padx=16,
            pady=12,
            cursor="hand2",
        )
        self.btn_run.pack(fill=tk.X, padx=16, pady=(8, 8))

        prog_frame = tk.Frame(outer, bg=BG)
        prog_frame.pack(fill=tk.X, padx=16, pady=(0, 16))
        self.lbl_progress = tk.Label(
            prog_frame,
            text="",
            bg=BG,
            fg="#333",
            font=("Consolas", 9),
            anchor="w",
            justify=tk.LEFT,
        )
        self.lbl_progress.pack(fill=tk.X, anchor="w")
        self.progress_bar = ttk.Progressbar(
            prog_frame,
            mode="determinate",
            length=480,
            maximum=100,
        )
        self.progress_bar.pack(fill=tk.X, pady=(4, 0))

    def _schedule_progress(self, phase: str, current: int, total: int) -> None:
        """Wywołanie z wątku roboczego — aktualizacja UI w głównym wątku."""

        def update_ui() -> None:
            if total > 0:
                self.progress_bar.config(mode="determinate", maximum=max(1, total), value=min(current, total))
                pct = int(100 * min(current, total) / max(1, total))
                self.lbl_progress.config(text=f"{phase}  {current}/{total}  ({pct}%)")
            else:
                self.progress_bar.config(mode="indeterminate")
                self.progress_bar.start(12)
                self.lbl_progress.config(text=phase)
            self.update_idletasks()

        self.after(0, update_ui)

    def _reset_progress_ui(self) -> None:
        try:
            self.progress_bar.stop()
        except tk.TclError:
            pass
        self.progress_bar.config(mode="determinate", maximum=100, value=0)
        self.lbl_progress.config(text="")

    def _pick_folder(self) -> None:
        d = filedialog.askdirectory(initialdir=self.var_target.get() or ".")
        if d:
            self.var_target.set(d)

    def _add_child_row(self, default_age: int) -> None:
        fr = tk.Frame(self.frame_children, bg=CARD)
        fr.pack(fill=tk.X, pady=2)
        tk.Label(fr, text="Dziecko — wiek", bg=CARD, width=18, anchor="w").pack(side=tk.LEFT)
        sp = tk.Spinbox(fr, from_=0, to=17, width=4, font=("Segoe UI", 11))
        sp.delete(0, tk.END)
        sp.insert(0, str(default_age))
        sp.pack(side=tk.LEFT, padx=4)

        def remove() -> None:
            fr.destroy()
            if (fr, sp) in self._child_rows:
                self._child_rows.remove((fr, sp))

        tk.Button(fr, text="✕", command=remove, width=2).pack(side=tk.LEFT, padx=4)
        self._child_rows.append((fr, sp))

    def _collect_children_ages(self) -> str:
        ages = []
        for _fr, sp in self._child_rows:
            try:
                ages.append(str(int(sp.get())))
            except (ValueError, tk.TclError):
                continue
        return ",".join(ages)

    def _validate_dates(self, *fields: tuple[str, tk.StringVar]) -> str | None:
        import re

        pat = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for label, var in fields:
            v = var.get().strip()
            if not pat.match(v):
                return f"Niepoprawna data ({label}): użyj YYYY-MM-DD."
        return None

    def _parse_iso(self, s: str):
        from datetime import datetime

        return datetime.strptime(s.strip(), "%Y-%m-%d").date()

    def _validate_ranges(self) -> str | None:
        try:
            df = self._parse_iso(self.var_dep_from.get())
            dt = self._parse_iso(self.var_dep_to.get())
            rf = self._parse_iso(self.var_ret_from.get())
            rt = self._parse_iso(self.var_ret_to.get())
        except ValueError:
            return "Niepoprawny format daty (oczekiwano YYYY-MM-DD)."
        if df > dt:
            return "Zakres wylotu: data „od” nie może być późniejsza niż „do”."
        if rf > rt:
            return "Zakres powrotu: data „od” nie może być późniejsza niż „do”."
        return None

    def _on_run(self) -> None:
        dest = self.var_destination.get().strip()
        if not dest:
            messagebox.showwarning("VacationSeeker", "Podaj kierunek.")
            return
        err = self._validate_dates(
            ("wylot od", self.var_dep_from),
            ("wylot do", self.var_dep_to),
            ("powrót od", self.var_ret_from),
            ("powrót do", self.var_ret_to),
        )
        if err:
            messagebox.showerror("VacationSeeker", err)
            return
        err = self._validate_ranges()
        if err:
            messagebox.showerror("VacationSeeker", err)
            return
        try:
            adults = max(1, int(self.spin_adults.get()))
        except (ValueError, tk.TclError):
            messagebox.showerror("VacationSeeker", "Niepoprawna liczba dorosłych.")
            return

        target = self.var_target.get().strip() or "target"
        children = self._collect_children_ages()
        report_name = report_filename_for_destination(dest)
        report_path = str(Path(target) / report_name)

        self.btn_run.config(state=tk.DISABLED)
        self.lbl_status.config(text="Pobieranie i walidacja ofert… może potrwać kilka minut.")
        self.after(0, self._reset_progress_ui)

        def task() -> None:
            def done_ok(n_alerts: int) -> None:
                self._reset_progress_ui()
                self.btn_run.config(state=tk.NORMAL)
                self.lbl_status.config(text=f"Gotowe: {report_path}")
                messagebox.showinfo(
                    "VacationSeeker",
                    f"Zapisano raport lokalizacyjny:\n{report_path}\n\n"
                    f"(osobny plik — nie nadpisuje report.html z run_report.bat)\nAlerty: {n_alerts}",
                )

            def done_err(exc: BaseException) -> None:
                self._reset_progress_ui()
                self.btn_run.config(state=tk.NORMAL)
                self.lbl_status.config(text="Błąd.")
                messagebox.showerror("VacationSeeker", str(exc))

            try:
                settings = Settings()
                settings.report_path = report_path
                settings.report_destination = dest
                settings.report_departure_from = self.var_dep_from.get().strip()
                settings.report_departure_to = self.var_dep_to.get().strip()
                settings.report_return_from = self.var_ret_from.get().strip()
                settings.report_return_to = self.var_ret_to.get().strip()
                settings.report_adults = adults
                settings.report_children_ages = children

                run_id = str(uuid.uuid4())
                ctx = RunContext(
                    run_id=run_id,
                    argv=["gui_location", "run-once", f"--destination={dest}"],
                    dry_run=False,
                    verbose_items=False,
                    no_progress=True,
                    progress_callback=lambda ph, c, t: self._schedule_progress(ph, c, t),
                )
                _ranked, alerts, _ = run_once(settings, ctx)
                self.after(0, lambda: done_ok(len(alerts)))
            except Exception as e:  # noqa: BLE001
                self.after(0, lambda e=e: done_err(e))

        threading.Thread(target=task, daemon=True).start()


def main() -> None:
    app = LocationReportApp()
    app.mainloop()


if __name__ == "__main__":
    main()

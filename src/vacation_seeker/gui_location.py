"""
GUI do raportu lokalizacyjnego (Kierunek, zakresy dat, osoby) — styl uproszczony jak wyszukiwarka podróży.
Uruchomienie: py -3 -m src.vacation_seeker.gui_location
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

from .config import Settings
from .main import report_filename_for_destination
from .pipeline import run_once


ACCENT = "#ff6b00"
BG = "#f0f0f0"
CARD = "#ffffff"


class LocationReportApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("VacationSeeker — raport lokalizacyjny")
        self.configure(bg=BG)
        self.minsize(520, 560)
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

        # Jedna data wylotu + jedna data powrotu (filtr w pipeline: from=to)
        card2 = tk.Frame(outer, bg=CARD, highlightbackground="#ddd", highlightthickness=1)
        card2.pack(fill=tk.X, **pad)
        tk.Label(card2, text="Terminy (YYYY-MM-DD)", font=("Segoe UI", 10, "bold"), bg=CARD).pack(anchor="w", padx=12, pady=(10, 4))

        row_d = tk.Frame(card2, bg=CARD)
        row_d.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(row_d, text="Data wylotu", bg=CARD, width=14, anchor="w").pack(side=tk.LEFT)
        self.var_dep = tk.StringVar(value="2026-06-27")
        tk.Entry(row_d, textvariable=self.var_dep, width=16, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=4)

        row_r = tk.Frame(card2, bg=CARD)
        row_r.pack(fill=tk.X, padx=12, pady=(0, 12))
        tk.Label(row_r, text="Data powrotu", bg=CARD, width=14, anchor="w").pack(side=tk.LEFT)
        self.var_ret = tk.StringVar(value="2026-07-05")
        tk.Entry(row_r, textvariable=self.var_ret, width=16, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=4)

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
        self.btn_run.pack(fill=tk.X, padx=16, pady=(8, 16))

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

    def _on_run(self) -> None:
        dest = self.var_destination.get().strip()
        if not dest:
            messagebox.showwarning("VacationSeeker", "Podaj kierunek.")
            return
        err = self._validate_dates(
            ("data wylotu", self.var_dep),
            ("data powrotu", self.var_ret),
        )
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

        def task() -> None:
            def done_ok(n_alerts: int) -> None:
                self.btn_run.config(state=tk.NORMAL)
                self.lbl_status.config(text=f"Gotowe: {report_path}")
                messagebox.showinfo(
                    "VacationSeeker",
                    f"Zapisano raport lokalizacyjny:\n{report_path}\n\n"
                    f"(osobny plik — nie nadpisuje report.html z run_report.bat)\nAlerty: {n_alerts}",
                )

            def done_err(exc: BaseException) -> None:
                self.btn_run.config(state=tk.NORMAL)
                self.lbl_status.config(text="Błąd.")
                messagebox.showerror("VacationSeeker", str(exc))

            try:
                settings = Settings()
                settings.report_path = report_path
                settings.report_destination = dest
                d = self.var_dep.get().strip()
                r = self.var_ret.get().strip()
                settings.report_departure_from = d
                settings.report_departure_to = d
                settings.report_return_from = r
                settings.report_return_to = r
                settings.report_adults = adults
                settings.report_children_ages = children

                _ranked, alerts, _ = run_once(settings)
                self.after(0, lambda: done_ok(len(alerts)))
            except Exception as e:  # noqa: BLE001
                self.after(0, lambda e=e: done_err(e))

        threading.Thread(target=task, daemon=True).start()


def main() -> None:
    app = LocationReportApp()
    app.mainloop()


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .models import Offer


WINDOWS = [
    ("0-3 dni", 0, 3),
    ("4-7 dni", 4, 7),
    ("8-14 dni", 8, 14),
    ("15-30 dni", 15, 30),
    ("31-56 dni", 31, 56),
]


@dataclass
class RankedResult:
    solo: dict[str, list[Offer]]
    duo: dict[str, list[Offer]]


def _days_to_departure(departure_date: str) -> int:
    dep = datetime.strptime(departure_date, "%Y-%m-%d").date()
    return (dep - date.today()).days


def _window_name(days: int) -> str | None:
    for label, lo, hi in WINDOWS:
        if lo <= days <= hi:
            return label
    return None


def _sort_key(o: Offer) -> tuple[int, float, float]:
    return (_days_to_departure(o.departure_date), o.price_per_person_pln, -o.score)


def rank(offers: list[Offer]) -> RankedResult:
    solo = {label: [] for label, _, _ in WINDOWS}
    duo = {label: [] for label, _, _ in WINDOWS}

    for o in offers:
        days = _days_to_departure(o.departure_date)
        w = _window_name(days)
        if w is None:
            continue
        if o.people_supported in {"1", "unknown"}:
            solo[w].append(o)
        if o.people_supported in {"2", "unknown"}:
            duo[w].append(o)

    for bucket in (solo, duo):
        for k, arr in bucket.items():
            arr.sort(key=_sort_key)
            bucket[k] = arr[:5]

    return RankedResult(solo=solo, duo=duo)


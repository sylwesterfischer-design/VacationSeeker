from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median

from .models import Offer


@dataclass
class WatchProfile:
    id: int
    destination_query: str
    adults: int
    children_ages: str
    target_email: str
    drop_ratio: float
    max_total_pln: float | None
    departure_from: str | None
    departure_to: str | None
    enabled: int

    @property
    def travelers(self) -> int:
        child_count = 0 if not self.children_ages else len([x for x in self.children_ages.split(",") if x.strip()])
        return self.adults + child_count


@dataclass
class WatchHit:
    watch_id: int
    offer_id_hash: str
    subject: str
    body: str


def evaluate_watch(watch: WatchProfile, offers: list[Offer]) -> WatchHit | None:
    matching = [
        o
        for o in offers
        if (
            watch.destination_query.lower() in o.destination_country.lower()
            or watch.destination_query.lower() in o.destination_city_or_region.lower()
        )
        and _in_date_range(o.departure_date, watch.departure_from, watch.departure_to)
    ]
    if not matching:
        return None

    family_costs = [(o, o.total_trip_cost_pln * watch.travelers) for o in matching]
    med = median(v for _, v in family_costs)
    best_offer, best_total = min(family_costs, key=lambda x: x[1])
    drop_ratio = 0.0 if med <= 0 else (med - best_total) / med

    hidden_cost_risk = []
    if best_offer.baggage_included != "yes":
        hidden_cost_risk.append("bagaż może podnieść koszt")
    if best_offer.transfer_included != "yes":
        hidden_cost_risk.append("transfer może podnieść koszt")
    risk_suffix = " | Ryzyko: " + ", ".join(hidden_cost_risk) if hidden_cost_risk else ""

    passes_ratio = drop_ratio >= watch.drop_ratio
    passes_cap = watch.max_total_pln is None or best_total <= watch.max_total_pln
    if not (passes_ratio and passes_cap):
        return None

    subject = f"VacationSeeker Alert: {watch.destination_query} dla {watch.travelers} os."
    body = (
        f"Znaleziono najlepsza oferte dla profilu watch #{watch.id}\n\n"
        f"Destynacja: {best_offer.destination_city_or_region}, {best_offer.destination_country}\n"
        f"Termin: {best_offer.departure_date} - {best_offer.return_date}\n"
        f"Hotel: {best_offer.hotel_name} ({best_offer.hotel_stars or 0}*)\n"
        f"Cena nominalna/os: {best_offer.price_per_person_pln:.0f} PLN\n"
        f"Koszt realny/os: {best_offer.total_trip_cost_pln:.0f} PLN\n"
        f"Koszt laczny rodziny ({watch.travelers} os): {best_total:.0f} PLN\n"
        f"Spadek vs mediana: {drop_ratio * 100:.1f}% (prog {watch.drop_ratio * 100:.0f}%)\n"
        f"Zrodlo: {best_offer.source_name}\n"
        f"Link: {best_offer.source_url}\n"
        f"Confidence ceny: {best_offer.price_confidence}{risk_suffix}\n"
    )
    return WatchHit(watch_id=watch.id, offer_id_hash=best_offer.offer_id_hash, subject=subject, body=body)


def _in_date_range(departure_date: str, departure_from: str | None, departure_to: str | None) -> bool:
    dep = datetime.strptime(departure_date, "%Y-%m-%d").date()
    if departure_from:
        frm = datetime.strptime(departure_from, "%Y-%m-%d").date()
        if dep < frm:
            return False
    if departure_to:
        to = datetime.strptime(departure_to, "%Y-%m-%d").date()
        if dep > to:
            return False
    return True


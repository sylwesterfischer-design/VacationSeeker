from __future__ import annotations

from datetime import datetime
from statistics import median

from .models import Offer


def apply_scoring(offers: list[Offer]) -> list[Offer]:
    by_destination_nominal: dict[str, list[float]] = {}
    by_destination_total: dict[str, list[float]] = {}
    for o in offers:
        key = o.destination_city_or_region.lower()
        by_destination_nominal.setdefault(key, []).append(o.price_per_person_pln)
        by_destination_total.setdefault(key, []).append(o.total_trip_cost_pln)

    nominal_medians = {k: median(v) for k, v in by_destination_nominal.items()}
    total_medians = {k: median(v) for k, v in by_destination_total.items()}

    for o in offers:
        key = o.destination_city_or_region.lower()
        dest_nominal_median = nominal_medians[key]
        dest_total_median = total_medians[key]
        nominal_price_component = max(0.0, min(1.0, (dest_nominal_median / max(o.price_per_person_pln, 1.0)))) * 40
        real_cost_component = max(0.0, min(1.0, (dest_total_median / max(o.total_trip_cost_pln, 1.0)))) * 50
        stars_component = (o.hotel_stars or 3.0) / 5.0 * 20
        convenience_component = 15 if o.departure_airport in {"WAW", "KTW", "KRK", "GDN", "POZ"} else 9
        weekday_bonus = 5 if _weekday_preference(o.departure_date) else 0
        inclusions = 0
        if o.baggage_included == "yes":
            inclusions += 1
        if o.transfer_included == "yes":
            inclusions += 1
        if o.board_type in {"AI", "HB"}:
            inclusions += 1
        inclusion_component = (inclusions / 3) * 10
        freshness_component = 10
        promo_component = 5 if o.promo_tag in {"last_minute", "flash_sale"} else 2
        o.nominal_score = round(
            nominal_price_component
            + stars_component
            + convenience_component
            + inclusion_component
            + freshness_component
            + promo_component,
            2,
        )
        confidence_penalty = 0 if o.price_confidence == "high" else 4
        o.score = round(
            real_cost_component
            + (stars_component * 0.7)
            + convenience_component
            + weekday_bonus
            + inclusion_component
            + freshness_component
            + promo_component
            - confidence_penalty,
            2,
        )
    return offers


def _weekday_preference(departure_date: str) -> bool:
    # Prefer Tuesday/Wednesday/Thursday departures for lower average prices.
    weekday = datetime.strptime(departure_date, "%Y-%m-%d").weekday()
    return weekday in {1, 2, 3}


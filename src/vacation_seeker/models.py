from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawOffer:
    source_name: str
    source_url: str
    destination_country: str
    destination_city_or_region: str
    departure_airport: str
    departure_date: str
    return_date: str
    trip_nights: int
    board_type: str
    hotel_name: str
    hotel_stars: float | None
    package_type: str
    price_total_pln: float
    price_per_person_pln: float | None
    people_supported: str
    baggage_included: str
    transfer_included: str
    cancellation_terms: str | None
    promo_tag: str | None


@dataclass
class Offer:
    source_name: str
    source_url: str
    collected_at_utc: datetime
    destination_country: str
    destination_city_or_region: str
    departure_airport: str
    departure_date: str
    return_date: str
    trip_nights: int
    board_type: str
    hotel_name: str
    hotel_stars: float | None
    package_type: str
    price_total_pln: float
    price_per_person_pln: float
    airport_transfer_cost_pln: float
    baggage_cost_pln: float
    local_daily_cost_pln: float
    total_trip_cost_pln: float
    people_supported: str
    baggage_included: str
    transfer_included: str
    cancellation_terms: str | None
    promo_tag: str | None
    offer_id_hash: str
    score: float
    nominal_score: float
    price_confidence: str
    stale_data: bool
    verification: str


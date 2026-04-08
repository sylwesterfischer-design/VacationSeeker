from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .models import Offer, RawOffer


def _make_offer_hash(raw: RawOffer) -> str:
    key = "|".join(
        [
            raw.destination_city_or_region.lower(),
            raw.departure_date,
            raw.return_date,
            raw.hotel_name.lower(),
            raw.source_name.lower(),
            str(round(raw.price_total_pln, 0)),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def normalize(raw: RawOffer) -> Offer:
    now = datetime.now(timezone.utc)
    ppp = raw.price_per_person_pln
    if ppp is None:
        if raw.people_supported == "2":
            ppp = raw.price_total_pln / 2
        else:
            ppp = raw.price_total_pln

    baggage_cost = 0.0 if raw.baggage_included == "yes" else 180.0
    transfer_cost = 0.0 if raw.transfer_included == "yes" else 120.0
    local_daily_cost = 120.0
    total_trip_cost = ppp + baggage_cost + transfer_cost + (local_daily_cost * raw.trip_nights)
    price_confidence = "high" if raw.price_per_person_pln is not None else "low"

    return Offer(
        source_name=raw.source_name,
        source_url=raw.source_url,
        collected_at_utc=now,
        destination_country=raw.destination_country,
        destination_city_or_region=raw.destination_city_or_region,
        departure_airport=raw.departure_airport,
        departure_date=raw.departure_date,
        return_date=raw.return_date,
        trip_nights=raw.trip_nights,
        board_type=raw.board_type,
        hotel_name=raw.hotel_name,
        hotel_stars=raw.hotel_stars,
        package_type=raw.package_type,
        price_total_pln=raw.price_total_pln,
        price_per_person_pln=ppp,
        airport_transfer_cost_pln=transfer_cost,
        baggage_cost_pln=baggage_cost,
        local_daily_cost_pln=local_daily_cost,
        total_trip_cost_pln=total_trip_cost,
        people_supported=raw.people_supported,
        baggage_included=raw.baggage_included,
        transfer_included=raw.transfer_included,
        cancellation_terms=raw.cancellation_terms,
        promo_tag=raw.promo_tag,
        offer_id_hash=_make_offer_hash(raw),
        score=0.0,
        nominal_score=0.0,
        price_confidence=price_confidence,
        stale_data=False,
        verification="single_source",
    )


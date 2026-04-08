from __future__ import annotations

from .base import BaseCollector
from ..models import RawOffer


class MockCollector(BaseCollector):
    source_name = "mock_feed"

    def collect(self) -> list[RawOffer]:
        return [
            RawOffer(
                source_name="wakacyjni_piraci",
                source_url="https://www.wakacyjnipiraci.pl/motywy/last-minute",
                destination_country="Hiszpania",
                destination_city_or_region="Teneryfa",
                departure_airport="WAW",
                departure_date="2026-03-26",
                return_date="2026-04-02",
                trip_nights=7,
                board_type="AI",
                hotel_name="Ocean View Resort",
                hotel_stars=4.0,
                package_type="flight+hotel",
                price_total_pln=3898.0,
                price_per_person_pln=1949.0,
                people_supported="2",
                baggage_included="yes",
                transfer_included="yes",
                cancellation_terms="standard",
                promo_tag="last_minute",
            ),
            RawOffer(
                source_name="tui",
                source_url="https://www.tui.pl/last-minute-z-poznania",
                destination_country="Egipt",
                destination_city_or_region="Hurghada",
                departure_airport="POZ",
                departure_date="2026-03-24",
                return_date="2026-03-31",
                trip_nights=7,
                board_type="AI",
                hotel_name="Sunrise Beach",
                hotel_stars=4.5,
                package_type="flight+hotel",
                price_total_pln=3298.0,
                price_per_person_pln=1649.0,
                people_supported="2",
                baggage_included="yes",
                transfer_included="yes",
                cancellation_terms="flex",
                promo_tag="flash_sale",
            ),
            RawOffer(
                source_name="rainbow",
                source_url="https://www.r.pl/",
                destination_country="Grecja",
                destination_city_or_region="Kreta",
                departure_airport="KTW",
                departure_date="2026-03-29",
                return_date="2026-04-05",
                trip_nights=7,
                board_type="HB",
                hotel_name="Blue Bay",
                hotel_stars=4.0,
                package_type="flight+hotel",
                price_total_pln=2199.0,
                price_per_person_pln=2199.0,
                people_supported="1",
                baggage_included="no",
                transfer_included="unknown",
                cancellation_terms=None,
                promo_tag="last_minute",
            ),
        ]


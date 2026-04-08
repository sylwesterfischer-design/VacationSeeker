from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .models import RawOffer


UNAVAILABLE_MARKERS = [
    "nie jest dostępna",
    "nie jest dostepna",
    "oferta niedostępna",
    "oferta niedostepna",
    "brak dostępności",
    "brak dostepnosci",
    "offer is no longer available",
    "offer unavailable",
]


def filter_available_offers(
    offers: list[RawOffer],
    timeout_seconds: int = 12,
    max_workers: int = 8,
) -> list[RawOffer]:
    if not offers:
        return offers

    validated: list[RawOffer] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_is_offer_available, o.source_url, timeout_seconds): o
            for o in offers
            if o.source_url.startswith("http")
        }

        # Keep non-http entries (defensive fallback).
        validated.extend([o for o in offers if not o.source_url.startswith("http")])

        for fut in as_completed(futures):
            offer = futures[fut]
            try:
                if fut.result():
                    validated.append(offer)
            except Exception:
                # If validator fails unexpectedly, keep the offer instead of losing data.
                validated.append(offer)
    return validated


def _is_offer_available(url: str, timeout_seconds: int) -> bool:
    try:
        r = requests.get(url, timeout=timeout_seconds, headers={"User-Agent": "Mozilla/5.0"})
    except requests.RequestException:
        return True

    if r.status_code >= 400:
        return False

    page = (r.text or "").lower()
    for marker in UNAVAILABLE_MARKERS:
        if marker in page:
            return False
    return True


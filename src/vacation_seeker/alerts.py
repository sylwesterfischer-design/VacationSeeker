from __future__ import annotations

import requests

from .models import Offer


def build_price_drop_alerts(current: list[Offer], previous: dict[str, float], threshold: float = 0.08) -> list[str]:
    alerts: list[str] = []
    for o in current:
        prev = previous.get(o.offer_id_hash)
        if prev is None or prev <= 0:
            continue
        drop = (prev - o.price_per_person_pln) / prev
        if drop >= threshold:
            alerts.append(
                f"{o.destination_city_or_region} | {o.hotel_name} | "
                f"{prev:.0f} -> {o.price_per_person_pln:.0f} PLN/os (-{drop * 100:.1f}%) | {o.source_url}"
            )
    return alerts


def send_webhook_alerts(webhook_url: str | None, alerts: list[str]) -> None:
    if not webhook_url or not alerts:
        return

    text = "Price drop alerts:\n" + "\n".join(f"- {a}" for a in alerts[:10])
    requests.post(webhook_url, json={"text": text}, timeout=10)


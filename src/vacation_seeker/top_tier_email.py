"""
Alert e-mail „TOP OF THE TOP”: najniższy koszt realny, najniższa cena nominalna, najwyższy score.
Wysyłka tylko gdy zestaw trzech „liderów” zmienił się względem ostatniego runu (anty-spam).
"""
from __future__ import annotations

import hashlib
import sqlite3
from statistics import median

from .config import Settings
from .db import get_meta_kv, set_meta_kv
from .emailer import send_email
from .models import Offer


META_KEY_TOP_DIGEST = "top_tier_last_digest"


def _median_costs(offers: list[Offer]) -> float:
    vals = [o.total_trip_cost_pln for o in offers]
    return float(median(vals)) if vals else 0.0


def _format_offer_block(title: str, o: Offer, median_pln: float) -> str:
    vs_med = ""
    if median_pln > 0:
        diff = (median_pln - o.total_trip_cost_pln) / median_pln * 100.0
        vs_med = f" vs mediana zbioru: {diff:+.1f}% (mediana {median_pln:.0f} PLN/os real)\n"
    stars = f"{o.hotel_stars:.1f}*" if o.hotel_stars else "brak gwiazdek w danych"
    return (
        f"--- {title} ---\n"
        f"{o.destination_city_or_region}, {o.destination_country} | wylot {o.departure_date} → powrót {o.return_date}\n"
        f"Lotnisko: {o.departure_airport} | {o.trip_nights} nocy | wyżywienie: {o.board_type}\n"
        f"Hotel: {o.hotel_name[:120]} ({stars})\n"
        f"Cena nominalna/os: {o.price_per_person_pln:.0f} PLN | koszt realny/os: {o.total_trip_cost_pln:.0f} PLN\n"
        f"Score (warunki/wartość wg modelu): {o.score:.1f} | nominal_score: {o.nominal_score:.1f}\n"
        f"Źródło: {o.source_name}\n"
        f"Link: {o.source_url}\n"
        f"Pewność ceny: {o.verification} / {o.price_confidence}{vs_med}"
    )


def build_top_tier_email_body(offers_near: list[Offer]) -> tuple[str, str, str]:
    """
    Zwraca (subject, body, digest_hash).
    digest = hash trzech offer_id_hash (real, nominal, score).
    """
    if not offers_near:
        return "", "", ""

    med = _median_costs(offers_near)
    best_real = min(offers_near, key=lambda o: o.total_trip_cost_pln)
    best_nominal = min(offers_near, key=lambda o: o.price_per_person_pln)
    best_score = max(offers_near, key=lambda o: o.score)

    digest = hashlib.sha256(
        f"{best_real.offer_id_hash}|{best_nominal.offer_id_hash}|{best_score.offer_id_hash}".encode("utf-8")
    ).hexdigest()

    subject = (
        f"VacationSeeker TOP OF THE TOP — real {best_real.total_trip_cost_pln:.0f} PLN/os | "
        f"nominal {best_nominal.price_per_person_pln:.0f} PLN/os"
    )

    body = (
        "Witaj,\n\n"
        "Poniżej trzy perspektywy „najlepszej” oferty w bieżącym zestawieniu (oferty z głównego horyzontu raportu, "
        "jak w tabelach HTML — nie „dalsze terminy”).\n"
        "Porównanie do mediany kosztu realnego dotyczy całego zbioru ofert w tym horyzoncie.\n\n"
        + _format_offer_block("1) Najtańszy KOSZT REALNY na osobę (lot/hotel + szac. dodatki)", best_real, med)
        + "\n"
        + _format_offer_block("2) Najniższa CENA NOMINALNA na osobę (bazowa z ogłoszenia)", best_nominal, med)
        + "\n"
        + _format_offer_block("3) Najwyższy SCORE (najkorzystniejsze warunki wg modelu vs mediana kierunku)", best_score, med)
        + "\n"
        "---\n"
        "Uwaga: RSS redakcyjne (Fly4free itd.) mają często package_type=deal_post — traktuj linki jak podpowiedź.\n"
        "Pełny raport: plik report.html z ostatniego uruchomienia.\n"
    )
    return subject, body, digest


def maybe_send_top_tier_email(
    conn: sqlite3.Connection,
    settings: Settings,
    offers_near: list[Offer],
) -> None:
    if not settings.top_email_enabled:
        print("[top] alert TOP OF THE TOP wylaczony (VACATION_TOP_EMAIL_ENABLED=false).")
        return
    if not offers_near:
        print("[top] brak ofert w horyzoncie — brak mailem TOP.")
        return
    to_addr = settings.top_email_to or settings.default_alert_email
    if not to_addr:
        print("[top] brak adresu (VACATION_TOP_EMAIL / VACATION_ALERT_EMAIL).")
        return

    subject, body, digest = build_top_tier_email_body(offers_near)
    if not digest:
        return

    prev = get_meta_kv(conn, META_KEY_TOP_DIGEST)
    if prev == digest:
        print("[top] TOP OF THE TOP bez zmian — mail nie wyslany (ci sami liderzy co poprzednio).")
        return

    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password or not settings.smtp_from:
        print(
            "[top] Skonfiguruj SMTP (VACATION_SMTP_HOST, USER, PASSWORD, FROM), zeby wyslac TOP OF THE TOP na "
            f"{to_addr}."
        )
        return

    ok = send_email(settings, to_addr, subject, body)
    if ok:
        set_meta_kv(conn, META_KEY_TOP_DIGEST, digest)
        print(f"[top] Wyslano TOP OF THE TOP → {to_addr}")
    else:
        print("[top] Blad wysylki e-mail (send_email zwrocil False).")

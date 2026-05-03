"""
Opcjonalne podpowiedzi cen lotów (Amadeus Self-Service API).

Macierz Kayak / Skyscanner / Google w HTML to tylko linki — bez API nie da się automatycznie
wyciągnąć ceny. Przy ustawionych VACATION_AMADEUS_CLIENT_ID / VACATION_AMADEUS_CLIENT_SECRET
VacationSeeker odpytuje GET /v2/shopping/flight-offers dla każdej pary (wylot, powrót),
sortuje wyniki i buduje tabelę TOP 3 (grandTotal w wybranej walucie).

Uwagi: środowisko test (test.api.amadeus.com) ma ograniczenia tras i dat; produkcja: api.amadeus.com.
Parametr GET używa liczby dzieci (children), nie listy wieków — zgodne z ograniczeniami API.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html import escape
from typing import Any

import requests

from .flight_fallback_links import FlightFallbackContext, google_flights_url, kayak_roundtrip_url, skyscanner_url


@dataclass
class ComboPriceRow:
    departure: str
    return_date: str
    total: float
    currency: str
    summary: str


def _fetch_token(host: str, client_id: str, client_secret: str, timeout: int = 20) -> str | None:
    url = f"https://{host}/v1/security/oauth2/token"
    r = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    if r.status_code != 200:
        return None
    try:
        return str(r.json().get("access_token") or "") or None
    except Exception:
        return None


def _cheapest_for_combo(
    host: str,
    token: str,
    origin: str,
    dest: str,
    dep: str,
    ret: str,
    adults: int,
    children_count: int,
    currency: str,
    timeout: int = 28,
) -> ComboPriceRow | None:
    url = f"https://{host}/v2/shopping/flight-offers"
    params: dict[str, str] = {
        "originLocationCode": origin.upper(),
        "destinationLocationCode": dest.upper(),
        "departureDate": dep,
        "returnDate": ret,
        "adults": str(max(1, adults)),
        "currencyCode": currency,
        "max": "5",
        "nonStop": "false",
    }
    if children_count > 0:
        params["children"] = str(children_count)
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=timeout,
    )
    if r.status_code != 200:
        return None
    try:
        payload: dict[str, Any] = r.json()
    except Exception:
        return None
    data = payload.get("data") or []
    if not data:
        return None
    offer = data[0]
    price = offer.get("price") or {}
    raw_total = price.get("grandTotal") or price.get("total")
    if raw_total is None:
        return None
    try:
        total = float(raw_total)
    except (TypeError, ValueError):
        return None
    cur = str(price.get("currency") or currency)
    summary = "oferta"
    try:
        it0 = (offer.get("itineraries") or [{}])[0]
        segs = it0.get("segments") or []
        if segs:
            c0 = segs[0].get("carrierCode", "?")
            summary = f"{c0}, {len(segs)} segment(ów) (wylot)"
    except Exception:
        pass
    return ComboPriceRow(departure=dep, return_date=ret, total=total, currency=cur, summary=summary)


def fetch_combo_prices_amadeus(
    *,
    host: str,
    client_id: str | None,
    client_secret: str | None,
    origin_iata: str,
    dest_iata: str,
    departure_dates: list[str],
    return_dates: list[str],
    adults: int,
    children_ages: tuple[int, ...],
    currency: str,
    max_workers: int = 5,
) -> tuple[list[ComboPriceRow], str | None]:
    """
    Zwraca (posortowane rosnąco po cenie wiersze dla wszystkich kombinacji z ceną, komunikat_błędu).
    """
    if not client_id or not client_secret:
        return [], None
    token = _fetch_token(host, client_id, client_secret)
    if not token:
        return [], "Brak tokena Amadeus (sprawdź CLIENT_ID / CLIENT_SECRET i host)."

    children_count = len(children_ages)
    tasks: list[tuple[str, str]] = []
    for dep in departure_dates:
        for ret in return_dates:
            tasks.append((dep, ret))

    rows: list[ComboPriceRow] = []
    workers = max(1, min(max_workers, len(tasks)))

    def _job(dep_ret: tuple[str, str]) -> ComboPriceRow | None:
        dep, ret = dep_ret
        return _cheapest_for_combo(
            host,
            token,
            origin_iata,
            dest_iata,
            dep,
            ret,
            adults,
            children_count,
            currency,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_job, t): t for t in tasks}
        for fut in as_completed(futs):
            try:
                row = fut.result()
            except Exception:
                row = None
            if row is not None:
                rows.append(row)

    rows.sort(key=lambda x: x.total)
    return rows, None


def render_flight_top3_price_table_html(
    *,
    origin_iata: str,
    dest_iata: str,
    destination_label: str,
    adults: int,
    children_ages: tuple[int, ...],
    ranked_rows: list[ComboPriceRow],
    api_error: str | None,
    amadeus_configured: bool,
) -> str:
    """Tabela TOP 3 pod macierzą linków + notka o źródle ceny."""
    pax = f"{max(1, adults)} dorosłych"
    if children_ages:
        pax += f", {len(children_ages)} dzieci (lata: {', '.join(str(a) for a in children_ages)})"

    if not amadeus_configured:
        note = (
            "<p><strong>TOP 3 po cenie (automatycznie):</strong> wymaga darmowych kluczy "
            "<a href=\"https://developers.amadeus.com/register\" target=\"_blank\" rel=\"noopener\">Amadeus Self-Service</a> "
            "— zmienne <code>VACATION_AMADEUS_CLIENT_ID</code> i <code>VACATION_AMADEUS_CLIENT_SECRET</code> "
            f"(opcjonalnie host: <code>VACATION_AMADEUS_HOST</code>, domyślnie <code>test.api.amadeus.com</code>). "
            "Bez kluczy linki w macierzy powyżej nie dostarczają ceny do VacationSeeker.</p>"
        )
        return "<h3>TOP 3 kombinacji dat wg ceny (Amadeus)</h3>" + note

    if api_error:
        return (
            "<h3>TOP 3 kombinacji dat wg ceny (Amadeus)</h3>"
            f"<p class=\"meta-warn\">{escape(api_error)}</p>"
        )

    if not ranked_rows:
        return (
            "<h3>TOP 3 kombinacji dat wg ceny (Amadeus)</h3>"
            "<p>Amadeus zwrócił pustą listę ofert dla wszystkich par dat (typowe w środowisku test lub przy "
            "odległych datach). Użyj macierzy linków powyżej albo przełącz na produkcyjny host Amadeus.</p>"
        )

    top = ranked_rows[:3]
    body_lines: list[str] = []
    o = origin_iata.upper()
    d = dest_iata.upper()
    a = max(1, adults)
    ch = children_ages
    for i, row in enumerate(top, start=1):
        ctx = FlightFallbackContext(
            destination_label=destination_label,
            departure_date=row.departure,
            return_date=row.return_date,
            origin_iata=o,
            adults=a,
            children_ages=ch,
        )
        k = kayak_roundtrip_url(o, d, row.departure, row.return_date, adults=a, children_ages=ch, sort="price_a")
        s = skyscanner_url(o, d, row.departure, row.return_date, adults=a, children_ages=ch)
        g = google_flights_url(ctx, d)
        links = (
            f"<a href=\"{escape(k, quote=True)}\" target=\"_blank\" rel=\"noopener\">Kayak</a> · "
            f"<a href=\"{escape(s, quote=True)}\" target=\"_blank\" rel=\"noopener\">Skyscanner</a> · "
            f"<a href=\"{escape(g, quote=True)}\" target=\"_blank\" rel=\"noopener\">Google Flights</a>"
        )
        body_lines.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td class=\"cell-nowrap\">{escape(row.departure)}</td>"
            f"<td class=\"cell-nowrap\">{escape(row.return_date)}</td>"
            f"<td><strong>{row.total:.2f}</strong> {escape(row.currency)}</td>"
            f"<td>{escape(row.summary)}</td>"
            f"<td><div class=\"meta-links\">{links}</div></td>"
            "</tr>"
        )

    note = (
        "<p><em>Cena: najtańsza oferta z pierwszej strony wyników Amadeus (grandTotal) dla podanego składu "
        f"({escape(pax)}). W API GET używana jest liczba dzieci, nie lista wieków. "
        "Cena orientacyjna — weryfikuj w biurze / u przewoźnika. Kierunek: "
        f"{escape(origin_iata)} → {escape(dest_iata)} ({escape(destination_label)}).</em></p>"
    )

    return (
        "<h3>TOP 3 kombinacji dat wg ceny (Amadeus API)</h3>"
        + note
        + "<table class=\"matrix\"><thead><tr>"
        "<th>#</th><th>Wylot</th><th>Powrót</th><th>Najniższa cena (w ofercie)</th><th>Skrót trasy</th>"
        "<th>Te same terminy — linki metasearch</th>"
        "</tr></thead><tbody>"
        + "".join(body_lines)
        + "</tbody></table>"
    )


def build_flight_top3_block(
    *,
    host: str,
    client_id: str | None,
    client_secret: str | None,
    origin_iata: str,
    destination_label: str,
    dest_iata: str,
    departure_dates: list[str],
    return_dates: list[str],
    adults: int,
    children_ages: tuple[int, ...],
    currency: str,
    skip_api: bool,
    amadeus_top3_enabled: bool,
) -> str:
    """Fragment HTML: sekcja TOP 3 pod macierzą lotów."""
    if not amadeus_top3_enabled:
        return (
            "<h3>TOP 3 kombinacji dat wg ceny (Amadeus API)</h3>"
            "<p><em>Sekcja wyłączona: <code>VACATION_AMADEUS_FLIGHT_TOP3=false</code>.</em></p>"
        )
    if skip_api:
        if client_id and client_secret:
            return (
                "<h3>TOP 3 kombinacji dat wg ceny (Amadeus API)</h3>"
                "<p><em>Tryb dry-run: pominięto zapytania do Amadeus (brak realnego odpytywania API).</em></p>"
            )
        return render_flight_top3_price_table_html(
            origin_iata=origin_iata,
            dest_iata=dest_iata,
            destination_label=destination_label,
            adults=adults,
            children_ages=children_ages,
            ranked_rows=[],
            api_error=None,
            amadeus_configured=False,
        )
    configured = bool(client_id and client_secret)
    if not configured:
        return render_flight_top3_price_table_html(
            origin_iata=origin_iata,
            dest_iata=dest_iata,
            destination_label=destination_label,
            adults=adults,
            children_ages=children_ages,
            ranked_rows=[],
            api_error=None,
            amadeus_configured=False,
        )
    rows, err = fetch_combo_prices_amadeus(
        host=host,
        client_id=client_id,
        client_secret=client_secret,
        origin_iata=origin_iata,
        dest_iata=dest_iata,
        departure_dates=departure_dates,
        return_dates=return_dates,
        adults=adults,
        children_ages=children_ages,
        currency=currency,
        max_workers=int(os.getenv("VACATION_AMADEUS_MAX_WORKERS", "5")),
    )
    return render_flight_top3_price_table_html(
        origin_iata=origin_iata,
        dest_iata=dest_iata,
        destination_label=destination_label,
        adults=adults,
        children_ages=children_ages,
        ranked_rows=rows,
        api_error=err,
        amadeus_configured=True,
    )

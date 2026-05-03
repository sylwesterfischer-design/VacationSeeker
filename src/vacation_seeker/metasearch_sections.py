"""
Sekcje HTML z linkami do metawyszukiwarek (bez API — ceny tylko na stronach docelowych).

Kayak, Skyscanner i Google Flights / Google Travel nie udostępniają stabilnego publicznego API
cenowego dla zwykłych skryptów; VacationSeeker buduje gotowe URL-e wyszukiwania (jak dotąd
w flight_fallback_links), tutaj rozszerzone o macierz dat i hotele (Booking + Google).
"""

from __future__ import annotations

from html import escape
from urllib.parse import quote, urlencode

from .flight_fallback_links import (
    FlightFallbackContext,
    guess_destination_iata,
    google_flights_url,
    kayak_roundtrip_url,
    skyscanner_url,
)


def parse_csv_tokens(s: str | None) -> list[str]:
    """Lista tokenów z CSV (daty YYYY-MM-DD lub nazwy miejscowości)."""
    if not s or not str(s).strip():
        return []
    return [p.strip() for p in str(s).split(",") if p.strip()]


def _booking_hotel_search_url(
    place_query: str,
    checkin: str,
    checkout: str,
    *,
    adults: int,
    children_ages: tuple[int, ...],
    mealplan: int | None = None,
) -> str:
    """
    Booking.com — wyniki wyszukiwania z datami i składem rodziny.
    mealplan (orientacyjnie): 1 = śniadanie, 2 = pół pensjonat / HB — Booking może zmieniać obsługę parametru.
    """
    params: list[tuple[str, str]] = [
        ("ss", place_query),
        ("checkin", checkin),
        ("checkout", checkout),
        ("group_adults", str(max(1, adults))),
        ("group_children", str(len(children_ages))),
        ("no_rooms", "1"),
        ("order", "price"),
    ]
    if mealplan is not None:
        params.append(("mealplan", str(mealplan)))
    for age in children_ages:
        params.append(("age", str(age)))
    return "https://www.booking.com/searchresults.html?" + urlencode(params)


def _google_hotels_url(place_query: str, checkin: str, checkout: str, *, meal_words: str | None = None) -> str:
    """Google Travel / hotele — zapytanie tekstowe + daty w parametrze q (stabilniejsze niż entity_id)."""
    q = f"hotels {place_query} check in {checkin} check out {checkout}"
    if meal_words:
        q = f"{q} {meal_words}"
    return "https://www.google.com/travel/hotels?q=" + quote(q) + "&hl=pl&curr=PLN"


def _kayak_hotels_url(place_query: str, checkin: str, checkout: str, adults: int, children_ages: tuple[int, ...]) -> str:
    """Kayak hotele — slug z nazwy miejsca (przybliżenie; użytkownik może doprecyzować na stronie)."""
    slug = quote(place_query.replace(" ", "-"), safe="-")
    base = f"https://www.kayak.pl/hotels/{slug}/{checkin}/{checkout}"
    a = max(1, adults)
    n = len(children_ages)
    if n == 0:
        path = f"{base}/{a}adults" if a != 1 else base
    else:
        path = f"{base}/{a}adults-children-{n}"
    if children_ages:
        return f"{path}?children={','.join(str(x) for x in children_ages)}"
    return path


def render_flight_date_matrix_html(
    *,
    origin_iata: str,
    destination_label: str,
    departure_dates: list[str],
    return_dates: list[str],
    adults: int,
    children_ages: tuple[int, ...],
) -> str:
    """Tabela: wiersze = powrót, kolumny = wylot; w komórce linki Kayak (cena) / Skyscanner / Google Flights."""
    dest_iata = guess_destination_iata(destination_label) or "ZTH"
    o = origin_iata.upper()
    thead = "<tr><th class=\"cell-nowrap\">Powrót \\ Wylot</th>"
    for dep in departure_dates:
        thead += f"<th class=\"cell-nowrap\">{escape(dep)}</th>"
    thead += "</tr>"

    body_rows: list[str] = []
    for ret in return_dates:
        row = f"<tr><th class=\"cell-nowrap\">{escape(ret)}</th>"
        for dep in departure_dates:
            ctx = FlightFallbackContext(
                destination_label=destination_label,
                departure_date=dep,
                return_date=ret,
                origin_iata=o,
                adults=max(1, adults),
                children_ages=children_ages,
            )
            k = kayak_roundtrip_url(o, dest_iata, dep, ret, adults=max(1, adults), children_ages=children_ages, sort="price_a")
            s = skyscanner_url(o, dest_iata, dep, ret, adults=max(1, adults), children_ages=children_ages)
            g = google_flights_url(ctx, dest_iata)
            cell = (
                "<div class=\"meta-links\">"
                f"<a href=\"{escape(k, quote=True)}\" target=\"_blank\" rel=\"noopener\">Kayak (cena)</a> · "
                f"<a href=\"{escape(s, quote=True)}\" target=\"_blank\" rel=\"noopener\">Skyscanner</a> · "
                f"<a href=\"{escape(g, quote=True)}\" target=\"_blank\" rel=\"noopener\">Google Flights</a>"
                "</div>"
            )
            row += f"<td>{cell}</td>"
        row += "</tr>"
        body_rows.append(row)

    note = (
        "<p><em>Kayak, Skyscanner i Google nie udostępniają tutaj API z cenami — każda komórka to osobne "
        f"wyszukiwanie online (lotnisko docelowe w linkach: <strong>{escape(dest_iata)}</strong>). "
        "Google Flights często traktuje 12+ jako dorosłych; i tak wybierz dokładny skład w UI po wejściu w link.</em></p>"
    )
    return (
        "<h2>Macierz lotów (porównanie terminów — Kayak / Skyscanner / Google Flights)</h2>"
        f"<p>Wyloty: <strong>{escape(', '.join(departure_dates))}</strong> · "
        f"Powroty: <strong>{escape(', '.join(return_dates))}</strong> · "
        f"Start: <strong>{escape(o)}</strong> · "
        f"Dorośli: <strong>{adults}</strong>"
        + (
            f" · Dzieci (lata): <strong>{escape(', '.join(str(x) for x in children_ages))}</strong>"
            if children_ages
            else ""
        )
        + f" · Kierunek: <strong>{escape(destination_label)}</strong></p>"
        + note
        + "<table class=\"matrix\"><thead>"
        + thead
        + "</thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table>"
    )


def render_hotel_metasearch_html(
    *,
    destination_label: str,
    checkin: str,
    checkout: str,
    towns: list[str],
    adults: int,
    children_ages: tuple[int, ...],
) -> str:
    """Linki Booking / Google / Kayak + osobne kolumny BB (śniadanie) i HB (śniadanie + obiadokolacja)."""
    rows: list[str] = []
    for town in towns:
        place = f"{town}, Zakynthos, Greece"
        geo = f"{town} Zakynthos Greece"
        b_any = _booking_hotel_search_url(place, checkin, checkout, adults=adults, children_ages=children_ages)
        b_bb = _booking_hotel_search_url(
            place, checkin, checkout, adults=adults, children_ages=children_ages, mealplan=1
        )
        b_hb = _booking_hotel_search_url(
            place, checkin, checkout, adults=adults, children_ages=children_ages, mealplan=2
        )
        g_any = _google_hotels_url(geo, checkin, checkout)
        g_bb = _google_hotels_url(geo, checkin, checkout, meal_words="breakfast included")
        g_hb = _google_hotels_url(geo, checkin, checkout, meal_words="half board breakfast dinner")
        k = _kayak_hotels_url(place, checkin, checkout, adults, children_ages)
        col_any = (
            f"<a href=\"{escape(b_any, quote=True)}\" target=\"_blank\" rel=\"noopener\">Booking</a> · "
            f"<a href=\"{escape(g_any, quote=True)}\" target=\"_blank\" rel=\"noopener\">Google</a> · "
            f"<a href=\"{escape(k, quote=True)}\" target=\"_blank\" rel=\"noopener\">Kayak</a>"
        )
        col_bb = (
            f"<a href=\"{escape(b_bb, quote=True)}\" target=\"_blank\" rel=\"noopener\">Booking (śniadanie)</a> · "
            f"<a href=\"{escape(g_bb, quote=True)}\" target=\"_blank\" rel=\"noopener\">Google (BB)</a>"
        )
        col_hb = (
            f"<a href=\"{escape(b_hb, quote=True)}\" target=\"_blank\" rel=\"noopener\">Booking (HB)</a> · "
            f"<a href=\"{escape(g_hb, quote=True)}\" target=\"_blank\" rel=\"noopener\">Google (HB)</a>"
        )
        rows.append(
            "<tr>"
            f"<td><strong>{escape(town)}</strong></td>"
            f"<td class=\"cell-nowrap\">{escape(checkin)} → {escape(checkout)}</td>"
            f"<td><div class=\"meta-links\">{col_any}</div></td>"
            f"<td><div class=\"meta-links\">{col_bb}</div></td>"
            f"<td><div class=\"meta-links\">{col_hb}</div></td>"
            "</tr>"
        )

    pax = f"{adults} dorosłych"
    if children_ages:
        pax += f", dzieci: {', '.join(str(a) for a in children_ages)} lat"

    return (
        "<h2>Hotele — metawyszukiwareki (dowolne wyżywienie / śniadanie BB / pół pensjonat HB)</h2>"
        f"<p>Destynacja: <strong>{escape(destination_label)}</strong> · Nocleg: "
        f"<strong>{escape(checkin)}</strong> – <strong>{escape(checkout)}</strong> · {escape(pax)}</p>"
        "<p><em>Booking: parametr <code>mealplan</code> (1 = śniadanie, 2 = HB) bywa aktualizowany przez serwis — "
        "jeśli filtr nie zadziała, użyj kolumny „dowolne” i wybierz wyżywienie w filtrach strony. "
        "Ceny tylko u operatora; VacationSeeker nie pobiera API cen hoteli.</em></p>"
        "<table><thead><tr>"
        "<th>Miejscowość</th><th>Termin pobytu</th>"
        "<th>Dowolne wyżywienie</th><th>Śniadanie w cenie (BB)</th><th>Śniadanie + obiadokolacja (HB)</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_metasearch_footer_html(
    *,
    origin_iata: str,
    destination_label: str,
    departure_dates: list[str],
    return_dates: list[str],
    hotel_checkin: str,
    hotel_checkout: str,
    hotel_towns: list[str],
    adults: int,
    children_ages: tuple[int, ...],
) -> str:
    """Jedna sekcja sklejona na koniec raportu HTML (loty + hotele)."""
    flights = render_flight_date_matrix_html(
        origin_iata=origin_iata,
        destination_label=destination_label,
        departure_dates=departure_dates,
        return_dates=return_dates,
        adults=adults,
        children_ages=children_ages,
    )
    hotels = render_hotel_metasearch_html(
        destination_label=destination_label,
        checkin=hotel_checkin,
        checkout=hotel_checkout,
        towns=hotel_towns,
        adults=adults,
        children_ages=children_ages,
    )
    return (
        "<section id=\"vacation-metasearch-bundle\">"
        "<hr style=\"margin:32px 0;\"/>"
        "<h1 style=\"font-size:1.4em;\">Porównanie zewnętrzne (loty + hotele)</h1>"
        f"{flights}{hotels}"
        "</section>"
    )

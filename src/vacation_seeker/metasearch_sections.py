"""
Sekcje HTML z linkami do metawyszukiwarek (bez API — ceny tylko na stronach docelowych).

Kayak, Skyscanner i Google Flights nie udostępniają stabilnego publicznego API cenowego;
VacationSeeker buduje URL-e wyszukiwania lotów (jak w flight_fallback_links) oraz linki
Booking dla hoteli — Google Hotels i Kayak Noclegi nie mają wiarygodnego URL z 2 dorosłymi + dziećmi.
"""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from .amadeus_flight_hints import build_flight_top3_block
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
        "Kayak: segment economy + licznik dzieci 2–17 (np. 11 i 13 = children-2, childages=11,13) + query adults/children; "
        "Google Flights często traktuje 12+ jako dorosłych — doprecyzuj skład w UI po wejściu w link.</em></p>"
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
    """
    Tylko Booking.com — jedyny z tych serwisów, dla którego URL sensownie przenosi skład rodziny
    (dorosłe + wieki dzieci). Google Travel Hotels i Kayak Noclegi nie mają stabilnego publicznego
    URL wymuszającego 2+2; linki udawały poprawną konfigurację — usunięte (zob. notka poniżej).
    """
    rows: list[str] = []
    for town in towns:
        place = f"{town}, Zakynthos, Greece"
        b_any = _booking_hotel_search_url(place, checkin, checkout, adults=adults, children_ages=children_ages)
        b_bb = _booking_hotel_search_url(
            place, checkin, checkout, adults=adults, children_ages=children_ages, mealplan=1
        )
        b_hb = _booking_hotel_search_url(
            place, checkin, checkout, adults=adults, children_ages=children_ages, mealplan=2
        )
        col_any = f"<a href=\"{escape(b_any, quote=True)}\" target=\"_blank\" rel=\"noopener\">Booking</a>"
        col_bb = f"<a href=\"{escape(b_bb, quote=True)}\" target=\"_blank\" rel=\"noopener\">Booking (śniadanie)</a>"
        col_hb = f"<a href=\"{escape(b_hb, quote=True)}\" target=\"_blank\" rel=\"noopener\">Booking (HB)</a>"
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

    google_kayak_note = (
        "<p><strong>Google Travel (Hotele) i Kayak (Noclegi):</strong> nie ma publicznego, "
        "stabilnego formatu URL, który wymuszałby wyszukiwanie dla <em>konkretnie</em> Twojej rodziny "
        "(np. 2 dorosłych + 2 dzieci z wiekami). Parametr <code>q=</code> w Google oraz ścieżki typu "
        "<code>…/2adults-children-2</code> na Kayak nie są dokumentowane jako nośnik składu gości — "
        "w praktyce strona często zostaje przy domyślnych „2 gościach”. "
        "<strong>Nie da się tego wiarygodnie zakodować w VacationSeeker</strong> bez oszukiwania użytkownika. "
        "Chcesz porównać z Google/Kayak: otwórz stronę główną wyszukiwarki hoteli i ustaw pokoje oraz dzieci ręcznie.</p>"
    )
    return (
        "<h2>Hotele — Booking.com (skład rodziny z raportu + opcjonalnie wyżywienie)</h2>"
        f"<p>Destynacja: <strong>{escape(destination_label)}</strong> · Nocleg: "
        f"<strong>{escape(checkin)}</strong> – <strong>{escape(checkout)}</strong> · {escape(pax)}</p>"
        + google_kayak_note
        + "<p><em>Booking: parametr <code>mealplan</code> (1 = śniadanie, 2 = HB) może być ignorowany — "
        "wtedy filtr wyżywienia na stronie. Ceny tylko u operatora.</em></p>"
        "<table><thead><tr>"
        "<th>Miejscowość</th><th>Termin pobytu</th>"
        "<th>Booking — dowolne</th><th>Booking — śniadanie (BB)</th><th>Booking — HB</th>"
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
    amadeus_client_id: str | None = None,
    amadeus_client_secret: str | None = None,
    amadeus_hostname: str = "test.api.amadeus.com",
    amadeus_currency: str = "PLN",
    amadeus_flight_top3_enabled: bool = True,
    skip_amadeus_api: bool = False,
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
    dest_iata = guess_destination_iata(destination_label) or "ZTH"
    top3 = build_flight_top3_block(
        host=amadeus_hostname,
        client_id=amadeus_client_id,
        client_secret=amadeus_client_secret,
        origin_iata=origin_iata,
        destination_label=destination_label,
        dest_iata=dest_iata,
        departure_dates=departure_dates,
        return_dates=return_dates,
        adults=adults,
        children_ages=children_ages,
        currency=amadeus_currency,
        skip_api=skip_amadeus_api,
        amadeus_top3_enabled=amadeus_flight_top3_enabled,
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
        f"{flights}{top3}{hotels}"
        "</section>"
    )

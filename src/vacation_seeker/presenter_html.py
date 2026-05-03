from __future__ import annotations

from datetime import date, datetime
from html import escape
from pathlib import Path

from .aggregator import RankedResult
from .flight_fallback_links import FlightFallbackContext, fallback_section_html
from .models import Offer


def _dictionary_html() -> str:
    rows = [
        ("AI", "All Inclusive - pelne wyzywienie + napoje"),
        ("HB", "Half Board - sniadanie + obiadokolacja"),
        ("BB", "Bed & Breakfast - nocleg + sniadanie"),
        ("RO", "Room Only - sam nocleg, bez wyzywienia"),
        ("Score realny", "Wynik oparty o koszt realny (z dodatkowymi kosztami)"),
        ("Score nominalny", "Wynik oparty o cene bazowa oferty"),
        ("Total", "Cena calej oferty (zrodlo), zwykle dla liczby osob podanej przez zrodlo"),
        ("Cena/os nominalna", "Cena na osobe bez doszacowanych dodatkowych kosztow"),
        ("Koszt realny/os", "Cena/os z doliczonymi kosztami typu bagaz/transfer/lokalne wydatki"),
        ("IRD", "Brak definicji w aktualnym modelu - jesli widzisz ten skrot, podepnij zrzut i dodam mapowanie"),
    ]
    rows_html = "".join(
        f"<tr><td><strong>{escape(k)}</strong></td><td>{escape(v)}</td></tr>" for k, v in rows
    )
    return (
        "<h2>Slownik skrotow</h2>"
        "<table><thead><tr><th>Skrot</th><th>Znaczenie</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
    )


def _offer_row(o: Offer) -> str:
    reason = f"Score realny {o.score}, nominalny {o.nominal_score}, {o.board_type}, {o.trip_nights} nocy"
    return (
        "<tr>"
        f"<td>{escape(o.destination_city_or_region)}</td>"
        f"<td class=\"cell-nowrap\">{escape(o.departure_date)} – {escape(o.return_date)}</td>"
        f"<td>{escape(o.departure_airport)}</td>"
        f"<td>{escape(o.hotel_name)} ({o.hotel_stars or 0}*)</td>"
        f"<td>{o.price_per_person_pln:.0f} PLN</td>"
        f"<td>{o.total_trip_cost_pln:.0f} PLN</td>"
        f"<td>{o.price_total_pln:.0f} PLN</td>"
        f"<td><a href='{escape(o.source_url)}' target='_blank'>{escape(o.source_name)}</a></td>"
        f"<td>{escape(reason)}</td>"
        "</tr>"
    )


def _window_table(title: str, offers: list[Offer]) -> str:
    if not offers:
        return f"<h4>{escape(title)}</h4><p>Brak ofert</p>"
    rows = "".join(_offer_row(o) for o in offers)
    return (
        f"<h4>{escape(title)}</h4>"
        "<table>"
        "<thead><tr>"
        "<th>Kierunek</th><th class=\"cell-nowrap\">Termin</th><th>Wylot</th><th>Hotel</th>"
        "<th>Cena/os nominalna</th><th>Koszt realny/os</th><th>Total</th><th>Zrodlo</th><th>Dlaczego warto</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _best_offer_block(o: Offer) -> str:
    """Wyróżnienie najkorzystniejszej oferty w raporcie (link do źródła)."""
    return (
        '<div style="border:2px solid #ff6b00;padding:16px;border-radius:8px;background:#fff8f0;margin-bottom:24px;">'
        '<h2 style="margin-top:0;">Najlepsza oferta w tym raporcie (wg kosztu realnego)</h2>'
        "<p><strong>"
        f"<a href='{escape(o.source_url)}' target='_blank' rel='noopener'>{escape(o.hotel_name)}</a></strong> — "
        f"{escape(o.destination_city_or_region)}, {escape(o.departure_date)} → {escape(o.return_date)}<br/>"
        f"Koszt realny/os: <strong>{o.total_trip_cost_pln:.0f} PLN</strong> "
        f"(nominalnie: {o.price_per_person_pln:.0f} PLN/os) · {escape(o.source_name)} — "
        f"<a href='{escape(o.source_url)}' target='_blank' rel='noopener'>otwórz ofertę</a></p>"
        "</div>"
    )


def _top_table(title: str, offers: list[Offer], real: bool) -> str:
    rows = []
    for o in offers:
        metric = f"{o.total_trip_cost_pln:.0f} PLN" if real else f"{o.price_per_person_pln:.0f} PLN"
        rows.append(
            "<tr>"
            f"<td>{escape(o.destination_city_or_region)}</td>"
            f"<td class=\"cell-nowrap\">{escape(o.departure_date)}</td>"
            f"<td>{escape(o.departure_airport)}</td>"
            f"<td>{escape(o.hotel_name)}</td>"
            f"<td>{metric}</td>"
            f"<td><a href='{escape(o.source_url)}' target='_blank'>{escape(o.source_name)}</a></td>"
            "</tr>"
        )
    rows_html = "".join(rows) if rows else "<tr><td colspan='6'>Brak ofert</td></tr>"
    metric_label = "Koszt realny/os" if real else "Cena nominalna/os"
    return (
        f"<h3>{escape(title)}</h3>"
        "<table><thead><tr>"
        f"<th>Kierunek</th><th class=\"cell-nowrap\">Wylot</th><th>Lotnisko</th><th>Hotel</th><th>{metric_label}</th><th>Zrodlo</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table>"
    )


def _far_future_section(offers: list[Offer], horizon_months: int) -> str:
    """Tabela ofert z wylotem dalej niż horyzont głównego raportu."""
    if not offers:
        return ""
    shown = offers[:50]
    rows = []
    for o in shown:
        rows.append(
            "<tr>"
            f"<td>{escape(o.destination_city_or_region)}</td>"
            f"<td class=\"cell-nowrap\">{escape(o.departure_date)}</td>"
            f"<td class=\"cell-nowrap\">{escape(o.return_date)}</td>"
            f"<td>{escape(o.hotel_name[:120])}</td>"
            f"<td>{o.total_trip_cost_pln:.0f} PLN</td>"
            f"<td><a href='{escape(o.source_url)}' target='_blank' rel='noopener'>{escape(o.source_name)}</a></td>"
            "</tr>"
        )
    more = ""
    if len(offers) > 50:
        more = f"<p><em>Pokazano 50 z {len(offers)} ofert w tej kategorii.</em></p>"
    today_s = date.today().isoformat()
    return (
        f"<h2>Oferty z dalszym terminem (wylot ponad {horizon_months} mies. — np. za rok)</h2>"
        "<p>Te pozycje <strong>nie</strong> są w głównych tabelach powyżej — termin wylotu jest "
        f"późniejszy niż ok. <strong>{horizon_months} miesięcy</strong> od dzisiaj "
        f"({escape(today_s)}).</p>"
        "<table><thead><tr>"
        "<th>Kierunek</th><th class=\"cell-nowrap\">Wylot</th><th class=\"cell-nowrap\">Powrót</th>"
        "<th>Hotel</th><th>Koszt realny/os</th><th>Zrodlo</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        + more
    )


def render_html(
    result: RankedResult,
    alerts: list[str],
    output_path: str,
    offers: list[Offer],
    data_mode: str,
    family_size: int,
    alternative_tips: list[str],
    best_offer_highlight: Offer | None = None,
    flight_fallback: FlightFallbackContext | None = None,
    offers_beyond_horizon: list[Offer] | None = None,
    horizon_months: int = 6,
    metasearch_footer_html: str = "",
) -> None:
    sections = []
    cheapest_nominal = sorted(offers, key=lambda x: x.price_per_person_pln)[:10]
    cheapest_real = sorted(offers, key=lambda x: x.total_trip_cost_pln)[:10]

    sections.append(f"<h2>Najtaniej nominalnie vs najtaniej realnie (rodzina: {family_size} os.)</h2>")
    sections.append(_top_table("TOP 10 nominalnie", cheapest_nominal, real=False))
    sections.append(_top_table("TOP 10 realnie", cheapest_real, real=True))

    sections.append("<h2>TOP oferty dla 1 osoby</h2>")
    for window, offers in result.solo.items():
        sections.append(_window_table(window, offers))

    sections.append("<h2>TOP oferty dla 2 osob</h2>")
    for window, offers in result.duo.items():
        sections.append(_window_table(window, offers))
    sections.append(_dictionary_html())
    if alternative_tips:
        tips_html = "".join(f"<li>{escape(t)}</li>" for t in alternative_tips)
        sections.append("<h2>Podpowiedz dat (+/- 1 dzien)</h2><ul>" + tips_html + "</ul>")

    if flight_fallback is not None:
        sections.append(fallback_section_html(flight_fallback))

    if offers_beyond_horizon:
        sections.append(_far_future_section(offers_beyond_horizon, horizon_months))

    highlight_html = _best_offer_block(best_offer_highlight) if best_offer_highlight else ""

    alert_html = "<ul>" + "".join(f"<li>{escape(a)}</li>" for a in alerts) + "</ul>" if alerts else "<p>Brak alertow</p>"

    mode_label = {
        "LIVE": "REALNE ZRODLA (LIVE)",
        "LIVE_PLUS_MOCK_FALLBACK": "LIVE + awaryjny fallback MOCK",
        "MOCK_ONLY": "DANE TESTOWE (MOCK). Wyniki moga sie powtarzac.",
        "NO_DATA": "BRAK DANYCH Z KOLEKTOROW",
    }.get(data_mode, data_mode)

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>VacationSeeker Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; table-layout: auto; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 14px; vertical-align: top; }}
    th {{ background: #f3f3f3; text-align: left; }}
    h2 {{ margin-top: 28px; }}
    .cell-nowrap {{ white-space: nowrap; min-width: 9.5em; }}
    table.matrix th {{ background: #e8f4fc; }}
    table.matrix td {{ vertical-align: top; }}
    .meta-links {{ font-size: 0.92em; line-height: 1.45; }}
    section#vacation-metasearch-bundle {{ margin-top: 8px; }}
  </style>
</head>
<body>
  <h1>VacationSeeker - Last Minute</h1>
  <p>Generowano: {datetime.now().isoformat(timespec="seconds")}</p>
  <p><strong>Tryb danych:</strong> {escape(mode_label)}</p>
  <p><strong>Główne rankingi:</strong> tylko oferty z wylotem w ciągu ok. <strong>{horizon_months} miesięcy</strong> od dzisiaj. Późniejsze terminy — osobna sekcja na dole raportu.</p>
  <h2>Alerty</h2>
  {alert_html}
  {highlight_html}
  {''.join(sections)}
  {metasearch_footer_html}
</body>
</html>
"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


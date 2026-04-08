"""
Linki do metasearch (Kayak, Google Flights, Skyscanner) gdy brak ofert w feedach.
Nie wywołujemy API — tylko gotowe URL-e wyszukiwania (dynamiczne ceny na stronach docelowych).

Parametry pasażerów muszą odpowiadać GUI: liczba dorosłych + lista wieków dzieci (np. 12, 14),
a nie „łączna liczba osób” jako dorośli.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlencode


@dataclass(frozen=True)
class FlightFallbackContext:
    destination_label: str
    departure_date: str  # YYYY-MM-DD
    return_date: str
    origin_iata: str
    adults: int
    """Wiek każdego dziecka (2–17), jak w GUI — children-ages „12,14”."""
    children_ages: tuple[int, ...] = ()


def parse_children_ages(s: str | None) -> tuple[int, ...]:
    if not s:
        return ()
    out: list[int] = []
    for part in s.split(","):
        p = part.strip()
        if p.isdigit():
            out.append(int(p))
    return tuple(out)


def guess_destination_iata(name: str) -> str | None:
    """Heurystyka IATA dla popularnych kierunków z PL; None = tylko wyszukiwanie tekstowe."""
    n = name.lower().strip()
    hints: list[tuple[str, str]] = [
        ("zakynthos", "ZTH"),
        ("zante", "ZTH"),
        ("kreta", "HER"),
        ("crete", "HER"),
        ("chania", "CHQ"),
        ("majorka", "PMI"),
        ("mallorca", "PMI"),
        ("palma", "PMI"),
        ("teneryfa", "TFS"),
        ("tenerife", "TFS"),
        ("lanzarote", "ACE"),
        ("fuerteventura", "FUE"),
        ("gran canaria", "LPA"),
        ("las palmas", "LPA"),
        ("barcelona", "BCN"),
        ("alicante", "ALC"),
        ("malaga", "AGP"),
        ("antalya", "AYT"),
        ("bodrum", "BJV"),
        ("dalaman", "DLM"),
        ("rodos", "RHO"),
        ("rhodes", "RHO"),
        ("kos", "KGS"),
        ("korfu", "CFU"),
        ("corfu", "CFU"),
        ("cypr", "LCA"),
        ("paphos", "PFO"),
        ("larnaka", "LCA"),
        ("malta", "MLA"),
        ("dubrovnik", "DBV"),
        ("split", "SPU"),
        ("zadar", "ZAD"),
        ("irlandia", "DUB"),
        ("dublin", "DUB"),
        ("portugalia", "LIS"),
        ("lizbona", "LIS"),
        ("algarve", "FAO"),
        ("faro", "FAO"),
        ("grecja", "ATH"),
        ("ateny", "ATH"),
        ("bulgaria", "VAR"),
        ("burgas", "BOJ"),
        ("wlochy", "FCO"),
        ("rzym", "FCO"),
        ("egipt", "HRG"),
        ("hurghada", "HRG"),
        ("sharm", "SSH"),
        ("maroko", "RAK"),
        ("tunezja", "TUN"),
    ]
    for needle, iata in hints:
        if needle in n:
            return iata
    return None


def _travelers_total(ctx: FlightFallbackContext) -> int:
    return max(1, ctx.adults + len(ctx.children_ages))


def _passenger_summary_pl(ctx: FlightFallbackContext) -> str:
    parts = [f"{ctx.adults} dorosłych"]
    if ctx.children_ages:
        ages = ", ".join(str(a) for a in ctx.children_ages)
        parts.append(f"dzieci (lata): {ages}")
    return "; ".join(parts)


def kayak_roundtrip_url(
    origin: str,
    dest: str,
    dep: str,
    ret: str,
    *,
    adults: int,
    children_ages: tuple[int, ...],
    sort: str = "bestflight_a",
) -> str:
    """
    Kayak PL — daty YYYY-MM-DD w ścieżce.

    Samo `?adults=&children=` jest często ignorowane — Kayak oczekuje segmentu w ścieżce,
    np. `/2adults-children-2` (wtedy UI pokazuje 2 dorosłych + 2 dzieci).
    """
    o, d = origin.upper(), dest.upper()
    base = f"https://www.kayak.pl/flights/{o}-{d}/{dep}/{ret}"
    a = max(1, adults)
    n_children = len(children_ages)

    # Segment pasażerów (weryfikowany na kayak.pl — bez tego zostaje 1 dorosły)
    if n_children == 0:
        pax_seg = f"{a}adults" if a > 1 else ""
    else:
        pax_seg = f"{a}adults-children-{n_children}"

    path = f"{base}/{pax_seg}" if pax_seg else base
    q: dict[str, str] = {"sort": sort}
    if children_ages:
        q["childages"] = ",".join(str(x) for x in children_ages)
    return f"{path}?{urlencode(q)}"


def _english_count_word(n: int) -> str:
    return (
        {
            1: "one",
            2: "two",
            3: "three",
            4: "four",
            5: "five",
            6: "six",
            7: "seven",
            8: "eight",
            9: "nine",
        }.get(n, str(n))
    )


def google_flights_url(ctx: FlightFallbackContext, dest_iata: str | None) -> str:
    """
    Google Travel Flights — `q` w stylu natural language (działa stabilniej niż sam opis „N adults”).

    Format jak w dokumentacji/community: „Flights to X from Y on … through … with two adults and two children economy”.
    Uwaga: w UI Google „dziecko” to zwykle 2–11 lat; osoby 12+ bywają liczone jako dorośli —
    wtedy w opisie można dodać wieki (Google i tak może pokazać część jako dorosłych).
    """
    o = ctx.origin_iata.upper()
    dest = dest_iata or ctx.destination_label
    dep = ctx.departure_date
    ret = ctx.return_date
    a = max(1, ctx.adults)
    n_ch = len(ctx.children_ages)

    parts = [f"Flights to {dest} from {o} on {dep} through {ret}"]

    if n_ch == 0:
        adult_phrase = f"{_english_count_word(a)} adult" + ("s" if a != 1 else "")
        parts.append(f"with {adult_phrase}")
    else:
        # np. „with two adults and two children” — to ustawia licznik pasażerów lepiej niż „4 adults” przy 12+12
        parts.append(
            f"with {_english_count_word(a)} adult{'s' if a != 1 else ''} and {_english_count_word(n_ch)} children"
        )
        ages = " and ".join(str(x) for x in ctx.children_ages)
        parts.append(f"ages {ages}")

    parts.append("economy")
    q = " ".join(parts)
    return "https://www.google.com/travel/flights?q=" + quote(q) + "&curr=PLN&hl=pl"


def skyscanner_url(
    origin: str,
    dest: str,
    dep: str,
    ret: str,
    *,
    adults: int,
    children_ages: tuple[int, ...],
) -> str:
    """
    Skyscanner PL — segmenty dat jako yyyymmdd.
    Dokumentacja referral: adultsv2 + childrenv2 z wiekami oddzielonymi |.
    """
    dep_s = dep.replace("-", "")
    ret_s = ret.replace("-", "")
    o, d = origin.lower(), dest.lower()
    base = f"https://www.skyscanner.pl/transport/loty/{o}/{d}/{dep_s}/{ret_s}/"
    params: list[tuple[str, str]] = [
        ("adultsv2", str(max(1, adults))),
        ("cabinclass", "economy"),
    ]
    if children_ages:
        params.append(("childrenv2", "|".join(str(a) for a in children_ages)))
    return f"{base}?{urlencode(params)}"


def build_fallback_rows(ctx: FlightFallbackContext) -> list[tuple[str, str, str]]:
    """
    Zwraca listę (etykieta, opis, url).
    """
    dest_iata = guess_destination_iata(ctx.destination_label)
    o = ctx.origin_iata.upper()
    rows: list[tuple[str, str, str]] = []
    a = max(1, ctx.adults)
    ch = ctx.children_ages

    if dest_iata:
        rows.append(
            (
                "Najtańsze loty (Kayak)",
                "Sortowanie: cena — bezpośrednie i z przesiadkami w jednym widoku.",
                kayak_roundtrip_url(o, dest_iata, ctx.departure_date, ctx.return_date, adults=a, children_ages=ch, sort="price_a"),
            )
        )
        rows.append(
            (
                "Najszybsze loty (Kayak)",
                "Sortowanie: czas lotu (często bezpośrednie na górze).",
                kayak_roundtrip_url(o, dest_iata, ctx.departure_date, ctx.return_date, adults=a, children_ages=ch, sort="duration_a"),
            )
        )
        rows.append(
            (
                "Skyscanner — porównanie",
                "Alternatywny agregator; czasem inne kombinacje przesiadek.",
                skyscanner_url(o, dest_iata, ctx.departure_date, ctx.return_date, adults=a, children_ages=ch),
            )
        )
    else:
        rows.append(
            (
                "Kayak — wyszukiwanie po nazwie",
                f"Nie znaleziono kodu IATA dla „{ctx.destination_label}” — otwórz Kayak i wskaż lotnisko docelowe.",
                "https://www.kayak.pl/flights",
            )
        )

    rows.append(
        (
            "Google Flights — elastycznie (przesiadki)",
            "Porównanie tras, często najlepsza cena z 1 przesiadką vs bezpośredni.",
            google_flights_url(ctx, dest_iata),
        )
    )

    return rows


def fallback_section_html(ctx: FlightFallbackContext) -> str:
    rows = build_fallback_rows(ctx)
    body = "".join(
        "<tr>"
        f"<td><strong>{_esc(label)}</strong></td>"
        f"<td>{_esc(desc)}</td>"
        f"<td><a href=\"{_href(url)}\" target=\"_blank\" rel=\"noopener\">Otwórz wyszukiwanie</a></td>"
        "</tr>"
        for label, desc, url in rows
    )
    note = (
        "<p><em>Uwaga: ceny na Kayak / Google / Skyscanner są dynamiczne — to linki do gotowego wyszukiwania, "
        "nie gwarancja ceny z raportu VacationSeeker. Google Flights liczy „dzieci” zwykle w wieku 2–11 lat; "
        "osoby 12+ mogą pojawić się jako dorośli — ceny i tak są za całą grupę z GUI.</em></p>"
    )
    pax = _esc(_passenger_summary_pl(ctx))
    return (
        "<h2>Brak pasujących ofert last minute w feedach — loty na metach (Kayak / Google Flights)</h2>"
        f"<p>Dla: <strong>{_esc(ctx.destination_label)}</strong>, "
        f"wylot {_esc(ctx.departure_date)}, powrót {_esc(ctx.return_date)}, "
        f"lotnisko startowe: <strong>{_esc(ctx.origin_iata)}</strong>, "
        f"pasażerowie: <strong>{pax}</strong> (łącznie {_travelers_total(ctx)} os.).</p>"
        + note
        + "<table><thead><tr><th>Typ</th><th>Opis</th><th>Link</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def _esc(s: str) -> str:
    from html import escape

    return escape(s, quote=True)


def _href(url: str) -> str:
    from html import escape

    return escape(url, quote=True)

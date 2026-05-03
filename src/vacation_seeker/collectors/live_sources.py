from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from xml.etree import ElementTree as ET

import requests

from .base import BaseCollector
from ..models import RawOffer


class WakacyjniPiraciRssCollector(BaseCollector):
    source_name = "wakacyjni_piraci_rss"
    feed_url = "https://www.wakacyjnipiraci.pl/feed/"
    # Pobierz HTML artykułu, gdy RSS nie ma pełnego terminu (np. „14 - 21 maja” tylko na stronie)
    fetch_article_html: bool = os.getenv("VACATION_PIRACI_FETCH_ARTICLE", "true").lower() in {"1", "true", "yes"}
    fetch_article_max: int = int(os.getenv("VACATION_PIRACI_FETCH_MAX", "28"))
    fetch_timeout: int = int(os.getenv("VACATION_PIRACI_FETCH_TIMEOUT", "14"))

    def collect(self) -> list[RawOffer]:
        r = requests.get(self.feed_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.text)
        items = root.findall(".//item")
        offers: list[RawOffer] = []
        pending_fetch: list[tuple[Any, str, str, str, date | None, str]] = []

        for item in items[:60]:
            title = _text(item.find("title"))
            link = _text(item.find("link"))
            desc = _text(item.find("description"))
            pub_date = _text(item.find("pubDate"))
            pub_d = _safe_pubdate_to_date(pub_date)

            rss_blob = _strip_html(_item_full_text(item))
            dep_date, ret_date, nights = _extract_trip_dates(rss_blob, pub_d)

            hotel_name = title[:80] if title else "Oferta z feedu"
            if dep_date is None and self.fetch_article_html and link and _is_piraci_url(link):
                pending_fetch.append((item, title, link, desc, pub_d, hotel_name))
                continue

            dep_date, ret_date, nights, hotel_name = self._finalize_dates(
                dep_date, ret_date, nights, pub_d, hotel_name, rss_blob
            )

            ppp = _extract_price_pln(f"{title} {desc}")
            destination = _extract_destination(title, desc)
            board = _extract_board_type(f"{title} {desc}")
            offers.append(
                RawOffer(
                    source_name=self.source_name,
                    source_url=link or self.feed_url,
                    destination_country=destination,
                    destination_city_or_region=destination,
                    departure_airport="unknown",
                    departure_date=dep_date.isoformat(),
                    return_date=ret_date.isoformat(),
                    trip_nights=nights,
                    board_type=board,
                    hotel_name=hotel_name,
                    hotel_stars=None,
                    package_type="deal_post",
                    price_total_pln=(ppp * 2) if ppp else 9998.0,
                    price_per_person_pln=ppp,
                    people_supported="unknown",
                    baggage_included="unknown",
                    transfer_included="unknown",
                    cancellation_terms=None,
                    promo_tag="last_minute",
                )
            )

        # Drugi przebieg: strona artykułu (pełny „proponowany termin”, zakresy dat w treści)
        if pending_fetch and self.fetch_article_html:
            to_fetch = pending_fetch[: self.fetch_article_max]
            html_by_link: dict[str, str | None] = {}
            unique_urls = list(dict.fromkeys(url for _, _, url, _, _, _ in to_fetch if url))
            with ThreadPoolExecutor(max_workers=6) as pool:
                futs = {pool.submit(_fetch_article_text, u, self.fetch_timeout): u for u in unique_urls}
                for fut in as_completed(futs):
                    url = futs[fut]
                    try:
                        html_by_link[url] = fut.result()
                    except Exception:
                        html_by_link[url] = None

            for item, title, link, desc, pub_d, hotel_name in to_fetch:
                page = html_by_link.get(link)
                dep_date, ret_date, nights = (None, None, 7)
                if page:
                    dep_date, ret_date, nights = _extract_trip_dates(_strip_html(page), pub_d)
                if dep_date is None:
                    rss_blob = _strip_html(_item_full_text(item))
                    dep_date, ret_date, nights = _extract_trip_dates(rss_blob, pub_d)

                text_blob = ""
                if page:
                    text_blob = _strip_html(page) + " "
                text_blob += _strip_html(_item_full_text(item))

                dep_date, ret_date, nights, hotel_name = self._finalize_dates(
                    dep_date, ret_date, nights, pub_d, hotel_name, text_blob
                )

                ppp = _extract_price_pln(f"{title} {desc}")
                destination = _extract_destination(title, desc)
                board = _extract_board_type(f"{title} {desc}")
                offers.append(
                    RawOffer(
                        source_name=self.source_name,
                        source_url=link or self.feed_url,
                        destination_country=destination,
                        destination_city_or_region=destination,
                        departure_airport="unknown",
                        departure_date=dep_date.isoformat(),
                        return_date=ret_date.isoformat(),
                        trip_nights=nights,
                        board_type=board,
                        hotel_name=hotel_name,
                        hotel_stars=None,
                        package_type="deal_post",
                        price_total_pln=(ppp * 2) if ppp else 9998.0,
                        price_per_person_pln=ppp,
                        people_supported="unknown",
                        baggage_included="unknown",
                        transfer_included="unknown",
                        cancellation_terms=None,
                        promo_tag="last_minute",
                    )
                )

        return offers

    def _finalize_dates(
        self,
        dep_date: date | None,
        ret_date: date | None,
        nights: int,
        pub_d: date | None,
        hotel_name: str,
        text_blob: str = "",
    ) -> tuple[date, date, int, str]:
        """Ostatnia deska: frazy dostępności z treści strony zamiast suchego „brak terminu”."""
        if dep_date is not None and ret_date is not None:
            n = max(1, (ret_date - dep_date).days)
            return dep_date, ret_date, n, hotel_name

        snippet, end_avail = _extract_availability_until_text(text_blob)
        if snippet and end_avail:
            dep, ret = _dates_from_availability_window(pub_d, end_avail)
            n = max(1, (ret - dep).days)
            prefix = f"[{snippet}] "
            return dep, ret, n, (prefix + hotel_name)[:200]

        # Brak terminu — nie podawaj pubDate jako „wylotu”; oznacz w nazwie.
        fallback = pub_d or date.today()
        dep_date = fallback
        ret_date = fallback + timedelta(days=7)
        warn = "[brak terminu w RSS — data w tabeli to publikacja; sprawdź link] "
        return dep_date, ret_date, 7, (warn + hotel_name)[:200]


class TuiLastMinuteCollector(BaseCollector):
    source_name = "tui_live"
    page_urls = [
        "https://www.tui.pl/last-minute",
        "https://www.tui.pl/last-minute?page=2",
        "https://www.tui.pl/last-minute?page=3",
    ]

    def collect(self) -> list[RawOffer]:
        offers: list[RawOffer] = []
        seen: set[str] = set()
        for page_url in self.page_urls:
            try:
                r = requests.get(page_url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
            except Exception:
                continue
            m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.S)
            if not m:
                continue
            data = json.loads(m.group(1))
            for obj in _walk_dicts(data):
                if "hotelName" not in obj or "departureDate" not in obj:
                    continue
                departure = _parse_any_date(str(obj.get("departureDate", "")))
                if not departure:
                    continue
                return_date = _parse_any_date(str(obj.get("returnDate", "")))
                ppp = _to_float(obj.get("discountPerPersonPrice")) or _to_float(obj.get("originalPerPersonPrice"))
                if ppp is None or ppp <= 0:
                    continue

                hotel_name = str(obj.get("hotelName") or "Oferta TUI")
                destination = str(obj.get("city") or obj.get("destinationCode") or "unknown")
                nights = int(_to_float(obj.get("duration")) or 7)
                if not return_date:
                    return_date = departure + timedelta(days=nights)
                board = _extract_board_type(str(obj.get("boardType") or obj.get("boardCode") or "RO"))
                airport = str(obj.get("departureAirport") or "unknown")
                stars = _to_float(obj.get("hotelStandard"))
                url = str(obj.get("offerUrl") or page_url)
                if url.startswith("/"):
                    url = "https://www.tui.pl" + url

                key = f"{hotel_name}|{departure.isoformat()}|{ppp}"
                if key in seen:
                    continue
                seen.add(key)
                offers.append(
                    RawOffer(
                        source_name=self.source_name,
                        source_url=url,
                        destination_country=destination,
                        destination_city_or_region=destination,
                        departure_airport=airport,
                        departure_date=departure.isoformat(),
                        return_date=return_date.isoformat(),
                        trip_nights=max(1, nights),
                        board_type=board,
                        hotel_name=hotel_name[:80],
                        hotel_stars=stars,
                        package_type="flight+hotel",
                        price_total_pln=ppp * 2,
                        price_per_person_pln=ppp,
                        people_supported="2",
                        baggage_included="unknown",
                        transfer_included="unknown",
                        cancellation_terms=None,
                        promo_tag="last_minute",
                    )
                )
                if len(offers) >= 240:
                    break
            if len(offers) >= 240:
                break
        return offers


class RainbowLastMinuteCollector(BaseCollector):
    source_name = "rainbow_live"
    base_url = "https://www.r.pl/last-minute"
    max_pages: int = int(os.getenv("VACATION_RAINBOW_MAX_PAGES", "4"))
    max_offers: int = int(os.getenv("VACATION_RAINBOW_MAX_OFFERS", "260"))
    timeout: int = int(os.getenv("VACATION_RAINBOW_TIMEOUT", "20"))

    def collect(self) -> list[RawOffer]:
        offers: list[RawOffer] = []
        seen_urls: set[str] = set()

        for page_no in range(1, max(1, self.max_pages) + 1):
            page_url = self.base_url if page_no == 1 else f"{self.base_url}?strona={page_no}"
            try:
                r = requests.get(page_url, timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
            except Exception:
                continue

            for offer in _extract_rainbow_offers_from_html(r.text, page_url):
                if offer.source_url in seen_urls:
                    continue
                seen_urls.add(offer.source_url)
                offers.append(offer)
                if len(offers) >= self.max_offers:
                    return offers
        return offers


def _text(node) -> str:
    return (node.text or "").strip() if node is not None else ""


def _safe_pubdate_to_date(pub_date: str):
    if not pub_date:
        return None
    try:
        return parsedate_to_datetime(pub_date).date()
    except Exception:
        return None


def _extract_price_pln(text: str) -> float | None:
    m = re.search(r"(\d[\d\s]{2,6})\s?z[łl]", text, re.I)
    if not m:
        return None
    val = re.sub(r"\s+", "", m.group(1))
    try:
        return float(val)
    except ValueError:
        return None


def _extract_destination(title: str, desc: str) -> str:
    text = f"{title} {desc}"
    for marker in [" do ", " w ", " na "]:
        if marker in text.lower():
            idx = text.lower().find(marker) + len(marker)
            chunk = text[idx : idx + 30]
            token = re.split(r"[,\.\|\-:]", chunk)[0].strip()
            if token:
                return token.title()
    return "unknown"


def _norm_board_scan(text: str) -> str:
    """Małe litery + odpolszczenie znaków — do dopasowań wyżywienia w treści ofert."""
    t = text.lower()
    for a, b in (
        ("ą", "a"),
        ("ć", "c"),
        ("ę", "e"),
        ("ł", "l"),
        ("ń", "n"),
        ("ó", "o"),
        ("ś", "s"),
        ("ź", "z"),
        ("ż", "z"),
    ):
        t = t.replace(a, b)
    return t


def _extract_board_type(text: str) -> str:
    """
    RO / BB / HB / AI z opisu (PL/EN). HB przed BB — żeby „śniadanie i obiadokolacja” nie wpadało jako samo BB.
    """
    if not text:
        return "RO"
    up = text.upper()
    n = _norm_board_scan(text)

    if (
        "ALL INCLUSIVE" in up
        or " AI" in up
        or re.search(r"\bAI\b", up)
        or "all inclusive" in n
    ):
        return "AI"

    hb_markers = (
        "half board",
        "halfboard",
        "pol pensjonat",
        "demi-pension",
        "demi pension",
        "obiadokolacja",
        "obiadokolacji",
        "sniadanie i obiadokolacja",
        "sniadanie i kolacja",
        "snidanie i kolacja",
        "2 posilki",
        "dwa posilki",
        "dwie posilki",
        "posilki: sniadanie i obiadokolacja",
    )
    if re.search(r"\bHB\b", up) or any(m in n for m in hb_markers):
        return "HB"

    bb_markers = (
        "bed & breakfast",
        "bed and breakfast",
        "b&b",
        "nocleg ze sniadaniem",
        "samo sniadanie",
        "tylko sniadanie",
        "sniadanie wliczone",
        "sniadanie w cenie",
        "wyzywienie: sniadanie",
        "w package sniadanie",
    )
    if re.search(r"\bBB\b", up) or any(m in n for m in bb_markers):
        return "BB"

    if "BB" in up:
        return "BB"
    if "HB" in up:
        return "HB"
    return "RO"


# Nazwy miesięcy w treści artykułów WP (np. „proponowany termin: 14 - 21 maja”)
_POLISH_MONTHS: dict[str, int] = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "wrzesnia": 9,
    "października": 10,
    "pazdziernika": 10,
    "listopada": 11,
    "grudnia": 12,
}


def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _item_full_text(item) -> str:
    parts: list[str] = []
    for child in item:
        tag = child.tag
        if tag.endswith("title") or tag.endswith("description") or tag.endswith("encoded"):
            parts.append(_text(child))
    if not parts:
        parts = [_text(item.find("title")), _text(item.find("description"))]
    return " ".join(parts)


def _is_piraci_url(url: str) -> bool:
    return bool(url) and "wakacyjnipiraci.pl" in url.lower()


def _fetch_article_text(url: str, timeout: int) -> str:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (compatible; VacationSeeker/1.0)"})
    r.raise_for_status()
    return r.text


def _year_for_trip(ref: date, month: int, day: int) -> int:
    y = ref.year
    try:
        cand = date(y, month, day)
    except ValueError:
        return y
    if cand < ref:
        return y + 1
    return y


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _dates_from_availability_window(pub_d: date | None, end_avail: date) -> tuple[date, date]:
    """Szacowany zakres: wylot od publikacji (lub dziś), powrót nie później niż koniec okna dostępności."""
    today = date.today()
    dep = pub_d or today
    if dep > end_avail:
        dep = end_avail - timedelta(days=7)
        if dep < today:
            dep = today
    ret = min(dep + timedelta(days=7), end_avail)
    if ret <= dep:
        ret = end_avail
    return dep, ret


def _extract_availability_until_text(text: str) -> tuple[str | None, date | None]:
    """
    Wyciąga z treści strony m.in.:
    „Wolne terminy znajdziecie do listopada 2026” → koniec okna = ostatni dzień tego miesiąca.
    """
    if not text:
        return None, None
    month_alt = "|".join(sorted(_POLISH_MONTHS.keys(), key=len, reverse=True))
    # Bez zbędnego nawiasu zewnętrznego — grupy 1/2 to miesiąc i rok (snippet = group(0)).
    patterns = [
        # np. "Wolne terminy znajdziecie do listopada 2026"
        rf"Wolne\s+terminy\s+znajdziecie\s+(?:(?:aż|az)\s+)?do\s+({month_alt})\s+(\d{{4}})",
        # np. "wolne terminy do listopada 2026"
        rf"wolne\s+terminy\s+(?:(?:aż|az)\s+)?do\s+({month_alt})\s+(\d{{4}})",
        # np. "do końca listopada 2026"
        rf"do\s+ko(?:ń|n)ca\s+({month_alt})\s+(\d{{4}})",
        # np. "Terminy znajdziecie aż do września 2026"
        rf"terminy\s+znajdziecie\s+(?:(?:aż|az)\s+)?do\s+({month_alt})\s+(\d{{4}})",
        # np. "terminy do września 2026 znajdziecie w kalendarzu"
        rf"terminy\s+(?:(?:aż|az)\s+)?do\s+({month_alt})\s+(\d{{4}})\s+znajdziecie",
        # szeroki fallback: "terminy ... do września 2026"
        rf"terminy.{0,60}?(?:(?:aż|az)\s+)?do\s+({month_alt})\s+(\d{{4}})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        mon_word = m.group(1).lower()
        year = int(m.group(2))
        mo = _POLISH_MONTHS.get(mon_word)
        if mo is None:
            continue
        try:
            end = _last_day_of_month(year, mo)
        except ValueError:
            continue
        snippet = m.group(0).strip()
        if len(snippet) > 140:
            snippet = snippet[:137] + "…"
        return snippet, end
    return None, None


def _extract_trip_dates(text: str, pub_d: date | None) -> tuple[date | None, date | None, int]:
    """
    Wyciąga termin wyjazdu z RSS / HTML.
    NIE używa pubDate jako terminu — unikamy sytuacji „wszystko 2026-03-23”.
    """
    if not text:
        return None, None, 7
    ref = pub_d or date.today()
    t = re.sub(r"\s+", " ", text.strip())

    # 1) Nawias: (14.05.2026 - 21.05.2026) — często na stronie artykułu
    m = re.search(
        r"\(\s*(\d{2})\.(\d{2})\.(\d{4})\s*[-–]\s*(\d{2})\.(\d{2})\.(\d{4})\s*\)",
        t,
    )
    if m:
        d1, mo1, y1, d2, mo2, y2 = map(int, m.groups())
        try:
            dep = date(y1, mo1, d1)
            ret = date(y2, mo2, d2)
            return dep, ret, max(1, (ret - dep).days)
        except ValueError:
            pass

    # 2) Zakres dd.mm.yyyy - dd.mm.yyyy
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\s*[-–]\s*(\d{2})\.(\d{2})\.(\d{4})", t)
    if m:
        d1, mo1, y1, d2, mo2, y2 = map(int, m.groups())
        try:
            dep = date(y1, mo1, d1)
            ret = date(y2, mo2, d2)
            return dep, ret, max(1, (ret - dep).days)
        except ValueError:
            pass

    # 3) „proponowany termin”, „wylot”, polskie miesiące: 14 - 21 maja
    month_alt = "|".join(sorted(_POLISH_MONTHS.keys(), key=len, reverse=True))
    rx_kw = re.compile(
        rf"(?:proponowany\s+termin|termin\s+podróży|terminie|wylot(?:u|em)?|termin)[:\s]*"
        rf"(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s+({month_alt})",
        re.I,
    )
    mm = rx_kw.search(t)
    if not mm:
        rx_loose = re.compile(rf"(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s+({month_alt})\b", re.I)
        mm = rx_loose.search(t)
    if mm:
        d_a, d_b = int(mm.group(1)), int(mm.group(2))
        mon_key = mm.group(3).lower()
        mo = _POLISH_MONTHS.get(mon_key)
        if mo:
            y = _year_for_trip(ref, mo, min(d_a, d_b))
            try:
                dep = date(y, mo, d_a)
                ret = date(y, mo, d_b)
                if ret < dep:
                    ret = date(y + 1, mo, d_b)
                return dep, ret, max(1, (ret - dep).days)
            except ValueError:
                pass

    # 4) Zakres YYYY-MM-DD — YYYY-MM-DD
    m = re.search(
        r"(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})",
        t,
    )
    if m:
        try:
            dep = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            ret = datetime.strptime(m.group(2), "%Y-%m-%d").date()
            return dep, ret, max(1, (ret - dep).days)
        except ValueError:
            pass

    # 5) Ostatnie dopasowania dd.mm.yyyy (unikaj daty publikacji przy „Opublikował 22.03.2026”)
    matches = list(re.finditer(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", t))
    for m in reversed(matches):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            cand = date(y, mo, d)
        except ValueError:
            continue
        if pub_d and cand == pub_d:
            continue
        if pub_d and cand < pub_d - timedelta(days=550):
            continue
        return cand, cand + timedelta(days=7), 7

    return None, None, 7


def _walk_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_dicts(item)


def _pick(obj: dict[str, Any], keys: list[str]):
    for key in keys:
        if key in obj and obj[key] not in (None, "", []):
            return obj[key]
    return None


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", "").replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _parse_any_date(value: str):
    value = value.strip()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        pass
    # Try to extract date fragment from datetime string.
    m = re.search(r"(\d{4}-\d{2}-\d{2})", value)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _extract_rainbow_offers_from_html(page_html: str, page_url: str) -> list[RawOffer]:
    offers: list[RawOffer] = []
    if not page_html:
        return offers

    # Rainbow SSR renderuje karty jako <a href="...unikalnyKluczOferty=...">...</a>.
    for m in re.finditer(r'<a[^>]+href="([^"]*unikalnyKluczOferty[^"]+)"[^>]*>(.*?)</a>', page_html, re.I | re.S):
        href_raw = unescape(m.group(1) or "").strip()
        if not href_raw:
            continue
        url = href_raw if href_raw.startswith("http") else ("https://www.r.pl" + href_raw)

        text = _strip_html(unescape(m.group(2) or ""))
        if not text:
            continue

        dep = _extract_first_pl_date(text)
        if not dep:
            continue

        nights = _extract_nights_from_text(text)
        ret = dep + timedelta(days=max(1, nights))
        ppp = _extract_price_pln(text)
        if ppp is None or ppp <= 0:
            continue

        destination = _extract_rainbow_destination(text)
        hotel_name = _extract_rainbow_hotel_name(text)
        airport = _extract_rainbow_airport(text, dep)
        board = _extract_board_type(text)

        offers.append(
            RawOffer(
                source_name="rainbow_live",
                source_url=url or page_url,
                destination_country=destination,
                destination_city_or_region=destination,
                departure_airport=airport,
                departure_date=dep.isoformat(),
                return_date=ret.isoformat(),
                trip_nights=max(1, nights),
                board_type=board,
                hotel_name=hotel_name[:80],
                hotel_stars=None,
                package_type="flight+hotel",
                price_total_pln=ppp * 2,
                price_per_person_pln=ppp,
                people_supported="2",
                baggage_included="unknown",
                transfer_included="unknown",
                cancellation_terms=None,
                promo_tag="last_minute",
            )
        )
    return offers


def _extract_first_pl_date(text: str) -> date | None:
    m = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _extract_nights_from_text(text: str) -> int:
    m = re.search(r"\(\s*\d+\s*dni\s*/\s*(\d+)\s*nocleg", text, re.I)
    if m:
        try:
            return max(1, int(m.group(1)))
        except ValueError:
            return 7
    m = re.search(r"\b(\d+)\s*noc", text, re.I)
    if m:
        try:
            return max(1, int(m.group(1)))
        except ValueError:
            return 7
    return 7


def _extract_rainbow_destination(text: str) -> str:
    m = re.search(r"•\s*([^:]+):", text)
    if m:
        val = m.group(1).strip()
        if val:
            return val
    return _extract_destination(text, text)


def _extract_rainbow_hotel_name(text: str) -> str:
    m = re.search(r":\s*(.*?)\s+\d{2}\.\d{2}\.\d{4}\b", text)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        if val:
            return val
    return text[:80] if text else "Oferta Rainbow"


def _extract_rainbow_airport(text: str, dep: date) -> str:
    date_str = dep.strftime("%d.%m.%Y")
    idx = text.find(date_str)
    if idx < 0:
        return "unknown"
    after = text[idx + len(date_str) :]
    after = re.sub(r"\(\d+\s*dni.*$", "", after, flags=re.I).strip()
    m = re.search(r"([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9 +\-]{3,40})", after)
    if not m:
        return "unknown"
    airport = m.group(1).strip(" -")
    return airport or "unknown"


"""
Dodatkowe źródła LIVE: RSS typu okazje (loty/pakiety) oraz Itaka last minute (Next.js __NEXT_DATA__).
Bez portali informacyjnych i „podróżniczej” redakcji (Gazeta, Onet podróże, WP turystyka itd.) — to nie są feedy ofert wycieczkowych.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Any
from xml.etree import ElementTree as ET

import requests

from .base import BaseCollector
from .live_sources import (
    _extract_board_type,
    _extract_destination,
    _extract_price_pln,
    _extract_trip_dates,
    _item_full_text,
    _safe_pubdate_to_date,
    _strip_html,
    _text,
)
from ..models import RawOffer

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _rss_blob(item) -> str:
    return _strip_html(_item_full_text(item))


def _rss_item_categories(item) -> list[str]:
    """Teksty tagów <category> w elemencie RSS (WordPress)."""
    out: list[str] = []
    for el in item.findall("category"):
        t = _text(el).strip()
        if t:
            out.append(t)
    return out


def _extract_price_pln_flexible(text: str) -> float | None:
    """Jak _extract_price_pln, plus wariant „1234 PLN” (częsty w opisach Fly4free)."""
    p = _extract_price_pln(text)
    if p is not None:
        return p
    m = re.search(r"(\d[\d\s]{2,6})\s*PLN\b", text, re.I)
    if not m:
        return None
    val = re.sub(r"\s+", "", m.group(1))
    try:
        return float(val)
    except ValueError:
        return None


class GenericRssDealCollector(BaseCollector):
    """Wpisy RSS → RawOffer (jak redakcyjne okazje / last minute)."""

    feed_url: str
    max_items: int = 45
    timeout: int = 25
    user_agent: str = _DEFAULT_UA

    def item_passes_filter(
        self, item, title: str, desc: str, categories: list[str]
    ) -> bool:
        """Domyślnie wszystkie wpisy; nadpisz w źródłach z mieszanym feedem (np. Fly4free)."""
        return True

    def collect(self) -> list[RawOffer]:
        r = requests.get(self.feed_url, timeout=self.timeout, headers={"User-Agent": self.user_agent})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        offers: list[RawOffer] = []
        for item in items[: self.max_items]:
            title = _text(item.find("title"))
            link = _text(item.find("link"))
            desc = _text(item.find("description"))
            categories = _rss_item_categories(item)
            if not self.item_passes_filter(item, title, desc, categories):
                continue
            pub_date = _text(item.find("pubDate"))
            pub_d = _safe_pubdate_to_date(pub_date)
            blob = _rss_blob(item)
            dep_date, ret_date, nights = _extract_trip_dates(blob, pub_d)
            hotel_name = (title or "Oferta z RSS")[:200]
            if dep_date is None or ret_date is None:
                fallback = pub_d or date.today()
                dep_date = fallback
                ret_date = fallback + timedelta(days=7)
                nights = 7
                hotel_name = (
                    "[brak terminu w RSS — sprawdź artykuł] " + hotel_name
                )[:200]
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
                    trip_nights=max(1, nights),
                    board_type=board,
                    hotel_name=hotel_name[:200],
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


# Fragmenty kategorii RSS Fly4free wskazujące na okazję (nie redakcyjny „News”).
_FLY4FREE_DEAL_CATEGORY_FRAGMENTS = (
    "tanie loty",
    "wczasy",
    "pakiety",
    "hotel4free",
    "polecane",
    "city break",
    "all inclusive",
    "słoneczne kierunki",
    "sloneczne kierunki",
    "loty czarterowe",
    "majówka",
    "first minute",
    "last minute",
    "okazje",
    "noclegi",
)


class Fly4freeRssCollector(GenericRssDealCollector):
    source_name = "fly4free_rss"
    feed_url = "https://www.fly4free.pl/feed/"

    def item_passes_filter(
        self, item, title: str, desc: str, categories: list[str]
    ) -> bool:
        flag = os.getenv("VACATION_FLY4FREE_FILTER", "1").strip().lower()
        if flag in ("0", "false", "no", "off"):
            return True

        cats_joined = " ".join(c.lower() for c in categories)
        for frag in _FLY4FREE_DEAL_CATEGORY_FRAGMENTS:
            if frag in cats_joined:
                return True

        require_cat = os.getenv(
            "VACATION_FLY4FREE_REQUIRE_CATEGORY", "0"
        ).strip().lower() in ("1", "true", "yes", "on")
        if require_cat:
            return False

        blob = f"{title} {desc}"
        p = _extract_price_pln_flexible(blob)
        try:
            min_p = float(os.getenv("VACATION_FLY4FREE_MIN_PLN", "80"))
            max_p = float(os.getenv("VACATION_FLY4FREE_MAX_PLN", "50000"))
        except ValueError:
            min_p, max_p = 80.0, 50000.0

        if p is None or p < min_p or p > max_p:
            return False

        cats_lower = [c.lower() for c in categories]
        if "news" in cats_lower:
            return False

        blob_l = blob.lower()
        for needle in (
            "uokik",
            "rekompensat",
            "podwyższ",
            "podwyższaj",
            "opłat za bagaż",
            "oplat za bagaz",
        ):
            if needle in blob_l:
                return False

        return True


class HolidayPiratesRssCollector(GenericRssDealCollector):
    source_name = "holidaypirates_rss"
    feed_url = "https://www.holidaypirates.pl/feed/"
    timeout = int(os.getenv("VACATION_HP_RSS_TIMEOUT", "30"))


def _itaka_geo_path(geographical: list[dict[str, Any]] | None) -> str | None:
    if not geographical:
        return None
    country = next((g for g in geographical if g.get("type") == "country"), None)
    province = next((g for g in geographical if g.get("type") == "province"), None)
    if not country:
        return None
    cid = str(country.get("id") or "").strip()
    if not cid:
        return None
    if province and province.get("id"):
        pid = str(province["id"]).strip()
        return f"https://www.itaka.pl/wczasy/{cid}/{pid}/"
    return f"https://www.itaka.pl/wczasy/{cid}/"


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    s = str(value).strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


class ItakaLastMinuteCollector(BaseCollector):
    """Listing last minute Itaka — dane z osadzonego JSON (__NEXT_DATA__)."""

    source_name = "itaka_lastminute_live"
    page_url = "https://www.itaka.pl/last-minute/"
    max_offers: int = int(os.getenv("VACATION_ITAKA_MAX_OFFERS", "120"))
    timeout: int = int(os.getenv("VACATION_ITAKA_TIMEOUT", "35"))

    def collect(self) -> list[RawOffer]:
        r = requests.get(self.page_url, timeout=self.timeout, headers={"User-Agent": _DEFAULT_UA})
        r.raise_for_status()
        m = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            r.text,
            re.S,
        )
        if not m:
            return []
        data = json.loads(m.group(1))
        queries = (
            data.get("props", {})
            .get("pageProps", {})
            .get("initialQueryState", {})
            .get("queries", [])
        )
        if not queries:
            return []
        rates = (
            queries[0]
            .get("state", {})
            .get("data", {})
            .get("main", {})
            .get("rates", {})
            .get("list", [])
        )
        if not isinstance(rates, list):
            return []

        offers: list[RawOffer] = []
        for rate in rates[: self.max_offers]:
            if not isinstance(rate, dict):
                continue
            participants = rate.get("participants") or []
            ppp_grosze = None
            for p in participants:
                if isinstance(p, dict) and p.get("type") == "adult":
                    ppp_grosze = p.get("price")
                    break
            if ppp_grosze is None:
                continue
            try:
                ppp = float(ppp_grosze) / 100.0
            except (TypeError, ValueError):
                continue
            if ppp <= 0:
                continue

            segments = rate.get("segments") or []
            hotel_seg = next((s for s in segments if isinstance(s, dict) and s.get("type") == "hotel"), None)
            flight_out = None
            for s in segments:
                if isinstance(s, dict) and s.get("type") == "flight":
                    flight_out = s
                    break

            dep_d: date | None = None
            ret_d: date | None = None
            nights = int((rate.get("duration") or {}).get("days") or 7)
            hotel_name = "Oferta Itaka"
            board = "RO"
            stars: float | None = None

            if hotel_seg:
                dep_d = _parse_iso_date(hotel_seg.get("beginDate"))
                ret_d = _parse_iso_date(hotel_seg.get("endDate"))
                content = (hotel_seg.get("content") or {}) if isinstance(hotel_seg.get("content"), dict) else {}
                hotel_name = str(content.get("title") or hotel_name)[:120]
                meal = hotel_seg.get("meal") or {}
                if isinstance(meal, dict) and meal.get("title"):
                    board = _extract_board_type(str(meal.get("title")))
                hr = content.get("hotelRating")
                if hr is not None:
                    try:
                        stars = float(hr) / 10.0
                    except (TypeError, ValueError):
                        stars = None

            if dep_d is None and flight_out:
                dep_d = _parse_iso_date(str(flight_out.get("beginDateTime") or "")[:10])

            if dep_d is None:
                continue
            if ret_d is None:
                ret_d = dep_d + timedelta(days=max(1, nights))

            dest_parts: list[str] = []
            geo = None
            if hotel_seg:
                geo = hotel_seg.get("geographicalIdentifiers")
            if isinstance(geo, list):
                for g in geo:
                    if isinstance(g, dict) and g.get("type") in ("country", "province") and g.get("title"):
                        dest_parts.append(str(g["title"]))
            destination = ", ".join(dest_parts) if dest_parts else "unknown"

            airport = "unknown"
            if flight_out:
                dep_node = flight_out.get("departure") or {}
                if isinstance(dep_node, dict) and dep_node.get("title"):
                    airport = str(dep_node["title"])[:40]

            url = _itaka_geo_path(geo if isinstance(geo, list) else None) or self.page_url

            offers.append(
                RawOffer(
                    source_name=self.source_name,
                    source_url=url,
                    destination_country=destination,
                    destination_city_or_region=destination,
                    departure_airport=airport,
                    departure_date=dep_d.isoformat(),
                    return_date=ret_d.isoformat(),
                    trip_nights=max(1, (ret_d - dep_d).days),
                    board_type=board,
                    hotel_name=hotel_name,
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
        return offers


def default_extra_collectors() -> list[BaseCollector]:
    """Fly4free + Holiday Pirates (okazje) + Itaka (biuro, last minute). Bez RSS redakcji podróżniczej."""
    return [
        Fly4freeRssCollector(),
        HolidayPiratesRssCollector(),
        ItakaLastMinuteCollector(),
    ]

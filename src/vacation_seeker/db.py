from __future__ import annotations

import sqlite3
from datetime import datetime

from .models import Offer
from .watcher import WatchProfile


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id_hash TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            collected_at_utc TEXT NOT NULL,
            destination_country TEXT NOT NULL,
            destination_city_or_region TEXT NOT NULL,
            departure_airport TEXT NOT NULL,
            departure_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            trip_nights INTEGER NOT NULL,
            board_type TEXT NOT NULL,
            hotel_name TEXT NOT NULL,
            hotel_stars REAL,
            package_type TEXT NOT NULL,
            price_total_pln REAL NOT NULL,
            price_per_person_pln REAL NOT NULL,
            airport_transfer_cost_pln REAL NOT NULL DEFAULT 0,
            baggage_cost_pln REAL NOT NULL DEFAULT 0,
            local_daily_cost_pln REAL NOT NULL DEFAULT 0,
            total_trip_cost_pln REAL NOT NULL DEFAULT 0,
            people_supported TEXT NOT NULL,
            baggage_included TEXT NOT NULL,
            transfer_included TEXT NOT NULL,
            cancellation_terms TEXT,
            promo_tag TEXT,
            score REAL NOT NULL,
            nominal_score REAL NOT NULL DEFAULT 0,
            price_confidence TEXT NOT NULL DEFAULT 'unknown',
            stale_data INTEGER NOT NULL,
            verification TEXT NOT NULL
        )
        """
    )
    for statement in (
        "ALTER TABLE offers ADD COLUMN airport_transfer_cost_pln REAL NOT NULL DEFAULT 0",
        "ALTER TABLE offers ADD COLUMN baggage_cost_pln REAL NOT NULL DEFAULT 0",
        "ALTER TABLE offers ADD COLUMN local_daily_cost_pln REAL NOT NULL DEFAULT 0",
        "ALTER TABLE offers ADD COLUMN total_trip_cost_pln REAL NOT NULL DEFAULT 0",
        "ALTER TABLE offers ADD COLUMN nominal_score REAL NOT NULL DEFAULT 0",
        "ALTER TABLE offers ADD COLUMN price_confidence TEXT NOT NULL DEFAULT 'unknown'",
    ):
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS offer_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id_hash TEXT NOT NULL,
            snapshot_at_utc TEXT NOT NULL,
            price_per_person_pln REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            destination_query TEXT NOT NULL,
            adults INTEGER NOT NULL,
            children_ages TEXT NOT NULL,
            target_email TEXT NOT NULL,
            drop_ratio REAL NOT NULL DEFAULT 0.5,
            max_total_pln REAL,
            departure_from TEXT,
            departure_to TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    for statement in (
        "ALTER TABLE watches ADD COLUMN departure_from TEXT",
        "ALTER TABLE watches ADD COLUMN departure_to TEXT",
    ):
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watch_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            watch_id INTEGER NOT NULL,
            offer_id_hash TEXT NOT NULL,
            sent_at_utc TEXT NOT NULL,
            UNIQUE(watch_id, offer_id_hash)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_kv (
            k TEXT PRIMARY KEY NOT NULL,
            v TEXT NOT NULL
        )
        """
    )
    conn.commit()


def save_offers(conn: sqlite3.Connection, offers: list[Offer]) -> None:
    now = datetime.utcnow().isoformat()
    for o in offers:
        conn.execute(
            """
            INSERT INTO offers (
                offer_id_hash, source_name, source_url, collected_at_utc, destination_country,
                destination_city_or_region, departure_airport, departure_date, return_date,
                trip_nights, board_type, hotel_name, hotel_stars, package_type,
                price_total_pln, price_per_person_pln, airport_transfer_cost_pln, baggage_cost_pln,
                local_daily_cost_pln, total_trip_cost_pln, people_supported, baggage_included,
                transfer_included, cancellation_terms, promo_tag, score, nominal_score,
                price_confidence, stale_data, verification
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                o.offer_id_hash,
                o.source_name,
                o.source_url,
                o.collected_at_utc.isoformat(),
                o.destination_country,
                o.destination_city_or_region,
                o.departure_airport,
                o.departure_date,
                o.return_date,
                o.trip_nights,
                o.board_type,
                o.hotel_name,
                o.hotel_stars,
                o.package_type,
                o.price_total_pln,
                o.price_per_person_pln,
                o.airport_transfer_cost_pln,
                o.baggage_cost_pln,
                o.local_daily_cost_pln,
                o.total_trip_cost_pln,
                o.people_supported,
                o.baggage_included,
                o.transfer_included,
                o.cancellation_terms,
                o.promo_tag,
                o.score,
                o.nominal_score,
                o.price_confidence,
                1 if o.stale_data else 0,
                o.verification,
            ),
        )
        conn.execute(
            """
            INSERT INTO offer_snapshots (offer_id_hash, snapshot_at_utc, price_per_person_pln)
            VALUES (?, ?, ?)
            """,
            (o.offer_id_hash, now, o.price_per_person_pln),
        )
    conn.commit()


def latest_price_by_hash(conn: sqlite3.Connection) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT s.offer_id_hash, s.price_per_person_pln
        FROM offer_snapshots s
        INNER JOIN (
            SELECT offer_id_hash, MAX(snapshot_at_utc) AS max_ts
            FROM offer_snapshots
            GROUP BY offer_id_hash
        ) latest
        ON s.offer_id_hash = latest.offer_id_hash AND s.snapshot_at_utc = latest.max_ts
        """
    ).fetchall()
    return {r["offer_id_hash"]: float(r["price_per_person_pln"]) for r in rows}


def add_watch(
    conn: sqlite3.Connection,
    destination_query: str,
    adults: int,
    children_ages: str,
    target_email: str,
    drop_ratio: float,
    max_total_pln: float | None,
    departure_from: str | None,
    departure_to: str | None,
) -> int:
    existing = conn.execute(
        """
        SELECT id FROM watches
        WHERE destination_query = ? AND adults = ? AND children_ages = ? AND target_email = ?
        LIMIT 1
        """,
        (destination_query, adults, children_ages, target_email),
    ).fetchone()
    if existing:
        watch_id = int(existing["id"])
        conn.execute(
            """
            UPDATE watches
            SET drop_ratio = ?, max_total_pln = ?, departure_from = ?, departure_to = ?, enabled = 1
            WHERE id = ?
            """,
            (drop_ratio, max_total_pln, departure_from, departure_to, watch_id),
        )
        conn.commit()
        return watch_id

    cur = conn.execute(
        """
        INSERT INTO watches (
            destination_query, adults, children_ages, target_email, drop_ratio, max_total_pln,
            departure_from, departure_to, enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (destination_query, adults, children_ages, target_email, drop_ratio, max_total_pln, departure_from, departure_to),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_enabled_watches(conn: sqlite3.Connection) -> list[WatchProfile]:
    rows = conn.execute(
        """
        SELECT
            id, destination_query, adults, children_ages, target_email, drop_ratio,
            max_total_pln, departure_from, departure_to, enabled
        FROM watches
        WHERE enabled = 1
        ORDER BY id ASC
        """
    ).fetchall()
    return [
        WatchProfile(
            id=int(r["id"]),
            destination_query=str(r["destination_query"]),
            adults=int(r["adults"]),
            children_ages=str(r["children_ages"]),
            target_email=str(r["target_email"]),
            drop_ratio=float(r["drop_ratio"]),
            max_total_pln=float(r["max_total_pln"]) if r["max_total_pln"] is not None else None,
            departure_from=str(r["departure_from"]) if r["departure_from"] is not None else None,
            departure_to=str(r["departure_to"]) if r["departure_to"] is not None else None,
            enabled=int(r["enabled"]),
        )
        for r in rows
    ]


def already_sent_watch_event(conn: sqlite3.Connection, watch_id: int, offer_id_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM watch_events WHERE watch_id = ? AND offer_id_hash = ?",
        (watch_id, offer_id_hash),
    ).fetchone()
    return row is not None


def save_watch_event(conn: sqlite3.Connection, watch_id: int, offer_id_hash: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO watch_events (watch_id, offer_id_hash, sent_at_utc)
        VALUES (?, ?, ?)
        """,
        (watch_id, offer_id_hash, datetime.utcnow().isoformat()),
    )
    conn.commit()


def get_meta_kv(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT v FROM meta_kv WHERE k = ?", (key,)).fetchone()
    return str(row["v"]) if row else None


def set_meta_kv(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO meta_kv (k, v) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


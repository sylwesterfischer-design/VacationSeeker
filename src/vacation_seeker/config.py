from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    db_path: str = os.getenv("VACATION_DB_PATH", "vacation_seeker.db")
    report_path: str = os.getenv("VACATION_REPORT_PATH", "output/report.html")
    refresh_minutes: int = int(os.getenv("VACATION_REFRESH_MINUTES", "60"))
    webhook_url: str | None = os.getenv("VACATION_WEBHOOK_URL")
    default_alert_email: str | None = os.getenv("VACATION_ALERT_EMAIL", "sylwester.fischer@gmail.com")
    # Alert „TOP OF THE TOP” (najtańszy real / nominal / najwyższy score) — ten sam SMTP co watch
    top_email_enabled: bool = os.getenv("VACATION_TOP_EMAIL_ENABLED", "true").lower() in {"1", "true", "yes"}
    top_email_to: str | None = os.getenv("VACATION_TOP_EMAIL") or None  # fallback: default_alert_email
    smtp_host: str | None = os.getenv("VACATION_SMTP_HOST")
    smtp_port: int = int(os.getenv("VACATION_SMTP_PORT", "587"))
    smtp_user: str | None = os.getenv("VACATION_SMTP_USER")
    smtp_password: str | None = os.getenv("VACATION_SMTP_PASSWORD")
    smtp_from: str | None = os.getenv("VACATION_SMTP_FROM")
    report_departure_from: str | None = os.getenv("VACATION_REPORT_DEPARTURE_FROM")
    report_departure_to: str | None = os.getenv("VACATION_REPORT_DEPARTURE_TO")
    report_destination: str | None = os.getenv("VACATION_REPORT_DESTINATION")
    report_return_from: str | None = os.getenv("VACATION_REPORT_RETURN_FROM")
    report_return_to: str | None = os.getenv("VACATION_REPORT_RETURN_TO")
    report_adults: int = int(os.getenv("VACATION_REPORT_ADULTS", "2"))
    report_children_ages: str = os.getenv("VACATION_REPORT_CHILDREN_AGES", "12,14")
    use_mock_fallback: bool = os.getenv("VACATION_USE_MOCK_FALLBACK", "true").lower() in {"1", "true", "yes"}
    validate_offer_links: bool = os.getenv("VACATION_VALIDATE_OFFER_LINKS", "true").lower() in {"1", "true", "yes"}
    validation_timeout_seconds: int = int(os.getenv("VACATION_VALIDATION_TIMEOUT_SECONDS", "12"))
    # Lotnisko wylotu dla linków fallback (Kayak / Google Flights), np. WAW, KRK
    origin_airport_iata: str = os.getenv("VACATION_ORIGIN_AIRPORT", "WAW").strip().upper() or "WAW"
    # Główne tabele raportu: tylko wylot w ciągu N miesięcy (reszta — sekcja „dalsze terminy”)
    report_horizon_months: int = max(1, min(24, int(os.getenv("VACATION_REPORT_HORIZON_MONTHS", "6"))))


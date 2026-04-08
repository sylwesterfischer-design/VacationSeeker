"""Kontekst uruchomienia run-once (observability: dry-run, verbose, postęp)."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# (etykieta fazy, bieżący krok, kroków w fazie) — np. do paska w GUI; wywoływane z wątku roboczego → UI po .after()
ProgressCallback = Callable[[str, int, int], None]


@dataclass
class RunContext:
    run_id: str
    argv: list[str]
    dry_run: bool = False
    verbose_items: bool = False
    no_progress: bool = False
    logger: logging.Logger | None = None
    progress_callback: ProgressCallback | None = None


@dataclass
class RunSummary:
    """Metryki końcowe jednego przebiegu (dla --dry-run i audytu)."""

    dry_run: bool = False
    collectors_total: int = 0
    collectors_failed: int = 0
    raw_offers_scanned: int = 0
    after_validation: int = 0
    offers_normalized: int = 0
    report_near_count: int = 0
    db_saved: bool = False
    html_written: bool = False
    webhook_sent: bool = False
    watch_emails_sent: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

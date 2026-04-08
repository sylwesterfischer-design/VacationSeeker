from __future__ import annotations

import time

from .config import Settings
from .pipeline import run_once


def run_scheduler(settings: Settings) -> None:
    while True:
        run_once(settings)
        time.sleep(max(1, settings.refresh_minutes) * 60)


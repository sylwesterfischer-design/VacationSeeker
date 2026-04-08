"""START/END run, log UTF-8, traceback przy wyjątkach."""
from __future__ import annotations

import logging
import shlex
import sys
import traceback
from pathlib import Path


def configure_run_logger(log_path: Path, run_id: str) -> logging.Logger:
    """Logger zapisujący do pliku UTF-8 (append). Osobny od printów na stdout."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger(f"vacation_seeker.run.{run_id[:8]}")
    lg.setLevel(logging.DEBUG)
    lg.handlers.clear()
    fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    lg.addHandler(fh)
    return lg


def log_start(lg: logging.Logger | None, run_id: str, argv: list[str]) -> None:
    try:
        argv_s = shlex.join(argv)
    except Exception:
        argv_s = repr(argv)
    line = f"START run_id={run_id} argv={argv_s}"
    if lg:
        lg.info(line)
    else:
        print(line, file=sys.stderr)


def log_end(lg: logging.Logger | None, run_id: str, status: str, exit_code: int, exc: BaseException | None = None) -> None:
    parts = [f"END run_id={run_id}", f"status={status}", f"code={exit_code}"]
    if exc is not None:
        parts.append(f"exception={type(exc).__name__}: {exc}")
    line = " ".join(parts)
    if lg:
        if exc is not None:
            lg.error(line)
            lg.error("Traceback:\n%s", "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        else:
            lg.info(line)
    else:
        print(line, file=sys.stderr)
        if exc is not None:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)

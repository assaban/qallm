"""Structured JSON logging configuration (QALLM-21 / US-27).

All log output goes to stdout in JSON format for easy Docker
log collection and CloudWatch ingestion.

Format per line:
    {"ts": "2025-03-01T12:00:00Z", "level": "INFO", "logger": "app.services.analysis_service", "msg": "...", ...}
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Include session_id if attached to the record via extra={}
        if hasattr(record, "session_id"):
            payload["session_id"] = record.session_id

        # Include exception info when present
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def setup_logging() -> None:
    """Configure root logger with JSON output to stdout.

    The log level is controlled by the ``LOG_LEVEL`` env var
    (default ``INFO``).
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any pre-existing handlers (e.g. uvicorn defaults)
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "httpcore", "httpx", "git.cmd"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

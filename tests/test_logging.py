"""Tests for structured JSON logging (QALLM-21 / US-27)."""

import json
import logging
import os

from qallm.analysis.log import JSONFormatter, setup_logging


def test_json_formatter_produces_valid_json():
    fmt = JSONFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    line = fmt.format(record)
    data = json.loads(line)
    assert data["level"] == "INFO"
    assert data["logger"] == "app.test"
    assert data["msg"] == "hello world"
    assert "ts" in data


def test_json_formatter_includes_session_id():
    fmt = JSONFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test",
        args=(),
        exc_info=None,
    )
    record.session_id = "abc-123"  # type: ignore[attr-defined]
    data = json.loads(fmt.format(record))
    assert data["session_id"] == "abc-123"


def test_json_formatter_includes_exception():
    fmt = JSONFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    data = json.loads(fmt.format(record))
    assert "exc" in data
    assert "ValueError: boom" in data["exc"]


def test_setup_logging_uses_log_level_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    setup_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_defaults_to_info():
    # Remove LOG_LEVEL if set
    os.environ.pop("LOG_LEVEL", None)
    setup_logging()
    assert logging.getLogger().level == logging.INFO


def test_log_output_is_json(capsys):
    setup_logging()
    logger = logging.getLogger("test.structured")
    logger.info("test message")
    captured = capsys.readouterr()
    # Should be valid JSON
    data = json.loads(captured.out.strip())
    assert data["msg"] == "test message"

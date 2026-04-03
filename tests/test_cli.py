from __future__ import annotations

import json
from pathlib import Path

import pytest

from qallm.cli import main


def test_cli_analyse_writes_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    src = tmp_path / "demo.py"
    src.write_text("print('hello')\n", encoding="utf-8")

    out = tmp_path / "report.json"

    monkeypatch.setattr(
        "sys.argv",
        ["qallm", "analyse", str(src), "--output", str(out)],
    )

    main()

    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "session_id" in payload
    assert "summary" in payload
    assert "findings" in payload


def test_cli_repair_requires_existing_analysis(monkeypatch: pytest.MonkeyPatch):
    fake_session = "does-not-exist"

    monkeypatch.setattr(
        "sys.argv",
        ["qallm", "repair", fake_session],
    )

    with pytest.raises(SystemExit):
        main()


def test_cli_verify_requires_existing_session(monkeypatch: pytest.MonkeyPatch):
    fake_session = "does-not-exist"

    monkeypatch.setattr(
        "sys.argv",
        ["qallm", "verify", fake_session],
    )

    with pytest.raises(SystemExit):
        main()
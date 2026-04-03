import json

from qallm.analysis.normalizers.base import NormalizationContext
from qallm.analysis.normalizers.trufflehog_normalizer import TruffleHogNormalizer


def _ctx(tmp_path) -> NormalizationContext:
    reports = tmp_path / "reports"
    reports.mkdir(exist_ok=True)
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    return NormalizationContext(session_id="test", workspace_dir=ws, reports_dir=reports)


def test_normalizes_trufflehog_jsonl(tmp_path):
    ctx = _ctx(tmp_path)

    finding = {
        "DetectorName": "AWS",
        "DetectorType": 2,
        "Verified": True,
        "SourceMetadata": {"Data": {"Filesystem": {"file": "./secrets.py"}}},
    }
    (ctx.reports_dir / "trufflehog.jsonl").write_text(json.dumps(finding) + "\n")

    raw = {
        "tool": "trufflehog",
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "artifact": "trufflehog.jsonl",
    }
    results = TruffleHogNormalizer().normalize(raw, ctx)

    assert len(results) == 1
    assert results[0].tool == "trufflehog"
    assert results[0].type == "SECRET"
    assert results[0].severity == "CRITICAL"  # verified → CRITICAL
    assert results[0].file == "secrets.py"
    assert "AWS" in results[0].message
    assert results[0].extra["verified"] is True


def test_unverified_secret_gets_high_severity(tmp_path):
    ctx = _ctx(tmp_path)

    finding = {
        "DetectorName": "GenericApiKey",
        "DetectorType": 55,
        "Verified": False,
        "SourceMetadata": {"Data": {"Filesystem": {"file": "./config.py"}}},
    }
    (ctx.reports_dir / "trufflehog.jsonl").write_text(json.dumps(finding) + "\n")

    raw = {
        "tool": "trufflehog",
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "artifact": "trufflehog.jsonl",
    }
    results = TruffleHogNormalizer().normalize(raw, ctx)

    assert len(results) == 1
    assert results[0].severity == "HIGH"  # unverified → HIGH
    assert results[0].extra["verified"] is False


def test_empty_artifact_returns_empty(tmp_path):
    ctx = _ctx(tmp_path)
    (ctx.reports_dir / "trufflehog.jsonl").write_text("")

    raw = {
        "tool": "trufflehog",
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "artifact": "trufflehog.jsonl",
    }
    results = TruffleHogNormalizer().normalize(raw, ctx)

    assert results == []


def test_missing_artifact_returns_empty(tmp_path):
    ctx = _ctx(tmp_path)

    raw = {
        "tool": "trufflehog",
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "artifact": "trufflehog.jsonl",
    }
    results = TruffleHogNormalizer().normalize(raw, ctx)

    assert results == []


def test_snippet_is_none_for_secret_redaction(tmp_path):
    """Secrets should never leak into code snippets."""
    ctx = _ctx(tmp_path)

    finding = {
        "DetectorName": "GitHubToken",
        "DetectorType": 3,
        "Verified": False,
        "SourceMetadata": {"Data": {"Filesystem": {"file": "./app.py"}}},
    }
    (ctx.reports_dir / "trufflehog.jsonl").write_text(json.dumps(finding) + "\n")

    raw = {
        "tool": "trufflehog",
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "artifact": "trufflehog.jsonl",
    }
    results = TruffleHogNormalizer().normalize(raw, ctx)

    assert results[0].code_snippet is None

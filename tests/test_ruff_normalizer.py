import json
from pathlib import Path

from qallm.analysis.normalizers.base import NormalizationContext
from qallm.analysis.normalizers.ruff_normalizer import RuffNormalizer


def _ctx(tmp_path: Path) -> NormalizationContext:
    ws = tmp_path / "ws"
    reports = tmp_path / "reports"
    ws.mkdir()
    reports.mkdir()
    return NormalizationContext(session_id="sid", workspace_dir=ws, reports_dir=reports)


def test_ruff_normalizer_extracts_findings_and_snippet(tmp_path: Path):
    workspace = tmp_path / "ws"
    reports = tmp_path / "reports"
    workspace.mkdir()
    reports.mkdir()

    src = workspace / "demo.py"
    src.write_text("import os\n\nprint('x')\n", encoding="utf-8")

    # Ruff JSON artifact (typical structure)
    ruff_items = [
        {
            "code": "F401",
            "message": "`os` imported but unused",
            "filename": str(src),
            "location": {"row": 1, "column": 1},
            "fixable": True,
        }
    ]
    (reports / "ruff.json").write_text(json.dumps(ruff_items), encoding="utf-8")

    raw = {"tool": "ruff", "artifact": "ruff.json"}
    ctx = NormalizationContext(session_id="sid", workspace_dir=workspace, reports_dir=reports)

    findings = RuffNormalizer().normalize(raw, ctx)

    assert len(findings) == 1
    f = findings[0]
    assert f.tool == "ruff"
    assert f.type == "SMELL"
    assert f.rule_id == "F401"
    assert f.line == 1
    assert f.code_snippet is not None
    assert "import os" in f.code_snippet


def test_ruff_empty_array(tmp_path: Path):
    ctx = _ctx(tmp_path)
    (ctx.reports_dir / "ruff.json").write_text("[]", encoding="utf-8")
    raw = {"tool": "ruff", "artifact": "ruff.json"}
    assert RuffNormalizer().normalize(raw, ctx) == []


def test_ruff_missing_artifact(tmp_path: Path):
    ctx = _ctx(tmp_path)
    raw = {"tool": "ruff", "artifact": "ruff.json"}
    assert RuffNormalizer().normalize(raw, ctx) == []


def test_ruff_severity_is_always_low(tmp_path: Path):
    ctx = _ctx(tmp_path)
    items = [
        {
            "code": "E501",
            "message": "Line too long",
            "filename": "demo.py",
            "location": {"row": 1, "column": 1},
        }
    ]
    (ctx.reports_dir / "ruff.json").write_text(json.dumps(items), encoding="utf-8")
    raw = {"tool": "ruff", "artifact": "ruff.json"}
    findings = RuffNormalizer().normalize(raw, ctx)
    assert len(findings) == 1
    assert findings[0].severity == "LOW"


def test_ruff_multiple_findings(tmp_path: Path):
    ctx = _ctx(tmp_path)
    items = [
        {
            "code": "F401",
            "message": "`os` imported but unused",
            "filename": "demo.py",
            "location": {"row": 1, "column": 1},
        },
        {
            "code": "E302",
            "message": "Expected 2 blank lines",
            "filename": "demo.py",
            "location": {"row": 3, "column": 1},
        },
    ]
    (ctx.reports_dir / "ruff.json").write_text(json.dumps(items), encoding="utf-8")
    raw = {"tool": "ruff", "artifact": "ruff.json"}
    findings = RuffNormalizer().normalize(raw, ctx)
    assert len(findings) == 2
    assert {f.rule_id for f in findings} == {"F401", "E302"}

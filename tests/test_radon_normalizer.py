import json
from pathlib import Path

import pytest

from qallm.analysis.normalizers.base import NormalizationContext
from qallm.analysis.normalizers.radon_normalizer import RadonNormalizer


def _ctx(tmp_path: Path) -> NormalizationContext:
    ws = tmp_path / "ws"
    reports = tmp_path / "reports"
    ws.mkdir()
    reports.mkdir()
    return NormalizationContext(session_id="sid", workspace_dir=ws, reports_dir=reports)


def test_radon_normalizer_extracts_findings_and_snippet(tmp_path: Path):
    workspace = tmp_path / "ws"
    reports = tmp_path / "reports"
    workspace.mkdir()
    reports.mkdir()

    src = workspace / "demo.py"
    src.write_text(
        "def f(x):\n    if x:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )

    # Radon cc -j output format: { "file.py": [ {..}, ... ] }
    radon_data = {
        str(src): [
            {"name": "f", "lineno": 1, "complexity": 12, "rank": "C"},
        ]
    }
    (reports / "radon_cc.json").write_text(json.dumps(radon_data), encoding="utf-8")

    raw = {"tool": "radon", "artifact": "radon_cc.json"}
    ctx = NormalizationContext(session_id="sid", workspace_dir=workspace, reports_dir=reports)

    findings = RadonNormalizer().normalize(raw, ctx)

    assert len(findings) == 1
    f = findings[0]
    assert f.tool == "radon"
    assert f.type == "COMPLEXITY"
    assert f.rule_id == "CC"
    assert f.line == 1
    assert f.code_snippet is not None
    assert "def f" in f.code_snippet
    assert f.extra["complexity"] == 12


@pytest.mark.parametrize(
    "cc,expected_sev",
    [
        (20, "HIGH"),
        (25, "HIGH"),
        (10, "MEDIUM"),
        (15, "MEDIUM"),
        (9, "LOW"),
        (1, "LOW"),
    ],
)
def test_radon_severity_thresholds(tmp_path: Path, cc: int, expected_sev: str):
    ctx = _ctx(tmp_path)
    radon_data = {"demo.py": [{"name": "f", "lineno": 1, "complexity": cc, "rank": "A"}]}
    (ctx.reports_dir / "radon_cc.json").write_text(json.dumps(radon_data), encoding="utf-8")
    raw = {"tool": "radon", "artifact": "radon_cc.json"}
    findings = RadonNormalizer().normalize(raw, ctx)
    assert len(findings) == 1
    assert findings[0].severity == expected_sev


def test_radon_multiple_functions(tmp_path: Path):
    ctx = _ctx(tmp_path)
    radon_data = {
        "demo.py": [
            {"name": "foo", "lineno": 1, "complexity": 5, "rank": "A"},
            {"name": "bar", "lineno": 10, "complexity": 22, "rank": "F"},
        ]
    }
    (ctx.reports_dir / "radon_cc.json").write_text(json.dumps(radon_data), encoding="utf-8")
    raw = {"tool": "radon", "artifact": "radon_cc.json"}
    findings = RadonNormalizer().normalize(raw, ctx)
    assert len(findings) == 2
    names = {f.extra["function"] for f in findings}
    assert names == {"foo", "bar"}


def test_radon_missing_artifact(tmp_path: Path):
    ctx = _ctx(tmp_path)
    raw = {"tool": "radon", "artifact": "radon_cc.json"}
    assert RadonNormalizer().normalize(raw, ctx) == []

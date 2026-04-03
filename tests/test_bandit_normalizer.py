import json
from pathlib import Path

from qallm.analysis.normalizers.bandit_normalizer import BanditNormalizer
from qallm.analysis.normalizers.base import NormalizationContext


def _ctx(tmp_path: Path) -> NormalizationContext:
    ws = tmp_path / "ws"
    reports = tmp_path / "reports"
    ws.mkdir()
    reports.mkdir()
    return NormalizationContext(session_id="sid", workspace_dir=ws, reports_dir=reports)


def test_bandit_normalizer_extracts_findings_and_snippet(tmp_path: Path):
    workspace = tmp_path / "ws"
    reports = tmp_path / "reports"
    workspace.mkdir()
    reports.mkdir()

    # Source file (snippet should be extracted from this)
    src = workspace / "demo.py"
    src.write_text(
        "import subprocess\nimport pickle\nx = 1\nsubprocess.call('ls', shell=True)\n",
        encoding="utf-8",
    )

    # Bandit JSON artifact
    bandit_data = {
        "results": [
            {
                "filename": str(src),
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "subprocess call with shell=True identified, security issue.",
                "test_id": "B602",
                "line_number": 4,
            }
        ]
    }
    (reports / "bandit.json").write_text(json.dumps(bandit_data), encoding="utf-8")

    raw = {"tool": "bandit", "artifact": "bandit.json"}
    ctx = NormalizationContext(session_id="sid", workspace_dir=workspace, reports_dir=reports)

    findings = BanditNormalizer().normalize(raw, ctx)

    assert len(findings) == 1
    f = findings[0]
    assert f.tool == "bandit"
    assert f.type == "SECURITY"
    assert f.severity == "HIGH"
    assert f.rule_id == "B602"
    assert f.file.endswith("demo.py")
    assert f.line == 4
    assert f.code_snippet is not None
    assert "shell=True" in f.code_snippet
    assert ">>" in f.code_snippet  # our snippet formatting


def test_bandit_empty_results(tmp_path: Path):
    ctx = _ctx(tmp_path)
    (ctx.reports_dir / "bandit.json").write_text(json.dumps({"results": []}), encoding="utf-8")
    raw = {"tool": "bandit", "artifact": "bandit.json"}
    assert BanditNormalizer().normalize(raw, ctx) == []


def test_bandit_missing_artifact(tmp_path: Path):
    ctx = _ctx(tmp_path)
    raw = {"tool": "bandit", "artifact": "bandit.json"}
    assert BanditNormalizer().normalize(raw, ctx) == []


def test_bandit_severity_mapping(tmp_path: Path):
    ctx = _ctx(tmp_path)
    bandit_data = {
        "results": [
            {
                "filename": "demo.py",
                "issue_severity": "MEDIUM",
                "issue_confidence": "MEDIUM",
                "issue_text": "Use of pickle detected.",
                "test_id": "B301",
                "line_number": 2,
            }
        ]
    }
    (ctx.reports_dir / "bandit.json").write_text(json.dumps(bandit_data), encoding="utf-8")
    raw = {"tool": "bandit", "artifact": "bandit.json"}
    findings = BanditNormalizer().normalize(raw, ctx)
    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"


def test_bandit_multiple_findings(tmp_path: Path):
    ctx = _ctx(tmp_path)
    bandit_data = {
        "results": [
            {
                "filename": "a.py",
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "Use of eval.",
                "test_id": "B307",
                "line_number": 1,
            },
            {
                "filename": "b.py",
                "issue_severity": "LOW",
                "issue_confidence": "LOW",
                "issue_text": "Use of assert.",
                "test_id": "B101",
                "line_number": 5,
            },
        ]
    }
    (ctx.reports_dir / "bandit.json").write_text(json.dumps(bandit_data), encoding="utf-8")
    raw = {"tool": "bandit", "artifact": "bandit.json"}
    findings = BanditNormalizer().normalize(raw, ctx)
    assert len(findings) == 2
    rule_ids = {f.rule_id for f in findings}
    assert rule_ids == {"B307", "B101"}

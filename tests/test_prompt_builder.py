"""Tests for repair prompt builder (QALLM-12)."""

from qallm.analysis.models import Finding
from qallm.repair.prompt_builder import SYSTEM_PROMPT, build_file_repair_prompt, build_repair_prompt


def _make_finding(**kwargs) -> Finding:
    defaults = dict(
        tool="bandit",
        type="SECURITY",
        severity="HIGH",
        file="app/main.py",
        line=10,
        message="Use of eval() detected",
        rule_id="B307",
    )
    defaults.update(kwargs)
    return Finding(**defaults)


def test_prompt_includes_finding_details():
    f = _make_finding()
    prompt = build_repair_prompt(f, "x = eval(input())", context_start_line=10)
    assert "bandit" in prompt
    assert "SECURITY" in prompt
    assert "HIGH" in prompt
    assert "B307" in prompt
    assert "eval()" in prompt
    assert "app/main.py" in prompt


def test_prompt_includes_code_context():
    ctx = "def foo():\n    eval('1+1')"
    prompt = build_repair_prompt(_make_finding(), ctx, context_start_line=5)
    assert "def foo():" in prompt
    assert "eval('1+1')" in prompt
    assert "line 5" in prompt


def test_prompt_includes_task_instruction():
    prompt = build_repair_prompt(_make_finding(), "x = 1", context_start_line=1)
    assert "Fix ONLY" in prompt
    assert "raw Python code" in prompt


def test_system_prompt_has_rules():
    assert "senior Python" in SYSTEM_PROMPT
    assert "no markdown" in SYSTEM_PROMPT.lower() or "no explanations" in SYSTEM_PROMPT.lower()


def test_file_repair_prompt_batches_all_findings():
    f1 = _make_finding(line=5, message="eval() detected", rule_id="B307")
    f2 = _make_finding(tool="ruff", type="SMELL", severity="LOW", line=1, message="unused import", rule_id="F401")

    source = "import os\n\ndef foo():\n    x = eval('1')\n    return x\n"
    prompt = build_file_repair_prompt("app/main.py", source, [f1, f2])

    assert "app/main.py" in prompt
    assert "eval() detected" in prompt
    assert "unused import" in prompt
    assert "import os" in prompt  # full file content included
    assert "COMPLETE corrected file" in prompt
    # Findings should be sorted by line
    idx_f401 = prompt.index("F401")
    idx_b307 = prompt.index("B307")
    assert idx_f401 < idx_b307  # line 1 before line 5


def test_file_repair_empty_findings():
    source = "x = 1\n"
    prompt = build_file_repair_prompt("app/main.py", source, [])
    assert "app/main.py" in prompt
    assert "x = 1" in prompt


def test_file_repair_none_line():
    f = _make_finding(line=None)
    prompt = build_file_repair_prompt("app/main.py", "x = 1\n", [f])
    assert "Use of eval() detected" in prompt


def test_file_repair_none_rule_id():
    f = _make_finding(rule_id=None)
    prompt = build_file_repair_prompt("app/main.py", "x = 1\n", [f])
    assert "Use of eval() detected" in prompt
    # rule_id parenthetical should not appear when rule_id is None
    assert "(None)" not in prompt


def test_system_prompt_key_rules():
    assert "os.environ" in SYSTEM_PROMPT
    assert "# noqa" in SYSTEM_PROMPT
    assert "COMPLETE" in SYSTEM_PROMPT
    assert "eval" in SYSTEM_PROMPT


def test_repair_prompt_none_line():
    f = _make_finding(line=None)
    prompt = build_repair_prompt(f, "x = eval(input())", context_start_line=1)
    assert "Use of eval() detected" in prompt
    assert "bandit" in prompt

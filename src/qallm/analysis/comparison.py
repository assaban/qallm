"""Generate comparison.json for each round.

Compares current round's metrics and test results against:
  1. Baseline (original code)
  2. Previous round
"""

from __future__ import annotations

import json
from typing import Any

from qallm.session.workspace import SessionService


def generate_comparison(session_id: str, round_num: int) -> dict[str, Any]:
    """Compare round_num against baseline and previous round.

    Reads paper_metrics.json and test_generation.json from each round.
    Returns and persists the comparison.
    """
    # Load current round metrics
    current_metrics = _load_metrics(session_id, round_num)
    current_tests = _load_test_summary(session_id, round_num)

    # Load baseline metrics (round 0)
    baseline_metrics = _load_metrics(session_id, 0)
    baseline_tests = _load_test_summary(session_id, 0)

    # Load previous round metrics
    prev_metrics = None
    prev_tests = None
    if round_num > 1:
        prev_metrics = _load_metrics(session_id, round_num - 1)
        prev_tests = _load_test_summary(session_id, round_num - 1)

    comparison: dict[str, Any] = {
        "round": round_num,
        "current": current_metrics,
    }

    # Compare vs baseline
    if baseline_metrics and current_metrics:
        comparison["vs_baseline"] = _compute_delta(baseline_metrics, current_metrics, baseline_tests, current_tests)

    # Compare vs previous
    if prev_metrics and current_metrics:
        comparison["vs_previous"] = _compute_delta(prev_metrics, current_metrics, prev_tests, current_tests)

    # Persist
    reports = SessionService.round_reports_dir(session_id, round_num)
    (reports / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    return comparison


def get_all_comparisons(session_id: str) -> list[dict[str, Any]]:
    """Load all comparison.json files across rounds."""
    comparisons = []
    base = SessionService.session_dir(session_id)
    for d in sorted(base.iterdir()) if base.exists() else []:
        if not d.is_dir() or not d.name.startswith("round_"):
            continue
        comp_path = d / "reports" / "comparison.json"
        if comp_path.exists():
            comparisons.append(json.loads(comp_path.read_text(encoding="utf-8")))
    return comparisons


def _load_metrics(session_id: str, round_num: int) -> dict[str, Any] | None:
    """Load paper_metrics.json for a given round."""
    if round_num <= 0:
        path = SessionService.baseline_reports_dir(session_id) / "paper_metrics.json"
    else:
        path = SessionService.round_reports_dir(session_id, round_num) / "paper_metrics.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _load_test_summary(session_id: str, round_num: int) -> dict[str, Any] | None:
    """Load test_generation.json for a given round."""
    if round_num <= 0:
        path = SessionService.baseline_reports_dir(session_id) / "test_generation.json"
    else:
        path = SessionService.round_reports_dir(session_id, round_num) / "test_generation.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _compute_delta(
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
    before_tests: dict[str, Any] | None,
    after_tests: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute metric deltas between two rounds."""
    delta: dict[str, Any] = {}

    for key in ["cs", "mi", "codu", "code", "loc", "cc"]:
        b = before_metrics.get(key, 0)
        a = after_metrics.get(key, 0)
        delta[f"{key}_before"] = b
        delta[f"{key}_after"] = a
        delta[f"{key}_delta"] = round(a - b, 2)

    # Test comparison
    if before_tests and after_tests:
        delta["bugs_before"] = before_tests.get("total_bugs", 0)
        delta["bugs_after"] = after_tests.get("total_bugs", 0)
        delta["bugs_delta"] = after_tests.get("total_bugs", 0) - before_tests.get("total_bugs", 0)

    # Findings count comparison
    before_findings = before_metrics.get("findings_count", before_metrics.get("cs", 0))
    after_findings = after_metrics.get("findings_count", after_metrics.get("cs", 0))
    delta["findings_before"] = before_findings
    delta["findings_after"] = after_findings
    delta["findings_delta"] = after_findings - before_findings

    return delta

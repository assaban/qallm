"""Repair service: LLM code repair (QALLM-12).

Flow:
  1. Load persisted findings from findings_unified.json
  2. Sort by severity, cap at MAX_REPAIR_ISSUES, skip SECRETs
  3. Group findings by file
  4. For each file:
     a. Read the full source file
     b. Build ONE prompt with all findings for that file
     c. Route to the strongest model needed (by highest severity in group)
     d. Call LLM, returns the complete corrected file
     e. Write corrected file back to workspace
     f. Generate unified diff (original vs corrected)
  5. Persist patches + token usage as repair_report.json

Note (Mohssin): This "batch per file" approach eliminates the overlapping-patch bug
where multiple line-slicing edits to the same file would corrupt it.
"""

from __future__ import annotations

import difflib
import json
import logging
from collections import defaultdict
from dataclasses import asdict

from qallm.analysis.models import Finding, Patch
from qallm.llm.base import LLMResponse, TokenTracker
from qallm.repair.config import settings
from qallm.repair.containers import build_llm_registry
from qallm.repair.prompt_builder import SYSTEM_PROMPT, build_file_repair_prompt
from qallm.session.workspace import SessionService

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

# Module-level registry (built once)
_llm_registry = build_llm_registry()


def _load_findings(session_id: str) -> list[Finding]:
    """Load persisted findings from the session's reports directory."""
    p = SessionService.reports_dir(session_id) / "findings_unified.json"
    if not p.exists():
        return []

    raw = json.loads(p.read_text(encoding="utf-8"))
    findings = []
    for r in raw:
        r.pop("id", None)
        r.pop("extra", None)
        try:
            findings.append(Finding(**r))
        except TypeError:
            continue
    return findings


def _make_file_diff(original: str, repaired: str, filename: str) -> str:
    """Generate a unified diff between original and repaired full file."""
    orig_lines = original.splitlines(keepends=True)
    fix_lines = repaired.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        fix_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(diff)


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text


def _group_by_file(findings: list[Finding]) -> dict[str, list[Finding]]:
    """Group findings by their file path."""
    groups: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        groups[f.file].append(f)
    return dict(groups)


def _highest_severity(findings: list[Finding]) -> str:
    """Return the highest severity among a list of findings."""
    best = "LOW"
    for f in findings:
        if SEVERITY_ORDER.get(f.severity, 99) < SEVERITY_ORDER.get(best, 99):
            best = f.severity
    return best


def list_models() -> dict:
    """Return available and configured LLM models for the dropdown."""
    return {
        "available": _llm_registry.list(),
        "configured": _llm_registry.list_configured(),
        "default": settings.LLM_DEFAULT_MODEL,
    }


# Keep old name for backward compat with routes
list_providers = list_models


def _resolve_model(severity: str, explicit_model: str | None) -> str:
    """Route to strong or fast model based on severity, unless user overrides."""
    if explicit_model:
        return explicit_model
    if severity in ("CRITICAL", "HIGH"):
        return settings.LLM_STRONG_MODEL
    return settings.LLM_FAST_MODEL


def run_repair(
    session_id: str,
    finding_ids: list[str] | None = None,
    max_issues: int | None = None,
    provider: str | None = None,
) -> dict:
    """Run LLM repair on findings for a session.

    Groups all findings by file and sends one LLM call per file with
    the complete source + all findings. The LLM returns the complete
    corrected file which is written back in full, no partial patches.
    """
    cap = max_issues or settings.MAX_REPAIR_ISSUES
    workspace = SessionService.workspace_active_dir(session_id)
    reports = SessionService.reports_dir(session_id)

    # 1. Load findings
    findings = _load_findings(session_id)
    if not findings:
        return {
            "patches": [],
            "token_usage": {},
            "repaired_count": 0,
            "provider_used": provider or "auto",
        }

    # 2. Filter / sort / cap
    if finding_ids:
        id_set = set(finding_ids)
        findings = [f for f in findings if f.id in id_set]
    else:
        findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 99))

    findings = findings[:cap]

    # Ignore secrets
    findings = [f for f in findings if f.type != "SECRET"]

    if not findings:
        return {
            "patches": [],
            "token_usage": {},
            "repaired_count": 0,
            "provider_used": provider or "auto",
        }

    # 3. Group by file
    file_groups = _group_by_file(findings)

    tracker = TokenTracker(budget=settings.TOKEN_BUDGET)
    patches: list[Patch] = []
    models_used: set[str] = set()

    # 4. One LLM call per file
    for filepath_rel, file_findings in file_groups.items():
        if tracker.remaining <= 0:
            logger.warning(
                "Token budget exhausted after %d calls",
                tracker.calls,
                extra={"session_id": session_id},
            )
            break

        filepath = workspace / filepath_rel

        # Read full original source
        if not filepath.exists():
            for ff in file_findings:
                patches.append(
                    Patch(
                        finding_id=ff.id,
                        description=f"File not found: {filepath_rel}",
                        unified_diff="",
                        error="file_not_found",
                    )
                )
            continue

        original_source = filepath.read_text(encoding="utf-8", errors="replace")

        # Route model based on highest severity in this file's findings
        top_severity = _highest_severity(file_findings)
        model_name = _resolve_model(top_severity, provider)
        try:
            llm = _llm_registry.pick(model_name)
        except ValueError:
            model_name = settings.LLM_DEFAULT_MODEL
            llm = _llm_registry.pick(model_name)

        models_used.add(model_name)

        # Build batched prompt
        user_prompt = build_file_repair_prompt(
            filepath=filepath_rel,
            source=original_source,
            findings=file_findings,
        )

        finding_summary = ", ".join(f"L{f.line}:{f.rule_id or f.tool}" for f in file_findings)
        logger.info(
            "Repairing %s (%d findings: %s) via %s",
            filepath_rel,
            len(file_findings),
            finding_summary,
            model_name,
            extra={"session_id": session_id},
        )

        resp: LLMResponse = llm.chat(SYSTEM_PROMPT, user_prompt, tracker)

        if resp.error:
            for ff in file_findings:
                patches.append(
                    Patch(
                        finding_id=ff.id,
                        description=f"LLM error: {resp.error}",
                        unified_diff="",
                        error=resp.error,
                        meta={"model": resp.model, "provider": resp.provider},
                    )
                )
            continue

        repaired_source = _strip_fences(resp.content)

        # Validate: repaired file should compile
        try:
            compile(repaired_source, filepath_rel, "exec")
        except SyntaxError as first_err:
            logger.warning(
                "LLM returned invalid Python for %s: %s — retrying once",
                filepath_rel,
                first_err,
                extra={"session_id": session_id},
            )
            # Retry once: feed the syntax error back so the LLM can self-correct
            retry_prompt = (
                user_prompt + f"\n\n## Your previous response had a Python syntax error:\n"
                f"  {first_err}\n"
                "Fix this syntax error. Ensure every 'try' block has a matching "
                "'except' or 'finally'. Return the COMPLETE corrected file."
            )
            resp = llm.chat(SYSTEM_PROMPT, retry_prompt, tracker)
            if not resp.error:
                repaired_source = _strip_fences(resp.content)
            try:
                compile(repaired_source, filepath_rel, "exec")
            except SyntaxError as e:
                logger.warning(
                    "LLM retry also returned invalid Python for %s: %s",
                    filepath_rel,
                    e,
                    extra={"session_id": session_id},
                )
                for ff in file_findings:
                    patches.append(
                        Patch(
                            finding_id=ff.id,
                            description=f"LLM returned invalid Python after retry: {e}",
                            unified_diff="",
                            error=f"syntax_error: {e}",
                            meta={"model": resp.model, "provider": resp.provider},
                        )
                    )
                continue

        # Generate diff
        diff = _make_file_diff(original_source, repaired_source, filepath_rel)

        if not diff.strip():
            for ff in file_findings:
                patches.append(
                    Patch(
                        finding_id=ff.id,
                        description="No change needed (possible false positive)",
                        unified_diff="",
                        meta={"model": resp.model, "provider": resp.provider},
                    )
                )
            continue

        # Write the complete corrected file
        filepath.write_text(repaired_source, encoding="utf-8")

        # One patch entry per file (covers all findings in that file)
        finding_ids_in_file = [ff.id for ff in file_findings]
        descriptions = [f"{ff.tool} {ff.rule_id or ''} L{ff.line}: {ff.message[:60]}" for ff in file_findings]
        patches.append(
            Patch(
                finding_id=",".join(finding_ids_in_file),
                description=f"Fixed {len(file_findings)} findings in {filepath_rel}: " + "; ".join(descriptions),
                unified_diff=diff,
                applied=True,
                meta={
                    "model": resp.model,
                    "provider": resp.provider,
                    "file": filepath_rel,
                    "findings_count": len(file_findings),
                },
            )
        )

    # 5. Persist
    provider_label = provider or ("auto: " + ", ".join(sorted(models_used)))
    report = {
        "session_id": session_id,
        "provider": provider_label,
        "patches": [asdict(p) for p in patches],
        "token_usage": tracker.to_dict(),
    }
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "repair_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    repaired_count = sum(1 for p in patches if p.applied)
    logger.info(
        "Repair complete: %d files patched, %d tokens used, models=%s",
        repaired_count,
        tracker.total_tokens,
        ", ".join(sorted(models_used)),
        extra={"session_id": session_id},
    )

    return {
        "patches": [asdict(p) for p in patches],
        "token_usage": tracker.to_dict(),
        "repaired_count": repaired_count,
        "provider_used": provider_label,
    }

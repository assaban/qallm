"""Build targeted prompts for LLM code repair (QALLM-12c).

Supports two modes:
  - Single finding + function context (legacy)
  - Batched: full file + all findings for that file (production)
"""

from __future__ import annotations

from qallm.analysis.models import Finding

SYSTEM_PROMPT = """\
You are a senior Python security and quality engineer.
Fix the code to address ALL the provided static analysis findings with minimal changes.

Rules:
1. Preserve external behavior unless a finding requires changing it for safety.
2. Do not introduce new dependencies unless explicitly allowed.
3. Prefer safe standard-library alternatives (e.g. ast.literal_eval over eval, \
subprocess with list args over shell=True).
4. Remove hardcoded secrets and replace with os.environ reads (never print secrets).
5. If a finding is a false positive or cannot be fixed safely, keep the \
original code unchanged and add a # noqa comment on the relevant line.
6. Keep changes small and localized, fix only the reported issues.
7. Return the COMPLETE corrected file. No explanations, no markdown fences, \
no partial snippets. Return the full file from first line to last line.
"""


def build_file_repair_prompt(
    filepath: str,
    source: str,
    findings: list[Finding],
) -> str:
    """Build a prompt that sends the full file with all its findings.

    This is the production approach: one LLM call per file, all findings
    listed together, full file returned. Eliminates overlapping patch bugs.
    """
    # Format findings list, ordered by line
    sorted_findings = sorted(findings, key=lambda f: f.line or 0)
    finding_lines = []
    for f in sorted_findings:
        line = f"- [{f.severity}][{f.tool}] line {f.line}: {f.message}"
        if f.rule_id:
            line += f" ({f.rule_id})"
        finding_lines.append(line)

    parts = [
        f"## File: {filepath}\n",
        "## Static analysis findings (ordered by line):\n",
        "\n".join(finding_lines),
        "\n## Current file content:\n",
        f"```python\n{source}\n```",
        "\n## Task",
        "Return the COMPLETE corrected file content that addresses ALL the "
        "findings listed above. Return the full file from the first import "
        "to the last line. Return raw Python code only, no markdown fences.",
    ]
    return "\n".join(parts)


def build_repair_prompt(
    finding: Finding,
    context: str,
    context_start_line: int,
) -> str:
    """Build the user prompt for a single finding (legacy, kept for compatibility and future research!)."""
    parts = [
        "## Static analysis finding\n",
        f"- **Tool:** {finding.tool}",
        f"- **Type:** {finding.type}",
        f"- **Severity:** {finding.severity}",
        f"- **File:** {finding.file}",
        f"- **Line:** {finding.line}",
        f"- **Rule:** {finding.rule_id or 'N/A'}",
        f"- **Message:** {finding.message}",
        f"\n## Code context (starting at line {context_start_line})\n",
        f"```python\n{context}\n```",
        "\n## Task",
        "Return the corrected version of the code above. "
        "Fix ONLY the issue described. Return raw Python code, no markdown.",
    ]
    return "\n".join(parts)

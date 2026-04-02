from __future__ import annotations

import json

from qallm.analysis.models import Finding

from .base import NormalizationContext, ToolNormalizer
from .util import get_rel_path, get_snippet


class BanditNormalizer(ToolNormalizer):
    tool_name = "bandit"

    def normalize(self, raw: dict, ctx: NormalizationContext) -> list[Finding]:
        artifact = raw.get("artifact") or "bandit.json"
        p = ctx.reports_dir / artifact
        if not p.exists():
            return []

        try:
            data = json.loads(p.read_text(encoding="utf-8") or "{}")
        except Exception:
            return []

        results = data.get("results") or []
        out: list[Finding] = []

        for r in results:
            filename_raw = str(r.get("filename") or "")
            line = r.get("line_number")

            # Normalize file path in a way snippet lookup can still find it
            file_rel = get_rel_path(ctx.workspace_dir, filename_raw)

            sev = (r.get("issue_severity") or "LOW").upper()
            conf = (r.get("issue_confidence") or "LOW").upper()
            msg = r.get("issue_text") or "Bandit finding"
            rule = r.get("test_id") or r.get("test_name")

            # Prefer snippet from workspace; fallback to bandit 'code' when snippet not possible
            snippet = get_snippet(ctx.workspace_dir, file_rel, int(line) if line else None, context=2)
            if not snippet:
                code = r.get("code")
                snippet = str(code) if code else None

            out.append(
                Finding(
                    tool="bandit",
                    type="SECURITY",
                    severity=sev if sev in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "LOW",
                    file=file_rel,
                    line=int(line) if line else None,
                    message=msg,
                    rule_id=str(rule) if rule else None,
                    code_snippet=snippet,
                    extra={"confidence": conf},
                )
            )

        return out

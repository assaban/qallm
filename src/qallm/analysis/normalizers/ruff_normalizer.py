from __future__ import annotations

import json

from qallm.analysis.models import Finding

from .base import NormalizationContext, ToolNormalizer
from .util import get_rel_path, get_snippet


class RuffNormalizer(ToolNormalizer):
    tool_name = "ruff"

    def normalize(self, raw: dict, ctx: NormalizationContext) -> list[Finding]:
        artifact = raw.get("artifact") or "ruff.json"
        p = ctx.reports_dir / artifact
        if not p.exists():
            return []

        try:
            items = json.loads(p.read_text(encoding="utf-8") or "[]")
        except Exception:
            return []

        out: list[Finding] = []
        for it in items:
            code = it.get("code") or it.get("rule") or it.get("name")
            msg = it.get("message") or "Ruff finding"

            loc = it.get("location") or {}
            row = loc.get("row")
            filename = it.get("filename") or ""
            file_rel = get_rel_path(ctx.workspace_dir, filename)

            snippet = get_snippet(ctx.workspace_dir, file_rel, int(row) if row else None, context=2)

            out.append(
                Finding(
                    tool="ruff",
                    type="SMELL",
                    severity="LOW",
                    file=file_rel,
                    line=int(row) if row else None,
                    message=msg,
                    rule_id=str(code) if code else None,
                    code_snippet=snippet,
                    extra={"fixable": bool(it.get("fix") or it.get("fixable") or False)},
                )
            )

        return out

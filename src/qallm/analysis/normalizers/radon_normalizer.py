from __future__ import annotations

import json

from qallm.analysis.models import Finding

from .base import NormalizationContext, ToolNormalizer
from .util import get_rel_path, get_snippet


class RadonNormalizer(ToolNormalizer):
    tool_name = "radon"

    def normalize(self, raw: dict, ctx: NormalizationContext) -> list[Finding]:
        artifact = raw.get("artifact") or "radon_cc.json"
        p = ctx.reports_dir / artifact
        if not p.exists():
            return []

        try:
            data = json.loads(p.read_text(encoding="utf-8") or "{}")
        except Exception:
            return []

        out: list[Finding] = []
        # radon cc -j returns: { "file.py": [ { "name":..., "lineno":..., "complexity":..., "rank":... }, ... ], ... }
        for file_name, items in (data or {}).items():
            file_rel = get_rel_path(ctx.workspace_dir, file_name)
            if not isinstance(items, list):
                continue

            for it in items:
                cc = int(it.get("complexity") or 0)
                lineno = int(it.get("lineno") or 1)
                name = it.get("name") or "function"
                rank = it.get("rank") or ""

                sev = _severity_from_cc(cc)
                msg = f"Cyclomatic complexity too high in {name} (CC={cc})"

                snippet = get_snippet(ctx.workspace_dir, file_rel, lineno, context=2)

                out.append(
                    Finding(
                        tool="radon",
                        type="COMPLEXITY",
                        severity=sev,
                        file=file_rel,
                        line=lineno,
                        message=msg,
                        rule_id="CC",
                        code_snippet=snippet,
                        extra={"function": name, "complexity": cc, "rank": rank},
                    )
                )

        return out


def _severity_from_cc(cc: int) -> str:
    # Simple thresholds (PoC): tweak later if needed
    if cc >= 20:
        return "HIGH"
    if cc >= 10:
        return "MEDIUM"
    return "LOW"

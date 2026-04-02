from __future__ import annotations

import json

from qallm.analysis.models import Finding

from .base import NormalizationContext, ToolNormalizer
from .util import get_rel_path


class TruffleHogNormalizer(ToolNormalizer):
    tool_name = "trufflehog"

    def normalize(self, raw: dict, ctx: NormalizationContext) -> list[Finding]:
        artifact = raw.get("artifact") or "trufflehog.jsonl"
        p = ctx.reports_dir / artifact
        if not p.exists():
            return []

        text = p.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            return []

        out: list[Finding] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                it = json.loads(line)
            except Exception:
                continue

            # Extract file path from nested SourceMetadata
            source = (it.get("SourceMetadata") or {}).get("Data") or {}
            fs = source.get("Filesystem") or {}
            file_raw = fs.get("file") or ""
            file_rel = get_rel_path(ctx.workspace_dir, file_raw)

            detector = it.get("DetectorName") or "Unknown"
            detector_type = it.get("DetectorType") or ""
            verified = bool(it.get("Verified"))

            status = "VERIFIED" if verified else "unverified"
            msg = f"Secret detected: {detector} ({status})"
            line_no = fs.get("line")
            line_int = int(line_no) if line_no else None

            out.append(
                Finding(
                    tool="trufflehog",
                    type="SECRET",
                    severity="CRITICAL" if verified else "HIGH",
                    file=file_rel,
                    line=line_int,
                    message=msg,
                    rule_id=str(detector_type) if detector_type else detector,
                    code_snippet=None,  # redact secrets from snippets
                    extra={
                        "detector": detector,
                        "verified": verified,
                    },
                )
            )

        return out

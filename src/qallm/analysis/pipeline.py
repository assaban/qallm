from __future__ import annotations

import json
import logging
from dataclasses import asdict

from qallm.analysis.analyzers.registry import AnalyzerRegistry
from qallm.analysis.models import Finding, Summary, VerificationReport
from qallm.analysis.normalizers.base import NormalizationContext
from qallm.analysis.normalizers.registry import NormalizerRegistry
from qallm.session.workspace import SessionService

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Orchestrates: run selected analyzers → normalize raw output → unified findings.
    """

    def __init__(
        self,
        analyzer_registry: AnalyzerRegistry,
        normalizer_registry: NormalizerRegistry,
    ):
        self.analyzers = analyzer_registry
        self.normalizers = normalizer_registry

    def run(
        self,
        session_id: str,
        selected_tools: list[str] | None = None,
        _skip_versioning: bool = False,
    ) -> list[Finding]:
        workspace = SessionService.workspace_active_dir(session_id)
        reports = SessionService.reports_dir(session_id)
        reports.mkdir(parents=True, exist_ok=True)

        if not workspace.exists() or not any(workspace.rglob("*.py")):
            raise RuntimeError("Active workspace has no Python files. Did you select files first?")

        # Phase 1: Run analyzers
        raw_results: list[dict] = []
        for analyzer in self.analyzers.pick(selected_tools):
            logger.info(
                "Running %s ...",
                analyzer.tool_name(),
                extra={"session_id": session_id},
            )
            result = analyzer.analyze(workspace, reports)
            raw_results.append(result.__dict__)

        # Persist raw index
        (reports / "analysis_raw_index.json").write_text(
            json.dumps(raw_results, indent=2),
            encoding="utf-8",
        )

        # Phase 2: Normalize → unified findings
        ctx = NormalizationContext(
            session_id=session_id,
            workspace_dir=workspace,
            reports_dir=reports,
        )

        findings: list[Finding] = []
        for raw in raw_results:
            norm = self.normalizers.get(raw.get("tool", ""))
            if norm:
                findings.extend(norm.normalize(raw, ctx))

        # Persist unified report
        findings_dicts = [f.to_dict() for f in findings]
        (reports / "findings_unified.json").write_text(
            json.dumps(findings_dicts, indent=2),
            encoding="utf-8",
        )

        # # Persist versioned copy for analysis history
        # existing = sorted(reports.glob("findings_round_*.json"))
        # round_num = len(existing) + 1
        # (reports / f"findings_round_{round_num:02d}.json").write_text(
        #     json.dumps(findings_dicts, indent=2),
        #     encoding="utf-8",
        # )

        # Persist versioned copy for round comparison
        if not _skip_versioning:
            existing_rounds = sorted(reports.glob("findings_round_*.json"))
        next_round = len(existing_rounds) + 1
        (reports / f"findings_round_{next_round:02d}.json").write_text(
            json.dumps([f.to_dict() for f in findings], indent=2),
            encoding="utf-8",
        )

        # Auto-compute paper metrics (CS, MI, CoDu, CoDe, LoC, CC)
        try:
            from qallm.analysis.paper_metrics import compute_paper_metrics

            compute_paper_metrics(session_id)
        except Exception as e:
            logger.warning("Paper metrics computation failed: %s", e)

        logger.info(
            "Analysis complete: %d findings",
            len(findings),
            extra={"session_id": session_id},
        )
        return findings

    def verify(
        self,
        session_id: str,
        selected_tools: list[str] | None = None,
    ) -> VerificationReport:
        """Re-run analysis post-repair and diff against pre-repair findings."""
        reports = SessionService.reports_dir(session_id)
        pre_repair_path = reports / "findings_unified.json"

        if not pre_repair_path.exists():
            raise RuntimeError("No pre-repair findings found. Run POST /api/analyse first.")

        # Load pre-repair findings and snapshot them before run() overwrites the file
        pre_dicts = json.loads(pre_repair_path.read_text(encoding="utf-8"))
        before_ids: set[str] = {f["id"] for f in pre_dicts}
        before_summary = AnalysisService.summarize_dicts(pre_dicts)

        logger.info(
            "Verification starting: %d pre-repair findings",
            len(before_ids),
            extra={"session_id": session_id},
        )

        # Re-use run() — it will overwrite findings_unified.json with post-repair results
        post_findings = self.run(session_id, selected_tools=selected_tools, _skip_versioning=True)

        # Persist post-repair findings under a separate name for traceability
        (reports / "findings_post_repair.json").write_text(
            json.dumps([f.to_dict() for f in post_findings], indent=2),
            encoding="utf-8",
        )

        after_ids: set[str] = {f.id for f in post_findings}
        resolved_ids = sorted(before_ids - after_ids)
        new_ids = sorted(after_ids - before_ids)

        report = VerificationReport(
            session_id=session_id,
            before=before_summary,
            after=Summary(**AnalysisService.summarize(post_findings)),
            resolved=len(resolved_ids),
            remaining=len(before_ids & after_ids),
            new=len(new_ids),
            resolved_ids=resolved_ids,
            new_ids=new_ids,
        )

        (reports / "verification_report.json").write_text(
            json.dumps(asdict(report), indent=2),
            encoding="utf-8",
        )

        logger.info(
            "Verification complete: %d resolved, %d remaining, %d new",
            report.resolved,
            report.remaining,
            report.new,
            extra={"session_id": session_id},
        )

        return report

    @staticmethod
    def summarize(findings: list[Finding]) -> dict:
        by_sev = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        by_type = {"SECURITY": 0, "SMELL": 0, "COMPLEXITY": 0, "SECRET": 0, "OTHER": 0}
        for f in findings:
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
            by_type[f.type] = by_type.get(f.type, 0) + 1
        return {
            "total": len(findings),
            "by_severity": by_sev,
            "by_type": by_type,
        }

    @staticmethod
    def summarize_dicts(findings: list[dict]) -> Summary:
        by_sev = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        by_type = {"SECURITY": 0, "SMELL": 0, "COMPLEXITY": 0, "SECRET": 0, "OTHER": 0}
        for f in findings:
            by_sev[f.get("severity", "LOW")] = by_sev.get(f.get("severity", "LOW"), 0) + 1
            by_type[f.get("type", "OTHER")] = by_type.get(f.get("type", "OTHER"), 0) + 1
        return Summary(total=len(findings), by_severity=by_sev, by_type=by_type)

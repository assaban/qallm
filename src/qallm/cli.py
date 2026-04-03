from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from qallm.analysis.containers import build_analyzer_registry, build_normalizer_registry
from qallm.analysis.pipeline import AnalysisService
from qallm.analysis.selection_service import SelectionService
from qallm.repair.repair_service import run_repair
from qallm.services.ingest_service import IngestService
from qallm.session.workspace import SessionService


def build_analysis_service() -> AnalysisService:
    return AnalysisService(
        build_analyzer_registry(),
        build_normalizer_registry(),
    )


def cmd_analyse(args) -> None:
    session_id = IngestService.create_session_from_input(args.input)

    files = SessionService.list_workspace_files(session_id)
    if not files:
        raise SystemExit(f"No analyzable files found in session {session_id}")

    SelectionService.apply_selection(session_id, files)

    service = build_analysis_service()
    findings = service.run(session_id, selected_tools=args.tools)
    summary = AnalysisService.summarize(findings)

    payload = {
        "session_id": session_id,
        "summary": summary,
        "findings": [finding.to_dict() for finding in findings],
    }

    output = json.dumps(payload, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output + "\n")
        print(f"[QALLM] Report written to {args.output}")
    else:
        print(output)


def cmd_repair(args) -> None:
    session_id = args.session_id

    if not SessionService.session_exists(session_id):
        raise SystemExit(f"Session not found: {session_id}")

    reports_dir = SessionService.reports_dir(session_id)
    findings_report = reports_dir / "findings_unified.json"
    if not findings_report.exists():
        raise SystemExit(
            f"No analysis report found for session {session_id}. Run `qallm analyse ...` first."
        )

    try:
        result = run_repair(
            session_id=session_id,
            finding_ids=args.finding_ids,
            max_issues=args.max_issues,
            provider=args.provider,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    payload = {"session_id": session_id, **result}
    output = json.dumps(payload, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output + "\n")
        print(f"[QALLM] Repair report written to {args.output}")
    else:
        print(output)


def cmd_verify(args) -> None:
    session_id = args.session_id

    if not SessionService.session_exists(session_id):
        raise SystemExit(f"Session not found: {session_id}")

    reports_dir = SessionService.reports_dir(session_id)
    findings_report = reports_dir / "findings_unified.json"
    repair_report = reports_dir / "repair_report.json"

    if not findings_report.exists():
        raise SystemExit(
            f"No analysis report found for session {session_id}. Run `qallm analyse ...` first."
        )

    if not repair_report.exists():
        raise SystemExit(
            f"No repair report found for session {session_id}. Run `qallm repair {session_id}` first."
        )

    service = build_analysis_service()

    try:
        report = service.verify(
            session_id=session_id,
            selected_tools=args.tools,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    payload = {"session_id": session_id, **asdict(report)}
    output = json.dumps(payload, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output + "\n")
        print(f"[QALLM] Verification report written to {args.output}")
    else:
        print(output)


def cmd_server(args) -> None:
    import uvicorn

    uvicorn.run(
        "qallm.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="qallm")
    sub = parser.add_subparsers(dest="command")

    p_analyse = sub.add_parser("analyse", help="Run static analysis")
    p_analyse.add_argument(
        "input",
        help="Input can be .ipynb, .py, .zip, a directory, or a GitHub URL",
    )
    p_analyse.add_argument(
        "--tools",
        nargs="*",
        help="Optional subset of analyzers: bandit ruff radon trufflehog",
    )
    p_analyse.add_argument("-o", "--output", help="Write JSON output to file")
    p_analyse.set_defaults(func=cmd_analyse)

    p_repair = sub.add_parser("repair", help="Run LLM-based repair on an analysed session")
    p_repair.add_argument("session_id", help="Existing session id")
    p_repair.add_argument(
        "--provider",
        help="Optional LLM provider/model override",
    )
    p_repair.add_argument(
        "--max-issues",
        type=int,
        help="Maximum number of findings to repair",
    )
    p_repair.add_argument(
        "--finding-ids",
        nargs="*",
        help="Optional specific finding ids to repair",
    )
    p_repair.add_argument("-o", "--output", help="Write JSON output to file")
    p_repair.set_defaults(func=cmd_repair)

    p_verify = sub.add_parser("verify", help="Verify repairs by re-running static analysis")
    p_verify.add_argument("session_id", help="Existing session id")
    p_verify.add_argument(
        "--tools",
        nargs="*",
        help="Optional subset of analyzers: bandit ruff radon trufflehog",
    )
    p_verify.add_argument("-o", "--output", help="Write JSON output to file")
    p_verify.set_defaults(func=cmd_verify)

    p_server = sub.add_parser("server", help="Start the web server")
    p_server.add_argument("--host", default="0.0.0.0")
    p_server.add_argument("--port", type=int, default=8000)
    p_server.add_argument("--reload", action="store_true")
    p_server.set_defaults(func=cmd_server)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

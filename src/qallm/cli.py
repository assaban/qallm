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
        raise SystemExit(f"No analysis report found for session {session_id}. Run `qallm analyse ...` first.")

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
        raise SystemExit(f"No analysis report found for session {session_id}. Run `qallm analyse ...` first.")

    if not repair_report.exists():
        raise SystemExit(f"No repair report found for session {session_id}. Run `qallm repair {session_id}` first.")

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


def cmd_generate_tests(args) -> None:
    """Run RL-guided test generation on input code."""
    from qallm.repair.containers import build_llm_registry
    from qallm.verification.extractor import extract_functions_from_source
    from qallm.verification.loop import TestGenerationLoop, save_session

    # Step 1: Ingest input and create session
    if args.session:
        session_id = args.input
        if not SessionService.session_exists(session_id):
            raise SystemExit(f"Session not found: {session_id}")
    else:
        session_id = IngestService.create_session_from_input(args.input)

    # Step 2: Find Python source files
    workspace = SessionService.workspace_active_dir(session_id)
    if not workspace.exists():
        workspace = SessionService.workspace_raw_dir(session_id)

    py_files = list(workspace.rglob("*.py"))
    if not py_files:
        raise SystemExit(f"No Python files found in session {session_id}")

    # Step 3: Pick LLM model
    registry = build_llm_registry()
    model_name = args.model or "gpt-4o-mini"
    try:
        llm = registry.pick(model_name)
    except ValueError:
        raise SystemExit(f"Model '{model_name}' not found. Available: {registry.list()}")

    if not llm.is_configured():
        raise SystemExit(f"Model '{model_name}' is not configured. Set the required API key environment variable.")

    # Step 4: Extract functions and run verification loop
    all_sessions = []
    total_functions = 0
    total_bugs = 0

    for py_file in py_files:
        source_code = py_file.read_text(encoding="utf-8")
        module_name = py_file.stem
        functions = extract_functions_from_source(source_code, filepath=str(py_file))

        if not functions:
            continue

        total_functions += len(functions)
        print(f"[QALLM] Found {len(functions)} function(s) in {py_file.name}", file=sys.stderr)

        for func in functions:
            print(f"[QALLM] Generating tests for {func.name} ({args.rounds} rounds)...", file=sys.stderr)

            loop = TestGenerationLoop(
                llm=llm,
                rounds=args.rounds,
                oracle=args.oracle,
                timeout=args.timeout,
            )
            tests_dir = SessionService.generated_tests_dir(session_id)
            session = loop.run(func, source_code, module_name=module_name, persist_dir=tests_dir)
            all_sessions.append(asdict(session))
            total_bugs += session.final_bugs

            # Persist per-function session
            reports_dir = SessionService.reports_dir(session_id)
            reports_dir.mkdir(parents=True, exist_ok=True)
            save_session(session, reports_dir / f"verification_{func.name}.json")

            print(
                f"[QALLM]   {func.name}: coverage={session.final_coverage}%, "
                f"bugs={session.final_bugs}, rounds={len(session.rounds)}",
                file=sys.stderr,
            )

    # Step 5: Output aggregate results
    payload = {
        "session_id": session_id,
        "model": model_name,
        "oracle": args.oracle,
        "rounds_per_function": args.rounds,
        "total_functions": total_functions,
        "total_bugs": total_bugs,
        "functions": all_sessions,
    }

    output_str = json.dumps(payload, indent=2, default=str)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output_str + "\n")
        print(f"[QALLM] Verification report written to {args.output}", file=sys.stderr)
    else:
        print(output_str)


def _prompt(question: str, default: str = "y") -> str:
    """Prompt user for input with a default value."""
    try:
        answer = input(question).strip()
        return answer if answer else default
    except (EOFError, KeyboardInterrupt):
        print("\n[QALLM] Cancelled.", file=sys.stderr)
        sys.exit(0)


def _confirm(question: str, default: bool = True) -> bool:
    """Ask a yes/no question. Returns True for yes."""
    hint = "Y/n" if default else "y/N"
    answer = _prompt(f"{question} [{hint}]: ", "y" if default else "n")
    return answer.lower() in ("y", "yes", "")


def _choose_model(registry, default: str = "gpt-4o-mini") -> str:
    """Let user pick an LLM model from the registry."""
    available = registry.list_configured()
    if not available:
        print("[QALLM] No LLM models configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.", file=sys.stderr)
        sys.exit(1)
    display = " / ".join(available)
    choice = _prompt(f"  Model? [{display}] (default: {default}): ", default)
    if choice not in available:
        print(f"[QALLM] '{choice}' not available. Using {default}.", file=sys.stderr)
        return default
    return choice


def cmd_full(args) -> None:
    """Run the full interactive pipeline: analyse → repair → generate tests."""
    from qallm.repair.containers import build_llm_registry
    from qallm.verification.extractor import extract_functions_from_source
    from qallm.verification.loop import TestGenerationLoop, save_session

    skip_prompts = args.yes

    # ── Ingest ────────────────────────────────────────────────────
    session_id = IngestService.create_session_from_input(args.input)
    files = SessionService.list_workspace_files(session_id)

    if not files:
        raise SystemExit(f"No analyzable files found in {args.input}")

    print(f"\n[QALLM] Ingested {args.input} → session {session_id}", file=sys.stderr)
    print(f"[QALLM] Found {len(files)} analyzable file(s)\n", file=sys.stderr)

    static_payload = {"summary": {"total": 0}, "findings": []}
    repair_payload = None
    registry = build_llm_registry()

    # ── Step 1: Static Analysis ───────────────────────────────────
    run_analysis = skip_prompts or _confirm("Step 1: Run static analysis?")

    if run_analysis:
        SelectionService.apply_selection(session_id, files)
        service = build_analysis_service()
        findings = service.run(session_id, selected_tools=args.tools)
        summary = AnalysisService.summarize(findings)
        static_payload = {
            "summary": summary,
            "findings": [f.to_dict() for f in findings],
        }

        by_sev = summary["by_severity"]
        parts = []
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            count = by_sev.get(sev, 0)
            if count > 0:
                parts.append(f"{count} {sev}")
        detail = ", ".join(parts) if parts else "none"
        print(f"  → {summary['total']} findings ({detail})\n", file=sys.stderr)
    else:
        print("  → Skipped\n", file=sys.stderr)
        # Still need files in active workspace for later steps
        SelectionService.apply_selection(session_id, files)

    # ── Step 2: Repair ────────────────────────────────────────────
    finding_count = static_payload["summary"].get("total", 0)

    if finding_count > 0:
        run_repair_step = skip_prompts or _confirm(f"Step 2: Run LLM repair on {finding_count} findings?")
    else:
        run_repair_step = False
        print("Step 2: Repair (skipped, no findings to repair)\n", file=sys.stderr)

    if run_repair_step:
        if skip_prompts:
            repair_model = args.model or "gpt-4o-mini"
            repair_rounds = args.repair_rounds or 1
        else:
            repair_model = _choose_model(registry, default=args.model or "gpt-4o-mini")
            repair_rounds_str = _prompt("  How many repair rounds? [1]: ", "1")
            repair_rounds = int(repair_rounds_str) if repair_rounds_str.isdigit() else 1

        print(f"  Repairing with {repair_model} ({repair_rounds} round(s))...", file=sys.stderr)

        for i in range(repair_rounds):
            result = run_repair(
                session_id=session_id,
                provider=repair_model,
            )
            repaired_count = result.get("repaired_count", 0)
            print(f"  → Round {i + 1}: {repaired_count} file(s) patched", file=sys.stderr)

        repair_payload = result
        print("", file=sys.stderr)
    else:
        if finding_count > 0:
            print("  → Skipped\n", file=sys.stderr)

    # ── Step 3: Generate Tests ────────────────────────────────────
    workspace = SessionService.workspace_active_dir(session_id)
    py_files = list(workspace.rglob("*.py"))

    if not py_files:
        print("Step 3: Generate tests (skipped, no Python files)\n", file=sys.stderr)
    else:
        # Count functions first
        all_functions = []
        for py_file in py_files:
            source_code = py_file.read_text(encoding="utf-8")
            funcs = extract_functions_from_source(source_code, filepath=str(py_file))
            for func in funcs:
                all_functions.append((py_file, func))

        func_names = [f.name for _, f in all_functions]
        func_display = ", ".join(func_names[:10])
        if len(func_names) > 10:
            func_display += f" ... and {len(func_names) - 10} more"

        print(f"[QALLM] Found {len(all_functions)} function(s): {func_display}", file=sys.stderr)
        run_gen = skip_prompts or _confirm(f"Step 3: Generate tests for {len(all_functions)} function(s)?")

        if run_gen:
            if skip_prompts:
                gen_model_name = args.model or "gpt-4o-mini"
                gen_rounds = args.rounds
            else:
                gen_model_name = _choose_model(registry, default=args.model or "gpt-4o-mini")
                gen_rounds_str = _prompt(f"  How many test generation rounds? [{args.rounds}]: ", str(args.rounds))
                gen_rounds = int(gen_rounds_str) if gen_rounds_str.isdigit() else args.rounds

            try:
                llm = registry.pick(gen_model_name)
            except ValueError:
                raise SystemExit(f"Model '{gen_model_name}' not found. Available: {registry.list()}")

            if not llm.is_configured():
                raise SystemExit(f"Model '{gen_model_name}' is not configured. Set the required API key.")

            print(f"  Generating with {gen_model_name} ({gen_rounds} round(s))...\n", file=sys.stderr)

            verification_sessions = []
            total_bugs = 0
            tests_dir = SessionService.generated_tests_dir(session_id)

            for py_file, func in all_functions:
                source_code = py_file.read_text(encoding="utf-8")
                module_name = py_file.stem

                loop = TestGenerationLoop(llm=llm, rounds=gen_rounds, timeout=args.timeout)
                session = loop.run(func, source_code, module_name=module_name, persist_dir=tests_dir)
                verification_sessions.append(asdict(session))
                total_bugs += session.final_bugs

                reports_dir = SessionService.reports_dir(session_id)
                reports_dir.mkdir(parents=True, exist_ok=True)
                save_session(session, reports_dir / f"verification_{func.name}.json")

                cov = session.final_coverage or 0
                print(
                    f"  → {func.name}: coverage={cov:.0f}%, bugs={session.final_bugs}, rounds={len(session.rounds)}",
                    file=sys.stderr,
                )

            print("", file=sys.stderr)
        else:
            verification_sessions = []
            total_bugs = 0
            gen_model_name = ""
            gen_rounds = 0
            print("  → Skipped\n", file=sys.stderr)

    # ── Report ────────────────────────────────────────────────────
    payload = {
        "session_id": session_id,
        "static_analysis": static_payload,
    }
    if repair_payload:
        payload["repair"] = {
            "repaired_count": repair_payload.get("repaired_count", 0),
            "provider": repair_payload.get("provider_used", ""),
        }
    if verification_sessions:
        payload["verification"] = {
            "model": gen_model_name,
            "rounds_per_function": gen_rounds,
            "total_functions": len(all_functions),
            "total_bugs": total_bugs,
            "functions": verification_sessions,
        }

    output_str = json.dumps(payload, indent=2, default=str)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output_str + "\n")
        print(f"[QALLM] Report written to {args.output}", file=sys.stderr)
    else:
        print(output_str)

    tests_path = SessionService.generated_tests_dir(session_id)
    if tests_path.exists():
        test_count = len(list(tests_path.glob("*.py")))
        print(f"[QALLM] Generated tests saved to {tests_path} ({test_count} files)", file=sys.stderr)

    print(f"[QALLM] Session: {session_id}", file=sys.stderr)


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

    # T-022: RL-guided test generation
    p_gen = sub.add_parser("generate-tests", help="Run RL-guided test generation")
    p_gen.add_argument(
        "input",
        help="Input (.ipynb, .py, dir, .zip, GitHub URL) or session ID with --session",
    )
    p_gen.add_argument("--session", action="store_true", help="Treat input as an existing session ID")
    p_gen.add_argument("--model", default=None, help="LLM model (default: gpt-4o-mini)")
    p_gen.add_argument("--rounds", type=int, default=5, help="Number of RL feedback rounds (default: 5)")
    p_gen.add_argument("--oracle", default="crash", help="Oracle type: crash, property, metamorphic")
    p_gen.add_argument("--timeout", type=int, default=60, help="Test execution timeout in seconds (default: 60)")
    p_gen.add_argument("-o", "--output", help="Write JSON output to file")
    p_gen.set_defaults(func=cmd_generate_tests)

    # T-022: Full pipeline (analyse + generate-tests)
    p_full = sub.add_parser("full", help="Run full interactive pipeline: analyse → repair → generate tests")
    p_full.add_argument(
        "input",
        help="Input can be .ipynb, .py, .zip, a directory, or a GitHub URL",
    )
    p_full.add_argument("--tools", nargs="*", help="Static analysis tools subset")
    p_full.add_argument("--model", default=None, help="LLM model (default: gpt-4o-mini)")
    p_full.add_argument("--rounds", type=int, default=5, help="Test generation rounds (default: 5)")
    p_full.add_argument("--repair-rounds", type=int, default=None, help="Repair rounds (default: 1)")
    p_full.add_argument("--timeout", type=int, default=60, help="Test execution timeout in seconds")
    p_full.add_argument("-y", "--yes", action="store_true", help="Skip all prompts, use defaults")
    p_full.add_argument("-o", "--output", help="Write JSON output to file")
    p_full.set_defaults(func=cmd_full)

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

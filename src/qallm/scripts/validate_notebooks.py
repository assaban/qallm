from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from qallm.analysis.containers import build_analyzer_registry, build_normalizer_registry
from qallm.analysis.pipeline import AnalysisService
from qallm.analysis.selection_service import SelectionService
from qallm.services.ingest_service import IngestService
from qallm.session.workspace import SessionService


@dataclass
class NotebookValidationRow:
    source_input: str
    session_id: str
    notebook_path: str
    extracted_python_exists: bool
    cell_map_exists: bool
    analyzable_files_count: int
    analysis_ran: bool
    findings_count: int
    error: str | None = None


def build_analysis_service() -> AnalysisService:
    return AnalysisService(
        build_analyzer_registry(),
        build_normalizer_registry(),
    )


def load_inputs_from_file(path: Path) -> list[str]:
    items: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        items.append(stripped)
    return items


def find_notebooks_in_session(session_id: str) -> list[str]:
    raw_dir = SessionService.workspace_raw_dir(session_id)
    if not raw_dir.exists():
        return []

    notebooks: list[str] = []
    for path in raw_dir.rglob("*.ipynb"):
        if path.is_file():
            notebooks.append(path.relative_to(raw_dir).as_posix())
    notebooks.sort()
    return notebooks


def expected_extracted_paths(session_id: str, notebook_rel_path: str) -> tuple[Path, Path]:
    raw_dir = SessionService.workspace_raw_dir(session_id)
    extracted_dir = raw_dir / "_extracted_notebooks"

    notebook_name = Path(notebook_rel_path).stem
    py_path = extracted_dir / f"{notebook_name}.extracted.py"
    cell_map_path = extracted_dir / f"{notebook_name}.cell_map.json"
    return py_path, cell_map_path


def run_analysis_for_session(session_id: str, tools: list[str] | None) -> tuple[bool, int, str | None]:
    files = SessionService.list_workspace_files(session_id)
    if not files:
        return False, 0, "no_analyzable_files"

    try:
        SelectionService.apply_selection(session_id, files)
        service = build_analysis_service()
        findings = service.run(session_id, selected_tools=tools)
        return True, len(findings), None
    except Exception as exc:
        return False, 0, str(exc)


def validate_one_input(source_input: str, tools: list[str] | None) -> list[NotebookValidationRow]:
    try:
        session_id = IngestService.create_session_from_input(source_input)
    except Exception as exc:
        return [
            NotebookValidationRow(
                source_input=source_input,
                session_id="",
                notebook_path="",
                extracted_python_exists=False,
                cell_map_exists=False,
                analyzable_files_count=0,
                analysis_ran=False,
                findings_count=0,
                error=f"ingest_failed: {exc}",
            )
        ]

    notebooks = find_notebooks_in_session(session_id)
    analyzable_files = SessionService.list_workspace_files(session_id)

    analysis_ran, findings_count, analysis_error = run_analysis_for_session(session_id, tools)

    if not notebooks:
        return [
            NotebookValidationRow(
                source_input=source_input,
                session_id=session_id,
                notebook_path="",
                extracted_python_exists=False,
                cell_map_exists=False,
                analyzable_files_count=len(analyzable_files),
                analysis_ran=analysis_ran,
                findings_count=findings_count,
                error=analysis_error or "no_notebooks_found",
            )
        ]

    rows: list[NotebookValidationRow] = []
    for notebook_rel in notebooks:
        extracted_py, cell_map = expected_extracted_paths(session_id, notebook_rel)
        rows.append(
            NotebookValidationRow(
                source_input=source_input,
                session_id=session_id,
                notebook_path=notebook_rel,
                extracted_python_exists=extracted_py.exists(),
                cell_map_exists=cell_map.exists(),
                analyzable_files_count=len(analyzable_files),
                analysis_ran=analysis_ran,
                findings_count=findings_count,
                error=analysis_error,
            )
        )
    return rows


def summarize(rows: list[NotebookValidationRow]) -> dict[str, Any]:
    total_rows = len(rows)
    notebook_rows = [r for r in rows if r.notebook_path]
    ingest_failures = [r for r in rows if r.error and r.error.startswith("ingest_failed")]
    no_notebooks = [r for r in rows if r.error == "no_notebooks_found"]

    extracted_ok = sum(1 for r in notebook_rows if r.extracted_python_exists)
    cell_map_ok = sum(1 for r in notebook_rows if r.cell_map_exists)
    analysis_ok = sum(1 for r in rows if r.analysis_ran)

    error_buckets: dict[str, int] = {}
    for r in rows:
        if not r.error:
            continue
        error_buckets[r.error] = error_buckets.get(r.error, 0) + 1

    return {
        "total_result_rows": total_rows,
        "total_notebook_rows": len(notebook_rows),
        "ingest_failures": len(ingest_failures),
        "inputs_with_no_notebooks": len(no_notebooks),
        "extracted_python_success_count": extracted_ok,
        "cell_map_success_count": cell_map_ok,
        "analysis_success_count": analysis_ok,
        "extracted_python_success_rate": (
            round(extracted_ok / len(notebook_rows), 4) if notebook_rows else 0.0
        ),
        "cell_map_success_rate": (
            round(cell_map_ok / len(notebook_rows), 4) if notebook_rows else 0.0
        ),
        "analysis_success_rate": (
            round(analysis_ok / len(rows), 4) if rows else 0.0
        ),
        "error_buckets": error_buckets,
    }


def write_csv(rows: list[NotebookValidationRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_input",
                "session_id",
                "notebook_path",
                "extracted_python_exists",
                "cell_map_exists",
                "analyzable_files_count",
                "analysis_ran",
                "findings_count",
                "error",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(rows: list[NotebookValidationRow], summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "rows": [asdict(r) for r in rows],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="qallm-validate-notebooks",
        description="T-011 validation runner for notebook ingestion and analysis",
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Notebook paths, directories, ZIPs, or GitHub repo URLs",
    )
    parser.add_argument(
        "--input-file",
        help="Text file with one input per line",
    )
    parser.add_argument(
        "--tools",
        nargs="*",
        help="Optional subset of analyzers: bandit ruff radon trufflehog",
    )
    parser.add_argument(
        "--json-out",
        default="validation_results/notebook_validation_summary.json",
        help="Path to write JSON summary",
    )
    parser.add_argument(
        "--csv-out",
        default="validation_results/notebook_validation_rows.csv",
        help="Path to write CSV rows",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    all_inputs: list[str] = list(args.inputs)
    if args.input_file:
        all_inputs.extend(load_inputs_from_file(Path(args.input_file)))

    # preserve order while removing duplicates
    deduped_inputs = list(dict.fromkeys(all_inputs))

    if not deduped_inputs:
        print("No inputs provided.", file=sys.stderr)
        raise SystemExit(1)

    all_rows: list[NotebookValidationRow] = []
    for source_input in deduped_inputs:
        print(f"[QALLM] Validating: {source_input}")
        rows = validate_one_input(source_input, args.tools)
        all_rows.extend(rows)

    summary = summarize(all_rows)

    json_out = Path(args.json_out)
    csv_out = Path(args.csv_out)

    write_json(all_rows, summary, json_out)
    write_csv(all_rows, csv_out)

    print("\n[QALLM] Validation complete")
    print(json.dumps(summary, indent=2))
    print(f"[QALLM] JSON summary: {json_out}")
    print(f"[QALLM] CSV rows: {csv_out}")


if __name__ == "__main__":
    main()
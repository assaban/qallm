# T-022: Pipeline Integration Design

## Overview

T-022 wires the RL verification module (T-014 through T-017) into the user
facing interfaces: CLI and Web API. After this, a user can run the complete
verification pipeline with a single command or API call, without writing any
Python scripts.

## User Experience

### CLI: `qallm generate-tests`

```bash
# Run RL test generation on a notebook
qallm generate-tests path/to/notebook.ipynb

# Control the model and rounds
qallm generate-tests my_code.py --model gpt-4o-mini --rounds 5

# Save results to file
qallm generate-tests my_code.py --output results.json

# Run the full pipeline: analyse + generate-tests combined
qallm full my_code.py --rounds 3
```

### Web API: `POST /api/verification/run`

```json
{
    "session_id": "abc-123",
    "model": "gpt-4o-mini",
    "rounds": 5,
    "oracle": "crash",
    "timeout": 60
}
```

Response: `VerificationSession` JSON with all rounds, learning curve,
and aggregate metrics.

## Design Decisions

### 1. `generate-tests` as a new CLI command (not overriding `verify`)

The existing `verify` command runs static analysis re-check after repair.
That's a different operation. Adding `generate-tests` keeps both available
and makes the intent clear from the command name.

### 2. Direct input (not session-id only)

Like `qallm analyse`, the `generate-tests` command accepts input directly
(notebook, file, directory, URL). It creates a session internally, extracts
functions, and runs the loop. This removes the need for the user to manually
manage session IDs for simple cases.

For advanced use (e.g., running generation on an already analysed session),
the `--session` flag accepts an existing session ID.

### 3. `full` command chains analyse + generate-tests

The most common use case is: "give me everything you've got on this code."
The `full` command runs static analysis first, then RL verification, and
outputs a combined report. This maps to the RQ2 evaluation design where
static-only is compared against static+RL.

### 4. Model selection from existing registry

The `--model` flag picks from the existing LLM registry (built in
`repair/containers.py`). No new configuration needed. Default is
`gpt-4o-mini` (fast, cheap, good for development); `gpt-5-mini` or
`claude-haiku-4-5-20251001` for stronger results.

## Data Flow

```
CLI: qallm generate-tests my_code.py --rounds 5

  1. IngestService.create_session_from_input("my_code.py")
     → session_id

  2. Read source from session workspace
     → source_code: str

  3. extract_functions_from_source(source_code)
     → functions: list[FunctionInfo]

  4. For each function:
     VerificationLoop(llm, rounds=5).run(func, source_code)
     → VerificationSession

  5. Aggregate results
     → combined JSON output
```

## Module Changes

| File | Change | Type |
|------|--------|------|
| `cli.py` | Add `generate-tests` and `full` subcommands | Modified |
| `api/verification_routes.py` | New API router for `/api/verification/*` | New |
| `main.py` | Register verification router | Modified |
| `verification/__init__.py` | Export key classes for convenience | Modified |

## Mapping to Thesis

| Thesis element | Implementation |
|---------------|---------------|
| "Single command" (Expected Results, item 1) | `qallm generate-tests <input>` |
| "Jupyter frontend quality check trigger" (Section 3.4) | Foundation for T-023 (uses same API endpoint) |
| RQ2 "controlled comparison" (Section 4.2) | `qallm full` produces both static and RL results for the same code |
| "Compatible with Volentir et al. framework" (Section 3.4) | JSON output structure |

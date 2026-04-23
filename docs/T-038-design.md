# T-038: Workspace Restructure (Round-Based Layout)

## Problem

The current workspace layout scatters data across multiple directories:
`workspace_raw/`, `workspace/`, `repair_history/`, `generated_tests/`, `reports/`.
This makes it difficult to:

1. Compare results across rounds
2. Understand which code version produced which test results
3. Generate the paper's Table 5/6 data cleanly
4. Tell the thesis story: baseline → round 1 → round 2 → ...

## New Layout

```
data/<session-id>/
├── original/                     # Uploaded code, never modified
├── baseline_tests/               # Tests generated on original code
│   ├── generated_tests/
│   └── reports/
│       ├── test_generation.json
│       └── paper_metrics.json
├── round_01/
│   ├── repaired_code/            # Code after repair round 1
│   ├── generated_tests/
│   └── reports/
│       ├── findings.json
│       ├── repair_report.json
│       ├── test_generation.json
│       ├── paper_metrics.json
│       └── comparison.json       # Delta vs baseline + previous
├── round_02/
│   ├── repaired_code/
│   ├── generated_tests/
│   └── reports/
│       ├── findings.json
│       ├── repair_report.json
│       ├── test_generation.json
│       ├── paper_metrics.json
│       └── comparison.json
└── session.json
```

## Pipeline Flow

```
1. Upload → store in original/
2. Baseline:
     analyse(original/) → baseline paper metrics
     generate_tests(original/) → baseline_tests/
3. Round 1:
     repair(original/, baseline findings) → round_01/repaired_code/
     analyse(round_01/repaired_code/) → round_01/reports/findings.json
     generate_tests(round_01/repaired_code/) → round_01/generated_tests/
     compare(round_01, baseline) → round_01/reports/comparison.json
4. Round N:
     repair(round_N-1/repaired_code/, previous findings) → round_N/repaired_code/
     analyse → generate_tests → compare
```

## Key Invariants

1. `original/` is NEVER modified after ingest
2. Each round is self-contained: code + tests + reports live together
3. `comparison.json` always compares against both baseline and previous round
4. The "current" code is always the latest round's `repaired_code/`
5. Baseline tests provide the reference point for all comparisons

## Module Changes

| Module | Change |
|--------|--------|
| `session/workspace.py` | Rewrite: new directory helpers, round management |
| `analysis/selection_service.py` | Read from round dir instead of workspace |
| `analysis/pipeline.py` | Save to round reports |
| `repair/repair_service.py` | Write to round_NN/repaired_code/ |
| `verification/loop.py` | Save to round_NN/generated_tests/ |
| `analysis/paper_metrics.py` | Save to round_NN/reports/ |
| `analysis/comparison.py` | NEW: generate comparison.json |
| `api/session_routes.py` | Updated paths |
| `cli.py` | Updated orchestration |

## Mapping to Paper

| Paper element | Workspace location |
|--------------|-------------------|
| Table 5 baseline row | `original/` metrics + `baseline_tests/` |
| Table 5 LLM row | `round_NN/reports/paper_metrics.json` |
| Table 6 Step 0 | `baseline_tests/reports/paper_metrics.json` |
| Table 6 Step N | `round_NN/reports/paper_metrics.json` |
| Table 7 (pairwise) | Computed from `comparison.json` across rounds |

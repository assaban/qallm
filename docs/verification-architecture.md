# Verification Module Architecture

## Position in QALLM

The verification module (`qallm/verification/`) implements the **Test Case Agent**
from the Agentic Workflow proposed by Islam & Zhao [6]. Within the QALLM tool,
it sits alongside two other operations:

| Operation | Module | Status |
|-----------|--------|--------|
| Analyse | `qallm/analysis/` | Working (from P4) |
| Repair | `qallm/repair/` | Working (from P4) |
| **Verify** | **`qallm/verification/`** | **Core thesis contribution** |

Users can run any combination of these three operations, in any order,
through CLI, Web UI, or Jupyter trigger.

## Session Folder Structure

Each session has a self-contained directory with the following layout:

```
data/<session-id>/
├── workspace_raw/          # original uploaded/cloned files (never modified)
├── workspace/              # current active version (may be repaired)
├── repair_history/         # snapshots before each repair round
│   ├── round_01/           # workspace state before round 1 wrote changes
│   ├── round_02/           # workspace state before round 2 wrote changes
│   └── ...
├── generated_tests/        # persisted test code from each generation round
│   ├── compute_mean_round_01.py
│   ├── compute_mean_round_02.py
│   └── dangerous_hypothesis.py    # Hypothesis baseline output
├── reports/                # JSON reports from analysis and verification
│   ├── findings_unified.json
│   ├── repair_report.json
│   ├── verification_compute_mean.json
│   └── verification_aggregate.json
└── session.json            # session metadata (source type, config)
```

Key invariants:
- `workspace_raw` is never modified after initial ingest
- `workspace` always holds the "current" version (original or latest repair)
- `repair_history/round_NN` captures the workspace state BEFORE round N modified it
- Users can restore any version via `SessionService.restore_repair_round()`

## Module Map

```
qallm/verification/
├── models.py       Data classes for all inputs and outputs
├── extractor.py    AST-based function extraction from Python source
├── prompts.py      System prompt, oracle prompts, feedback prompt builder
├── generator.py    LLM-based test code generation (calls prompts + LLM)
├── executor.py     Subprocess pytest runner with coverage capture
├── reward.py       Reward function scoring execution results
└── loop.py         RL feedback loop orchestrating the full cycle
```

Each module has a single responsibility. Dependencies flow downward:

```
loop.py
├── generator.py
│   ├── prompts.py
│   │   └── models.py
│   └── models.py
├── executor.py
│   └── models.py
├── reward.py
│   └── models.py
└── prompts.py (feedback prompt)
    └── models.py
```

No module imports from `loop.py`, so each component can be used
independently for testing, debugging, or alternative orchestration.

## Complete Pipeline Flow

The full verification pipeline processes a single function through
multiple rounds of test generation and execution:

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                    QALLM Verification Pipeline                  │
 │                                                                 │
 │  INPUT                                                          │
 │  ─────                                                          │
 │  Python source file (.py or extracted from .ipynb)              │
 │          │                                                      │
 │          ▼                                                      │
 │  ┌───────────────┐                                              │
 │  │   Extractor    │  Parse AST, extract public functions        │
 │  │ (extractor.py) │  with name, source, docstring, args         │
 │  └───────┬───────┘                                              │
 │          │ list[FunctionInfo]                                    │
 │          ▼                                                      │
 │  ┌─────────────────────────────────────────────────────────┐    │
 │  │              RL LOOP (loop.py) — per function            │    │
 │  │                                                          │    │
 │  │   Round 1:  oracle prompt ──┐                            │    │
 │  │   Round 2+: feedback prompt ┤                            │    │
 │  │                              ▼                           │    │
 │  │                     ┌──────────────┐                     │    │
 │  │                     │  Generator   │  LLM API call       │    │
 │  │                     │(generator.py)│  Returns test code   │    │
 │  │                     └──────┬───────┘                     │    │
 │  │                            │ GeneratedTest               │    │
 │  │                            ▼                             │    │
 │  │                     ┌──────────────┐                     │    │
 │  │                     │   Executor   │  Subprocess pytest   │    │
 │  │                     │ (executor.py)│  + coverage.py       │    │
 │  │                     └──────┬───────┘                     │    │
 │  │                            │ ExecutionResult             │    │
 │  │                            ▼                             │    │
 │  │                     ┌──────────────┐                     │    │
 │  │                     │   Reward     │  Score the batch     │    │
 │  │                     │ (reward.py)  │  Scalar + breakdown  │    │
 │  │                     └──────┬───────┘                     │    │
 │  │                            │ RewardBreakdown             │    │
 │  │                            ▼                             │    │
 │  │                     ┌──────────────┐                     │    │
 │  │                     │  Feedback    │  Build prompt with   │    │
 │  │                     │ (prompts.py) │  coverage gaps,      │    │
 │  │                     │              │  reward signal,      │    │
 │  │                     │              │  improvement goals   │    │
 │  │                     └──────┬───────┘                     │    │
 │  │                            │ str (next round's prompt)   │    │
 │  │                            └────── loops back to top ──┘ │    │
 │  │                                                          │    │
 │  │   Output: TestGenerationSession                            │    │
 │  │     rounds[], learning_curve, final_coverage, final_bugs │    │
 │  └──────────────────────────────────────────────────────────┘    │
 │                                                                 │
 │  OUTPUT                                                         │
 │  ──────                                                         │
 │  TestGenerationSession (JSON) per function                        │
 │    ├── Per round: test code, execution result, reward breakdown │
 │    ├── Learning curve: cumulative reward over rounds             │
 │    └── Aggregate: best coverage, total bugs, token usage        │
 │                                                                 │
 └─────────────────────────────────────────────────────────────────┘
```

## The Feedback Mechanism (the "RL" in "RL-guided")

The iterative improvement works through **prompt-based feedback**, not
gradient-based optimization. Each round, the feedback prompt builder
translates quantitative execution results into natural language instructions:

```
 Round N execution results          Feedback prompt for Round N+1
 ──────────────────────             ────────────────────────────
 coverage: 45%              →       "Coverage is 45%. Generate tests
                                     that exercise UNTESTED branches."

 3 tests passed,                    "3 tests were redundant (no new
 0 bugs, 0 coverage gain    →       coverage, no bugs). Replace them
                                     with different edge cases."

 1 test errored              →      "Fix invalid tests. Make sure all
 (ImportError)                       imports are correct."

 0 bugs found                →      "No bugs yet. Try empty inputs,
                                     None, overflow, type mismatches."

 reward: -0.6                →      "Your score was -0.6. Focus on
                                     finding bugs and covering new paths."
```

This approach has two advantages over traditional RL:

1. **No model training required.** The LLM's weights are fixed. Improvement
   comes from richer context, not parameter updates. This keeps the thesis
   within SE scope (see proposal Section 6).

2. **Interpretable feedback.** Every instruction in the prompt can be traced
   to a specific gap in the previous round's results. There is no black box
   reward shaping.

## Reward Function Internals

The reward function (T-016) converts execution metrics into a single scalar:

```
                 ExecutionResult
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  Bugs    │ │ Coverage │ │ Validity │
    │  found?  │ │  gained? │ │  errors? │
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │
    +1.0 × N     +0.5 × Δ%   −0.5 × N
         │            │            │
         └────────────┼────────────┘
                      │
                      ▼
              ┌──────────────┐
              │  Redundancy  │  If bugs==0 AND Δ%==0:
              │   check      │  passed tests are redundant
              └──────┬───────┘
                     │
                −0.2 × N (if redundant)
                     │
                     ▼
               Total Reward
```

Coverage gain is measured against the **best coverage seen so far** (high-water
mark), not against the previous round. This prevents the reward from cycling
up and down when coverage fluctuates between rounds.

## Data Model Hierarchy

```
TestGenerationSession
│   function_name: str
│   source_code: str
│   oracle: "crash" | "property" | "metamorphic"
│   model: str
│   total_rounds: int
│   total_input_tokens: int
│   total_output_tokens: int
│
├── rounds: list[RoundResult]
│   │   round_number: int
│   │   cumulative_coverage: float
│   │   cumulative_bugs: int
│   │
│   ├── generated_test: GeneratedTest
│   │       function_name: str
│   │       oracle: OracleType
│   │       test_code: str
│   │       is_valid: bool
│   │       generation_error: str | None
│   │       model, provider: str
│   │       input_tokens, output_tokens: int
│   │
│   ├── execution: ExecutionResult
│   │       passed, failed, errors, skipped, total: int
│   │       coverage_percent: float | None
│   │       coverage_branches: dict[str, float]
│   │       duration_seconds: float
│   │       test_details: list[TestDetail]
│   │       │   name: str
│   │       │   status: "passed" | "failed" | "error" | "skipped"
│   │       │   message: str | None
│   │       │   duration_seconds: float
│   │       execution_error: str | None
│   │
│   └── reward: RewardBreakdown
│           bug_reward: float
│           coverage_reward: float
│           validity_penalty: float
│           redundancy_penalty: float
│           total: float
│           bugs_found: int
│           coverage_gain: float
│           valid_tests, invalid_tests, redundant_tests: int
│
├── Properties (computed):
│   ├── final_coverage: float      (best coverage across all rounds)
│   ├── final_bugs: int            (total unique bugs found)
│   ├── learning_curve: list[float] (cumulative reward per round)
│   └── reward_per_round: list[float] (individual reward per round)
```

## Mapping to Thesis Evaluation Metrics (Proposal Table 4)

| Metric | Source | Calculation |
|--------|--------|-------------|
| Bug finding rate (RQ1) | `session.final_bugs` | Unique bugs found / code units tested |
| Branch coverage (RQ1) | `session.final_coverage` | Best coverage.py percentage across rounds |
| Test validity rate (RQ1) | `execution.validity_rate` | (total − errors) / total, averaged across rounds |
| Learning curve slope (RQ1) | `session.reward_per_round` | Linear regression coefficient of reward over rounds |
| False confidence rate (RQ2) | Comparison pipeline | Cells rated "clean" by static analysis that have test failures |
| Total issues found (RQ2) | Static findings + bugs | Count of static warnings + execution-found bugs, deduplicated |
| Assessment time (RQ2) | `execution.duration_seconds` | Wall-clock time for full pipeline per notebook |

## Extension Points

| Extension | Where | Thesis Item |
|-----------|-------|-------------|
| Property oracle | `prompts.py`: add `build_property_oracle_prompt` | T-018 |
| Metamorphic oracle | `prompts.py`: add `build_metamorphic_oracle_prompt` | T-019 |
| Hypothesis baseline | New module `hypothesis_baseline.py` | T-020 |
| CLI integration | `cli.py`: wire `qallm verify` to `TestGenerationLoop` | T-022 |
| API endpoint | `api/verification_routes.py` | T-022 |
| Adaptive temperature | `loop.py`: increase temperature in later rounds | T-021 |
| Multi-function sessions | `loop.py`: iterate over `extract_functions` output | T-022 |

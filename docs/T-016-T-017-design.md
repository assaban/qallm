# T-016 / T-017: Reward Function and RL Feedback Loop Design

## Overview

This document covers the reward scoring mechanism (T-016) and the iterative
feedback loop (T-017) that together form the "RL" in "RL-guided test
generation." These components close the cycle described in the thesis proposal
(Section 3.4, Figure 2): generate → execute → **score → feedback** → iterate.

The key insight: the LLM does not train weights or update parameters. Instead,
the reward signal is translated into a natural language feedback prompt that
guides the LLM toward generating better tests in the next round. This is
"RL-guided" in the sense that a quantitative reward function drives iterative
improvement, implemented as prompt-based feedback rather than gradient-based
optimization. This framing is deliberate (see Section 6, Required Expertise in
the proposal): it keeps the thesis within Software Engineering scope rather
than requiring deep RL or model training.

## T-016: Reward Function

### Purpose

Score the quality of a generated test batch after execution. The reward
function converts raw execution metrics (pass/fail counts, coverage
percentages, error counts) into a single scalar reward with a detailed
component breakdown.

### Algorithm

```
Input:
    execution: ExecutionResult (from T-015 executor)
    previous_coverage: float | None (best coverage from prior rounds)
    weights: RewardWeights (configurable, defaults below)

Output:
    RewardBreakdown (scalar total + per-component scores)

Procedure:
    1. If execution_error (timeout, crash): return penalty score
    2. If zero tests: return 0.0

    3. bug_reward = execution.failed × w.bug_found
    4. coverage_gain = max(0, current_coverage − previous_coverage)
       coverage_reward = coverage_gain × w.coverage_gain_per_point
    5. validity_penalty = execution.errors × w.invalid_test
    6. If bugs == 0 AND coverage_gain == 0:
           redundant_count = execution.passed
       Else:
           redundant_count = 0
       redundancy_penalty = redundant_count × w.redundant_test

    7. total = bug_reward + coverage_reward + validity_penalty + redundancy_penalty
    8. Return RewardBreakdown with all components
```

### Reward Weights (Default)

| Component | Weight | Rationale |
|-----------|--------|-----------|
| Bug found | +1.0 per test | Finding a real defect is the highest value outcome. A test that reveals a crash, property violation, or unexpected exception has directly demonstrated a quality gap that static analysis missed. |
| Coverage gain | +0.5 per percentage point | New coverage means the tests are exploring untested code paths. The per-point scaling means going from 0% to 60% is rewarded heavily (30 points), while going from 95% to 100% still earns 2.5 points. |
| Invalid test | −0.5 per test | A test with syntax errors, import failures, or collection errors is worse than no test. It wastes an execution cycle and indicates the LLM produced unusable output. |
| Redundant test | −0.2 per test | A test that passes but adds no coverage and finds no bugs is slightly harmful: it clutters the test suite without contributing value. The mild penalty discourages the LLM from regenerating similar tests. |

### Design Decisions

**Why a scalar reward?** The RL loop needs a single number to communicate
"this round was better than the last" in the feedback prompt. The breakdown
is preserved for analysis and debugging.

**Why penalise redundancy mildly (−0.2) rather than heavily?** Some passing
tests confirm correct behavior, which has value even without finding bugs.
A heavy penalty would discourage the LLM from generating any passing tests,
which would bias toward only crash-seeking tests.

**Why is coverage gain relative to previous best, not previous round?** If
Round 2 achieves 80% and Round 3 drops to 60%, we don't want Round 4 to be
"rewarded" for regaining the lost 20%. The `previous_coverage` tracks the
high-water mark across all rounds, so only genuinely new coverage is rewarded.

## T-017: RL Feedback Loop

### Purpose

Orchestrate multiple rounds of test generation, execution, and scoring.
After each round, construct a feedback prompt that tells the LLM what
worked, what didn't, and what to focus on next.

### Algorithm

```
Input:
    func: FunctionInfo (the function to test)
    source_code: str (complete source module)
    llm: LLMModel (the language model to use)
    rounds: int (number of iterations, default 5, max 20)
    oracle: OracleType (prompt strategy, default "crash")
    weights: RewardWeights (reward configuration)
    timeout: int (execution timeout per round, seconds)

Output:
    VerificationSession (all rounds, learning curve, cumulative metrics)

Procedure:
    best_coverage = None
    cumulative_bugs = 0

    FOR round_num = 1 TO rounds:

        STEP 1: GENERATE
        If round_num == 1:
            prompt = build_crash_oracle_prompt(func)  # standard T-014 prompt
        Else:
            prompt = build_feedback_prompt(
                func, previous_test_code, previous_execution,
                previous_reward, round_num
            )
        generated = llm.chat(SYSTEM_PROMPT, prompt)
        Validate and parse the response.

        STEP 2: EXECUTE
        If generated.is_valid:
            execution = run_tests(source_code, generated.test_code, timeout)
        Else:
            execution = empty result with error message

        STEP 3: SCORE
        reward = compute_reward(execution, best_coverage, weights)

        STEP 4: UPDATE CUMULATIVE METRICS
        best_coverage = max(best_coverage, execution.coverage_percent)
        cumulative_bugs += execution.bugs_found
        Store RoundResult(round_num, generated, execution, reward, ...)

        STEP 5: EARLY STOP CHECK
        If best_coverage >= 100% AND cumulative_bugs > 0:
            Break  # no further improvement possible

        STEP 6: PREPARE FEEDBACK
        previous_test_code = generated.test_code
        previous_execution = execution
        previous_reward = reward

    Return VerificationSession(all rounds)
```

### Feedback Prompt Mechanism

The feedback prompt is the core RL mechanism. It translates the quantitative
reward signal into natural language instructions. The prompt includes:

| Section | Content | Purpose |
|---------|---------|---------|
| Function under test | Same source code | Remind the LLM what it's testing |
| Previous test code | The test file from the last round | Show what was already tried |
| Execution results | Pass/fail/error counts, coverage % | Quantitative feedback |
| Test failures | Per-test status and error messages | Specific failure details |
| Reward breakdown | Score per component | What contributed value |
| Improvement instructions | Dynamic, based on gaps | Targeted guidance |

The improvement instructions are generated dynamically:

| Condition | Instruction |
|-----------|-------------|
| `errors > 0` | "Fix the invalid tests. Make sure all imports are correct." |
| `coverage < 100%` | "Current coverage is X%. Generate tests that exercise UNTESTED branches." |
| `redundant_tests > 0` | "N tests were redundant. Replace them with tests exploring different edge cases." |
| `failed == 0` | "No bugs found yet. Try more aggressive edge cases: empty inputs, None, overflow, type mismatches." |

### Early Stopping

The loop terminates before the configured round count if:
- Coverage reaches 100% AND at least one bug has been found

This prevents wasting API tokens when the maximum possible improvement has
been achieved.

### Learning Curve

The `VerificationSession` stores two lists for analysis:

- `learning_curve`: cumulative reward per round [0.5, 1.7, 3.2, 4.1, 4.8]
- `reward_per_round`: individual reward per round [0.5, 1.2, 1.5, 0.9, 0.7]

A positive slope in `reward_per_round` indicates the RL loop is producing
improving results across iterations. This is the "learning curve slope"
metric from the thesis proposal (Table 4), calculated as the linear
regression coefficient.

### Cumulative Metrics

Two metrics track the best results seen across all rounds:

- `cumulative_coverage`: the highest coverage percentage achieved in any round
  (not the average, because a later round may produce worse coverage than an
  earlier one)
- `cumulative_bugs`: running total of bugs found across all rounds

## Data Model Summary

```
VerificationSession
├── function_name, source_code, oracle, model
├── total_rounds
├── rounds: list[RoundResult]
│   ├── round_number: int
│   ├── generated_test: GeneratedTest
│   │   ├── test_code, is_valid, generation_error
│   │   └── model, provider, input_tokens, output_tokens
│   ├── execution: ExecutionResult
│   │   ├── passed, failed, errors, total
│   │   ├── coverage_percent, coverage_branches
│   │   └── test_details: list[TestDetail]
│   ├── reward: RewardBreakdown
│   │   ├── bug_reward, coverage_reward, validity_penalty, redundancy_penalty
│   │   └── total, bugs_found, coverage_gain, valid_tests, invalid_tests
│   ├── cumulative_coverage: float
│   └── cumulative_bugs: int
├── total_input_tokens, total_output_tokens
└── Properties: final_coverage, final_bugs, learning_curve, reward_per_round
```

## Mapping to Thesis Proposal

| Proposal Element | Implementation |
|-----------------|---------------|
| Figure 2: RL loop diagram | `VerificationLoop.run()` in `loop.py` |
| "1. LLM generates test batch" | `TestGenerator.generate()` in `generator.py` |
| "2. Execute tests (pytest)" | `run_tests()` in `executor.py` |
| "3. Measure coverage (coverage.py)" | coverage.py JSON parsing in `executor.py` |
| "4. Score tests" | `compute_reward()` in `reward.py` |
| "5. Update prompt with feedback" | `build_feedback_prompt()` in `prompts.py` |
| "iterate (5–10 rounds)" | `VerificationLoop(rounds=N)` |
| Reward: +1.0 bug found | `RewardWeights.bug_found = 1.0` |
| Reward: +0.5 new code path | `RewardWeights.coverage_gain_per_point = 0.5` |
| Reward: 0.0 trivial/duplicate | redundancy penalty mechanism |
| Reward: −0.5 invalid test | `RewardWeights.invalid_test = -0.5` |
| Table 4: Learning curve slope | `session.reward_per_round` → linear regression |
| Table 4: Bug finding rate | `session.final_bugs / tests_generated` |
| Table 4: Branch coverage | `session.final_coverage` |
| Table 4: Test validity rate | `execution.validity_rate` per round |

## Testing Strategy

All tests use mock LLMs and patched executors. No API keys or subprocess
calls are needed to run the test suite. This ensures:

- Tests run in CI without credentials
- Tests are fast (< 1 second vs 30+ seconds for real execution)
- Tests are deterministic (no LLM randomness)

Integration tests with real LLMs are marked `@pytest.mark.llm` and
excluded from CI.

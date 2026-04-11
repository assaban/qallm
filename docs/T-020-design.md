# T-020: Hypothesis Baseline Design

## Overview

The Hypothesis baseline provides a non-trivial competitor for RQ1:
"How effectively does RL-guided test generation compare to property-based
testing?" Instead of prompting an LLM, it uses the Hypothesis library to
auto-generate property-based tests from function signatures and type hints.

## Why Hypothesis (not naive random)?

The thesis proposal originally specified a random baseline. This was upgraded
to Hypothesis because naive random generation is a straw man: it generates
syntactically invalid inputs that crash on type errors rather than revealing
real bugs. Hypothesis is a serious property-based testing tool used in
industry. If the RL-guided approach outperforms Hypothesis, that's a
meaningful result.

## How it works

1. Extract a FunctionInfo (same extractor as the LLM approach)
2. Infer a Hypothesis strategy for each argument from its type annotation
3. Generate a test file with `@given` decorators
4. Run through the same executor (`run_tests`)
5. Return the same `ExecutionResult`

This ensures apples-to-apples comparison: same source code, same executor,
same coverage measurement, same reward function.

## Strategy Inference

| Type annotation | Hypothesis strategy |
|----------------|---------------------|
| `int` | `integers()` |
| `float` | `floats(allow_nan=False)` |
| `str` | `text(max_size=100)` |
| `bool` | `booleans()` |
| `list` | `lists(integers())` |
| `list[int]` | `lists(integers())` |
| `list[str]` | `lists(text(max_size=20))` |
| `dict` | `dictionaries(text(max_size=10), integers())` |
| `None` (no annotation) | `one_of(integers(), text(), booleans(), lists(integers()))` |
| `Optional[X]` | `one_of(none(), strategy_for(X))` |

When no type annotation is available, the baseline uses a mixed strategy
that covers common Python types. This is generous to the baseline: it gets
to try many input types without needing the domain knowledge an LLM might
infer from the function name or docstring.

## Generated Test Structure

For a function like:
```python
def compute_mean(data: list) -> float:
    return sum(data) / len(data)
```

The baseline generates:
```python
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from source_module import compute_mean

@given(data=st.lists(st.integers()))
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_compute_mean_does_not_crash(data):
    try:
        result = compute_mean(data)
    except Exception:
        pass  # crash oracle: we record it, not assert

@given(data=st.lists(st.integers(), min_size=1))
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_compute_mean_nonempty_returns_float(data):
    result = compute_mean(data)
    assert isinstance(result, (int, float))
```

## What it does NOT do

The baseline does NOT:
- Use an LLM (that's the point: it's the non-LLM comparison)
- Iterate across rounds (Hypothesis generates all examples in one shot)
- Use feedback prompts (no reward loop)
- Understand docstrings or function semantics

These limitations are exactly why comparing it to the RL-guided approach
is informative for the thesis.

## Comparison Framework (for Evaluation chapter)

| Metric | RL-guided (T-017) | Hypothesis baseline (T-020) |
|--------|-------------------|----------------------------|
| Coverage | `session.final_coverage` | `execution.coverage_percent` |
| Bugs found | `session.final_bugs` | `execution.bugs_found` |
| Test validity | `execution.validity_rate` | `execution.validity_rate` |
| Cost | Token count × price | 0 (no API calls) |
| Time | N rounds × LLM latency | Single Hypothesis run |

The evaluation (T-023+) will run both on the same set of functions from
Li's dataset and the zero-to-mastery-ml notebooks, then apply Wilcoxon
signed-rank tests with Cliff's delta for statistical comparison.

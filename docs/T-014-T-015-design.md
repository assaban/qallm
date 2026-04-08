# T-014 / T-015: Test Generator and Executor Design

## Overview

The verification module (`qallm/verification/`) implements the Test Case Agent
from the Agentic Workflow proposed by Islam & Zhao. It generates test cases for
Python code using an LLM, executes them, and reports results.

This document covers the first two building blocks:

- **T-014 (Generator):** LLM generates pytest test cases for Python functions
- **T-015 (Executor):** Runs generated tests in isolation, captures pass/fail
  and coverage

These two components are prerequisites for T-016 (reward function) and T-017
(RL feedback loop), which close the iterative improvement cycle described in
the thesis proposal (Figure 2).

## Architecture

```
                     ┌──────────────────────┐
  Python source ───> │  Function Extractor   │ ───> list of functions
                     └──────────────────────┘         (name, source, docstring)
                                │
                                ▼
                     ┌──────────────────────┐
  System prompt ───> │    Test Generator     │ ───> pytest test file (str)
  Oracle type   ───> │  (LLM via API call)   │
                     └──────────────────────┘
                                │
                                ▼
                     ┌──────────────────────┐
  Source under   ───> │    Test Executor      │ ───> ExecutionResult
  test           ───> │  (subprocess pytest)  │      (pass/fail, coverage,
                     └──────────────────────┘       per test details)
```

## Design Decisions

### 1. Function level granularity

Tests are generated per function, not per file or per cell. This gives the
reward function (T-016) a clear unit to score: each function gets a set of
tests, and we can measure coverage and bug discovery per function. Functions
are extracted from the source using `ast.parse`, which handles both standalone
scripts and notebook-extracted code.

### 2. Crash oracle first, other oracles later

T-014 implements only the **crash oracle**: the generated tests call the function
with edge case inputs and assert that no unhandled exceptions are raised on
type-valid inputs. This is the simplest oracle type and establishes the end to
end pipeline. Property oracle (T-018) and metamorphic oracle (T-019) are added
later as additional prompt strategies that plug into the same generator.

### 3. Subprocess isolation for test execution

Generated tests run in a **separate subprocess** via `subprocess.run`. This
provides:

- **Safety:** Generated code cannot affect the QALLM process
- **Timeout handling:** A hard wall-clock limit prevents infinite loops
- **Clean coverage:** coverage.py measures only the code under test, not QALLM itself
- **Reproducibility:** Each execution starts from a clean state

### 4. Reuse of existing LLM infrastructure

The generator reuses the same `LLMModel` interface, `TokenTracker`, and
provider registry that the repair module uses. No new LLM client code is
needed. The only new code is the prompt templates and the output parser.

### 5. Temperature setting

Test generation uses `temperature=0.1` (same as repair) for the one-shot
baseline. The RL loop (T-017) may experiment with higher temperatures in
later rounds to encourage exploration, but that's a future concern.

## Module Structure

```
src/qallm/verification/
├── __init__.py
├── models.py          # Data classes: FunctionInfo, GeneratedTest, ExecutionResult
├── extractor.py       # Extract functions from Python source using ast
├── prompts.py         # System and user prompt templates for test generation
├── generator.py       # LLM-based test generation (crash oracle)
└── executor.py        # Subprocess pytest runner with coverage capture
```

## Data Flow

### Input (from adapter or CLI)

A Python source file (either raw `.py` or extracted from `.ipynb`).

### Function extraction

```python
functions = extract_functions("path/to/source.py")
# Returns: [FunctionInfo(name="compute_mean", source="def compute_mean(data): ...",
#            docstring="Compute arithmetic mean.", args=[("data", None)], lineno=5)]
```

### Test generation

```python
test_code = generator.generate_tests(function_info, oracle="crash")
# Returns: str containing valid pytest code
```

### Test execution

```python
result = executor.run(source_path="source.py", test_code=test_code, timeout=30)
# Returns: ExecutionResult(
#     passed=3, failed=1, errors=0, total=4,
#     coverage_percent=85.0, coverage_branches={...},
#     duration_seconds=1.2,
#     test_details=[TestDetail(name="test_empty_list", status="failed", message="ZeroDivisionError"), ...]
# )
```

## Metrics Captured (for T-016 reward function)

| Metric | Source | Used by |
|--------|--------|---------|
| Tests passed / failed / errored | pytest exit code + JSON report | Reward: bug finding |
| Branch coverage percentage | coverage.py JSON report | Reward: new paths |
| Test validity (compiles + runs) | pytest collection phase | Reward: penalise invalid |
| Execution duration | wall clock timing | Assessment time metric |
| Per test status and message | pytest JSON report | Detailed reporting |

## Example: Crash Oracle Prompt

For the function:

```python
def compute_mean(data):
    """Compute the arithmetic mean of a list of numbers."""
    return sum(data) / len(data)
```

The generator produces:

```python
import pytest
from source import compute_mean

def test_compute_mean_normal():
    assert compute_mean([1, 2, 3]) == 2.0

def test_compute_mean_single_element():
    assert compute_mean([42]) == 42.0

def test_compute_mean_empty_list():
    # Crash oracle: does it handle empty input?
    with pytest.raises(ZeroDivisionError):
        compute_mean([])

def test_compute_mean_negative_numbers():
    assert compute_mean([-1, -2, -3]) == -2.0
```

The executor runs this, discovers the empty list case raises ZeroDivisionError,
and reports it as a finding.

## Error Handling

| Scenario | Handling |
|----------|---------|
| LLM returns invalid Python | Report as generation error, test validity = 0 |
| LLM returns no test functions | Report as empty generation |
| Generated test hangs (infinite loop) | Subprocess timeout kills it after N seconds |
| Coverage tool not available | Skip coverage, report tests only |
| Source file has import errors | Report in execution result, not a generation failure |

## Testing Strategy (for T-014 and T-015 themselves)

Tests for the verification module use **synthetic functions with known
properties**, not real LLM calls. The LLM is mocked to return predetermined
test code, which lets us verify the generator's output parsing and the
executor's result capture independently of API availability.

Integration tests that call real LLMs are marked with `@pytest.mark.llm` and
skipped in CI (they require API keys and cost money).

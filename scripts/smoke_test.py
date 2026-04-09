from qallm.repair.containers import build_llm_registry
from qallm.verification.extractor import extract_functions_from_source
from qallm.verification.generator import TestGenerator
from qallm.verification.executor import run_tests

source = """
def compute_mean(data):
    \"\"\"Compute the arithmetic mean of a list of numbers.\"\"\"
    return sum(data) / len(data)
"""

funcs = extract_functions_from_source(source)

registry = build_llm_registry()
llm = registry.pick("gpt-4o-mini")  # or "gpt-5-mini" for the stronger model
gen = TestGenerator(llm)
result = gen.generate(funcs[0], oracle="crash")

print("Valid:", result.is_valid)
print("Model:", result.model)
print("Tokens:", result.input_tokens, "in /", result.output_tokens, "out")
print()
print(result.test_code)

if result.is_valid:
    exec_result = run_tests(source, result.test_code)
    print(f"\nPassed: {exec_result.passed}")
    print(f"Failed: {exec_result.failed}")
    print(f"Coverage: {exec_result.coverage_percent}%")
    print(f"Bugs found: {exec_result.bugs_found}")
    for detail in exec_result.test_details:
        print(f"  {detail.name}: {detail.status}")
        if detail.message:
            print(f"    {detail.message[:200]}")
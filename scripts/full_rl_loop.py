from qallm.repair.containers import build_llm_registry
from qallm.verification.extractor import extract_functions_from_source
from qallm.verification.loop import VerificationLoop

source = """
def compute_mean(data):
    \"\"\"Compute the arithmetic mean of a list of numbers.\"\"\"
    return sum(data) / len(data)
"""

funcs = extract_functions_from_source(source)
registry = build_llm_registry()
llm = registry.pick("gpt-4o-mini")

loop = VerificationLoop(llm, rounds=5)
session = loop.run(funcs[0], source)

print(f"Rounds: {len(session.rounds)}")
print(f"Final coverage: {session.final_coverage}%")
print(f"Total bugs found: {session.final_bugs}")
print(f"Learning curve: {session.learning_curve}")
print(f"Reward per round: {session.reward_per_round}")

for r in session.rounds:
    print()
    print(r.generated_test)
    print()
    print(f"\n  Round {r.round_number}: reward={r.reward.total:.2f}, "
          f"coverage={r.execution.coverage_percent}%, "
          f"bugs={r.execution.bugs_found}, "
          f"valid={r.generated_test.is_valid}")
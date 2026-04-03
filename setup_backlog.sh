#!/usr/bin/env bash
# =============================================================================
# QALLM Thesis Backlog: GitHub Issues Batch Import
# =============================================================================
#
# Prerequisites:
#   1. Install GitHub CLI: brew install gh
#   2. Authenticate: gh auth login
#   3. Navigate to your repo: cd /path/to/qallm
#   4. Run this script: bash setup_backlog.sh
#
# This script creates:
#   - 4 milestones (one per TAR cycle)
#   - 7 labels (cycle tags + priority + type)
#   - 32 issues with labels and milestone assignments
# =============================================================================

set -e

echo "================================================"
echo "  QALLM Thesis Backlog Setup"
echo "================================================"
echo ""

# ── Check prerequisites ───────────────────────────────────────────
if ! command -v gh &> /dev/null; then
    echo "ERROR: GitHub CLI (gh) not found. Install with: brew install gh"
    exit 1
fi

if ! gh auth status &> /dev/null; then
    echo "ERROR: Not authenticated. Run: gh auth login"
    exit 1
fi

REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null)
if [ -z "$REPO" ]; then
    echo "ERROR: Not inside a GitHub repo. Navigate to your qallm directory first."
    exit 1
fi

echo "Repository: $REPO"
echo ""

# ── Create Labels ─────────────────────────────────────────────────
echo "Creating labels..."

gh label create "cycle-0"       --color "D4C5F9" --description "Foundation and cleanup"           --force
gh label create "cycle-1"       --color "C2E0C6" --description "Jupyter adapter and input modes"  --force
gh label create "cycle-2"       --color "FEF2C0" --description "RL test generation (core)"        --force
gh label create "cycle-3"       --color "F9D0C4" --description "Evaluation and Jupyter trigger"   --force
gh label create "continuous"    --color "E6E6E6" --description "Ongoing work across all cycles"   --force
gh label create "thesis-core"   --color "D93F0B" --description "Core thesis contribution"         --force
gh label create "existing-code" --color "0E8A16" --description "Refactoring existing P4 code"     --force
gh label create "new-feature"   --color "1D76DB" --description "New implementation"               --force
gh label create "size-S"        --color "EDEDED" --description "Small effort"                     --force
gh label create "size-M"        --color "EDEDED" --description "Medium effort"                    --force
gh label create "size-L"        --color "EDEDED" --description "Large effort"                     --force
gh label create "size-XL"       --color "EDEDED" --description "Extra large effort"               --force

echo "Labels created."
echo ""

# ── Create Milestones ─────────────────────────────────────────────
echo "Creating milestones..."

gh api repos/$REPO/milestones -f title="Cycle 0: Foundation"      -f description="Clean fork, consolidate microservices, setup CI. Weeks 1 to 2."                       -f due_on="2026-04-19T23:59:59Z" 2>/dev/null || echo "  (Cycle 0 milestone already exists)"
gh api repos/$REPO/milestones -f title="Cycle 1: Adapter"         -f description="Jupyter adapter, unified input modes, CLI. Weeks 2 to 4."                              -f due_on="2026-05-03T23:59:59Z" 2>/dev/null || echo "  (Cycle 1 milestone already exists)"
gh api repos/$REPO/milestones -f title="Cycle 2: RL Verification" -f description="RL guided test generation, the core thesis contribution. Weeks 5 to 10."               -f due_on="2026-06-14T23:59:59Z" 2>/dev/null || echo "  (Cycle 2 milestone already exists)"
gh api repos/$REPO/milestones -f title="Cycle 3: Evaluation"      -f description="Experiments, expert validation, Jupyter trigger, quality metrics. Weeks 11 to 16."      -f due_on="2026-07-26T23:59:59Z" 2>/dev/null || echo "  (Cycle 3 milestone already exists)"

echo "Milestones created."
echo ""

# ── Helper function ───────────────────────────────────────────────
create_issue() {
    local title="$1"
    local body="$2"
    local labels="$3"
    local milestone="$4"

    echo "  Creating: $title"
    gh issue create \
        --title "$title" \
        --body "$body" \
        --label "$labels" \
        --milestone "$milestone" \
        > /dev/null 2>&1
}

# ── Cycle 0: Foundation & Cleanup (Weeks 1–2) ────────────────────
echo "Creating Cycle 0 issues..."

create_issue \
    "T-001: Fork P4 repo to personal GitHub" \
    "## Acceptance Criteria
- New repo under personal GitHub account
- Clean git history
- README updated with thesis context

## Notes
Original repo: https://github.com/ChiefGitau/UvA-DevOps-Software-QA-LLM-MVP" \
    "cycle-0,existing-code,size-S" \
    "Cycle 0: Foundation"

create_issue \
    "T-002: Consolidate microservices into single package" \
    "## Acceptance Criteria
- All 5 services merged into \`qallm/\` package structure
- Single FastAPI application
- \`pip install -e .\` works
- No Docker dependency for development

## Notes
Merge analysis, llm, session, frontend services. Drop llm-agent entirely." \
    "cycle-0,existing-code,size-L" \
    "Cycle 0: Foundation"

create_issue \
    "T-003: Remove dead code" \
    "## Acceptance Criteria
- \`llm-agent/\` (LangGraph) deleted
- \`old/\` directory deleted
- \`aws/\` CloudFormation deleted
- Duplicated analyzer/normalizer files in llm service deleted
- Line count drops from ~8K to ~3K

## Notes
The llm-agent service was unnecessarily made complex by a colleague. The simpler repair logic in the llm service stays." \
    "cycle-0,existing-code,size-M" \
    "Cycle 0: Foundation"

create_issue \
    "T-004: Simplify repair module" \
    "## Acceptance Criteria
- Repair logic extracted from llm service into \`qallm/repair/\`
- No LangGraph dependency
- Prompt builder and batch per file approach preserved
- Multi-provider support (OpenAI, Anthropic, Ollama) retained

## Notes
Keep the 'batch per file' repair approach (one LLM call per file with all findings). This eliminates the overlapping patch bug." \
    "cycle-0,existing-code,size-M" \
    "Cycle 0: Foundation"

create_issue \
    "T-005: Consolidate web frontend" \
    "## Acceptance Criteria
- Frontend served directly by FastAPI (static files + templates)
- No Nginx required
- No separate Docker service
- Web UI functional for upload, analysis, and repair

## Notes
Frontend stays as one of three user interfaces (CLI, Web, Jupyter trigger)." \
    "cycle-0,existing-code,size-M" \
    "Cycle 0: Foundation"

create_issue \
    "T-006: Migrate tests" \
    "## Acceptance Criteria
- Existing 25 test files adapted to new package structure
- All imports updated from \`app.*\` to \`qallm.*\`
- All tests passing with \`pytest\`
- Coverage report generated" \
    "cycle-0,existing-code,size-M" \
    "Cycle 0: Foundation"

create_issue \
    "T-007: Setup CI and dependencies" \
    "## Acceptance Criteria
- GitHub Actions workflow: lint (ruff) + test (pytest) on push/PR
- Single \`pyproject.toml\` with all dependencies
- No Docker required for development
- \`pip install -e '.[dev]'\` installs everything needed" \
    "cycle-0,existing-code,size-S" \
    "Cycle 0: Foundation"

# ── Cycle 1: Jupyter Adapter + Input Modes (Weeks 2–4) ───────────
echo "Creating Cycle 1 issues..."

create_issue \
    "T-008: Jupyter notebook parser" \
    "## Acceptance Criteria
- Given a \`.ipynb\` file, extracts all code cells
- Strips Jupyter magic commands (\`%matplotlib\`, \`!pip\`)
- Writes to temp \`.py\` files preserving cell order
- Handles edge cases: empty cells, markdown only notebooks, nested JSON

## Technical Notes
Jupyter notebooks store content as JSON with a well defined schema. The adapter parses the \`.ipynb\` structure, extracts cells where \`cell_type == 'code'\`, and strips magic commands." \
    "cycle-1,new-feature,size-M" \
    "Cycle 1: Adapter"

create_issue \
    "T-009: Cell metadata preservation" \
    "## Acceptance Criteria
- Each extracted code block retains source cell index
- Line offset tracked for mapping findings back to original cells
- Original magic commands logged (not executed)
- Findings in reports map back to cell numbers" \
    "cycle-1,new-feature,size-M" \
    "Cycle 1: Adapter"

create_issue \
    "T-010: Unified adapter interface" \
    "## Acceptance Criteria
- All three input modes produce the same intermediate representation:
  - Jupyter notebook (\`.ipynb\`)
  - Python source files (direct upload or local path)
  - Git repository (clone from URL)
- \`qallm analyse <notebook.ipynb | file.py | https://github.com/...>\` works for all

## Notes
The session service already supports ZIP upload and Git clone. The notebook adapter sits alongside those." \
    "cycle-1,new-feature,size-M" \
    "Cycle 1: Adapter"

create_issue \
    "T-011: Validate adapter on Li's dataset (sample)" \
    "## Acceptance Criteria
- Run adapter + static analysis on 50 notebooks from Li's (2025) dataset
- Verify Bandit/Radon results are consistent with Li's published findings
- Document any discrepancies with explanations
- Results stored as reproducible evaluation artifact

## Notes
Li's dataset contains 2,796 notebooks from 277 projects. A curated subset of 50 is used for this initial validation." \
    "cycle-1,size-L" \
    "Cycle 1: Adapter"

create_issue \
    "T-012: Adapter unit tests" \
    "## Acceptance Criteria
- Tests cover: valid notebook, empty notebook, markdown only notebook, magic command stripping, malformed JSON, Git clone, direct file input
- At least 90% coverage on the adapter module
- All tests passing in CI" \
    "cycle-1,size-M" \
    "Cycle 1: Adapter"

create_issue \
    "T-013: CLI interface" \
    "## Acceptance Criteria
- \`qallm analyse\`, \`qallm repair\`, \`qallm verify\` commands implemented
- Accepts all input types (notebook, file, URL)
- JSON output to stdout or file (\`--output\` flag)
- \`--help\` for each command
- \`qallm server\` starts the web UI" \
    "cycle-1,new-feature,size-M" \
    "Cycle 1: Adapter"

# ── Cycle 2: RL Test Generation (Weeks 5–10) ─────────────────────
echo "Creating Cycle 2 issues..."

create_issue \
    "T-014: Test generator (one shot baseline)" \
    "## Acceptance Criteria
- LLM generates test cases for a given Python function
- Uses crash oracle (call with edge case inputs, expect no unhandled exceptions)
- Output: valid pytest test file that can be executed
- Works with both Claude and GPT-4 APIs

## Notes
This is Strategy (b) from the proposal: one shot LLM test generation, the same LLM and prompt as the RL version but without iterative feedback. Serves as the ablation baseline." \
    "cycle-2,thesis-core,new-feature,size-L" \
    "Cycle 2: RL Verification"

create_issue \
    "T-015: Test executor" \
    "## Acceptance Criteria
- Runs generated pytest files in isolated subprocess
- Captures per test: pass/fail status, error message if failed
- Captures coverage report (coverage.py with branch=True)
- Captures execution time and stdout/stderr
- Handles timeouts for infinite loops or hanging tests" \
    "cycle-2,thesis-core,new-feature,size-M" \
    "Cycle 2: RL Verification"

create_issue \
    "T-016: Reward function v1" \
    "## Acceptance Criteria
- Scores a test batch with the following rewards:
  - +1.0 bug or vulnerability found
  - +0.5 new code branch covered
  - 0.0 trivial or duplicate test
  - −0.5 invalid test (syntax error, import failure)
- Returns scalar reward + detailed breakdown per test
- Configurable reward weights

## Notes
The reward function drives the RL loop. It must penalise redundancy and reward discovery." \
    "cycle-2,thesis-core,new-feature,size-M" \
    "Cycle 2: RL Verification"

create_issue \
    "T-017: RL feedback loop" \
    "## Acceptance Criteria
- Orchestrates 5 to 10 rounds: generate → execute → score → feed reward back into next prompt
- Stores per round metrics (reward, coverage delta, bugs found, test validity rate)
- Configurable round count via CLI and API
- Learning curve data exportable for plotting
- Full round history persisted as JSON

## Notes
This is the core thesis contribution. The loop iteratively improves test quality using reward signals from execution results." \
    "cycle-2,thesis-core,new-feature,size-XL" \
    "Cycle 2: RL Verification"

create_issue \
    "T-018: Property oracle" \
    "## Acceptance Criteria
- LLM extracts invariants from docstrings and type hints
- Generates property based test assertions (e.g., 'normalise to [0,1]' → assert output in range)
- Properties extracted automatically, no manual specification needed
- Integrates with the test generator as an oracle type

## Notes
Example: a function documented as 'normalise to [0,1] range' should not return values outside that range." \
    "cycle-2,thesis-core,new-feature,size-L" \
    "Cycle 2: RL Verification"

create_issue \
    "T-019: Metamorphic oracle" \
    "## Acceptance Criteria
- Generates metamorphic relation tests
- Domain general relations: sort invariance, scaling consistency, idempotency
- No specifications required
- Integrates with the test generator as an oracle type

## Notes
Metamorphic relations are domain general and do not require specifications. Example: sorting the input to a monotonic function should yield sorted output." \
    "cycle-2,thesis-core,new-feature,size-L" \
    "Cycle 2: RL Verification"

create_issue \
    "T-020: Hypothesis baseline" \
    "## Acceptance Criteria
- Property based testing using Hypothesis library
- Generates random inputs matching type annotations
- Automatic shrinking to find minimal failing cases
- Runs as Strategy (a) in the proposal's baseline comparison

## Notes
This is a non trivial baseline, not a strawman. If RL guided generation beats Hypothesis, that is genuinely impressive." \
    "cycle-2,thesis-core,new-feature,size-M" \
    "Cycle 2: RL Verification"

create_issue \
    "T-021: Prompt engineering iteration" \
    "## Acceptance Criteria
- Test and refine prompts across Claude and GPT-4
- Few shot examples for each oracle type (crash, property, metamorphic)
- Document prompt versions and their effect on test validity rate
- Results across at least two LLM providers reported

## Notes
Prompt sensitivity is acknowledged as an internal validity threat in the proposal." \
    "cycle-2,thesis-core,size-L" \
    "Cycle 2: RL Verification"

create_issue \
    "T-022: Integration: full pipeline" \
    "## Acceptance Criteria
- Full pipeline: input → adapter → static analysis → (optional) repair → (optional) RL verification → unified report
- Single command: \`qallm full <input>\`
- User chooses which operations to run via flags or web UI
- API endpoint for each operation individually
- JSON report combines static + verification results" \
    "cycle-2,new-feature,size-L" \
    "Cycle 2: RL Verification"

# ── Cycle 3: Evaluation & Jupyter Trigger (Weeks 11–16) ──────────
echo "Creating Cycle 3 issues..."

create_issue \
    "T-023: Jupyter frontend trigger" \
    "## Acceptance Criteria
- ipywidgets button in notebook: 'Run Quality Check'
- Calls pipeline and displays inline results (per cell pass/fail, summary stats)
- Options to select operations (analyse, repair, verify)
- Lightweight UI integration using ipywidgets

## Notes
Practical feature requested by Dr. Zhao. Expert validation (RQ3) will assess which integration patterns are most effective." \
    "cycle-3,new-feature,size-M" \
    "Cycle 3: Evaluation"

create_issue \
    "T-024: Web UI update for verification" \
    "## Acceptance Criteria
- Frontend updated to support all three operations
- User can select: analyse only, analyse + repair, analyse + verify, or full cycle
- Displays unified report with static + verification results
- Responsive and functional" \
    "cycle-3,existing-code,size-M" \
    "Cycle 3: Evaluation"

create_issue \
    "T-025: Collect evaluation notebooks" \
    "## Acceptance Criteria
- Curate 200 notebooks from Li's dataset (5 domains × 3 complexity tiers)
- Select 100 to 200 from Kaggle and GitHub (diverse domains, Python kernel, 5+ code cells with function definitions)
- Prepare HumanEval (164 problems) + MBPP (974 problems) benchmark subsets
- Selection criteria documented and reproducible" \
    "cycle-3,size-L" \
    "Cycle 3: Evaluation"

create_issue \
    "T-026: RQ1 Baseline comparison" \
    "## Acceptance Criteria
- Run all 3 strategies on the same code:
  (a) Hypothesis (property based)
  (b) One shot LLM
  (c) RL guided
- Measure: bug finding rate, branch coverage, test validity rate, learning curve slope
- Statistical tests: Wilcoxon signed rank at α = 0.05
- Effect sizes: Cliff's delta
- Results reported per benchmark and per notebook source" \
    "cycle-3,thesis-core,size-XL" \
    "Cycle 3: Evaluation"

create_issue \
    "T-027: RQ2 Controlled comparison" \
    "## Acceptance Criteria
- Same notebooks analysed under two conditions:
  (a) Static analysis only
  (b) Static analysis + RL verification
- Key metric: false confidence rate (cells rated 'clean' by static that have test failures)
- Report: total issues found, assessment time per notebook
- Statistical comparison with effect sizes" \
    "cycle-3,thesis-core,size-L" \
    "Cycle 3: Evaluation"

create_issue \
    "T-028: RQ3 Expert validation" \
    "## Acceptance Criteria
- Recruit 10 to 15 experts (academia + industry)
- Show 5 example notebook analyses under both conditions
- Collect: Likert scale responses on usefulness and trust, comparative judgement, integration preferences (trigger point, detail level, adoption barriers)
- Thematic analysis of open ended responses
- Design recommendations derived from expert feedback

## Notes
Following Soveizi et al. (15 IT professionals) and Volentir et al. (10 professionals) validation approaches." \
    "cycle-3,thesis-core,size-L" \
    "Cycle 3: Evaluation"

create_issue \
    "T-029: Quality metrics definition" \
    "## Acceptance Criteria
- Define 3 to 5 verification based quality metrics:
  - Functional correctness score (test pass rate)
  - Verification coverage (branch coverage from generated tests)
  - False confidence rate
  - Security assessment score
- JSON schema compatible with Volentir et al. framework
- Formal definitions with measurement procedures" \
    "cycle-3,thesis-core,new-feature,size-M" \
    "Cycle 3: Evaluation"

create_issue \
    "T-030: Quality reporting module" \
    "## Acceptance Criteria
- Generate structured JSON reports
- Include static metrics + verification results
- Per cell breakdown for notebooks
- Compatible with Volentir et al. framework
- Report schema documented" \
    "cycle-3,new-feature,size-M" \
    "Cycle 3: Evaluation"

# ── Continuous ────────────────────────────────────────────────────
echo "Creating continuous issues..."

create_issue \
    "T-031: Thesis writing" \
    "## Acceptance Criteria
- Continuous from Week 1 through Week 18
- Chapters: Introduction, Background, Methodology, Implementation, Evaluation, Discussion, Conclusion
- LaTeX on Overleaf (XeLaTeX + biblatex/biber)
- Supervisor review cycles built into timeline

## Notes
Thesis writing runs in parallel with all phases. Final three weeks (16 to 18) dedicated to completing evaluation, discussion, and defence preparation." \
    "continuous,size-XL" \
    "Cycle 3: Evaluation"

create_issue \
    "T-032: Open source release" \
    "## Acceptance Criteria
- GitHub repo with:
  - README with installation guide
  - Example notebooks
  - Reproducibility package (scripts to replicate all experiments)
  - License (MIT)
- All evaluation data and scripts included
- Documentation for extending the tool" \
    "continuous,size-M" \
    "Cycle 3: Evaluation"

# ── Done ──────────────────────────────────────────────────────────
echo ""
echo "================================================"
echo "  Setup complete!"
echo "================================================"
echo ""
echo "  View your board:  gh project list"
echo "  View all issues:  gh issue list"
echo "  View milestones:  gh api repos/$REPO/milestones --jq '.[].title'"
echo ""
echo "  Next step: go to https://github.com/$REPO/projects"
echo "  and create a Project board linked to this repo."
echo ""

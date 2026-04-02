# P4 Codebase Analysis & Thesis Execution Backlog (v2)

## 1. Codebase Analysis

### 1.1 Architecture Overview

The P4 tool is a **microservices application** with 5 services communicating via HTTP through an Nginx reverse proxy, sharing a Docker volume for file storage.

| Service | Lines | Purpose | Thesis Decision |
|---------|-------|---------|-----------------|
| `analysis` | 2,567 | Static analysis (Bandit, Radon, Ruff, TruffleHog) | **KEEP** — core pipeline |
| `llm` | 2,990 | LLM-based code repair + duplicated analysis layer | **KEEP repair, DROP duplicated analysis** |
| `llm-agent` | 1,533 | LangGraph multi-agent repair (over-engineered) | **DROP** — replaced by simplified repair + RL module |
| `session` | 906 | Session/workspace management, file upload, Git clone | **KEEP & SIMPLIFY** — input adapter layer |
| `frontend` | ~90K | Nginx + HTML/JS/CSS web UI | **KEEP & SIMPLIFY** — one of three user interfaces |
| **Total** | **~8,000 Python** | | |

Plus: AWS CloudFormation (694 lines), Docker Compose, CI/CD workflows, 25 test files (1,927 lines).

### 1.2 What Works Well (Keep)

**Analyzer/Normalizer pattern** — Clean abstractions with registry pattern:
- `StaticCodeAnalyzer` (abstract base) → `BanditAnalyzer`, `RadonAnalyzer`, `RuffAnalyzer`, `TruffleHogAnalyzer`
- Each analyzer runs a CLI tool, captures output to JSON artifact
- Each normalizer converts raw tool output → unified `Finding` objects
- Registry pattern makes it trivial to add new analyzers

**`Finding` data model** — Well-designed with deterministic SHA1 IDs, severity levels (LOW/MEDIUM/HIGH/CRITICAL), finding types (SECURITY/SMELL/COMPLEXITY/SECRET), and code snippet capture. Directly usable for thesis quality reporting.

**`AnalysisService` orchestration** — Clean two-phase flow: run analyzers → normalize findings → persist JSON report. The `verify()` method (diff pre/post repair) is a good pattern we can adapt for pre/post test generation comparison.

**LLM repair service** — The "batch per file" approach (one LLM call per file with all findings) is clean and eliminates the overlapping-patch bug. Multi-provider support (OpenAI, Anthropic, Ollama), token tracking with cost calculation, syntax validation with retry. This stays as one of the three pipeline operations.

**LLM abstractions** — `LLMModel` interface, `LLMResponse`, `TokenTracker` with cost calculation. Reusable for both repair prompts and test generation prompts.

**Session/workspace management** — UUID-based sessions with file upload (ZIP extraction), Git clone, workspace isolation. This becomes the foundation for the input adapter layer.

**Web frontend** — Functional UI for upload, analysis, and repair. Stays as one of three interfaces (CLI, Web, Jupyter trigger).

**Test suite** — 25 test files covering analyzers, normalizers, health checks, and utilities. Good foundation for maintaining quality during refactoring.

### 1.3 What Must Go (Remove)

| Component | Reason |
|-----------|--------|
| `services/llm-agent/` | LangGraph repair — over-engineered by colleague, replaced by simpler repair in `llm` service |
| `services/llm/app/analyzers/` | **Duplicated** — 12 files identical to `analysis` service |
| `services/llm/app/normalizers/` | **Duplicated** — identical to `analysis` service |
| `aws/` | CloudFormation not needed for thesis |
| `old/` | Legacy code archive |
| Docker Compose microservices | Consolidate to single FastAPI application |
| Nginx reverse proxy | FastAPI serves frontend directly |
| CI/CD for DevOps branches | Replace with thesis-specific CI |

### 1.4 Code Duplication Problem

The `llm` service duplicated the entire analysis layer from the `analysis` service so it could run analysis + repair in one container. **12 files are byte-for-byte identical** between the two services:

`bandit.py`, `radon.py`, `ruff.py`, `trufflehog.py`, `bandit_normalizer.py`, `radon_normalizer.py`, `ruff_normalizer.py`, `trufflehog_normalizer.py`, `logging.py`, `schemas.py`, `util.py`, `__init__.py`

**Fix:** Consolidate into shared modules within a single package.

### 1.5 Architecture Decision: Microservices → Single Application

The microservices architecture was a DevOps course requirement. For the thesis, it adds complexity without value. The new architecture is a **single FastAPI application** with clear module boundaries and three user-facing interfaces.

**Design principle:** 3 input adapters × 3 operations × 3 interfaces. A user picks what they need.

**Input adapters:**
- Jupyter notebook (`.ipynb` → extract code cells) — **NEW**
- Source files (direct `.py` upload or local path) — **EXISTING**
- Git repository (clone from URL) — **EXISTING**

**Operations (user chooses any combination):**
- Analyse — static analysis (Bandit, Radon, Ruff, TruffleHog) — **EXISTING**
- Repair — LLM-based code fix — **EXISTING (simplified)**
- Verify — RL-guided test generation — **NEW (core thesis contribution)**

**User interfaces:**
- CLI — command-line tool — **NEW**
- Web UI — browser-based interface — **EXISTING (simplified)**
- Jupyter trigger — ipywidgets button inside notebooks — **NEW**

```
qallm/
├── src/
│   └── qallm/
│       ├── __init__.py
│       ├── adapters/                 # Input adapters
│       │   ├── __init__.py
│       │   ├── notebook.py           # .ipynb → code cells (NEW)
│       │   ├── source.py             # Direct .py files (FROM session service)
│       │   └── repository.py         # Git clone (FROM session service)
│       ├── analysis/                 # Static analysis (FROM analysis service)
│       │   ├── __init__.py
│       │   ├── analyzers/            # Bandit, Radon, Ruff, TruffleHog
│       │   ├── normalizers/          # Finding normalizers
│       │   ├── models.py             # Finding, Summary, VerificationReport
│       │   └── pipeline.py           # AnalysisService
│       ├── repair/                   # LLM code repair (FROM llm service, simplified)
│       │   ├── __init__.py
│       │   ├── prompt_builder.py     # Repair prompt templates
│       │   └── repair_service.py     # Batch-per-file repair logic
│       ├── verification/             # RL test generation (NEW — core contribution)
│       │   ├── __init__.py
│       │   ├── generator.py          # LLM test generation
│       │   ├── executor.py           # pytest + coverage.py runner
│       │   ├── reward.py             # Reward function
│       │   ├── loop.py               # RL feedback loop orchestrator
│       │   └── oracles.py            # Crash, property, metamorphic oracles
│       ├── llm/                      # LLM provider interface (FROM llm service)
│       │   ├── __init__.py
│       │   ├── base.py               # LLMModel, LLMResponse, TokenTracker
│       │   ├── anthropic_provider.py
│       │   ├── openai_provider.py
│       │   ├── ollama_provider.py
│       │   └── registry.py
│       ├── session/                  # Workspace management (FROM session service, simplified)
│       │   ├── __init__.py
│       │   └── workspace.py          # Session dirs, file management
│       ├── reporting/                # Quality report generation (NEW)
│       │   ├── __init__.py
│       │   └── reporter.py           # JSON output (Volentir et al. compatible)
│       ├── api/                      # FastAPI routes (CONSOLIDATED from all services)
│       │   ├── __init__.py
│       │   ├── analysis_routes.py
│       │   ├── repair_routes.py
│       │   ├── verification_routes.py  # NEW
│       │   └── session_routes.py
│       ├── web/                      # Web frontend (FROM frontend service, simplified)
│       │   ├── static/
│       │   └── templates/
│       ├── cli.py                    # CLI entry point (NEW)
│       └── main.py                   # FastAPI app
├── jupyter_trigger/                  # Jupyter extension (NEW)
│   └── ...
├── tests/                            # Migrated + new tests
├── pyproject.toml
└── README.md
```

---

## 2. Thesis Product Backlog

Organised by TAR cycle (matching proposal timeline). Each item has an ID, description, acceptance criteria, and estimated effort (S/M/L/XL).

### Cycle 0: Foundation & Cleanup (Weeks 1–2)

| ID | Item | Acceptance Criteria | Effort |
|----|------|---------------------|--------|
| T-001 | **Fork P4 repo to personal GitHub** | New repo under your account, clean git history, README updated with thesis context | S |
| T-002 | **Consolidate microservices → single package** | All services merged into `qallm/` package structure. Single FastAPI app. `pip install -e .` works. | L |
| T-003 | **Remove dead code** | `llm-agent/`, `old/`, `aws/`, duplicated analyzer/normalizer files in `llm` service deleted. | M |
| T-004 | **Simplify repair module** | Repair logic extracted from `llm` service into `qallm/repair/`. No LangGraph dependency. Prompt builder and batch-per-file approach preserved. | M |
| T-005 | **Consolidate web frontend** | Frontend served directly by FastAPI (static files + templates). No Nginx. No separate Docker service. | M |
| T-006 | **Migrate tests** | Existing 25 test files adapted to new package structure. All passing with `pytest`. | M |
| T-007 | **Setup CI + dependencies** | GitHub Actions: lint (ruff) + test (pytest) on push/PR. Single `pyproject.toml` with all deps. No Docker required for dev. | S |

### Cycle 1: Jupyter Adapter + Input Modes (Weeks 2–4)

| ID | Item | Acceptance Criteria | Effort |
|----|------|---------------------|--------|
| T-008 | **Jupyter notebook parser** | Given a `.ipynb` file, extracts all code cells, strips magic commands (`%matplotlib`, `!pip`), writes to temp `.py` files preserving cell order. Handles edge cases: empty cells, markdown-only notebooks, nested JSON. | M |
| T-009 | **Cell metadata preservation** | Each extracted code block retains source cell index, line offset, and original magic commands (logged, not executed). Findings map back to cell numbers in reports. | M |
| T-010 | **Unified adapter interface** | All three input modes (notebook, source files, repo URL) produce the same intermediate representation. `qallm analyse <notebook.ipynb | file.py | https://github.com/...>` works for all. | M |
| T-011 | **Validate on Li's dataset (sample)** | Run adapter + static analysis on 50 notebooks from Li's dataset. Verify Bandit/Radon results are consistent with Li's published findings. Document any discrepancies. | L |
| T-012 | **Adapter unit tests** | Tests for: valid notebook, empty notebook, notebook with only markdown, magic command stripping, malformed JSON, Git clone, direct file input. ≥90% coverage on adapter module. | M |
| T-013 | **CLI interface** | `qallm analyse`, `qallm repair`, `qallm verify` commands. Accepts all input types. JSON output to stdout or file. `--help` for each command. | M |

### Cycle 2: RL Test Generation — Core Contribution (Weeks 5–10)

| ID | Item | Acceptance Criteria | Effort |
|----|------|---------------------|--------|
| T-014 | **Test generator (one-shot baseline)** | LLM generates test cases for a given Python function. Uses crash oracle (try calling with edge-case inputs). Output: valid pytest test file. | L |
| T-015 | **Test executor** | Runs generated pytest files in isolated subprocess. Captures: pass/fail per test, coverage report (coverage.py with branch=True), execution time, stdout/stderr. | M |
| T-016 | **Reward function v1** | Scores test batch: +1.0 bug/vulnerability found, +0.5 new branch covered, 0.0 trivial/duplicate, −0.5 invalid test (syntax error, import failure). Returns scalar reward + breakdown. | M |
| T-017 | **RL feedback loop** | Orchestrates 5–10 rounds: generate → execute → score → feed reward back into next prompt. Stores per-round metrics (reward, coverage delta, bugs found). Configurable round count. | XL |
| T-018 | **Property oracle** | LLM extracts invariants from docstrings/type hints (e.g., "normalise to [0,1]" → assert output in range). Generates property-based test assertions. | L |
| T-019 | **Metamorphic oracle** | Generates metamorphic relation tests (e.g., sort invariance, scaling consistency). Domain-general relations, no specifications needed. | L |
| T-020 | **Hypothesis baseline** | Property-based testing using Hypothesis library as non-trivial baseline (Strategy a in proposal). Generates tests from type annotations with automatic shrinking. | M |
| T-021 | **Prompt engineering iteration** | Test and refine prompts across Claude and GPT-4. Few-shot examples for each oracle type. Document prompt versions and their effect on test validity rate. | L |
| T-022 | **Integration: full pipeline** | Full pipeline: input → adapter → static analysis → (optional) repair → (optional) RL verification → unified report. Single command or single web UI flow. User chooses which operations to run. | L |

### Cycle 3: Evaluation & Jupyter Trigger (Weeks 11–16)

| ID | Item | Acceptance Criteria | Effort |
|----|------|---------------------|--------|
| T-023 | **Jupyter frontend trigger** | ipywidgets button in notebook: "Run Quality Check". Calls pipeline, displays inline results (per-cell pass/fail, summary stats). Options to select operations (analyse/repair/verify). | M |
| T-024 | **Web UI update** | Frontend updated to support all three operations. User can select: analyse only, analyse + repair, analyse + verify, or full cycle. Displays unified report. | M |
| T-025 | **Collect evaluation notebooks** | Curate 200 notebooks from Li's dataset (5 domains × 3 complexity tiers). Select 100–200 from Kaggle/GitHub. Prepare HumanEval + MBPP benchmark subsets. | L |
| T-026 | **RQ1: Baseline comparison** | Run all 3 strategies (Hypothesis, one-shot LLM, RL-guided) on same code. Measure: bug-finding rate, branch coverage, test validity rate, learning curve slope. Statistical tests (Wilcoxon, Cliff's delta). | XL |
| T-027 | **RQ2: Controlled comparison** | Same notebooks under 2 conditions: static-only vs. static+RL. Key metric: false confidence rate. Report total issues found and assessment time. | L |
| T-028 | **RQ3: Expert validation** | Recruit 10–15 experts. Show 5 notebook analyses (static-only vs. static+RL). Collect Likert-scale responses + open-ended feedback. Thematic analysis for integration design recommendations. | L |
| T-029 | **Quality metrics definition** | Define 3–5 verification-based metrics: functional correctness score, verification coverage, false confidence rate, security assessment score. JSON schema compatible with Volentir et al. | M |
| T-030 | **Quality reporting module** | Generate structured JSON reports. Include static metrics + verification results. Per-cell breakdown for notebooks. Compatible with Volentir et al. framework. | M |

### Continuous

| ID | Item | Acceptance Criteria | Effort |
|----|------|---------------------|--------|
| T-031 | **Thesis writing** | Continuous from Week 1. Chapters: Introduction, Background, Methodology, Implementation, Evaluation, Discussion, Conclusion. | — |
| T-032 | **Open-source release** | GitHub repo with: README, installation guide, example notebooks, reproducibility package (scripts to replicate all experiments). | M |

---

## 3. Plan of Action

### Phase 1: Clean Fork & Restructure (Weeks 1–2)

**Goal:** Your own clean repo with the QALLM tool as a single application. Analysis, repair, and web UI working. No Docker dependency for development.

1. Fork the repo to your GitHub account
2. Create a `thesis-main` branch
3. Delete: `llm-agent/`, `old/`, `aws/`, duplicated files in `llm` service
4. Restructure into single package (`qallm/`)
5. Consolidate analysis + repair + session + frontend into one FastAPI app
6. Get `pip install -e .` and `pytest` passing
7. Setup GitHub Actions CI
8. Push clean baseline

### Phase 2: Jupyter Adapter + CLI (Weeks 2–4)

**Goal:** `qallm analyse <notebook.ipynb | file.py | repo-url>` works end-to-end. All three input modes unified.

1. Build notebook parser (T-008, T-009)
2. Unify adapter interface (T-010)
3. Build CLI (T-013)
4. Validate against Li's data (T-011)
5. Write tests (T-012)

**Deliverable:** Pipeline v0.1 (all input modes + static analysis + repair on notebooks).

### Phase 3: RL Verification (Weeks 5–10)

**Goal:** The core thesis contribution works and integrates with the existing tool.

1. Start with one-shot baseline (T-014) — get LLM generating any tests at all
2. Build test executor (T-015) — run tests, capture coverage
3. Build reward function (T-016) — score test quality
4. Close the loop (T-017) — iterative RL feedback
5. Add oracle types (T-018, T-019) — property and metamorphic
6. Build Hypothesis baseline (T-020) — non-trivial competitor
7. Integrate into full pipeline (T-022) — user picks operations

**Deliverable:** Pipeline v0.5 (all input modes + analyse + repair + RL verification).

### Phase 4: Evaluation & Polish (Weeks 11–16)

**Goal:** Answer all three research questions with evidence. All three interfaces working.

1. Build Jupyter trigger (T-023)
2. Update web UI (T-024)
3. Collect and curate evaluation data (T-025)
4. Run experiments (T-026, T-027)
5. Expert validation (T-028)
6. Define metrics and build reporting (T-029, T-030)

**Deliverable:** Pipeline v1.0 + complete evaluation results.

### Phase 5: Thesis Completion (Weeks 16–18)

**Goal:** Defend.

1. Finalize evaluation and discussion chapters
2. Open-source release (T-032)
3. Defence preparation

---

## 4. Immediate Next Steps

1. **Fork the repo** on GitHub
2. **Review this backlog** — adjust priorities, flag anything missing
3. **Execute T-001 through T-007** — the cleanup sprint (we build this together now)

---

*Document generated: 2 April 2026*
*Based on analysis of P4 repository (github.com/ChiefGitau/UvA-DevOps-Software-QA-LLM-MVP)*
*Revision 2: Repair stays, frontend stays, multiple input adapters*

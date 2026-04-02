# QALLM — Quality Assessment of AI-Generated Code

MSc Software Engineering Thesis Project, University of Amsterdam

**Author:** Mohssin Assaban  
**Main Supervisor:** Dr. Zhiming Zhao (MNS Research Group, UvA)  
**Daily Supervisor:** Dr. Nafis Tanveer Islam (UvA)

## Overview

QALLM is a quality assessment tool for Python code and Jupyter notebooks. It combines static analysis, LLM-based repair, and RL-guided test generation into a unified pipeline.

### Operations

| Operation | Description | Status |
|-----------|-------------|--------|
| **Analyse** | Static analysis via Bandit, Radon, Ruff, TruffleHog | Working |
| **Repair** | LLM-based code fixes for flagged issues | Working |
| **Verify** | RL-guided test generation (core thesis contribution) | In development |

### Input modes

- **Jupyter notebooks** (`.ipynb`) — code cells extracted via adapter
- **Python source files** — direct analysis
- **Git repositories** — clone and analyse

### Interfaces

- **CLI** — `qallm analyse <input>`
- **Web UI** — browser-based interface at `http://localhost:8000`
- **Jupyter trigger** — quality check button inside notebooks

## Installation

```bash
git clone https://github.com/<your-username>/qallm.git
cd qallm
pip install -e ".[dev]"
```

## Usage

```bash
# Static analysis
qallm analyse path/to/file.py

# Start web server
qallm server --port 8000

# Run tests
pytest
```

## Project structure

```
src/qallm/
├── adapters/       # Input adapters (notebook, source files, git repos)
├── analysis/       # Static analysis pipeline (Bandit, Radon, Ruff, TruffleHog)
├── repair/         # LLM-based code repair
├── verification/   # RL-guided test generation (thesis contribution)
├── llm/            # LLM provider interface (OpenAI, Anthropic, Ollama)
├── session/        # Workspace and file management
├── api/            # FastAPI routes
├── web/            # Web frontend (static files + templates)
├── reporting/      # Quality report generation
├── cli.py          # CLI entry point
└── main.py         # FastAPI application
```

## Origin

This tool builds on the P4 quality analysis tool developed during the UvA DevOps course (Group 17). The original microservices architecture has been consolidated into a single application. The RL-guided test generation module is the core thesis contribution.

## License

MIT

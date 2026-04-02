"""QALLM CLI — command-line interface for quality assessment.

Usage:
    qallm analyse <input>          Run static analysis
    qallm repair <session_id>      Run LLM-based repair
    qallm verify <session_id>      Run RL-guided test generation (future)
    qallm server                   Start the web server

Input can be:
    - A .ipynb notebook file
    - A .py source file or directory
    - A Git repository URL
"""

from __future__ import annotations

import argparse
import sys


def cmd_analyse(args):
    """Run static analysis on the given input."""
    print(f"[QALLM] Analysing: {args.input}")
    print("[QALLM] TODO: implement adapter detection + pipeline run")
    # Future:
    # 1. Detect input type (notebook, file, repo URL)
    # 2. Run appropriate adapter
    # 3. Run analysis pipeline
    # 4. Output JSON report


def cmd_repair(args):
    """Run LLM-based repair on a session's findings."""
    print(f"[QALLM] Repairing session: {args.session_id}")
    print("[QALLM] TODO: wire up repair service")


def cmd_verify(args):
    """Run RL-guided test generation on a session's code."""
    print(f"[QALLM] Verifying session: {args.session_id}")
    print("[QALLM] TODO: implement RL verification loop (core thesis contribution)")


def cmd_server(args):
    """Start the FastAPI web server."""
    import uvicorn

    print(f"[QALLM] Starting server on http://localhost:{args.port}")
    uvicorn.run(
        "qallm.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def main():
    parser = argparse.ArgumentParser(
        prog="qallm",
        description="QALLM — Quality Assessment of AI-Generated Code",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # analyse
    p_analyse = sub.add_parser("analyse", help="Run static analysis")
    p_analyse.add_argument("input", help="Notebook (.ipynb), Python file/dir, or Git URL")
    p_analyse.add_argument("--tools", nargs="*", help="Tools to run (bandit, ruff, radon, trufflehog)")
    p_analyse.add_argument("--output", "-o", help="Output file (default: stdout)")
    p_analyse.set_defaults(func=cmd_analyse)

    # repair
    p_repair = sub.add_parser("repair", help="Run LLM-based code repair")
    p_repair.add_argument("session_id", help="Session ID from a previous analysis")
    p_repair.add_argument("--provider", help="LLM provider (auto, openai, anthropic, ollama)")
    p_repair.set_defaults(func=cmd_repair)

    # verify
    p_verify = sub.add_parser("verify", help="Run RL-guided test generation")
    p_verify.add_argument("session_id", help="Session ID from a previous analysis")
    p_verify.add_argument("--rounds", type=int, default=5, help="Number of RL feedback rounds (default: 5)")
    p_verify.set_defaults(func=cmd_verify)

    # server
    p_server = sub.add_parser("server", help="Start the web server")
    p_server.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    p_server.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    p_server.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    p_server.set_defaults(func=cmd_server)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

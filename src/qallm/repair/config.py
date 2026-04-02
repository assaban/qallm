import os

from pydantic import BaseModel


class Settings(BaseModel):
    DATA_DIR: str = os.getenv("DATA_DIR", "data")

    # LLM — OpenAI
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # LLM — Anthropic
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    # LLM — Ollama (local)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma3:4b")

    # LLM — shared
    LLM_DEFAULT_MODEL: str = os.getenv("LLM_DEFAULT_MODEL", "gpt-4o-mini")
    LLM_STRONG_MODEL: str = os.getenv("LLM_STRONG_MODEL", "gpt-5-mini")
    LLM_FAST_MODEL: str = os.getenv("LLM_FAST_MODEL", "gpt-4o-mini")
    TOKEN_BUDGET: int = int(os.getenv("TOKEN_BUDGET", "20000"))
    MAX_REPAIR_ISSUES: int = int(os.getenv("MAX_REPAIR_ISSUES", "10"))

    # Storage (local only for PoC)
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")


settings = Settings()

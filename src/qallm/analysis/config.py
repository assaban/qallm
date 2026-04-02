import os

from pydantic import BaseModel


class Settings(BaseModel):
    DATA_DIR: str = os.getenv("DATA_DIR", "data")

    # Storage (local only for PoC)
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")


settings = Settings()

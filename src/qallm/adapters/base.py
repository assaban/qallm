from __future__ import annotations

from abc import ABC, abstractmethod


class InputAdapter(ABC):
    """Strategy interface for ingesting a source into a session workspace."""

    @abstractmethod
    def ingest(self, input_value: str) -> str:
        """Prepare a session workspace and return the session id."""
        raise NotImplementedError

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AbstractGameStorage(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        """Prepare the storage backend."""

    @abstractmethod
    async def close(self) -> None:
        """Release storage resources."""

    @abstractmethod
    async def save_state(self, state: dict[str, Any]) -> None:
        """Persist the full game state."""

    @abstractmethod
    async def load_state(self, game_id: str) -> Optional[dict[str, Any]]:
        """Load the full game state."""

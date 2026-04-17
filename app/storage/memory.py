from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from app.storage.base import AbstractGameStorage


class MemoryGameStorage(AbstractGameStorage):
    def __init__(self) -> None:
        self._games: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def save_state(self, state: dict[str, Any]) -> None:
        self._games[state["id"]] = deepcopy(state)

    async def load_state(self, game_id: str) -> Optional[dict[str, Any]]:
        state = self._games.get(game_id)
        return deepcopy(state) if state is not None else None

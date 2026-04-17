from __future__ import annotations

from typing import Any, Optional

from app.storage.base import AbstractGameStorage
from app.storage.postgres_repository import PostgresGameRepository
from app.storage.redis_cache import RedisGameCache


class GameStorage(AbstractGameStorage):
    def __init__(self, redis_cache: RedisGameCache, postgres_repository: PostgresGameRepository) -> None:
        self._redis_cache = redis_cache
        self._postgres_repository = postgres_repository

    async def initialize(self) -> None:
        await self._redis_cache.ping()
        await self._postgres_repository.initialize()

    async def close(self) -> None:
        await self._redis_cache.close()
        await self._postgres_repository.close()

    async def save_state(self, state: dict[str, Any]) -> None:
        await self._postgres_repository.save_state(state)
        await self._redis_cache.save_state(state)

    async def load_state(self, game_id: str) -> Optional[dict[str, Any]]:
        state = await self._redis_cache.load_state(game_id)
        if state is not None:
            return state

        state = await self._postgres_repository.load_state(game_id)
        if state is not None:
            await self._redis_cache.save_state(state)
        return state

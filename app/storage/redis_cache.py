from __future__ import annotations

import json
from typing import Any, Optional

from redis.asyncio import Redis


class RedisGameCache:
    def __init__(self, redis_url: str, ttl_seconds: int = 60 * 60 * 24) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = ttl_seconds

    async def ping(self) -> None:
        await self._redis.ping()

    async def close(self) -> None:
        await self._redis.aclose()

    async def save_state(self, state: dict[str, Any]) -> None:
        key = self._key(state["id"])
        await self._redis.set(key, json.dumps(state), ex=self._ttl_seconds)

    async def load_state(self, game_id: str) -> Optional[dict[str, Any]]:
        raw_state = await self._redis.get(self._key(game_id))
        if raw_state is None:
            return None
        return json.loads(raw_state)

    async def delete_state(self, game_id: str) -> None:
        await self._redis.delete(self._key(game_id))

    @staticmethod
    def _key(game_id: str) -> str:
        return f"game:{game_id}:state"

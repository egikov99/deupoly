from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

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

    async def create_user(
        self,
        username: str,
        password_hash: str,
        password_salt: str,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        return await self._postgres_repository.create_user(
            user_id=str(uuid4()),
            username=username,
            password_hash=password_hash,
            password_salt=password_salt,
            is_admin=is_admin,
        )

    async def get_user_by_username(self, username: str) -> Optional[dict[str, Any]]:
        return await self._postgres_repository.get_user_by_username(username)

    async def get_user_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        return await self._postgres_repository.get_user_by_id(user_id)

    async def list_users(self) -> list[dict[str, Any]]:
        return await self._postgres_repository.list_users()

    async def set_user_admin(self, user_id: str, is_admin: bool) -> Optional[dict[str, Any]]:
        return await self._postgres_repository.set_user_admin(user_id=user_id, is_admin=is_admin)

    async def create_session(self, session_token: str, user_id: str, expires_at: str) -> None:
        await self._postgres_repository.create_session(session_token=session_token, user_id=user_id, expires_at=expires_at)

    async def get_user_by_session(self, session_token: str) -> Optional[dict[str, Any]]:
        return await self._postgres_repository.get_user_by_session(session_token)

    async def delete_session(self, session_token: str) -> None:
        await self._postgres_repository.delete_session(session_token)

    async def save_membership(self, game_id: str, user_id: str, player_id: str, player_name: str) -> None:
        await self._postgres_repository.save_membership(
            game_id=game_id,
            user_id=user_id,
            player_id=player_id,
            player_name=player_name,
        )

    async def get_membership(self, game_id: str, user_id: str) -> Optional[dict[str, Any]]:
        return await self._postgres_repository.get_membership(game_id, user_id)

    async def list_memberships(self, game_id: str) -> list[dict[str, Any]]:
        return await self._postgres_repository.list_memberships(game_id)

    async def list_game_summaries(self, user_id: str) -> list[dict[str, Any]]:
        return await self._postgres_repository.list_game_summaries(user_id)

    async def save_game_results(self, game_id: str, results: list[dict[str, Any]]) -> None:
        await self._postgres_repository.save_game_results(game_id=game_id, results=results)

    async def get_user_stats(self, user_id: str) -> dict[str, int]:
        return await self._postgres_repository.get_user_stats(user_id)

    async def delete_game(self, game_id: str, keep_results: bool = True) -> None:
        await self._postgres_repository.delete_game(game_id=game_id, keep_results=keep_results)
        await self._redis_cache.delete_state(game_id)

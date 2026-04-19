from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from psycopg.errors import UniqueViolation

from app.core.exceptions import AuthenticationError, ConflictError
from app.storage.base import AbstractGameStorage


class AuthService:
    def __init__(self, storage: AbstractGameStorage, session_ttl_days: int) -> None:
        self._storage = storage
        self._session_ttl_days = session_ttl_days

    async def register(self, username: str, password: str, is_admin: bool = False) -> dict[str, Any]:
        existing = await self._storage.get_user_by_username(username)
        if existing is not None:
            raise ConflictError("Пользователь с таким логином уже существует.")

        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password=password, salt=salt)
        try:
            user = await self._storage.create_user(
                username=username.strip(),
                password_hash=password_hash,
                password_salt=salt,
                is_admin=is_admin,
            )
        except (ValueError, UniqueViolation) as exc:
            raise ConflictError("Пользователь с таким логином уже существует.") from exc
        return await self._to_public_user(user)

    async def login(self, username: str, password: str) -> tuple[dict[str, Any], str, datetime]:
        user = await self._storage.get_user_by_username(username.strip())
        if user is None:
            raise AuthenticationError("Неверный логин или пароль.")

        expected_hash = self._hash_password(password=password, salt=user["password_salt"])
        if not hmac.compare_digest(expected_hash, user["password_hash"]):
            raise AuthenticationError("Неверный логин или пароль.")

        session_token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._session_ttl_days)
        await self._storage.create_session(session_token=session_token, user_id=user["id"], expires_at=expires_at.isoformat())
        return await self._to_public_user(user), session_token, expires_at

    async def get_user_by_session(self, session_token: Optional[str]) -> Optional[dict[str, Any]]:
        if not session_token:
            return None
        user = await self._storage.get_user_by_session(session_token)
        if user is None:
            return None
        return await self._to_public_user(user)

    async def logout(self, session_token: Optional[str]) -> None:
        if not session_token:
            return
        await self._storage.delete_session(session_token)

    async def list_users(self) -> list[dict[str, Any]]:
        users = await self._storage.list_users()
        return [await self._to_public_user(user) for user in users]

    async def ensure_admin(self, username: Optional[str], password: Optional[str]) -> Optional[dict[str, Any]]:
        if not username or not password:
            return None
        existing = await self._storage.get_user_by_username(username)
        if existing is not None:
            if not existing.get("is_admin"):
                updated = await self._storage.set_user_admin(existing["id"], True)
                existing = updated or existing
            return await self._to_public_user(existing)
        return await self.register(username=username, password=password, is_admin=True)

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            120_000,
        ).hex()

    async def _to_public_user(self, user: dict[str, Any]) -> dict[str, Any]:
        stats = await self._storage.get_user_stats(user["id"])
        return {
            "id": user["id"],
            "username": user["username"],
            "is_admin": bool(user.get("is_admin", False)),
            "stats": stats,
        }

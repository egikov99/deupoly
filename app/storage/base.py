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

    @abstractmethod
    async def create_user(
        self,
        username: str,
        password_hash: str,
        password_salt: str,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        """Create a new user account."""

    @abstractmethod
    async def get_user_by_username(self, username: str) -> Optional[dict[str, Any]]:
        """Find a user by username."""

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        """Find a user by id."""

    @abstractmethod
    async def list_users(self) -> list[dict[str, Any]]:
        """Return all users."""

    @abstractmethod
    async def set_user_admin(self, user_id: str, is_admin: bool) -> Optional[dict[str, Any]]:
        """Update admin role for a user."""

    @abstractmethod
    async def update_user(self, user_id: str, username: str, is_admin: bool) -> Optional[dict[str, Any]]:
        """Update editable user profile fields."""

    @abstractmethod
    async def update_user_password(self, user_id: str, password_hash: str, password_salt: str) -> Optional[dict[str, Any]]:
        """Replace user password credentials."""

    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user and related sessions/memberships."""

    @abstractmethod
    async def create_session(self, session_token: str, user_id: str, expires_at: str) -> None:
        """Persist a login session."""

    @abstractmethod
    async def get_user_by_session(self, session_token: str) -> Optional[dict[str, Any]]:
        """Resolve a user from a session token."""

    @abstractmethod
    async def delete_session(self, session_token: str) -> None:
        """Remove a login session."""

    @abstractmethod
    async def save_membership(self, game_id: str, user_id: str, player_id: str, player_name: str) -> None:
        """Bind a user to a specific in-game player."""

    @abstractmethod
    async def get_membership(self, game_id: str, user_id: str) -> Optional[dict[str, Any]]:
        """Resolve a membership for a user in a game."""

    @abstractmethod
    async def list_memberships(self, game_id: str) -> list[dict[str, Any]]:
        """List all memberships for a specific game."""

    @abstractmethod
    async def list_game_summaries(self, user_id: str) -> list[dict[str, Any]]:
        """List all visible games and membership status for the user."""

    @abstractmethod
    async def save_game_results(self, game_id: str, results: list[dict[str, Any]]) -> None:
        """Persist final game results in an idempotent way."""

    @abstractmethod
    async def get_user_stats(self, user_id: str) -> dict[str, int]:
        """Return rating counters for the user."""

    @abstractmethod
    async def delete_game(self, game_id: str, keep_results: bool = True) -> None:
        """Delete game snapshot and memberships."""

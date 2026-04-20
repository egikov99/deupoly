from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app.storage.base import AbstractGameStorage


class MemoryGameStorage(AbstractGameStorage):
    def __init__(self) -> None:
        self._games: dict[str, dict[str, Any]] = {}
        self._users: dict[str, dict[str, Any]] = {}
        self._usernames: dict[str, str] = {}
        self._sessions: dict[str, dict[str, Any]] = {}
        self._memberships: dict[tuple[str, str], dict[str, Any]] = {}
        self._updated_at: dict[str, str] = {}

    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def save_state(self, state: dict[str, Any]) -> None:
        self._games[state["id"]] = deepcopy(state)
        self._updated_at[state["id"]] = datetime.now(timezone.utc).isoformat()

    async def load_state(self, game_id: str) -> Optional[dict[str, Any]]:
        state = self._games.get(game_id)
        return deepcopy(state) if state is not None else None

    async def create_user(
        self,
        username: str,
        password_hash: str,
        password_salt: str,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        normalized = username.strip().lower()
        if normalized in self._usernames:
            raise ValueError("username_exists")
        user = {
            "id": str(uuid4()),
            "username": username.strip(),
            "password_hash": password_hash,
            "password_salt": password_salt,
            "is_admin": is_admin,
        }
        self._users[user["id"]] = deepcopy(user)
        self._usernames[normalized] = user["id"]
        return deepcopy(user)

    async def get_user_by_username(self, username: str) -> Optional[dict[str, Any]]:
        user_id = self._usernames.get(username.strip().lower())
        if user_id is None:
            return None
        user = self._users.get(user_id)
        return deepcopy(user) if user is not None else None

    async def get_user_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        user = self._users.get(user_id)
        return deepcopy(user) if user is not None else None

    async def list_users(self) -> list[dict[str, Any]]:
        return deepcopy(sorted(self._users.values(), key=lambda user: user["username"].lower()))

    async def set_user_admin(self, user_id: str, is_admin: bool) -> Optional[dict[str, Any]]:
        user = self._users.get(user_id)
        if user is None:
            return None
        user["is_admin"] = is_admin
        return deepcopy(user)

    async def update_user(self, user_id: str, username: str, is_admin: bool) -> Optional[dict[str, Any]]:
        user = self._users.get(user_id)
        if user is None:
            return None
        normalized = username.strip().lower()
        existing_user_id = self._usernames.get(normalized)
        if existing_user_id is not None and existing_user_id != user_id:
            raise ValueError("username_exists")

        old_normalized = user["username"].strip().lower()
        self._usernames.pop(old_normalized, None)
        self._usernames[normalized] = user_id
        user["username"] = username.strip()
        user["is_admin"] = is_admin
        return deepcopy(user)

    async def update_user_password(self, user_id: str, password_hash: str, password_salt: str) -> Optional[dict[str, Any]]:
        user = self._users.get(user_id)
        if user is None:
            return None
        user["password_hash"] = password_hash
        user["password_salt"] = password_salt
        self._sessions = {
            token: session for token, session in self._sessions.items() if session["user_id"] != user_id
        }
        return deepcopy(user)

    async def delete_user(self, user_id: str) -> bool:
        user = self._users.pop(user_id, None)
        if user is None:
            return False
        self._usernames.pop(user["username"].strip().lower(), None)
        self._sessions = {
            token: session for token, session in self._sessions.items() if session["user_id"] != user_id
        }
        self._memberships = {
            key: membership for key, membership in self._memberships.items() if key[1] != user_id
        }
        if hasattr(self, "_results"):
            self._results = {
                key: result for key, result in self._results.items() if key[1] != user_id
            }
        return True

    async def create_session(self, session_token: str, user_id: str, expires_at: str) -> None:
        self._sessions[session_token] = {"session_token": session_token, "user_id": user_id, "expires_at": expires_at}

    async def get_user_by_session(self, session_token: str) -> Optional[dict[str, Any]]:
        session = self._sessions.get(session_token)
        if session is None:
            return None
        if session["expires_at"] <= datetime.now(timezone.utc).isoformat():
            self._sessions.pop(session_token, None)
            return None
        return await self.get_user_by_id(session["user_id"])

    async def delete_session(self, session_token: str) -> None:
        self._sessions.pop(session_token, None)

    async def save_membership(self, game_id: str, user_id: str, player_id: str, player_name: str) -> None:
        self._memberships[(game_id, user_id)] = {
            "game_id": game_id,
            "user_id": user_id,
            "player_id": player_id,
            "player_name": player_name,
        }

    async def get_membership(self, game_id: str, user_id: str) -> Optional[dict[str, Any]]:
        membership = self._memberships.get((game_id, user_id))
        return deepcopy(membership) if membership is not None else None

    async def list_memberships(self, game_id: str) -> list[dict[str, Any]]:
        memberships = [value for (membership_game_id, _user_id), value in self._memberships.items() if membership_game_id == game_id]
        return deepcopy(memberships)

    async def list_game_summaries(self, user_id: str) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for game_id, state in self._games.items():
            membership = self._memberships.get((game_id, user_id))
            summaries.append(
                {
                    "game_id": game_id,
                    "name": state.get("name", "Новый стол"),
                    "phase": state["phase"],
                    "round": state["round"],
                    "player_count": len(state["players"]),
                    "max_players": state["max_players"],
                    "players": [player["name"] for player in state["players"]],
                    "joined": membership is not None,
                    "player_id": membership["player_id"] if membership else None,
                    "player_name": membership["player_name"] if membership else None,
                    "can_join": membership is not None or len(state["players"]) < state["max_players"],
                    "can_start": membership is not None and state["phase"] == "waiting_for_players" and len(state["players"]) >= 2,
                    "updated_at": self._updated_at.get(game_id),
                }
            )
        summaries.sort(key=lambda item: item["updated_at"] or "", reverse=True)
        return deepcopy(summaries)

    async def save_game_results(self, game_id: str, results: list[dict[str, Any]]) -> None:
        if not hasattr(self, "_results"):
            self._results: dict[tuple[str, str], dict[str, Any]] = {}
        for result in results:
            self._results[(game_id, result["user_id"])] = {
                "game_id": game_id,
                "user_id": result["user_id"],
                "result": result["result"],
            }

    async def get_user_stats(self, user_id: str) -> dict[str, int]:
        results = getattr(self, "_results", {})
        games_played = 0
        wins = 0
        losses = 0
        for (_, result_user_id), result in results.items():
            if result_user_id != user_id:
                continue
            games_played += 1
            if result["result"] == "win":
                wins += 1
            elif result["result"] == "loss":
                losses += 1

        current_games = 0
        for (game_id, membership_user_id), _membership in self._memberships.items():
            if membership_user_id != user_id:
                continue
            game = self._games.get(game_id)
            if game is not None and game["phase"] != "finished":
                current_games += 1

        return {
            "games_played": games_played,
            "current_games": current_games,
            "wins": wins,
            "losses": losses,
        }

    async def delete_game(self, game_id: str, keep_results: bool = True) -> None:
        self._games.pop(game_id, None)
        self._updated_at.pop(game_id, None)
        self._memberships = {
            key: value for key, value in self._memberships.items() if key[0] != game_id
        }
        if not keep_results and hasattr(self, "_results"):
            self._results = {
                key: value for key, value in self._results.items() if key[0] != game_id
            }

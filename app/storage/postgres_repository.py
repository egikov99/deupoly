from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from psycopg import AsyncConnection
from psycopg.rows import dict_row


class PostgresGameRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def initialize(self) -> None:
        async with await AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS game_snapshots (
                        game_id UUID PRIMARY KEY,
                        state JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id UUID PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        password_salt TEXT NOT NULL,
                        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                await cursor.execute(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
                )
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        session_token TEXT PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        expires_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS game_memberships (
                        game_id UUID NOT NULL,
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        player_id UUID NOT NULL,
                        player_name TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (game_id, user_id),
                        UNIQUE (game_id, player_id)
                    )
                    """
                )
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS game_results (
                        game_id UUID NOT NULL,
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        result TEXT NOT NULL CHECK (result IN ('win', 'loss')),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (game_id, user_id)
                    )
                    """
                )
            await connection.commit()

    async def close(self) -> None:
        return None

    async def save_state(self, state: dict[str, Any]) -> None:
        async with await AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO game_snapshots (game_id, state)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (game_id) DO UPDATE
                    SET state = EXCLUDED.state,
                        updated_at = NOW()
                    """,
                    (state["id"], json.dumps(state)),
                )
            await connection.commit()

    async def load_state(self, game_id: str) -> Optional[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT state FROM game_snapshots WHERE game_id = %s",
                    (game_id,),
                )
                row = await cursor.fetchone()

        if row is None:
            return None
        return row["state"]

    async def create_user(
        self,
        user_id: str,
        username: str,
        password_hash: str,
        password_salt: str,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO users (id, username, password_hash, password_salt, is_admin)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id::text AS id, username, password_hash, password_salt, is_admin
                    """,
                    (user_id, username, password_hash, password_salt, is_admin),
                )
                row = await cursor.fetchone()
            await connection.commit()
        if row is None:
            raise RuntimeError("Не удалось создать пользователя.")
        return row

    async def get_user_by_username(self, username: str) -> Optional[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id::text AS id, username, password_hash, password_salt, is_admin
                    FROM users
                    WHERE lower(username) = lower(%s)
                    """,
                    (username,),
                )
                row = await cursor.fetchone()
        return row

    async def get_user_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id::text AS id, username, password_hash, password_salt, is_admin
                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                row = await cursor.fetchone()
        return row

    async def list_users(self) -> list[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id::text AS id, username, password_hash, password_salt, is_admin
                    FROM users
                    ORDER BY lower(username)
                    """
                )
                rows = await cursor.fetchall()
        return rows

    async def set_user_admin(self, user_id: str, is_admin: bool) -> Optional[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE users
                    SET is_admin = %s
                    WHERE id = %s
                    RETURNING id::text AS id, username, password_hash, password_salt, is_admin
                    """,
                    (is_admin, user_id),
                )
                row = await cursor.fetchone()
            await connection.commit()
        return row

    async def update_user(self, user_id: str, username: str, is_admin: bool) -> Optional[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE users
                    SET username = %s,
                        is_admin = %s
                    WHERE id = %s
                    RETURNING id::text AS id, username, password_hash, password_salt, is_admin
                    """,
                    (username, is_admin, user_id),
                )
                row = await cursor.fetchone()
            await connection.commit()
        return row

    async def update_user_password(self, user_id: str, password_hash: str, password_salt: str) -> Optional[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE users
                    SET password_hash = %s,
                        password_salt = %s
                    WHERE id = %s
                    RETURNING id::text AS id, username, password_hash, password_salt, is_admin
                    """,
                    (password_hash, password_salt, user_id),
                )
                row = await cursor.fetchone()
                if row is not None:
                    await cursor.execute("DELETE FROM user_sessions WHERE user_id = %s", (user_id,))
            await connection.commit()
        return row

    async def delete_user(self, user_id: str) -> bool:
        async with await AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                deleted = cursor.rowcount > 0
            await connection.commit()
        return deleted

    async def create_session(self, session_token: str, user_id: str, expires_at: str) -> None:
        async with await AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO user_sessions (session_token, user_id, expires_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (session_token) DO UPDATE
                    SET user_id = EXCLUDED.user_id,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (session_token, user_id, expires_at),
                )
            await connection.commit()

    async def get_user_by_session(self, session_token: str) -> Optional[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT u.id::text AS id, u.username, u.password_hash, u.password_salt, u.is_admin, s.expires_at
                    FROM user_sessions s
                    JOIN users u ON u.id = s.user_id
                    WHERE s.session_token = %s
                    """,
                    (session_token,),
                )
                row = await cursor.fetchone()
                if row is None:
                    return None
                expires_at = row["expires_at"]
                if expires_at <= datetime.now(timezone.utc):
                    await cursor.execute("DELETE FROM user_sessions WHERE session_token = %s", (session_token,))
                    await connection.commit()
                    return None
        row.pop("expires_at", None)
        return row

    async def delete_session(self, session_token: str) -> None:
        async with await AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("DELETE FROM user_sessions WHERE session_token = %s", (session_token,))
            await connection.commit()

    async def save_membership(self, game_id: str, user_id: str, player_id: str, player_name: str) -> None:
        async with await AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO game_memberships (game_id, user_id, player_id, player_name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (game_id, user_id) DO UPDATE
                    SET player_id = EXCLUDED.player_id,
                        player_name = EXCLUDED.player_name
                    """,
                    (game_id, user_id, player_id, player_name),
                )
            await connection.commit()

    async def get_membership(self, game_id: str, user_id: str) -> Optional[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT game_id::text AS game_id, user_id::text AS user_id, player_id::text AS player_id, player_name
                    FROM game_memberships
                    WHERE game_id = %s AND user_id = %s
                    """,
                    (game_id, user_id),
                )
                row = await cursor.fetchone()
        return row

    async def list_memberships(self, game_id: str) -> list[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT game_id::text AS game_id, user_id::text AS user_id, player_id::text AS player_id, player_name
                    FROM game_memberships
                    WHERE game_id = %s
                    """,
                    (game_id,),
                )
                rows = await cursor.fetchall()
        return rows

    async def list_game_summaries(self, user_id: str) -> list[dict[str, Any]]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT
                        gs.game_id::text AS game_id,
                        gs.state,
                        gs.updated_at,
                        gm.player_id::text AS player_id,
                        gm.player_name
                    FROM game_snapshots gs
                    LEFT JOIN game_memberships gm
                      ON gm.game_id = gs.game_id
                     AND gm.user_id = %s
                    ORDER BY gs.updated_at DESC
                    """,
                    (user_id,),
                )
                rows = await cursor.fetchall()

        summaries: list[dict[str, Any]] = []
        for row in rows:
            state = row["state"]
            joined = row["player_id"] is not None
            summaries.append(
                {
                    "game_id": row["game_id"],
                    "name": state.get("name", "Новый стол"),
                    "phase": state["phase"],
                    "round": state["round"],
                    "player_count": len(state["players"]),
                    "max_players": state["max_players"],
                    "players": [player["name"] for player in state["players"]],
                    "joined": joined,
                    "player_id": row["player_id"],
                    "player_name": row["player_name"],
                    "can_join": joined or len(state["players"]) < state["max_players"],
                    "can_start": joined and state["phase"] == "waiting_for_players" and len(state["players"]) >= 2,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
            )
        return summaries

    async def save_game_results(self, game_id: str, results: list[dict[str, Any]]) -> None:
        if not results:
            return
        async with await AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                for result in results:
                    await cursor.execute(
                        """
                        INSERT INTO game_results (game_id, user_id, result)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (game_id, user_id) DO UPDATE
                        SET result = EXCLUDED.result
                        """,
                        (game_id, result["user_id"], result["result"]),
                    )
            await connection.commit()

    async def get_user_stats(self, user_id: str) -> dict[str, int]:
        async with await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT
                        COUNT(*)::int AS games_played,
                        COUNT(*) FILTER (WHERE result = 'win')::int AS wins,
                        COUNT(*) FILTER (WHERE result = 'loss')::int AS losses
                    FROM game_results
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                result_row = await cursor.fetchone()
                await cursor.execute(
                    """
                    SELECT COUNT(*)::int AS current_games
                    FROM game_memberships gm
                    JOIN game_snapshots gs ON gs.game_id = gm.game_id
                    WHERE gm.user_id = %s
                      AND (gs.state->>'phase') <> 'finished'
                    """,
                    (user_id,),
                )
                current_row = await cursor.fetchone()

        return {
            "games_played": result_row["games_played"] if result_row else 0,
            "current_games": current_row["current_games"] if current_row else 0,
            "wins": result_row["wins"] if result_row else 0,
            "losses": result_row["losses"] if result_row else 0,
        }

    async def delete_game(self, game_id: str, keep_results: bool = True) -> None:
        async with await AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("DELETE FROM game_memberships WHERE game_id = %s", (game_id,))
                await cursor.execute("DELETE FROM game_snapshots WHERE game_id = %s", (game_id,))
                if not keep_results:
                    await cursor.execute("DELETE FROM game_results WHERE game_id = %s", (game_id,))
            await connection.commit()

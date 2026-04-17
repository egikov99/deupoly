from __future__ import annotations

import json
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

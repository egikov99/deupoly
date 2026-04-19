from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass
class VideoRoomSession:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    participants: dict[str, dict[str, Any]] = field(default_factory=dict)


class VideoCallManager:
    def __init__(self) -> None:
        self._rooms: dict[str, VideoRoomSession] = {}

    async def connect(self, game_id: str, user: dict[str, Any], player: dict[str, Any], websocket: WebSocket) -> list[dict[str, Any]]:
        room = self._rooms.setdefault(game_id, VideoRoomSession())
        participant = {
            "user_id": user["id"],
            "player_id": player["player_id"],
            "username": user["username"],
            "player_name": player["player_name"],
            "socket": websocket,
        }
        async with room.lock:
            existing = [
                self._participant_public_info(item)
                for user_id, item in room.participants.items()
                if user_id != user["id"]
            ]
            room.participants[user["id"]] = participant
        await self._broadcast(
            game_id,
            {
                "type": "participant_joined",
                "participant": self._participant_public_info(participant),
            },
            exclude_user_id=user["id"],
        )
        return existing

    async def disconnect(self, game_id: str, user_id: str, websocket: WebSocket) -> None:
        room = self._rooms.get(game_id)
        if room is None:
            return

        should_delete = False
        async with room.lock:
            participant = room.participants.get(user_id)
            if participant is None or participant["socket"] is not websocket:
                return
            room.participants.pop(user_id, None)
            should_delete = not room.participants

        await self._broadcast(
            game_id,
            {
                "type": "participant_left",
                "user_id": user_id,
            },
            exclude_user_id=user_id,
        )

        if should_delete:
            self._rooms.pop(game_id, None)

    async def relay_signal(self, game_id: str, from_user: dict[str, Any], target_user_id: str, signal: dict[str, Any]) -> None:
        room = self._rooms.get(game_id)
        if room is None:
            return

        target_socket = None
        async with room.lock:
            target = room.participants.get(target_user_id)
            if target is not None:
                target_socket = target["socket"]

        if target_socket is None:
            return

        await target_socket.send_json(
            {
                "type": "signal",
                "from_user_id": from_user["id"],
                "from_username": from_user["username"],
                "signal": signal,
            }
        )

    async def _broadcast(self, game_id: str, payload: dict[str, Any], exclude_user_id: str | None = None) -> None:
        room = self._rooms.get(game_id)
        if room is None:
            return

        async with room.lock:
            recipients = [
                participant["socket"]
                for user_id, participant in room.participants.items()
                if user_id != exclude_user_id
            ]

        for socket in recipients:
            try:
                await socket.send_json(payload)
            except Exception:
                continue

    def _participant_public_info(self, participant: dict[str, Any]) -> dict[str, Any]:
        return {
            "user_id": participant["user_id"],
            "player_id": participant["player_id"],
            "username": participant["username"],
            "player_name": participant["player_name"],
        }

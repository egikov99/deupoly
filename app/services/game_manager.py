from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

from fastapi import WebSocket

from app.core.engine import GameEngine
from app.core.exceptions import GameNotFoundError, InvalidActionError
from app.models.domain import Player
from app.models.messages import ClientMessage, ServerEvent, ServerEventType
from app.storage.base import AbstractGameStorage


@dataclass
class GameSession:
    engine: GameEngine
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    connections: dict[str, set[WebSocket]] = field(default_factory=dict)


class GameManager:
    def __init__(self, storage: AbstractGameStorage) -> None:
        self._storage = storage
        self._games: dict[str, GameSession] = {}

    async def create_game(self, max_players: int = 4) -> dict[str, Any]:
        game_id = str(uuid4())
        session = GameSession(engine=GameEngine(game_id=game_id, max_players=max_players))
        self._games[game_id] = session
        await self._persist_session(session)
        return {"game_id": game_id, "state": session.engine.serialize_state()}

    async def get_session(self, game_id: str) -> GameSession:
        session = self._games.get(game_id)
        if session is not None:
            return session

        state = await self._storage.load_state(game_id)
        if state is None:
            raise GameNotFoundError(f"Game {game_id} not found.")

        session = GameSession(engine=GameEngine.from_state(state))
        self._games[game_id] = session
        return session

    async def get_state(self, game_id: str) -> dict[str, Any]:
        session = await self.get_session(game_id)
        return session.engine.serialize_state()

    async def add_player(self, game_id: str, name: str) -> dict[str, Any]:
        session = await self.get_session(game_id)
        async with session.lock:
            player = session.engine.add_player(name)
            await self._persist_session(session)
            state = session.engine.serialize_state()
        await self.broadcast_state(game_id)
        return {"player": player.model_dump(mode="json"), "state": state}

    async def start_game(self, game_id: str) -> dict[str, Any]:
        session = await self.get_session(game_id)
        async with session.lock:
            events = session.engine.start_game()
            await self._persist_session(session)
        await self.broadcast_events(game_id, events)
        return {"state": session.engine.serialize_state()}

    async def handle_message(self, game_id: str, player_id: str, message: ClientMessage) -> list[ServerEvent]:
        session = await self.get_session(game_id)
        async with session.lock:
            events = session.engine.process_action(player_id=player_id, action=message.action, payload=message.payload)
            await self._persist_session(session)
        await self.broadcast_events(game_id, events)
        return events

    async def register(self, game_id: str, player_id: str, websocket: WebSocket) -> None:
        session = await self.get_session(game_id)
        player = self._get_player(session, player_id)
        if player is None:
            raise InvalidActionError("Unknown player_id for this game.")
        session.connections.setdefault(player_id, set()).add(websocket)
        player.is_connected = True
        await self._persist_session(session)
        await websocket.send_json(
            ServerEvent(
                type=ServerEventType.GAME_STATE_UPDATE,
                game_id=game_id,
                state=session.engine.serialize_state(),
            ).model_dump(mode="json")
        )
        await self.broadcast_state(game_id)

    async def unregister(self, game_id: str, player_id: str, websocket: WebSocket) -> None:
        session = await self.get_session(game_id)
        connections = session.connections.get(player_id)
        if connections:
            connections.discard(websocket)
            if not connections:
                session.connections.pop(player_id, None)
        player = self._get_player(session, player_id)
        if player is not None and not session.connections.get(player_id):
            player.is_connected = False
        await self._persist_session(session)
        await self.broadcast_state(game_id)

    async def broadcast_state(self, game_id: str) -> None:
        session = await self.get_session(game_id)
        event = ServerEvent(
            type=ServerEventType.GAME_STATE_UPDATE,
            game_id=game_id,
            state=session.engine.serialize_state(),
        )
        await self._broadcast(game_id, event)

    async def broadcast_events(self, game_id: str, events: list[ServerEvent]) -> None:
        for event in events:
            await self._broadcast(game_id, event)

    async def send_error(self, websocket: WebSocket, game_id: str, message: str) -> None:
        await websocket.send_json(
            ServerEvent(type=ServerEventType.ERROR, game_id=game_id, payload={"message": message}).model_dump(
                mode="json"
            )
        )

    async def _broadcast(self, game_id: str, event: ServerEvent) -> None:
        session = await self.get_session(game_id)
        disconnected: list[tuple[str, WebSocket]] = []

        for player_id, sockets in session.connections.items():
            for websocket in list(sockets):
                try:
                    await websocket.send_json(event.model_dump(mode="json"))
                except Exception:
                    disconnected.append((player_id, websocket))

        for player_id, websocket in disconnected:
            await self.unregister(game_id, player_id, websocket)

    async def _persist_session(self, session: GameSession) -> None:
        await self._storage.save_state(session.engine.serialize_state())

    def _get_player(self, session: GameSession, player_id: str) -> Optional[Player]:
        for player in session.engine.game.players:
            if player.id == player_id:
                return player
        return None

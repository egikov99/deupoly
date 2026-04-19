from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

from fastapi import WebSocket

from app.core.engine import GameEngine
from app.core.exceptions import AuthorizationError, GameNotFoundError, InvalidActionError
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

    async def create_game(
        self,
        user_id: str,
        player_name: str,
        max_players: int = 4,
        table_name: str = "Новый стол",
    ) -> dict[str, Any]:
        game_id = str(uuid4())
        session = GameSession(engine=GameEngine(game_id=game_id, max_players=max_players, name=table_name))
        player = session.engine.add_player(player_name)
        self._games[game_id] = session
        await self._storage.save_membership(
            game_id=game_id,
            user_id=user_id,
            player_id=player.id,
            player_name=player.name,
        )
        await self._persist_session(session)
        return {"game_id": game_id, "player": player.model_dump(mode="json"), "state": session.engine.serialize_state()}

    async def get_session(self, game_id: str) -> GameSession:
        session = self._games.get(game_id)
        if session is not None:
            return session

        state = await self._storage.load_state(game_id)
        if state is None:
            raise GameNotFoundError(f"Игра {game_id} не найдена.")

        session = GameSession(engine=GameEngine.from_state(state))
        self._games[game_id] = session
        return session

    async def get_state(self, game_id: str) -> dict[str, Any]:
        session = await self.get_session(game_id)
        return session.engine.serialize_state()

    async def list_games(self, user_id: str) -> list[dict[str, Any]]:
        return await self._storage.list_game_summaries(user_id)

    async def add_player(self, game_id: str, user_id: str, name: str) -> dict[str, Any]:
        session = await self.get_session(game_id)
        membership = await self._storage.get_membership(game_id=game_id, user_id=user_id)
        if membership is not None:
            player = self._get_player(session, membership["player_id"])
            if player is None:
                raise InvalidActionError("Связанный игрок не найден в состоянии игры.")
            return {"player": player.model_dump(mode="json"), "state": session.engine.serialize_state()}

        async with session.lock:
            player = session.engine.add_player(name)
            await self._storage.save_membership(
                game_id=game_id,
                user_id=user_id,
                player_id=player.id,
                player_name=player.name,
            )
            await self._persist_session(session)
            state = session.engine.serialize_state()
        await self.broadcast_state(game_id)
        return {"player": player.model_dump(mode="json"), "state": state}

    async def start_game(self, game_id: str, user_id: str) -> dict[str, Any]:
        membership = await self._storage.get_membership(game_id=game_id, user_id=user_id)
        if membership is None:
            raise AuthorizationError("Вы не присоединились к этой игре.")
        session = await self.get_session(game_id)
        async with session.lock:
            events = session.engine.start_game()
            await self._persist_session(session)
            await self._store_results_if_finished(session)
        await self.broadcast_events(game_id, events)
        return {"state": session.engine.serialize_state()}

    async def handle_message(self, game_id: str, player_id: str, message: ClientMessage) -> list[ServerEvent]:
        session = await self.get_session(game_id)
        async with session.lock:
            events = session.engine.process_action(player_id=player_id, action=message.action, payload=message.payload)
            await self._persist_session(session)
            await self._store_results_if_finished(session)
        await self.broadcast_events(game_id, events)
        return events

    async def get_membership(self, game_id: str, user_id: str) -> dict[str, Any]:
        membership = await self._storage.get_membership(game_id=game_id, user_id=user_id)
        if membership is None:
            raise AuthorizationError("Вы не присоединились к этой игре.")
        return membership

    async def register(self, game_id: str, user_id: str, websocket: WebSocket) -> None:
        session = await self.get_session(game_id)
        membership = await self.get_membership(game_id=game_id, user_id=user_id)
        player_id = membership["player_id"]
        player = self._get_player(session, player_id)
        if player is None:
            raise InvalidActionError("Неизвестный player_id для этой игры.")
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
        try:
            session = await self.get_session(game_id)
        except GameNotFoundError:
            return
        connections = session.connections.get(player_id)
        if connections:
            connections.discard(websocket)
            if not connections:
                session.connections.pop(player_id, None)
        player = self._get_player(session, player_id)
        if player is not None and not session.connections.get(player_id):
            player.is_connected = False
        await self._persist_session(session)
        if session.engine.game.phase.value == "finished" and not self._has_active_connections(session):
            await self.delete_game(game_id=game_id, keep_results=True)
            return
        await self.broadcast_state(game_id)

    async def delete_game(self, game_id: str, keep_results: bool = True) -> None:
        self._games.pop(game_id, None)
        await self._storage.delete_game(game_id=game_id, keep_results=keep_results)

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

    async def _store_results_if_finished(self, session: GameSession) -> None:
        if session.engine.game.phase.value != "finished":
            return

        memberships = await self._storage.list_memberships(session.engine.game.id)
        if not memberships:
            return

        winner_ids = {player.id for player in session.engine.active_players}
        results = []
        for membership in memberships:
            results.append(
                {
                    "user_id": membership["user_id"],
                    "result": "win" if membership["player_id"] in winner_ids else "loss",
                }
            )
        await self._storage.save_game_results(game_id=session.engine.game.id, results=results)

    def _get_player(self, session: GameSession, player_id: str) -> Optional[Player]:
        for player in session.engine.game.players:
            if player.id == player_id:
                return player
        return None

    def _has_active_connections(self, session: GameSession) -> bool:
        return any(sockets for sockets in session.connections.values())

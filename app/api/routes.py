from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from app.core.exceptions import GameError
from app.models.api import CreateGameRequest, JoinGameRequest
from app.models.messages import ClientMessage
from app.services.game_manager import GameManager


def get_game_manager(request: Request) -> GameManager:
    return request.app.state.game_manager


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/games")
    async def create_game(payload: CreateGameRequest, gm: GameManager = Depends(get_game_manager)) -> dict:
        return await gm.create_game(max_players=payload.max_players)

    @router.get("/games/{game_id}")
    async def get_game(game_id: str, gm: GameManager = Depends(get_game_manager)) -> dict:
        return {"game_id": game_id, "state": await gm.get_state(game_id)}

    @router.post("/games/{game_id}/players")
    async def join_game(game_id: str, payload: JoinGameRequest, gm: GameManager = Depends(get_game_manager)) -> dict:
        return await gm.add_player(game_id=game_id, name=payload.name)

    @router.post("/games/{game_id}/start")
    async def start_game(game_id: str, gm: GameManager = Depends(get_game_manager)) -> dict:
        return await gm.start_game(game_id)

    @router.websocket("/ws/games/{game_id}")
    async def game_socket(websocket: WebSocket, game_id: str) -> None:
        gm: GameManager = websocket.app.state.game_manager
        player_id = websocket.query_params.get("player_id")
        if not player_id:
            await websocket.close(code=4400, reason="player_id query parameter is required")
            return

        await websocket.accept()

        try:
            await gm.register(game_id=game_id, player_id=player_id, websocket=websocket)
            while True:
                try:
                    raw_message = await websocket.receive_json()
                    message = ClientMessage.model_validate(raw_message)
                    await gm.handle_message(game_id=game_id, player_id=player_id, message=message)
                except GameError as exc:
                    await gm.send_error(websocket, game_id=game_id, message=str(exc))
        except WebSocketDisconnect:
            await gm.unregister(game_id=game_id, player_id=player_id, websocket=websocket)
        except GameError as exc:
            await gm.send_error(websocket, game_id=game_id, message=str(exc))
            await websocket.close(code=4400, reason=str(exc))
        except Exception as exc:
            await gm.send_error(websocket, game_id=game_id, message=f"Unexpected server error: {exc}")
            await websocket.close(code=1011, reason="Unexpected server error")

    return router

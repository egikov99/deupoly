from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.core.exceptions import AuthenticationError, GameError
from app.core.exceptions import AuthorizationError
from app.models.api import (
    AdminCreateUserRequest,
    AuthResponse,
    CreateGameRequest,
    GameSummary,
    JoinGameRequest,
    UserCredentialsRequest,
    UserSummary,
)
from app.models.messages import ClientMessage
from app.services.auth_service import AuthService
from app.services.game_manager import GameManager


settings = get_settings()


def get_game_manager(request: Request) -> GameManager:
    return request.app.state.game_manager


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


async def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    session_token = request.cookies.get(settings.session_cookie_name)
    user = await auth_service.get_user_by_session(session_token)
    if user is None:
        raise AuthenticationError("Требуется вход в систему.")
    return user


async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("is_admin"):
        raise AuthorizationError("Требуются права администратора.")
    return current_user


def _set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/auth/register", response_model=AuthResponse)
    async def register(
        payload: UserCredentialsRequest,
        response: Response,
        auth_service: AuthService = Depends(get_auth_service),
    ) -> dict:
        await auth_service.register(username=payload.username, password=payload.password)
        user, session_token, _ = await auth_service.login(username=payload.username, password=payload.password)
        _set_session_cookie(response, session_token)
        return {"user": user}

    @router.post("/auth/login", response_model=AuthResponse)
    async def login(
        payload: UserCredentialsRequest,
        response: Response,
        auth_service: AuthService = Depends(get_auth_service),
    ) -> dict:
        user, session_token, _ = await auth_service.login(username=payload.username, password=payload.password)
        _set_session_cookie(response, session_token)
        return {"user": user}

    @router.post("/auth/logout")
    async def logout(
        request: Request,
        response: Response,
        auth_service: AuthService = Depends(get_auth_service),
    ) -> dict[str, bool]:
        await auth_service.logout(request.cookies.get(settings.session_cookie_name))
        _clear_session_cookie(response)
        return {"ok": True}

    @router.get("/auth/me", response_model=AuthResponse)
    async def me(current_user: dict = Depends(get_current_user)) -> dict:
        return {"user": current_user}

    @router.get("/admin/users", response_model=list[UserSummary])
    async def list_users(_: dict = Depends(get_admin_user), auth_service: AuthService = Depends(get_auth_service)) -> list[dict]:
        return await auth_service.list_users()

    @router.post("/admin/users", response_model=AuthResponse)
    async def create_user_by_admin(
        payload: AdminCreateUserRequest,
        _: dict = Depends(get_admin_user),
        auth_service: AuthService = Depends(get_auth_service),
    ) -> dict:
        user = await auth_service.register(
            username=payload.username,
            password=payload.password,
            is_admin=payload.is_admin,
        )
        return {"user": user}

    @router.get("/games", response_model=list[GameSummary])
    async def list_games(current_user: dict = Depends(get_current_user), gm: GameManager = Depends(get_game_manager)) -> list[dict]:
        return await gm.list_games(user_id=current_user["id"])

    @router.post("/games")
    async def create_game(
        payload: CreateGameRequest,
        current_user: dict = Depends(get_current_user),
        gm: GameManager = Depends(get_game_manager),
    ) -> dict:
        player_name = payload.player_name or current_user["username"]
        return await gm.create_game(user_id=current_user["id"], player_name=player_name, max_players=payload.max_players)

    @router.get("/games/{game_id}")
    async def get_game(game_id: str, _: dict = Depends(get_current_user), gm: GameManager = Depends(get_game_manager)) -> dict:
        return {"game_id": game_id, "state": await gm.get_state(game_id)}

    @router.post("/games/{game_id}/players")
    async def join_game(
        game_id: str,
        payload: JoinGameRequest,
        current_user: dict = Depends(get_current_user),
        gm: GameManager = Depends(get_game_manager),
    ) -> dict:
        player_name = payload.name or current_user["username"]
        return await gm.add_player(game_id=game_id, user_id=current_user["id"], name=player_name)

    @router.post("/games/{game_id}/start")
    async def start_game(
        game_id: str,
        current_user: dict = Depends(get_current_user),
        gm: GameManager = Depends(get_game_manager),
    ) -> dict:
        return await gm.start_game(game_id=game_id, user_id=current_user["id"])

    @router.delete("/games/{game_id}")
    async def delete_game(
        game_id: str,
        _: dict = Depends(get_admin_user),
        gm: GameManager = Depends(get_game_manager),
    ) -> dict[str, bool]:
        await gm.delete_game(game_id=game_id, keep_results=False)
        return {"ok": True}

    @router.websocket("/ws/games/{game_id}")
    async def game_socket(websocket: WebSocket, game_id: str) -> None:
        gm: GameManager = websocket.app.state.game_manager
        auth_service: AuthService = websocket.app.state.auth_service
        session_token = websocket.cookies.get(settings.session_cookie_name)
        user = await auth_service.get_user_by_session(session_token)
        if user is None:
            await websocket.close(code=4401, reason="Требуется вход в систему")
            return

        await websocket.accept()

        try:
            membership = await gm.get_membership(game_id=game_id, user_id=user["id"])
            player_id = membership["player_id"]
            await gm.register(game_id=game_id, user_id=user["id"], websocket=websocket)
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
            await gm.send_error(websocket, game_id=game_id, message=f"Непредвиденная ошибка сервера: {exc}")
            await websocket.close(code=1011, reason="Непредвиденная ошибка сервера")

    return router

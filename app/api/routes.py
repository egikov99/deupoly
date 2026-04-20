from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.core.exceptions import AuthenticationError, GameError
from app.core.exceptions import AuthorizationError
from app.models.api import (
    AdminCreateUserRequest,
    AdminResetPasswordRequest,
    AdminUpdateUserRequest,
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
from app.services.video_call_manager import VideoCallManager


settings = get_settings()


def get_game_manager(request: Request) -> GameManager:
    return request.app.state.game_manager


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_video_call_manager(request: Request) -> VideoCallManager:
    return request.app.state.video_call_manager


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


def _build_ice_servers() -> list[dict]:
    ice_servers: list[dict] = []
    if settings.video_stun_urls:
        ice_servers.append({"urls": settings.video_stun_urls})
    if settings.video_turn_url:
        turn_server = {"urls": [settings.video_turn_url]}
        if settings.video_turn_username:
            turn_server["username"] = settings.video_turn_username
        if settings.video_turn_password:
            turn_server["credential"] = settings.video_turn_password
        ice_servers.append(turn_server)
    return ice_servers


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

    @router.get("/video/config")
    async def video_config(_: dict = Depends(get_current_user)) -> dict:
        return {
            "ice_servers": _build_ice_servers(),
            "mesh_mode": True,
        }

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

    @router.put("/admin/users/{user_id}", response_model=AuthResponse)
    async def update_user_by_admin(
        user_id: str,
        payload: AdminUpdateUserRequest,
        admin_user: dict = Depends(get_admin_user),
        auth_service: AuthService = Depends(get_auth_service),
    ) -> dict:
        user = await auth_service.update_user(
            user_id=user_id,
            username=payload.username,
            is_admin=payload.is_admin,
            actor_user_id=admin_user["id"],
        )
        return {"user": user}

    @router.post("/admin/users/{user_id}/reset-password", response_model=AuthResponse)
    async def reset_user_password_by_admin(
        user_id: str,
        payload: AdminResetPasswordRequest,
        _: dict = Depends(get_admin_user),
        auth_service: AuthService = Depends(get_auth_service),
    ) -> dict:
        user = await auth_service.reset_user_password(user_id=user_id, password=payload.password)
        return {"user": user}

    @router.delete("/admin/users/{user_id}")
    async def delete_user_by_admin(
        user_id: str,
        admin_user: dict = Depends(get_admin_user),
        auth_service: AuthService = Depends(get_auth_service),
    ) -> dict[str, bool]:
        await auth_service.delete_user(user_id=user_id, actor_user_id=admin_user["id"])
        return {"ok": True}

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
        table_name = payload.table_name or f"Стол {current_user['username']}"
        return await gm.create_game(
            user_id=current_user["id"],
            player_name=player_name,
            max_players=payload.max_players,
            table_name=table_name,
        )

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

    @router.websocket("/ws/video/{game_id}")
    async def video_socket(websocket: WebSocket, game_id: str) -> None:
        gm: GameManager = websocket.app.state.game_manager
        auth_service: AuthService = websocket.app.state.auth_service
        video_manager: VideoCallManager = websocket.app.state.video_call_manager
        session_token = websocket.cookies.get(settings.session_cookie_name)
        user = await auth_service.get_user_by_session(session_token)
        if user is None:
            await websocket.close(code=4401, reason="Требуется вход в систему")
            return

        try:
            membership = await gm.get_membership(game_id=game_id, user_id=user["id"])
        except GameError as exc:
            await websocket.close(code=4403, reason=str(exc))
            return

        await websocket.accept()
        existing_participants = await video_manager.connect(game_id=game_id, user=user, player=membership, websocket=websocket)
        await websocket.send_json({"type": "participants", "participants": existing_participants})

        try:
            while True:
                message = await websocket.receive_json()
                message_type = message.get("type")
                if message_type == "signal":
                    target_user_id = message.get("target_user_id")
                    signal = message.get("signal")
                    if target_user_id and isinstance(signal, dict):
                        await video_manager.relay_signal(
                            game_id=game_id,
                            from_user=user,
                            target_user_id=target_user_id,
                            signal=signal,
                        )
                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            await video_manager.disconnect(game_id=game_id, user_id=user["id"], websocket=websocket)
        except Exception:
            await video_manager.disconnect(game_id=game_id, user_id=user["id"], websocket=websocket)
            await websocket.close(code=1011, reason="Ошибка видеосоединения")

    return router

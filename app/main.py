from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import get_router
from app.config import get_settings
from app.core.exceptions import GameError, GameNotFoundError
from app.services.game_manager import GameManager
from app.storage.game_storage import GameStorage
from app.storage.postgres_repository import PostgresGameRepository
from app.storage.redis_cache import RedisGameCache


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = GameStorage(
        redis_cache=RedisGameCache(settings.redis_url),
        postgres_repository=PostgresGameRepository(settings.database_url),
    )
    await storage.initialize()
    app.state.game_manager = GameManager(storage=storage)
    try:
        yield
    finally:
        await storage.close()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(get_router(), prefix=settings.api_prefix)

    static_dir = Path(__file__).resolve().parent.parent / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    @app.exception_handler(GameNotFoundError)
    async def game_not_found_handler(_, exc: GameNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(GameError)
    async def game_error_handler(_, exc: GameError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


app = create_app()

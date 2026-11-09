"""FastAPI application entrypoint."""

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import text

from app.api.v1.router import build_api_router
from app.core.config import get_settings
from app.core.csrf import install_csrf
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.database.session import dispose_engine, get_engine
from app.infrastructure.redis import close_redis, get_redis

log = structlog.get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    task: asyncio.Task[None] | None = None
    if settings.run_maintenance_loop:
        from app.modules.orders.maintenance import maintenance_loop

        task = asyncio.create_task(maintenance_loop())
    log.info("startup", environment=settings.environment, payment_provider=settings.payment_provider)
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await close_redis()
        await dispose_engine()


class HealthOut(BaseModel):
    status: str
    environment: str
    payment_provider: str
    mock_payments: bool


class ReadyOut(BaseModel):
    database: bool
    redis: bool


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    install_error_handlers(app)
    install_csrf(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "Idempotency-Key",
            "Accept-Language",
            "X-Client-Type",
        ],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    app.include_router(build_api_router())

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount(settings.media_url_prefix, StaticFiles(directory=upload_dir), name="media")

    @app.get("/health", tags=["health"])
    async def health() -> HealthOut:
        return HealthOut(
            status="ok",
            environment=settings.environment.value,
            payment_provider=settings.payment_provider.value,
            mock_payments=settings.mock_payments_enabled,
        )

    @app.get("/ready", tags=["health"])
    async def ready(response: Response) -> ReadyOut:
        database = redis = False
        with contextlib.suppress(Exception):
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            database = True
        with contextlib.suppress(Exception):
            redis = bool(await get_redis().ping())
        if not (database and redis):
            response.status_code = 503
        return ReadyOut(database=database, redis=redis)

    return app


app = create_app()

"""Test configuration.

Tests run against a real PostgreSQL database and Redis (the same engines used in
production) because the financial guarantees rely on database constraints and
triggers. A fresh ``<db>_test`` database is created and migrated with Alembic at
the start of every session; ledger tables are immutable (no TRUNCATE), so tests
isolate themselves by creating their own users, merchants and orders.
"""

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.engine import make_url

if TYPE_CHECKING:
    from tests.helpers import Client

_BASE_URL = make_url(
    os.environ.get("TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql+asyncpg://marketplace:marketplace@localhost:55432/marketplace"
)
TEST_DB_NAME = f"{_BASE_URL.database}_test"
TEST_DB_URL = _BASE_URL.set(database=TEST_DB_NAME).render_as_string(hide_password=False)

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": TEST_DB_URL,
        "REDIS_URL": os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/15"),
        "PAYMENT_PROVIDER": "mock",
        "RATE_LIMIT_ENABLED": "false",
        "RUN_MAINTENANCE_LOOP": "false",
        "LOG_JSON": "false",
        "LOG_LEVEL": "WARNING",
        "UPLOAD_DIR": str(Path(__file__).parent / ".uploads"),
        "MOCK_AUTO_ACTIVATE_MERCHANTS": "true",
    }
)


def _recreate_database() -> None:
    import asyncio

    import asyncpg

    admin_dsn = _BASE_URL.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)

    async def run() -> None:
        conn = await asyncpg.connect(admin_dsn)
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
        finally:
            await conn.close()

    asyncio.run(run())


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.attributes["database_url"] = TEST_DB_URL
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    _recreate_database()
    _migrate()


@pytest.fixture(scope="session")
async def app(database: None):  # type: ignore[no-untyped-def]
    from app.database.session import dispose_engine
    from app.infrastructure.redis import close_redis, get_redis
    from app.main import create_app

    await get_redis().flushdb()
    application = create_app()
    yield application
    await close_redis()
    await dispose_engine()


@pytest.fixture
async def client(app) -> AsyncIterator["Client"]:  # type: ignore[no-untyped-def]
    import httpx

    from tests.helpers import Client

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield Client(http)


@pytest.fixture
def unique() -> str:
    return uuid.uuid4().hex[:10]

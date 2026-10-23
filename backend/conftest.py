"""BD de pruebas aislada `<nombre>_test` (se crea si falta y se migra)."""

import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Entorno minimo para importar la app sin depender de un `.env` local.
for _k, _v in {
    "CORS_ORIGINS": "http://localhost:3300",
    "INCUBUS_API_URL": "http://incubus.test",
    "LEO_URL": "http://leo.test",
    "LEO_API_URL": "http://leo.test/api/v1",
    "APP_CLIENT_ID": "acuarius",
    "APP_CLIENT_SECRET": "test-secret",
    "PUBLIC_URL": "http://acuarius.test",
    "COOKIE_SECURE": "false",
}.items():
    os.environ.setdefault(_k, _v)


def _prepare_test_database() -> None:
    from app.core.config import get_settings

    url = make_url(get_settings().database_url)
    test_name = f"{url.database}_test"
    admin = url.set(drivername="postgresql", database="postgres")
    import psycopg

    with psycopg.connect(
        admin.render_as_string(hide_password=False), autocommit=True
    ) as conn:
        if not conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (test_name,)
        ).fetchone():
            conn.execute(f'CREATE DATABASE "{test_name}"')
    os.environ["DATABASE_URL"] = url.set(database=test_name).render_as_string(
        hide_password=False
    )
    get_settings.cache_clear()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parent,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
    )


_prepare_test_database()

from app.core.database import engine


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    """Transaccion externa revertida al final; cada violacion de restriccion
    se prueba dentro de un savepoint (`session.begin_nested()`)."""
    async with engine.connect() as connection:
        outer = await connection.begin()
        maker = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with maker() as test_session:
            yield test_session
        await outer.rollback()


pytest_plugins = ["app.testing"]

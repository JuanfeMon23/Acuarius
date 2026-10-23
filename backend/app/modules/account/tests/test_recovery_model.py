"""Integridad de `activation_recovery` y reversibilidad de la migracion 0002."""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.modules.account.models import ActivationRecovery

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[4]


def rec(**kw) -> ActivationRecovery:
    return ActivationRecovery(
        reference=kw.pop("reference", uuid4().hex[:12]),
        reason=kw.pop("reason", "leo_conflict"),
        patient_document_type="CC",
        patient_document_number="123",
        **kw,
    )


async def expect_violation(session, obj, constraint: str) -> None:
    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(obj)
            await session.flush()
    assert constraint in str(exc.value)


@pytest.mark.parametrize(
    "reason", ["leo_conflict", "leo_weak_password", "leo_unavailable", "db_error"]
)
async def test_valid_reasons(session, reason):
    session.add(rec(reason=reason))
    await session.flush()


async def test_reason_invalid(session):
    await expect_violation(
        session, rec(reason="otro"), "ck_activation_recovery_reason_valid"
    )


async def test_reference_unique(session):
    session.add(rec(reference="abc"))
    await session.flush()
    await expect_violation(
        session, rec(reference="abc"), "uq_activation_recovery_reference"
    )


async def test_resolved_before_created_rejected(session):
    await expect_violation(
        session,
        rec(resolved_at=NOW - timedelta(days=1), created_at=NOW),
        "ck_activation_recovery_resolved_after_created",
    )


async def test_resolved_after_created_ok(session):
    session.add(rec(resolved_at=NOW + timedelta(days=1), created_at=NOW))
    await session.flush()


async def test_note_max_length(session):
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            session.add(rec(resolved_note="x" * 201))
            await session.flush()


async def test_partial_index_on_unresolved(session):
    row = (
        await session.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'ix_activation_recovery_unresolved'"
            )
        )
    ).scalar_one()
    assert "resolved_at IS NULL" in row


def _alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
    )


def test_migration_0002_up_down_up():
    # Sin sesion: DDL real sobre la BD de pruebas; termina en head.
    try:
        _alembic("downgrade", "0001")
        _alembic("upgrade", "head")
        _alembic("downgrade", "0001")
    finally:
        _alembic("upgrade", "head")

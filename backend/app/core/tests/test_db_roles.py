"""`deploy/db_roles.sql`: roles de minimo privilegio.

Corre el script contra una BD temporal (`acuarius_roles_test`, migrada con
`MIGRATION_DATABASE_URL` mientras `DATABASE_URL` apunta a un servidor
inexistente, para probar tambien `migrations/env.py`) y verifica con
`SET ROLE` lo que `acuarius_app` puede y no puede hacer. Si los roles no
existian en el servidor, el test los borra al terminar.
"""

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[3]
ROLES_DB = "acuarius_roles_test"
ROLES = ("acuarius_app", "acuarius_migrator")
SCRIPT = (BACKEND_DIR / "deploy" / "db_roles.sql").read_text(encoding="utf-8")
INSUFFICIENT_PRIVILEGE = "42501"


def _dsn(database: str, driver: str) -> str:
    url = make_url(get_settings().database_url).set(
        drivername=driver, database=database
    )
    return url.render_as_string(hide_password=False)


async def _sqlstate(conn: asyncpg.Connection, role: str, sql: str) -> str | None:
    """SQLSTATE con que falla `sql` ejecutado como `role` (None si funciona)."""
    await conn.execute(f"SET ROLE {role}")
    try:
        await conn.execute(sql)
    except asyncpg.PostgresError as exc:
        return exc.sqlstate
    finally:
        await conn.execute("RESET ROLE")
    return None


@pytest_asyncio.fixture(scope="module")
async def roles_db() -> AsyncGenerator[asyncpg.Connection]:
    admin = await asyncpg.connect(_dsn("postgres", "postgresql"))
    existing = {
        r["rolname"]
        for r in await admin.fetch(
            "SELECT rolname FROM pg_roles WHERE rolname = ANY($1)", list(ROLES)
        )
    }
    await admin.execute(f'DROP DATABASE IF EXISTS "{ROLES_DB}" WITH (FORCE)')
    await admin.execute(f'CREATE DATABASE "{ROLES_DB}"')
    conn = None
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env={
                **os.environ,
                "DATABASE_URL": "postgresql+asyncpg://nadie:x@127.0.0.1:1/nada",
                "MIGRATION_DATABASE_URL": _dsn(ROLES_DB, "postgresql+asyncpg"),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        conn = await asyncpg.connect(_dsn(ROLES_DB, "postgresql"))
        await conn.execute(SCRIPT)
        yield conn
    finally:
        if conn is not None:
            await conn.close()
        await admin.execute(f'DROP DATABASE IF EXISTS "{ROLES_DB}" WITH (FORCE)')
        for role in ROLES:
            if role not in existing:
                await admin.execute(f"DROP ROLE IF EXISTS {role}")
        await admin.close()


async def test_alembic_uso_migration_database_url(roles_db) -> None:
    assert await roles_db.fetchval("SELECT count(*) FROM alembic_version") == 1


async def test_el_script_es_idempotente(roles_db) -> None:
    await roles_db.execute(SCRIPT)
    await roles_db.execute(SCRIPT)


async def test_los_roles_no_tienen_privilegios_de_rol(roles_db) -> None:
    for role in ROLES:
        row = await roles_db.fetchrow(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
            "rolbypassrls FROM pg_roles WHERE rolname = $1",
            role,
        )
        assert not any(row.values()), role
    assert not await roles_db.fetchval(
        "SELECT pg_has_role('acuarius_app', 'acuarius_migrator', 'MEMBER')"
    )


async def test_migrator_es_duenio_del_esquema_tablas_y_funciones(roles_db) -> None:
    owners = {
        r["tableowner"]
        for r in await roles_db.fetch(
            "SELECT tableowner FROM pg_tables WHERE schemaname = 'public'"
        )
    }
    assert owners == {"acuarius_migrator"}
    assert (
        await roles_db.fetchval(
            "SELECT pg_get_userbyid(nspowner) FROM pg_namespace "
            "WHERE nspname = 'public'"
        )
        == "acuarius_migrator"
    )
    fn_owners = {
        r["owner"]
        for r in await roles_db.fetch(
            "SELECT pg_get_userbyid(p.proowner) AS owner FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public'"
        )
    }
    assert fn_owners <= {"acuarius_migrator"}


async def test_app_opera_paciente_invitacion_y_secuencias(roles_db) -> None:
    doc = uuid.uuid4().hex[:12]
    await roles_db.execute("SET ROLE acuarius_app")
    try:
        ids = []
        for n in (1, 2):
            ids.append(
                await roles_db.fetchval(
                    "INSERT INTO patients (leo_user_id, document_type, "
                    "document_number, birth_date, display_name) VALUES ($1, 'CC', $2, "
                    "'1990-01-01', 'Roles Test') RETURNING id",
                    uuid.uuid4(),
                    f"{doc}{n}",
                )
            )
        group_id = await roles_db.fetchval(
            "INSERT INTO family_groups (created_by_patient_id) VALUES ($1) "
            "RETURNING id",
            ids[0],
        )
        inv_id = await roles_db.fetchval(
            "INSERT INTO family_invitations (group_id, inviter_patient_id, "
            "invitee_patient_id, expires_at) VALUES ($1, $2, $3, "
            "now() + interval '1 day') RETURNING id",
            group_id,
            ids[0],
            ids[1],
        )
        await roles_db.execute(
            "UPDATE family_invitations SET status = 'rejected', "
            "responded_at = now() WHERE id = $1",
            inv_id,
        )
        assert (
            await roles_db.fetchval(
                "SELECT status FROM family_invitations WHERE id = $1", inv_id
            )
            == "rejected"
        )
        await roles_db.execute(
            "INSERT INTO activation_recovery (reference, reason, "
            "patient_document_type, patient_document_number) "
            "VALUES ($1, 'db_error', 'CC', $2)",
            doc,
            doc,
        )
        await roles_db.execute(
            "UPDATE activation_recovery SET resolved_at = now(), "
            "resolved_note = 'ok' WHERE reference = $1",
            doc,
        )
        # Secuencias (si las hay): la app tiene USAGE y SELECT.
        for seq in await roles_db.fetch(
            "SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'"
        ):
            assert await roles_db.fetchval(
                "SELECT has_sequence_privilege('acuarius_app', $1, 'USAGE, SELECT')",
                f"public.{seq['sequencename']}",
            )
    finally:
        await roles_db.execute("RESET ROLE")


async def test_settings_sin_delete_y_su_historial_solo_select_e_insert(
    roles_db,
) -> None:
    key = "roles.prueba"
    await roles_db.execute("SET ROLE acuarius_app")
    try:
        await roles_db.execute(
            "INSERT INTO settings (key, value, value_type, default_value, "
            "group_name, description) VALUES ($1, '5'::jsonb, 'int', "
            "'5'::jsonb, 'g', 'd')",
            key,
        )
        await roles_db.execute(
            "UPDATE settings SET value = '6'::jsonb, version = 2 WHERE key = $1",
            key,
        )
        await roles_db.execute(
            "INSERT INTO settings_history (setting_key, old_value, new_value, "
            "version_after, reason) VALUES ($1, '5'::jsonb, '6'::jsonb, 2, "
            "'prueba')",
            key,
        )
        assert await roles_db.fetchval(
            "SELECT count(*) FROM settings_history WHERE setting_key = $1", key
        )
    finally:
        await roles_db.execute("RESET ROLE")
    for sql in (
        "UPDATE settings_history SET reason = 'otra cosa'",
        "DELETE FROM settings_history",
        "TRUNCATE settings_history",
        "ALTER TABLE settings_history DISABLE TRIGGER ALL",
        "DELETE FROM settings",
        "TRUNCATE settings",
    ):
        assert (
            await _sqlstate(roles_db, "acuarius_app", sql) == INSUFFICIENT_PRIVILEGE
        ), sql


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE patients",
        "ALTER TABLE patients ADD COLUMN x int",
        "TRUNCATE patients",
        "DELETE FROM patients",
        "CREATE TABLE intruso (id int)",
        "DROP SCHEMA public CASCADE",
        "CREATE INDEX ix_intruso ON patients (birth_date)",
        "SELECT * FROM alembic_version",
        "CREATE ROLE intruso",
    ],
)
async def test_app_no_puede_ddl_truncate_ni_delete(roles_db, sql: str) -> None:
    assert await _sqlstate(roles_db, "acuarius_app", sql) == INSUFFICIENT_PRIVILEGE


async def test_migrator_hace_ddl_y_las_tablas_nuevas_requieren_reaplicar(
    roles_db,
) -> None:
    create = "CREATE TABLE tabla_nueva (id serial PRIMARY KEY, v text)"
    assert await _sqlstate(roles_db, "acuarius_migrator", create) is None
    try:
        # Falla cerrada: la tabla nueva no es accesible hasta re-aplicar el script.
        assert (
            await _sqlstate(roles_db, "acuarius_app", "SELECT * FROM tabla_nueva")
            == INSUFFICIENT_PRIVILEGE
        )
        await roles_db.execute(SCRIPT)
        insert = "INSERT INTO tabla_nueva (v) VALUES ('x')"
        assert await _sqlstate(roles_db, "acuarius_app", insert) is None
    finally:
        drop = "DROP TABLE tabla_nueva"
        assert await _sqlstate(roles_db, "acuarius_migrator", drop) is None

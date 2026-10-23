"""Registro de ajustes, valores heredados del entorno y esquema sin FK."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core import runtime_settings
from app.core.config import LegacyPolicyEnv
from app.core.db.settings_model import SETTINGS_MODELS

EXPECTED = {
    # clave: (default, min, max, security)
    "activation.max_per_ip_doc": (5, 3, 20, True),
    "activation.max_per_doc": (15, 5, 60, True),
    "activation.max_per_ip": (30, 10, 200, True),
    "activation.window_seconds": (900, 60, 3600, True),
    "profile.max_per_user": (10, 3, 50, True),
    "profile.window_seconds": (900, 60, 3600, True),
    "family.invite_max_per_patient": (20, 5, 100, True),
    "family.invite_max_per_ip": (30, 5, 200, True),
    "family.invite_window_seconds": (3600, 300, 86400, True),
    "family.invitation_ttl_days": (7, 1, 30, False),
    "family.max_pending_per_group": (10, 1, 50, False),
    "results.max_page_size": (50, 10, 200, False),
    "account.public_policy_per_window": (60, 10, 600, False),
}


def test_registry_keys_ranges_and_security_flags():
    reg = runtime_settings.ACUARIUS_SETTINGS
    assert set(reg.keys()) == set(EXPECTED)
    for key, (default, lo, hi, security) in EXPECTED.items():
        d = reg.get(key)
        assert (d.default, d.min, d.max, d.requires_security) == (
            default,
            lo,
            hi,
            security,
        ), key


def test_legacy_env_provides_initial_values_and_ignores_garbage(monkeypatch):
    monkeypatch.setenv("ACTIVATION_MAX_PER_IP_DOC", "7")
    monkeypatch.setenv("PROFILE_WINDOW_SECONDS", " 600 ")
    monkeypatch.setenv("ACTIVATION_MAX_PER_IP", "mucho")
    values = LegacyPolicyEnv().initial_values()
    assert values["activation.max_per_ip_doc"] == 7
    assert values["profile.window_seconds"] == 600
    assert "activation.max_per_ip" not in values
    assert set(values) <= set(EXPECTED)


async def test_legacy_value_only_applies_when_key_is_inserted(session):
    """`sync_registry` usa el valor heredado solo al INSERTAR la clave."""
    store = runtime_settings.store
    await store.sync_registry({})  # asegura las filas
    result = await store.sync_registry({"activation.max_per_ip_doc": 9})
    assert "activation.max_per_ip_doc" not in result.inserted
    assert await store.get("activation.max_per_ip_doc") == 5


def test_settings_tables_have_no_foreign_keys_in_metadata():
    for model in (SETTINGS_MODELS.Setting, SETTINGS_MODELS.SettingHistory):
        assert not model.__table__.foreign_keys


async def test_settings_tables_have_no_foreign_keys_in_db(session):
    rows = await session.execute(
        text(
            "SELECT conname FROM pg_constraint WHERE contype = 'f' AND conrelid IN "
            "('settings'::regclass, 'settings_history'::regclass)"
        )
    )
    assert rows.all() == []
    cols = await session.execute(
        text(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE (table_name, column_name) IN (('settings','updated_by'),"
            "('settings_history','changed_by'))"
        )
    )
    assert {(t, c): d for t, c, d in cols.all()} == {
        ("settings", "updated_by"): "uuid",
        ("settings_history", "changed_by"): "uuid",
    }


async def test_history_is_append_only(session):
    await session.execute(
        text(
            "INSERT INTO settings_history (setting_key, old_value, new_value, "
            "version_after, reason) VALUES ('a.b', '1', '2', 2, 'prueba')"
        )
    )
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(text("DELETE FROM settings_history"))

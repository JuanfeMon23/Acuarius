"""Pantalla Ajustes: permisos, edicion con version/motivo, historial y auditoria."""

import pytest
from sqlalchemy import text

from app.core import permissions as perms
from app.core import runtime_settings
from app.core.database import engine
from app.modules.settings.router import UPDATE_TAG

API = "/api/v1/settings"
PLAIN = "family.max_pending_per_group"
SECURE = "activation.max_per_ip"


@pytest.fixture(autouse=True)
async def _settings_rows():
    """Filas presentes antes y valores de fabrica despues (la tabla es de la BD
    de pruebas, compartida; el historial es append-only y se conserva)."""
    store = runtime_settings.store
    await store.sync_registry({})
    store.invalidate()
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE settings SET value = default_value, version = 1")
        )
    store.invalidate()


def _find(body: dict, key: str) -> dict:
    return next(s for g in body["groups"] for s in g["settings"] if s["key"] == key)


def _put(client, key, value, version=1, reason="Prueba de ajuste"):
    return client.put(
        f"{API}/{key}",
        json={"value": value, "reason": reason, "expected_version": version},
    )


async def test_requires_login(client, leo):
    leo.user = None
    assert (await client.get(API)).status_code == 401
    assert (await _put(client, PLAIN, 12)).status_code == 401


async def test_view_lists_groups_with_metadata(client, leo):
    leo.login({perms.SETTINGS_VIEW})
    r = await client.get(API)
    assert r.status_code == 200
    body = r.json()
    assert {g["group"] for g in body["groups"]} == {
        "activation",
        "profile",
        "family",
        "results",
        "account",
    }
    s = _find(body, SECURE)
    assert (s["value"], s["default"], s["min"], s["max"], s["version"]) == (
        30,
        30,
        10,
        200,
        1,
    )
    assert s["requires_security_permission"] is True
    assert _find(body, PLAIN)["requires_security_permission"] is False


async def test_view_permission_is_required_to_list(client, leo):
    leo.login({perms.SETTINGS_EDIT})
    assert (await client.get(API)).status_code == 403


async def test_edit_needs_edit_permission(client, leo):
    leo.login({perms.SETTINGS_VIEW})
    assert (await _put(client, PLAIN, 12)).status_code == 403


async def test_edit_plain_setting_updates_value_audits_and_applies(client, leo):
    leo.login({perms.SETTINGS_EDIT})
    r = await _put(client, PLAIN, 12)
    assert r.status_code == 200
    assert (r.json()["value"], r.json()["version"]) == (12, 2)
    assert await runtime_settings.get(PLAIN) == 12
    (event,) = [e for e in leo.events if e["action_tag"] == UPDATE_TAG]
    assert UPDATE_TAG == "acuarius.settings.update"
    assert event["entity_id"] == PLAIN and event["reason"] == "Prueba de ajuste"
    assert event["changes"]["value"] == {"before": 10, "after": 12}


async def test_security_setting_needs_edit_security_too(client, leo):
    leo.login({perms.SETTINGS_EDIT})
    assert (await _put(client, SECURE, 40)).status_code == 403
    assert await runtime_settings.get(SECURE) == 30
    leo.login({perms.SETTINGS_EDIT_SECURITY})
    assert (await _put(client, SECURE, 40)).status_code == 403  # falta edit
    leo.login({perms.SETTINGS_EDIT, perms.SETTINGS_EDIT_SECURITY})
    r = await _put(client, SECURE, 40)
    assert r.status_code == 200 and r.json()["value"] == 40


async def test_validation_errors_are_readable(client, leo):
    leo.login({perms.SETTINGS_EDIT})
    assert (await _put(client, PLAIN, 999)).status_code == 422  # fuera de rango
    assert (await _put(client, PLAIN, "diez")).status_code == 422  # tipo
    assert (await _put(client, PLAIN, 12, reason="")).status_code == 422  # motivo
    assert (await _put(client, PLAIN, 12, version=7)).status_code == 409  # version
    assert (await _put(client, "no.existe", 1)).status_code == 404
    assert await runtime_settings.get(PLAIN) == 10


async def test_history_lists_changes(client, leo):
    leo.login({perms.SETTINGS_VIEW, perms.SETTINGS_EDIT})
    await _put(client, PLAIN, 12)
    r = await client.get(f"{API}/{PLAIN}/history")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["new_value"] == 12 and items[0]["old_value"] == 10
    assert items[0]["changed_by"] == str(leo.user.id)
    assert (await client.get(f"{API}/no.existe/history")).status_code == 404

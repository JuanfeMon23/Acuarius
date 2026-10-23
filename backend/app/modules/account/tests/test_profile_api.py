"""Autogestion de perfil y contrasena (proxy a Leo en nombre del usuario)."""

import json
import logging
from datetime import date

import pytest
from leo_sdk import InvalidTokenError, LeoError, TooManyAttemptsError

from app.modules.account.models import Patient

PROFILE = "/api/v1/account/profile"
PASSWORD = "/api/v1/account/password"
SECRET = "Sup3r!Secreta-Actual"
NEW = "N4eva!Contraseña-Larga"


@pytest.fixture
async def me(session, leo):
    user = leo.login()
    p = Patient(
        leo_user_id=user.id,
        document_type="CC",
        document_number="1001",
        birth_date=date(1990, 1, 1),
        display_name="Paciente U.",
    )
    session.add(p)
    await session.flush()
    return p


async def test_get_profile(client, me):
    r = await client.get(PROFILE)
    assert r.status_code == 200
    assert r.json() == {
        "first_name": "Paciente",
        "last_name": "Uno",
        "email": "paciente@example.com",
        "username": "paciente",
    }
    assert r.headers["cache-control"] == "no-store"


async def test_unauthenticated_401(client, leo):
    leo.user = None
    assert (await client.get(PROFILE)).status_code == 401
    assert (await client.patch(PROFILE, json={"first_name": "A"})).status_code == 401
    r = await client.post(PASSWORD, json={"current_password": "x", "new_password": NEW})
    assert r.status_code == 401


async def test_patch_names_updates_display_name(client, leo, me, session):
    r = await client.patch(
        PROFILE, json={"first_name": "Ana", "last_name": "Perez Gomez"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["first_name"] == "Ana"
    assert leo.profile_calls == [
        {
            "token": "token-falso",
            "first_name": "Ana",
            "last_name": "Perez Gomez",
            "email": None,
            "current_password": None,
        }
    ]
    await session.refresh(me)
    assert me.display_name == "Ana P. G."
    assert leo.events


async def test_patch_email_with_password_keeps_display_name(client, leo, me, session):
    r = await client.patch(
        PROFILE, json={"email": "nuevo@example.com", "current_password": SECRET}
    )
    assert r.status_code == 200
    assert r.json()["email"] == "nuevo@example.com"
    assert leo.profile_calls[0]["current_password"] == SECRET
    await session.refresh(me)
    assert me.display_name == "Paciente U."
    assert SECRET not in r.text


async def test_patch_validation(client, me):
    for body in (
        {"username": "x"},
        {"first_name": "A", "user_access_token": "t"},
        {"document_number": "1"},
        {},
        {"email": "no-es-correo"},
    ):
        r = await client.patch(PROFILE, json=body)
        assert r.status_code == 422, body


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (
            LeoError("current_password_required", "interno", 422),
            422,
            "current_password_required",
        ),
        (
            LeoError("invalid_current_password", "interno", 403),
            403,
            "invalid_current_password",
        ),
        (LeoError("duplicate", "interno", 409, {"email": "x"}), 409, "duplicate"),
    ],
)
async def test_patch_leo_errors_forwarded(client, leo, me, error, status, code):
    leo.fail_with = error
    r = await client.patch(PROFILE, json={"email": "a@b.co"})
    assert r.status_code == status
    body = r.json()
    assert body["code"] == code
    assert "interno" not in r.text and set(body) == {"code", "message", "details"}


async def test_patch_429_retry_after(client, leo, me):
    leo.fail_with = TooManyAttemptsError("too_many_attempts", "interno", retry_after=42)
    r = await client.patch(PROFILE, json={"email": "a@b.co", "current_password": "x"})
    assert r.status_code == 429
    assert r.headers["retry-after"] == "42"
    assert r.json()["details"] == {"retry_after_seconds": 42}


async def test_invalid_user_token_is_401(client, leo, me):
    leo.fail_with = InvalidTokenError(
        "invalid_token", "x", 401, {"field": "user_access_token"}
    )
    r = await client.patch(PROFILE, json={"first_name": "A"})
    assert r.status_code == 401 and r.json()["code"] == "not_authenticated"


async def test_unexpected_leo_error_is_generic(client, leo, me):
    leo.fail_with = LeoError("boom", "traza interna", 500)
    r = await client.patch(PROFILE, json={"first_name": "A"})
    assert r.status_code == 502 and "traza" not in r.text


async def test_change_password_ok_never_leaks(client, leo, me, caplog):
    caplog.set_level(logging.DEBUG)
    r = await client.post(
        PASSWORD, json={"current_password": SECRET, "new_password": NEW}
    )
    assert r.status_code == 204 and r.content == b""
    assert leo.password_calls == [
        {"token": "token-falso", "current": SECRET, "new": NEW}
    ]
    blob = json.dumps(leo.events, default=str) + caplog.text + repr(r.headers)
    assert SECRET not in blob and NEW not in blob


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (LeoError("invalid_credentials", "interno", 401), 403, "invalid_credentials"),
        (
            LeoError(
                "weak_password",
                "interno",
                422,
                [{"field": "new_password", "message": "común"}],
            ),
            422,
            "weak_password",
        ),
        (LeoError("same_password", "interno", 422), 422, "same_password"),
    ],
)
async def test_password_leo_errors(client, leo, me, caplog, error, status, code):
    leo.fail_with = error
    r = await client.post(
        PASSWORD, json={"current_password": SECRET, "new_password": NEW}
    )
    assert r.status_code == status and r.json()["code"] == code
    assert SECRET not in r.text + caplog.text + json.dumps(leo.events, default=str)
    assert "interno" not in r.text


async def test_password_429(client, leo, me):
    leo.fail_with = TooManyAttemptsError("too_many_attempts", "x", retry_after=60)
    r = await client.post(
        PASSWORD, json={"current_password": SECRET, "new_password": NEW}
    )
    assert r.status_code == 429 and r.headers["retry-after"] == "60"


async def test_password_policy_and_extra_fields(client, leo, me):
    r = await client.post(
        PASSWORD, json={"current_password": SECRET, "new_password": "corta"}
    )
    assert r.status_code == 422 and "corta" not in r.text
    r = await client.post(
        PASSWORD, json={"current_password": SECRET, "new_password": NEW, "user_id": "1"}
    )
    assert r.status_code == 422
    assert leo.password_calls == []


async def test_per_user_rate_limit(client, leo, me, setting):
    setting("profile.max_per_user", 3)
    for _ in range(3):
        assert (
            await client.patch(PROFILE, json={"first_name": "A"})
        ).status_code == 200
    r = await client.patch(PROFILE, json={"first_name": "A"})
    assert r.status_code == 429 and "retry-after" in r.headers

"""Alta con codigo de activacion: exito, fallos uniformes y limites."""

import logging
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.modules.account import router as account_router
from app.modules.account.display_name import derive_display_name
from app.modules.account.models import ActivationRecovery, Patient

URL = "/api/v1/account/activate"
GOOD = {
    "code": "ABC-123",
    "document_type": "CC",
    "document_number": "1001",
    "birth_date": "1990-05-01",
    "username": "ana.perez",
    "email": "ana@example.com",
    "password": "Str0ng!Passw0rd",
}


async def assert_recovery(session, response, reason: str) -> ActivationRecovery:
    row = (await session.execute(select(ActivationRecovery))).scalar_one()
    assert row.reason == reason
    assert row.reference == response.json()["details"]["reference"]
    assert (row.patient_document_type, row.patient_document_number) == ("CC", "1001")
    assert row.resolved_at is None
    return row


@pytest.fixture(autouse=True)
def valid_code(incubus):
    incubus.add_activation("ABC-123", "CC", "1001", "1990-05-01")


async def test_success_creates_leo_user_and_patient(client, session, leo_users):
    r = await client.post(URL, json=GOOD)
    assert r.status_code == 201, r.text
    assert r.json()["username"] == "ana.perez"
    sent = leo_users.bodies[0]
    assert sent["first_name"] == "Ana Maria" and sent["last_name"] == "Perez Gomez"
    assert sent["document_type"] == "CC" and sent["document_number"] == "1001"
    row = (await session.execute(select(Patient))).scalar_one()
    assert (row.document_number, str(row.birth_date)) == ("1001", "1990-05-01")
    assert row.display_name == "Ana P. G."


async def test_display_name_never_taken_from_body(client, session):
    r = await client.post(URL, json={**GOOD, "display_name": "Hacker"})
    assert r.status_code == 422
    assert (await session.execute(select(Patient))).first() is None


def test_derive_display_name():
    d = {"first_name": "Ana", "first_last_name": "perez", "second_last_name": "Gomez"}
    assert derive_display_name(d) == "Ana P. G."
    assert derive_display_name({"first_name": "Ana"}) == "Ana"
    assert derive_display_name({}) == "Familiar"
    long = {"first_name": "A" * 100, "first_last_name": "B"}
    assert len(derive_display_name(long)) == 80


@pytest.mark.parametrize(
    "override",
    [
        {"document_number": "9999"},
        {"birth_date": "1991-05-01"},
        {"document_type": "TI"},
    ],
)
async def test_every_verification_failure_is_identical(client, override, leo_users):
    base = await client.post(URL, json={**GOOD, "code": "WRONG"})
    r = await client.post(URL, json={**GOOD, **override})
    assert r.status_code == base.status_code == 400
    assert r.json() == base.json()
    assert r.json()["code"] == "activation_failed"
    assert leo_users.bodies == []


async def test_used_code_same_neutral_response(client):
    assert (await client.post(URL, json=GOOD)).status_code == 201
    wrong = await client.post(URL, json={**GOOD, "code": "WRONG"})
    # mismo codigo, ya consumido, otro documento: igual de neutro
    incubus_used = await client.post(URL, json={**GOOD, "document_number": "1002"})
    assert incubus_used.status_code == 400 and incubus_used.json() == wrong.json()


async def test_existing_patient_neutral_and_code_not_consumed(client, incubus):
    assert (await client.post(URL, json=GOOD)).status_code == 201
    incubus.consumed.clear()
    before = len(incubus.calls)
    r = await client.post(URL, json=GOOD)
    assert r.status_code == 400 and r.json()["code"] == "activation_failed"
    assert len(incubus.calls) == before  # ni siquiera se consulto a Incubus


async def test_weak_password_rejected_before_consuming_code(client, incubus):
    r = await client.post(URL, json={**GOOD, "password": "corta"})
    assert r.status_code == 422
    assert "corta" not in r.text
    assert incubus.consumed == set() and incubus.calls == []


async def test_leo_conflict_registers_recovery_without_leaking(
    client, leo_users, caplog, session
):
    leo_users.mode = "conflict"
    with caplog.at_level(logging.INFO):
        r = await client.post(URL, json=GOOD)
    assert r.status_code == 409 and r.json()["code"] == "activation_recovery"
    assert r.json()["details"]["reference"]
    assert (await session.execute(select(Patient))).first() is None
    assert "activation_recovery" in caplog.text
    await assert_recovery(session, r, "leo_conflict")
    for secret in (
        "1001",
        "ana@example.com",
        "Str0ng!Passw0rd",
        "ana.perez",
        "ABC-123",
    ):
        assert secret not in caplog.text
        assert secret not in r.text


async def test_leo_down_after_consuming_code(client, leo_users, session):
    leo_users.mode = "down"
    r = await client.post(URL, json=GOOD)
    assert r.status_code == 409 and r.json()["code"] == "activation_recovery"
    assert "Str0ng" not in r.text
    await assert_recovery(session, r, "leo_unavailable")


async def test_leo_rejection_message_is_shown(client, leo_users, session):
    leo_users.mode = "weak"
    r = await client.post(URL, json=GOOD)
    assert r.status_code == 409
    assert r.json()["message"] == "Contraseña débil."
    await assert_recovery(session, r, "leo_weak_password")


async def test_patient_insert_failure_registers_db_error(client, session, monkeypatch):
    async def boom():
        raise IntegrityError("insert", {}, Exception("dup"))

    monkeypatch.setattr(session, "commit", boom)
    r = await client.post(
        URL, json={**GOOD, "document_type": "cc"}
    )  # tipo en minusculas: se normaliza
    assert r.status_code == 409 and r.json()["code"] == "activation_recovery"
    monkeypatch.undo()
    assert (await session.execute(select(Patient))).first() is None
    await assert_recovery(session, r, "db_error")


async def test_recovery_persist_failure_still_returns_reference(
    client, leo_users, monkeypatch, caplog
):
    from app.main import app
    from app.modules.account.router import get_recovery_sessions

    def broken():
        raise RuntimeError("db down")

    app.dependency_overrides[get_recovery_sessions] = lambda: broken
    leo_users.mode = "down"
    with caplog.at_level(logging.ERROR):
        r = await client.post(URL, json=GOOD)
    assert r.status_code == 409 and r.json()["details"]["reference"]
    assert "activation_recovery_persist_failed" in caplog.text


async def test_incubus_down_is_not_neutral_failure(client, incubus):
    incubus.down = True
    r = await client.post(URL, json=GOOD)
    assert r.status_code == 502 and r.json()["code"] == "upstream_unavailable"


async def test_rate_limit_per_ip_and_document(client):
    bad = {**GOOD, "code": "WRONG"}
    for _ in range(5):
        assert (await client.post(URL, json=bad)).status_code == 400
    r = await client.post(URL, json=bad)
    assert r.status_code == 429 and r.json()["code"] == "rate_limited"
    assert "retry-after" in r.headers
    # frena tambien al intento correcto: el limite es previo a la verificacion
    assert (await client.post(URL, json=GOOD)).status_code == 429


async def test_rate_limit_per_document_across_ips(client, monkeypatch):
    bad = {**GOOD, "code": "WRONG"}
    statuses = []
    for i in range(17):
        monkeypatch.setattr(
            account_router, "_client_ip", lambda _req, i=i: f"198.51.100.{i}"
        )
        statuses.append((await client.post(URL, json=bad)).status_code)
    assert statuses[:15] == [400] * 15 and statuses[15:] == [429, 429]


async def test_incubus_429_maps_to_rate_limited(client, incubus):
    incubus.rate_limited = True
    r = await client.post(URL, json=GOOD)
    assert r.status_code == 429 and r.json()["code"] == "rate_limited"


async def test_me_returns_session_patient(client, leo, session):
    user = leo.login(user_id=uuid4())
    session.add(
        Patient(
            leo_user_id=user.id,
            document_type="CC",
            document_number="1001",
            birth_date=date(1990, 5, 1),
            display_name="Ana P. G.",
        )
    )
    await session.flush()
    r = await client.get("/api/v1/account/me")
    assert r.status_code == 200
    assert r.json()["document_number"] == "1001" and r.json()["username"] == "paciente"
    assert r.json()["display_name"] == "Ana P. G."
    leo.user = None
    assert (await client.get("/api/v1/account/me")).status_code == 401


async def test_activation_limits_come_from_settings(client, setting):
    setting("activation.max_per_ip_doc", 3)
    bad = {**GOOD, "code": "WRONG"}
    for _ in range(3):
        assert (await client.post(URL, json=bad)).status_code == 400
    assert (await client.post(URL, json=bad)).status_code == 429

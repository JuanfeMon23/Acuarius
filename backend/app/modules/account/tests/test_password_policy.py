"""Politica de contrasenas de Leo: endpoint publico y uso en activacion/perfil."""

from datetime import date

from leo_sdk import PasswordPolicy

from app.core.password_policy import STRICT_POLICY
from app.modules.account.models import Patient
from app.modules.account.tests.test_activation_flow import GOOD, URL

POLICY = "/api/v1/account/password-policy"
PASSWORD = "/api/v1/account/password"
CURRENT = "Sup3r!Secreta-Actual"


async def test_public_policy_same_body_as_leo_and_cacheable(client, leo):
    leo.user = None  # publico: sin sesion
    leo.policy = PasswordPolicy(min_length=14, require_symbol=False)
    r = await client.get(POLICY)
    assert r.status_code == 200
    assert r.json() == {
        "min_length": 14,
        "max_length": 128,
        "require_lowercase": True,
        "require_uppercase": True,
        "require_digit": True,
        "require_symbol": False,
    }
    assert r.headers["cache-control"] == "public, max-age=30"
    assert "pragma" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


async def test_public_policy_falls_back_to_strict_when_leo_is_down(client, leo):
    leo.policy_down = True
    r = await client.get(POLICY)
    assert r.status_code == 200
    assert r.json() == STRICT_POLICY.model_dump()
    assert r.json()["min_length"] == 12 and r.json()["max_length"] == 128


async def test_public_policy_is_rate_limited_per_ip(client, setting):
    setting("account.public_policy_per_window", 10)
    for _ in range(10):
        assert (await client.get(POLICY)).status_code == 200
    r = await client.get(POLICY)
    assert r.status_code == 429 and "retry-after" in r.headers
    assert r.headers["cache-control"] == "no-store"


async def test_activation_uses_leos_policy(client, leo, incubus):
    incubus.add_activation("ABC-123", "CC", "1001", "1990-05-01")
    leo.policy = PasswordPolicy(min_length=20)
    r = await client.post(URL, json=GOOD)  # 15 caracteres: ya no alcanza
    assert r.status_code == 422
    (detail,) = r.json()["details"]
    assert detail["field"] == "password" and detail["code"] == "too_short"
    assert "20" in detail["message"] and GOOD["password"] not in r.text
    assert incubus.consumed == set()


async def test_activation_accepts_relaxed_policy(client, leo, incubus, leo_users):
    incubus.add_activation("ABC-123", "CC", "1001", "1990-05-01")
    leo.policy = PasswordPolicy(min_length=8, require_symbol=False)
    r = await client.post(URL, json={**GOOD, "password": "Abcdefg1"})
    assert r.status_code == 201
    assert leo_users.bodies[0]["password"] == "Abcdefg1"


async def test_activation_uses_strict_policy_when_leo_is_down(client, leo, incubus):
    leo.policy_down = True
    r = await client.post(URL, json={**GOOD, "password": "Abcdefg1"})
    assert r.status_code == 422 and incubus.calls == []


async def test_password_change_uses_leos_policy(client, leo, session):
    user = leo.login()
    session.add(
        Patient(
            leo_user_id=user.id,
            document_type="CC",
            document_number="1001",
            birth_date=date(1990, 1, 1),
            display_name="Paciente U.",
        )
    )
    await session.flush()
    leo.policy = PasswordPolicy(min_length=8, require_symbol=False)
    r = await client.post(
        PASSWORD, json={"current_password": CURRENT, "new_password": "Abcdefg1"}
    )
    assert r.status_code == 204
    leo.policy = PasswordPolicy(min_length=30)
    r = await client.post(
        PASSWORD, json={"current_password": CURRENT, "new_password": "Abcdefg1"}
    )
    assert r.status_code == 422
    assert r.json()["details"][0]["field"] == "new_password"
    assert len(leo.password_calls) == 1

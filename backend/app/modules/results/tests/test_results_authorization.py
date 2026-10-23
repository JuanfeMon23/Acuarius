"""Ataques de autorizacion por objeto sobre resultados."""

import json
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as p
from app.modules.account.models import Patient
from app.modules.family.models import FamilyGroup, FamilyMembership, FamilyShare
from app.testing import FakeIncubus, FakeLeo

NOW = datetime(2026, 10, 22, tzinfo=UTC)
API = "/api/v1/results"


async def make_patient(session: AsyncSession, doc: str) -> Patient:
    pt = Patient(
        leo_user_id=uuid4(),
        document_type="CC",
        document_number=doc,
        birth_date=date(1990, 1, 1),
        display_name="Ana P. G.",
    )
    session.add(pt)
    await session.flush()
    return pt


async def make_share(
    session: AsyncSession,
    owner: Patient,
    viewer: Patient,
    *,
    revoked: bool = False,
    viewer_active: bool = True,
    owner_active: bool = True,
) -> None:
    group = FamilyGroup(created_by_patient_id=owner.id)
    session.add(group)
    await session.flush()
    for pt, active in ((owner, owner_active), (viewer, viewer_active)):
        session.add(
            FamilyMembership(
                group_id=group.id,
                patient_id=pt.id,
                status="active" if active else "left",
                joined_at=NOW,
                left_at=None if active else NOW,
            )
        )
    session.add(
        FamilyShare(
            group_id=group.id,
            owner_patient_id=owner.id,
            viewer_patient_id=viewer.id,
            granted_at=NOW,
            revoked_at=NOW if revoked else None,
        )
    )
    await session.flush()


@pytest_asyncio.fixture
async def world(session, leo: FakeLeo, incubus: FakeIncubus):
    me = await make_patient(session, "1001")
    other = await make_patient(session, "2002")
    incubus.orders[("CC", "1001")] = ["A-1", "A-2"]
    incubus.orders[("CC", "2002")] = ["B-1"]
    leo.login(user_id=me.leo_user_id)
    return me, other


async def test_list_uses_session_patient_document(client, world, incubus):
    r = await client.get(API)
    assert r.status_code == 200
    assert [i["order_number"] for i in r.json()["items"]] == ["A-1", "A-2"]
    assert "GET /api/v1/delivery/patients/CC/1001/orders" in incubus.calls
    assert not any("2002" in c for c in incubus.calls)


async def test_idor_foreign_order_number_is_404(client, world, incubus):
    r = await client.get(f"{API}/B-1")
    assert r.status_code == 404
    assert "2002" not in r.text
    assert not any(c.endswith("/orders/B-1") for c in incubus.calls)
    r = await client.get(f"{API}/B-1/report.pdf")
    assert r.status_code == 404
    assert not any("B-1/report.pdf" in c for c in incubus.calls)


async def test_own_order_detail_and_pdf(client, world):
    r = await client.get(f"{API}/A-1")
    assert r.status_code == 200 and r.json()["order_number"] == "A-1"
    pdf = await client.get(f"{API}/A-1/report.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF") and b"DOC-1001" in pdf.content
    assert pdf.headers["content-type"] == "application/pdf"
    assert (
        pdf.headers["content-disposition"]
        == 'attachment; filename="resultados-A-1.pdf"'
    )
    assert pdf.headers["cache-control"] == "no-store"


async def test_patient_id_without_share_is_404_and_audited(client, world, leo):
    _, other = world
    r = await client.get(API, params={"patient_id": str(other.id)})
    assert r.status_code == 404
    assert "B-1" not in r.text
    assert any(e.get("result") == "denied" for e in leo.events)
    r = await client.get(f"{API}/B-1", params={"patient_id": str(other.id)})
    assert r.status_code == 404


async def test_unknown_patient_id_same_response_as_unshared(client, world):
    _, other = world
    a = await client.get(API, params={"patient_id": str(other.id)})
    b = await client.get(API, params={"patient_id": str(uuid4())})
    assert (a.status_code, a.json()) == (b.status_code, b.json())


async def test_active_share_allows_viewing_owner_and_audits(
    client, world, session, leo
):
    me, other = world
    await make_share(session, owner=other, viewer=me)
    r = await client.get(API, params={"patient_id": str(other.id)})
    assert r.status_code == 200
    assert [i["order_number"] for i in r.json()["items"]] == ["B-1"]
    q = {"patient_id": str(other.id)}
    assert (await client.get(f"{API}/B-1", params=q)).status_code == 200
    # una orden propia no sirve con el patient_id ajeno
    assert (await client.get(f"{API}/A-1", params=q)).status_code == 404
    ok = [
        e
        for e in leo.events
        if e["action_tag"] == p.RESULTS_VIEW and e.get("result", "ok") == "ok"
    ]
    assert any(e.get("entity_id") == "B-1" for e in ok)
    assert str(other.id) in json.dumps(ok)


async def test_share_is_directional(client, world, session):
    me, other = world
    await make_share(session, owner=me, viewer=other)  # yo comparto con el otro
    r = await client.get(API, params={"patient_id": str(other.id)})
    assert r.status_code == 404


async def test_revoked_share_denied(client, world, session):
    me, other = world
    await make_share(session, owner=other, viewer=me, revoked=True)
    r = await client.get(API, params={"patient_id": str(other.id)})
    assert r.status_code == 404


@pytest.mark.parametrize("viewer_active,owner_active", [(False, True), (True, False)])
async def test_inactive_membership_denied(
    client, world, session, viewer_active, owner_active
):
    me, other = world
    await make_share(
        session,
        owner=other,
        viewer=me,
        viewer_active=viewer_active,
        owner_active=owner_active,
    )
    r = await client.get(API, params={"patient_id": str(other.id)})
    assert r.status_code == 404


async def test_scan_finds_order_beyond_first_page(client, world, incubus):
    incubus.orders[("CC", "1001")] = [f"N-{i}" for i in range(120)]
    assert (await client.get(f"{API}/N-119")).status_code == 200


async def test_requires_tag_and_session(client, world, leo):
    leo.login(tags=[p.RESULTS_VIEW], user_id=world[0].leo_user_id)
    assert (await client.get(f"{API}/A-1/report.pdf")).status_code == 403
    assert (await client.get(API)).status_code == 200
    leo.user = None
    assert (await client.get(API)).status_code == 401


async def test_user_without_patient_profile_forbidden(client, leo):
    leo.login()
    r = await client.get(API)
    assert r.status_code == 403
    assert set(r.json()) == {"code", "message", "details"}


async def test_bad_order_number_rejected(client, world):
    r = await client.get(f"{API}/..%2F..%2Fx")
    assert r.status_code in (404, 422)

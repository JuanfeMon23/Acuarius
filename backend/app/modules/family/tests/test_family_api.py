"""Grupo familiar: flujo feliz y ataques (IDOR, enumeracion, carreras, expiracion)."""

import json
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as perms
from app.modules.account.models import Patient
from app.modules.family import router as family_router
from app.modules.family import service
from app.modules.family.access import can_view
from app.modules.family.models import (
    FamilyGroup,
    FamilyInvitation,
    FamilyMembership,
    FamilyShare,
)
from app.testing import FakeLeo

API = "/api/v1/family"
NEUTRAL = {"message": "Si la persona está registrada, recibirá la invitación."}
NOW = datetime(2026, 10, 22, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset_limiter():
    family_router.limiter.reset()


async def mk(session: AsyncSession, doc: str) -> Patient:
    p = Patient(
        leo_user_id=uuid4(),
        document_type="CC",
        document_number=doc,
        birth_date=date(1990, 1, 1),
        display_name="Ana P. G.",
    )
    session.add(p)
    await session.flush()
    return p


async def mk_group(session, creator: Patient, *others: Patient) -> FamilyGroup:
    g = FamilyGroup(created_by_patient_id=creator.id)
    session.add(g)
    await session.flush()
    for p in (creator, *others):
        session.add(
            FamilyMembership(
                group_id=g.id, patient_id=p.id, status="active", joined_at=NOW
            )
        )
    await session.flush()
    return g


async def mk_share(session, g, owner: Patient, viewer: Patient) -> FamilyShare:
    s = FamilyShare(
        group_id=g.id,
        owner_patient_id=owner.id,
        viewer_patient_id=viewer.id,
        granted_at=NOW,
    )
    session.add(s)
    await session.flush()
    return s


async def mk_invitation(session, g, inviter, invitee, **kw) -> FamilyInvitation:
    created = kw.pop("created_at", datetime.now(UTC))
    inv = FamilyInvitation(
        group_id=g.id,
        inviter_patient_id=inviter.id,
        invitee_patient_id=invitee.id,
        status="pending",
        created_at=created,
        expires_at=kw.pop("expires_at", created + timedelta(days=7)),
    )
    session.add(inv)
    await session.flush()
    return inv


def login(leo: FakeLeo, p: Patient) -> None:
    leo.login(user_id=p.leo_user_id)


async def invite(client, doc: str, doc_type: str = "CC"):
    return await client.post(
        f"{API}/invitations", json={"document_type": doc_type, "document_number": doc}
    )


async def active_of(session, p: Patient) -> list[FamilyMembership]:
    return list(
        (
            await session.execute(
                select(FamilyMembership).where(
                    FamilyMembership.patient_id == p.id,
                    FamilyMembership.status == "active",
                )
            )
        ).scalars()
    )


# --- invitar ----------------------------------------------------------------


async def test_invite_creates_group_and_pending_invitation(client, session, leo):
    a, b = await mk(session, "1"), await mk(session, "2")
    login(leo, a)
    r = await invite(client, "2")
    assert r.status_code == 202 and r.json() == NEUTRAL
    me = (await client.get(f"{API}/me")).json()
    assert [m["is_me"] for m in me["group"]["members"]] == [True]
    assert me["group"]["created_by_me"] is True
    assert len(me["invitations_sent"]) == 1
    assert me["display_name"] == "Tú"
    login(leo, b)
    got = (await client.get(f"{API}/me")).json()
    inv = got["invitations_received"][0]
    assert inv["inviter_display_name"] == "Ana P. G."
    text = json.dumps(got)
    assert "Perez" not in text and "paciente@example.com" not in text
    assert "document" not in text


async def test_invite_response_identical_for_every_case(client, session, leo):
    a, _b, c, d, _e = [await mk(session, str(i)) for i in range(5)]
    await mk_group(session, c, d)  # c y d en otro grupo
    login(leo, a)
    responses = [
        await invite(client, "999"),  # no existe
        await invite(client, "1"),  # existe y libre
        await invite(client, "0"),  # uno mismo
        await invite(client, "2"),  # ya en otro grupo
        await invite(client, "1"),  # repetida
    ]
    assert {(r.status_code, json.dumps(r.json())) for r in responses} == {
        (202, json.dumps(NEUTRAL))
    }
    me = (await client.get(f"{API}/me")).json()
    assert len(me["invitations_sent"]) == 1  # solo la valida


async def test_cannot_invite_active_member_of_other_group(client, session, leo):
    a, c, d = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    await mk_group(session, c, d)
    login(leo, a)
    await invite(client, "3")
    count = (
        await session.execute(
            select(FamilyInvitation).where(FamilyInvitation.invitee_patient_id == d.id)
        )
    ).all()
    assert count == []


async def test_invite_expires_in_seven_days(client, session, leo):
    a, _b = await mk(session, "1"), await mk(session, "2")
    login(leo, a)
    await invite(client, "2")
    inv = (await session.execute(select(FamilyInvitation))).scalar_one()
    assert (
        timedelta(days=6, hours=23)
        < inv.expires_at - inv.created_at
        <= timedelta(days=7)
    )


async def test_max_ten_pending_per_group(client, session, leo):
    a = await mk(session, "0")
    others = [await mk(session, f"x{i}") for i in range(11)]
    login(leo, a)
    for o in others[:10]:
        assert (await invite(client, o.document_number)).status_code == 202
    r = await invite(client, others[10].document_number)
    assert r.status_code == 409 and "10" in r.json()["message"]


async def test_invite_rate_limited(client, session, leo):
    a = await mk(session, "0")
    login(leo, a)
    for i in range(20):
        assert (await invite(client, f"nope{i}")).status_code == 202
    r = await invite(client, "nope-last")
    assert r.status_code == 429 and "Retry-After" in r.headers


async def test_only_active_member_invites_from_own_group(client, session, leo):
    """Quien salio del grupo no invita al grupo anterior: crea uno propio."""
    a, b, _c = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    g = await mk_group(session, a, b)
    login(leo, b)
    assert (await client.post(f"{API}/leave")).status_code == 200
    await invite(client, "3")
    inv = (await session.execute(select(FamilyInvitation))).scalar_one()
    assert inv.group_id != g.id


# --- aceptar / rechazar / cancelar -----------------------------------------


async def test_accept_creates_membership_and_shares_nothing(client, session, leo):
    a, b = await mk(session, "1"), await mk(session, "2")
    g = await mk_group(session, a)
    inv = await mk_invitation(session, g, a, b)
    login(leo, b)
    r = await client.post(f"{API}/invitations/{inv.id}/accept")
    assert r.status_code == 200
    assert len(await active_of(session, b)) == 1
    assert not await can_view(session, b.id, a.id)
    assert not await can_view(session, a.id, b.id)
    assert (await session.execute(select(FamilyShare))).all() == []
    assert leo.events


async def test_accept_foreign_invitation_is_404(client, session, leo):
    a, b, c = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    g = await mk_group(session, a)
    inv = await mk_invitation(session, g, a, b)
    for who in (c, a):  # un tercero y el propio invitador
        login(leo, who)
        for action in ("accept", "reject"):
            r = await client.post(f"{API}/invitations/{inv.id}/{action}")
            assert r.status_code == 404
    unknown = await client.post(f"{API}/invitations/{uuid4()}/accept")
    assert unknown.status_code == 404
    assert unknown.json()["message"] == r.json()["message"]
    assert await active_of(session, c) == []
    await session.refresh(inv)
    assert inv.status == "pending"


async def test_accept_when_in_another_group_is_readable_409(client, session, leo):
    a, b, c = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    await mk_group(session, c, b)
    g = await mk_group(session, a)
    inv = await mk_invitation(session, g, a, b)
    login(leo, b)
    r = await client.post(f"{API}/invitations/{inv.id}/accept")
    assert r.status_code == 409
    assert r.json()["message"] == service.MSG_ALREADY_IN_GROUP
    assert "sal de él primero" in r.json()["message"]


async def test_double_group_race_loses_on_unique_index(
    client, session, leo, monkeypatch
):
    """Dos aceptaciones concurrentes pasan el chequeo previo; el indice unico
    deja pasar solo una y la otra recibe 409 legible (no 500)."""
    a, b, c = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    g1, g2 = await mk_group(session, a), await mk_group(session, c)
    inv1 = await mk_invitation(session, g1, a, b)
    inv2 = await mk_invitation(session, g2, c, b)
    login(leo, b)
    assert (await client.post(f"{API}/invitations/{inv1.id}/accept")).status_code == 200

    async def stale_check(_session, _patient_id):  # la otra peticion aun no veia nada
        return None

    monkeypatch.setattr(service, "my_membership", stale_check)
    r = await client.post(f"{API}/invitations/{inv2.id}/accept")
    assert r.status_code == 409
    assert r.json()["message"] == service.MSG_ALREADY_IN_GROUP
    monkeypatch.undo()
    assert len(await active_of(session, b)) == 1
    await session.refresh(inv2)
    assert inv2.status == "pending"


async def test_expired_invitation_cannot_be_accepted(client, session, leo):
    a, b = await mk(session, "1"), await mk(session, "2")
    g = await mk_group(session, a)
    old = datetime.now(UTC) - timedelta(days=8)
    inv = await mk_invitation(session, g, a, b, created_at=old)
    login(leo, b)
    r = await client.post(f"{API}/invitations/{inv.id}/accept")
    assert r.status_code == 409 and "expiró" in r.json()["message"]
    assert await active_of(session, b) == []
    await session.refresh(inv)
    assert inv.status == "expired"


async def test_expired_marked_lazily_on_me(client, session, leo):
    a, b = await mk(session, "1"), await mk(session, "2")
    g = await mk_group(session, a)
    inv = await mk_invitation(
        session, g, a, b, created_at=datetime.now(UTC) - timedelta(days=8)
    )
    login(leo, b)
    assert (await client.get(f"{API}/me")).json()["invitations_received"] == []
    await session.refresh(inv)
    assert inv.status == "expired"


async def test_reject_and_state_conflicts(client, session, leo):
    a, b = await mk(session, "1"), await mk(session, "2")
    g = await mk_group(session, a)
    inv = await mk_invitation(session, g, a, b)
    login(leo, b)
    assert (await client.post(f"{API}/invitations/{inv.id}/reject")).status_code == 200
    again = await client.post(f"{API}/invitations/{inv.id}/accept")
    assert again.status_code == 409
    assert await active_of(session, b) == []


async def test_cancel_only_by_inviter(client, session, leo):
    a, b, c = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    g = await mk_group(session, a, c)
    inv = await mk_invitation(session, g, a, b)
    for who in (b, c):  # el invitado y otro miembro del grupo
        login(leo, who)
        r = await client.post(f"{API}/invitations/{inv.id}/cancel")
        assert r.status_code == 404
    login(leo, a)
    assert (await client.post(f"{API}/invitations/{inv.id}/cancel")).status_code == 200
    login(leo, b)
    assert (await client.post(f"{API}/invitations/{inv.id}/accept")).status_code == 409


# --- compartir --------------------------------------------------------------


async def test_share_and_unshare_idempotent_and_visible(client, session, leo):
    a, b = await mk(session, "1"), await mk(session, "2")
    await mk_group(session, a, b)
    login(leo, a)
    assert not await can_view(session, b.id, a.id)
    for _ in range(2):  # idempotente
        assert (await client.put(f"{API}/shares/{b.id}")).status_code == 200
    assert await can_view(session, b.id, a.id)
    assert not await can_view(session, a.id, b.id)  # no es reciproco
    me = (await client.get(f"{API}/me")).json()
    assert [s["patient_id"] for s in me["shares_given"]] == [str(b.id)]
    login(leo, b)
    me = (await client.get(f"{API}/me")).json()
    assert [s["patient_id"] for s in me["shares_received"]] == [str(a.id)]
    login(leo, a)
    for _ in range(2):
        assert (await client.delete(f"{API}/shares/{b.id}")).status_code == 204
    assert not await can_view(session, b.id, a.id)
    revoked = (await session.execute(select(FamilyShare))).scalars().all()
    assert len(revoked) == 1 and revoked[0].revoked_at is not None


async def test_share_with_member_of_other_group_is_404(client, session, leo):
    a, b, c = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    await mk_group(session, a, b)
    await mk_group(session, c, await mk(session, "4"))
    login(leo, a)
    for target in (c.id, uuid4(), a.id):
        r = await client.put(f"{API}/shares/{target}")
        assert r.status_code == 404
    assert (await session.execute(select(FamilyShare))).all() == []
    assert not await can_view(session, c.id, a.id)


async def test_share_without_group_is_404(client, session, leo):
    a, b = await mk(session, "1"), await mk(session, "2")
    login(leo, a)
    assert (await client.put(f"{API}/shares/{b.id}")).status_code == 404


async def test_cannot_revoke_someone_elses_share(client, session, leo):
    a, b, c = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    g = await mk_group(session, a, b, c)
    await mk_share(session, g, a, b)  # a comparte con b
    login(leo, c)  # c intenta revocar a->b: solo toca c->b (nada)
    assert (await client.delete(f"{API}/shares/{b.id}")).status_code == 204
    login(leo, b)  # b intenta revocar lo que a le comparte: solo toca b->a
    assert (await client.delete(f"{API}/shares/{a.id}")).status_code == 204
    assert await can_view(session, b.id, a.id)
    login(leo, c)
    assert (await client.delete(f"{API}/shares/{uuid4()}")).status_code == 404


# --- salir / quitar ---------------------------------------------------------


async def test_leave_revokes_shares_and_keeps_group_with_one(client, session, leo):
    a, b, c = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    g = await mk_group(session, a, b, c)
    await mk_share(session, g, a, b)
    await mk_share(session, g, b, a)
    await mk_share(session, g, a, c)
    login(leo, b)
    assert (await client.post(f"{API}/leave")).status_code == 200
    assert not await can_view(session, b.id, a.id)
    assert not await can_view(session, a.id, b.id)
    assert await can_view(session, c.id, a.id)  # lo ajeno a b sigue intacto
    login(leo, a)
    await client.post(f"{API}/leave")
    await session.refresh(g)
    assert g.dissolved_at is None  # queda c solo: el grupo se mantiene
    assert not await can_view(session, c.id, a.id)
    login(leo, c)
    await client.post(f"{API}/leave")
    await session.refresh(g)
    assert g.dissolved_at is not None
    assert (await client.post(f"{API}/leave")).status_code == 404
    membership = (
        await session.execute(
            select(FamilyMembership).where(FamilyMembership.patient_id == b.id)
        )
    ).scalar_one()
    assert membership.status == "left" and membership.left_at is not None


async def test_remove_member_only_creator_and_blocks_visibility(client, session, leo):
    a, b, c = await mk(session, "1"), await mk(session, "2"), await mk(session, "3")
    g = await mk_group(session, a, b, c)
    await mk_share(session, g, b, a)
    await mk_share(session, g, a, b)
    login(leo, b)  # no es creador
    assert (await client.delete(f"{API}/members/{c.id}")).status_code == 403
    assert len(await active_of(session, c)) == 1
    login(leo, a)
    assert await can_view(session, a.id, b.id)
    assert (await client.delete(f"{API}/members/{b.id}")).status_code == 204
    assert not await can_view(session, a.id, b.id)  # el removido ya no ve
    assert not await can_view(session, b.id, a.id)
    assert await active_of(session, b) == []
    for target in (a.id, uuid4(), b.id):  # uno mismo, desconocido, ya removido
        assert (await client.delete(f"{API}/members/{target}")).status_code == 404
    # un grupo ajeno no se toca
    d, e = await mk(session, "4"), await mk(session, "5")
    await mk_group(session, d, e)
    assert (await client.delete(f"{API}/members/{e.id}")).status_code == 404
    assert len(await active_of(session, e)) == 1


# --- permisos y auditoria ---------------------------------------------------


async def test_requires_family_tags(client, session, leo):
    a = await mk(session, "1")
    leo.login(tags=[perms.RESULTS_VIEW], user_id=a.leo_user_id)
    assert (await client.get(f"{API}/me")).status_code == 403
    assert (await invite(client, "2")).status_code == 403
    assert (await client.post(f"{API}/leave")).status_code == 403
    leo.user = None
    assert (await client.get(f"{API}/me")).status_code == 401


async def test_actions_are_audited_without_health_or_document_data(
    client, session, leo
):
    a, _b = await mk(session, "1"), await mk(session, "20203030")
    login(leo, a)
    await invite(client, "20203030")
    inv = (await session.execute(select(FamilyInvitation))).scalar_one()
    await client.post(f"{API}/invitations/{inv.id}/cancel")
    await client.post(f"{API}/leave")
    blob = json.dumps(leo.events, default=str)
    assert "20203030" not in blob
    tags = {e.get("action_tag") or e.get("action") for e in leo.events}
    assert perms.FAMILY_INVITE in tags and perms.FAMILY_MANAGE in tags

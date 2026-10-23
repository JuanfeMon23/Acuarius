"""Integridad de la BD del modulo family: cada restriccion debe fallar al violarse."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.account.models import Patient
from app.modules.family.models import (
    FamilyGroup,
    FamilyInvitation,
    FamilyMembership,
    FamilyShare,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
DAY = timedelta(days=1)


async def patient(session: AsyncSession, **kw) -> Patient:
    p = Patient(
        leo_user_id=kw.get("leo_user_id", uuid4()),
        document_type=kw.get("document_type", "CC"),
        document_number=kw.get("document_number", uuid4().hex[:12]),
        birth_date=date(1990, 1, 1),
        display_name="Ana P. G.",
    )
    session.add(p)
    await session.flush()
    return p


async def group(session: AsyncSession, creator: Patient) -> FamilyGroup:
    g = FamilyGroup(created_by_patient_id=creator.id)
    session.add(g)
    await session.flush()
    return g


async def expect_violation(session: AsyncSession, obj, constraint: str) -> None:
    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            session.add(obj)
            await session.flush()
    assert constraint in str(exc.value)


def membership(g, p, status="active", **kw) -> FamilyMembership:
    if status != "active":
        kw.setdefault("left_at", NOW + DAY)
    return FamilyMembership(
        group_id=g.id, patient_id=p.id, status=status, joined_at=NOW, **kw
    )


def invitation(g, a, b, status="pending", **kw) -> FamilyInvitation:
    if status in ("accepted", "rejected", "cancelled"):
        kw.setdefault("responded_at", NOW + DAY)
    return FamilyInvitation(
        group_id=g.id,
        inviter_patient_id=a.id,
        invitee_patient_id=b.id,
        status=status,
        expires_at=kw.pop("expires_at", NOW + 7 * DAY),
        **kw,
    )


def share(g, o, v, **kw) -> FamilyShare:
    return FamilyShare(
        group_id=g.id,
        owner_patient_id=o.id,
        viewer_patient_id=v.id,
        granted_at=NOW,
        **kw,
    )


# --- patients ---------------------------------------------------------------


async def test_patient_leo_user_id_unique(session):
    a = await patient(session)
    dup = Patient(
        leo_user_id=a.leo_user_id,
        document_type="CC",
        document_number="otro",
        birth_date=date(1991, 1, 1),
        display_name="Ana P. G.",
    )
    await expect_violation(session, dup, "uq_patients_leo_user_id")


async def test_patient_document_unique_together(session):
    a = await patient(session)
    dup = Patient(
        leo_user_id=uuid4(),
        document_type=a.document_type,
        document_number=a.document_number,
        birth_date=date(1991, 1, 1),
        display_name="Ana P. G.",
    )
    await expect_violation(session, dup, "uq_patients_document_type")


async def test_patient_same_number_other_type_ok(session):
    a = await patient(session)
    await patient(session, document_type="TI", document_number=a.document_number)


async def test_patients_has_only_minimal_columns(session):
    cols = (
        (
            await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'patients'"
                )
            )
        )
        .scalars()
        .all()
    )
    assert set(cols) == {
        "id",
        "leo_user_id",
        "document_type",
        "document_number",
        "birth_date",
        "display_name",
        "created_at",
    }


# --- groups -----------------------------------------------------------------


async def test_group_dissolved_before_created_rejected(session):
    a = await patient(session)
    g = FamilyGroup(created_by_patient_id=a.id, created_at=NOW, dissolved_at=NOW - DAY)
    await expect_violation(session, g, "ck_family_groups_dissolved_after_created")


async def test_group_requires_existing_creator(session):
    await expect_violation(
        session,
        FamilyGroup(created_by_patient_id=uuid4()),
        "fk_family_groups_created_by_patient_id_patients",
    )


# --- memberships ------------------------------------------------------------


async def test_second_active_membership_in_other_group_rejected(session):
    a = await patient(session)
    g1, g2 = await group(session, a), await group(session, a)
    session.add(membership(g1, a))
    await session.flush()
    await expect_violation(
        session, membership(g2, a), "uq_family_memberships_active_patient"
    )


async def test_second_active_membership_in_same_group_rejected(session):
    a = await patient(session)
    g = await group(session, a)
    session.add(membership(g, a))
    await session.flush()
    await expect_violation(
        session, membership(g, a), "uq_family_memberships_active_patient"
    )


async def test_new_active_allowed_after_leaving(session):
    a = await patient(session)
    g1, g2 = await group(session, a), await group(session, a)
    session.add_all([membership(g1, a, "left"), membership(g1, a, "removed")])
    session.add(membership(g2, a))
    await session.flush()


async def test_membership_invalid_status_rejected(session):
    a = await patient(session)
    g = await group(session, a)
    await expect_violation(
        session, membership(g, a, "banned"), "ck_family_memberships_status_valid"
    )


async def test_active_membership_with_left_at_rejected(session):
    a = await patient(session)
    g = await group(session, a)
    await expect_violation(
        session,
        membership(g, a, left_at=NOW + DAY),
        "ck_family_memberships_status_dates_coherent",
    )


@pytest.mark.parametrize("status", ["left", "removed"])
async def test_closed_membership_without_left_at_rejected(session, status):
    a = await patient(session)
    g = await group(session, a)
    m = membership(g, a, status)
    m.left_at = None
    await expect_violation(session, m, "ck_family_memberships_status_dates_coherent")


async def test_membership_left_before_joined_rejected(session):
    a = await patient(session)
    g = await group(session, a)
    await expect_violation(
        session,
        membership(g, a, "left", left_at=NOW - DAY),
        "ck_family_memberships_left_after_joined",
    )


async def test_patient_with_memberships_cannot_be_deleted(session):
    a = await patient(session)
    g = await group(session, a)
    session.add(membership(g, a))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text("DELETE FROM patients WHERE id = :i"), {"i": a.id}
            )


# --- invitations ------------------------------------------------------------


async def test_duplicate_pending_invitation_rejected(session):
    a, b, c = [await patient(session) for _ in range(3)]
    g = await group(session, a)
    session.add(invitation(g, a, b))
    await session.flush()
    await expect_violation(
        session, invitation(g, c, b), "uq_family_invitations_pending_invitee"
    )


async def test_new_pending_allowed_after_resolution(session):
    a, b = await patient(session), await patient(session)
    g = await group(session, a)
    session.add_all(
        [
            invitation(g, a, b, "rejected"),
            invitation(g, a, b, "expired"),
            invitation(g, a, b, "cancelled"),
            invitation(g, a, b),
        ]
    )
    await session.flush()


async def test_invitation_to_self_rejected(session):
    a = await patient(session)
    g = await group(session, a)
    await expect_violation(
        session, invitation(g, a, a), "ck_family_invitations_inviter_not_invitee"
    )


async def test_invitation_invalid_status_rejected(session):
    a, b = await patient(session), await patient(session)
    g = await group(session, a)
    # Tambien incumple la coherencia estado/respuesta; basta con que la BD lo rechace.
    await expect_violation(
        session, invitation(g, a, b, "maybe"), "ck_family_invitations_"
    )


async def test_pending_invitation_with_responded_at_rejected(session):
    a, b = await patient(session), await patient(session)
    g = await group(session, a)
    await expect_violation(
        session,
        invitation(g, a, b, responded_at=NOW),
        "ck_family_invitations_status_responded_coherent",
    )


@pytest.mark.parametrize("status", ["accepted", "rejected", "cancelled"])
async def test_answered_invitation_without_responded_at_rejected(session, status):
    a, b = await patient(session), await patient(session)
    g = await group(session, a)
    inv = invitation(g, a, b, status)
    inv.responded_at = None
    await expect_violation(
        session, inv, "ck_family_invitations_status_responded_coherent"
    )


async def test_invitation_expiry_before_creation_rejected(session):
    a, b = await patient(session), await patient(session)
    g = await group(session, a)
    await expect_violation(
        session,
        invitation(g, a, b, created_at=NOW, expires_at=NOW - DAY),
        "ck_family_invitations_expires_after_created",
    )


# --- shares -----------------------------------------------------------------


async def test_share_to_self_rejected(session):
    a = await patient(session)
    g = await group(session, a)
    await expect_violation(session, share(g, a, a), "ck_family_shares_owner_not_viewer")


async def test_duplicate_active_share_rejected(session):
    a, b = await patient(session), await patient(session)
    g = await group(session, a)
    session.add(share(g, a, b))
    await session.flush()
    await expect_violation(
        session, share(g, a, b), "uq_family_shares_active_owner_viewer"
    )


async def test_reverse_and_regrant_after_revoke_allowed(session):
    a, b = await patient(session), await patient(session)
    g = await group(session, a)
    session.add_all(
        [share(g, a, b, revoked_at=NOW + DAY), share(g, a, b), share(g, b, a)]
    )
    await session.flush()


async def test_share_revoked_before_granted_rejected(session):
    a, b = await patient(session), await patient(session)
    g = await group(session, a)
    await expect_violation(
        session,
        share(g, a, b, revoked_at=NOW - DAY),
        "ck_family_shares_revoked_after_granted",
    )

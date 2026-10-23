"""Armado de `GET /family/me`: solo lo que le concierne a la sesion."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.account.models import Patient
from app.modules.family import service
from app.modules.family.models import FamilyInvitation, FamilyShare
from app.modules.family.names import DisplayNames
from app.modules.family.schemas import (
    FamilyMeOut,
    GroupOut,
    MemberOut,
    ReceivedInvitationOut,
    SentInvitationOut,
    ShareOut,
)


async def _pending(session: AsyncSession, *conds) -> list[FamilyInvitation]:
    return list(
        (
            await session.execute(
                select(FamilyInvitation)
                .where(FamilyInvitation.status == "pending", *conds)
                .order_by(FamilyInvitation.created_at)
            )
        ).scalars()
    )


async def build_overview(
    session: AsyncSession, me: Patient, names: DisplayNames
) -> FamilyMeOut:
    await service.expire_stale(session, me)
    mine = await service.my_membership(session, me.id)
    received = await _pending(session, FamilyInvitation.invitee_patient_id == me.id)
    sent = await _pending(session, FamilyInvitation.inviter_patient_id == me.id)

    members = await service.active_members(session, mine[1].id) if mine else []
    shares_given: list[FamilyShare] = []
    shares_received: list[FamilyShare] = []
    if mine:
        member_ids = {m.patient_id for m in members}
        rows = (
            await session.execute(
                select(FamilyShare).where(
                    FamilyShare.group_id == mine[1].id,
                    FamilyShare.revoked_at.is_(None),
                )
            )
        ).scalars()
        for s in rows:
            # Ambos extremos deben seguir siendo miembros activos.
            if not {s.owner_patient_id, s.viewer_patient_id} <= member_ids:
                continue
            if s.owner_patient_id == me.id:
                shares_given.append(s)
            elif s.viewer_patient_id == me.id:
                shares_received.append(s)

    patient_ids = {me.id}
    patient_ids |= {m.patient_id for m in members}
    patient_ids |= {i.inviter_patient_id for i in received}
    patient_ids |= {i.invitee_patient_id for i in sent}
    leo_ids: dict[uuid.UUID, uuid.UUID] = dict(
        (
            await session.execute(
                select(Patient.id, Patient.leo_user_id).where(
                    Patient.id.in_(patient_ids)
                )
            )
        ).all()
    )
    found = await names.lookup(list(leo_ids.values()))

    def label(patient_id: uuid.UUID, fallback: str = "Familiar") -> str:
        return found.get(leo_ids[patient_id], fallback)

    group = None
    if mine:
        group = GroupOut(
            id=mine[1].id,
            created_by_me=mine[1].created_by_patient_id == me.id,
            members=[
                MemberOut(
                    patient_id=m.patient_id,
                    display_name=label(m.patient_id),
                    is_me=m.patient_id == me.id,
                    is_creator=m.patient_id == mine[1].created_by_patient_id,
                    joined_at=m.joined_at,
                )
                for m in members
            ],
        )
    return FamilyMeOut(
        display_name="Tú",
        group=group,
        invitations_received=[
            ReceivedInvitationOut(
                id=i.id,
                inviter_display_name=label(i.inviter_patient_id),
                created_at=i.created_at,
                expires_at=i.expires_at,
            )
            for i in received
        ],
        invitations_sent=[
            SentInvitationOut(
                id=i.id,
                invitee_display_name=label(i.invitee_patient_id),
                created_at=i.created_at,
                expires_at=i.expires_at,
            )
            for i in sent
        ],
        shares_given=[
            ShareOut(
                patient_id=s.viewer_patient_id,
                display_name=label(s.viewer_patient_id),
                granted_at=s.granted_at,
            )
            for s in shares_given
        ],
        shares_received=[
            ShareOut(
                patient_id=s.owner_patient_id,
                display_name=label(s.owner_patient_id),
                granted_at=s.granted_at,
            )
            for s in shares_received
        ],
    )

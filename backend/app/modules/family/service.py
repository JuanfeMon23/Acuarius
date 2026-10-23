"""Reglas del grupo familiar. Todo se resuelve contra el paciente de la sesion
(`me`): ningun id del cliente se confia, y lo ajeno responde 404 neutro."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import runtime_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.account.models import Patient
from app.modules.family.models import (
    FamilyGroup,
    FamilyInvitation,
    FamilyMembership,
    FamilyShare,
)

MSG_ALREADY_IN_GROUP = (
    "Ya perteneces a un grupo familiar; sal de él primero para poder unirte a otro."
)
MSG_INVITATION_GONE = "La invitación ya no está disponible."
MSG_INVITATION_EXPIRED = "La invitación expiró."
MSG_NO_GROUP = "No perteneces a un grupo familiar."
MSG_NOT_FOUND = "No encontrado."


def now() -> datetime:
    return datetime.now(UTC)


# --- lecturas ---------------------------------------------------------------


async def my_membership(
    session: AsyncSession, patient_id: uuid.UUID
) -> tuple[FamilyMembership, FamilyGroup] | None:
    row = (
        await session.execute(
            select(FamilyMembership, FamilyGroup)
            .join(FamilyGroup, FamilyGroup.id == FamilyMembership.group_id)
            .where(
                FamilyMembership.patient_id == patient_id,
                FamilyMembership.status == "active",
                FamilyGroup.dissolved_at.is_(None),
            )
        )
    ).first()
    return (row[0], row[1]) if row else None


async def active_members(
    session: AsyncSession, group_id: uuid.UUID
) -> list[FamilyMembership]:
    return list(
        (
            await session.execute(
                select(FamilyMembership)
                .where(
                    FamilyMembership.group_id == group_id,
                    FamilyMembership.status == "active",
                )
                .order_by(FamilyMembership.joined_at, FamilyMembership.id)
            )
        ).scalars()
    )


async def _is_active_member(
    session: AsyncSession, group_id: uuid.UUID, patient_id: uuid.UUID
) -> bool:
    return (
        await session.execute(
            select(FamilyMembership.id).where(
                FamilyMembership.group_id == group_id,
                FamilyMembership.patient_id == patient_id,
                FamilyMembership.status == "active",
            )
        )
    ).first() is not None


# --- expiracion perezosa ----------------------------------------------------


async def expire_stale(session: AsyncSession, me: Patient) -> None:
    """Marca 'expired' las pendientes vencidas que me conciernen (como invitado,
    como quien invito o de mi grupo activo)."""
    mine = await my_membership(session, me.id)
    scope = [
        FamilyInvitation.invitee_patient_id == me.id,
        FamilyInvitation.inviter_patient_id == me.id,
    ]
    if mine:
        scope.append(FamilyInvitation.group_id == mine[1].id)
    await session.execute(
        update(FamilyInvitation)
        .where(
            FamilyInvitation.status == "pending",
            FamilyInvitation.expires_at <= now(),
            or_(*scope),
        )
        .values(status="expired")
    )


# --- invitaciones -----------------------------------------------------------


async def invite(
    session: AsyncSession, me: Patient, document_type: str, document_number: str
) -> uuid.UUID | None:
    """Devuelve el id de la invitacion creada, o `None` si no se creo por una
    causa que NO debe distinguirse para el cliente (la respuesta es neutra)."""
    await expire_stale(session, me)
    mine = await my_membership(session, me.id)
    if mine is None:
        # Siempre se crea el grupo (exista o no el invitado): no es un oraculo.
        group = FamilyGroup(created_by_patient_id=me.id)
        session.add(group)
        await session.flush()
        session.add(
            FamilyMembership(
                group_id=group.id, patient_id=me.id, status="active", joined_at=now()
            )
        )
        await session.flush()
    else:
        group = mine[1]

    pending = (
        await session.execute(
            select(FamilyInvitation.id).where(
                FamilyInvitation.group_id == group.id,
                FamilyInvitation.status == "pending",
            )
        )
    ).all()
    limits = await runtime_settings.get_many(
        "family.max_pending_per_group", "family.invitation_ttl_days"
    )
    max_pending = limits["family.max_pending_per_group"]
    if len(pending) >= max_pending:
        raise ConflictError(
            f"Tu grupo ya tiene {max_pending} invitaciones pendientes. Espera "
            "respuesta o cancela alguna."
        )

    invitee = (
        await session.execute(
            select(Patient).where(
                Patient.document_type == document_type.upper(),
                Patient.document_number == document_number,
            )
        )
    ).scalar_one_or_none()
    if invitee is None or invitee.id == me.id:
        return None
    if await my_membership(session, invitee.id) is not None:
        return None  # ya es miembro de un grupo (este u otro)

    created = now()
    invitation = FamilyInvitation(
        group_id=group.id,
        inviter_patient_id=me.id,
        invitee_patient_id=invitee.id,
        status="pending",
        created_at=created,
        expires_at=created + timedelta(days=limits["family.invitation_ttl_days"]),
    )
    try:
        async with session.begin_nested():
            session.add(invitation)
            await session.flush()
    except IntegrityError:
        return None  # ya hay una pendiente para esa persona en este grupo
    return invitation.id


async def _invitation_for_invitee(
    session: AsyncSession, me: Patient, invitation_id: uuid.UUID
) -> FamilyInvitation:
    inv = (
        await session.execute(
            select(FamilyInvitation)
            .where(
                FamilyInvitation.id == invitation_id,
                FamilyInvitation.invitee_patient_id == me.id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if inv is None:
        raise NotFoundError(MSG_NOT_FOUND)
    return inv


async def _require_open(session: AsyncSession, inv: FamilyInvitation) -> None:
    """Pendiente, vigente y con grupo no disuelto; si no, 409 legible."""
    if inv.status == "pending" and inv.expires_at <= now():
        inv.status = "expired"
        await session.flush()
    if inv.status == "expired":
        raise ConflictError(MSG_INVITATION_EXPIRED)
    group = await session.get(FamilyGroup, inv.group_id)
    if inv.status != "pending" or group is None or group.dissolved_at is not None:
        raise ConflictError(MSG_INVITATION_GONE)


async def accept(
    session: AsyncSession, me: Patient, invitation_id: uuid.UUID
) -> FamilyInvitation:
    inv = await _invitation_for_invitee(session, me, invitation_id)
    await _require_open(session, inv)
    if await my_membership(session, me.id) is not None:
        raise ConflictError(MSG_ALREADY_IN_GROUP)
    try:
        async with session.begin_nested():
            session.add(
                FamilyMembership(
                    group_id=inv.group_id,
                    patient_id=me.id,
                    status="active",
                    joined_at=now(),
                )
            )
            await session.flush()
    except IntegrityError:  # carrera: otra aceptacion gano el indice unico
        raise ConflictError(MSG_ALREADY_IN_GROUP) from None
    inv.status = "accepted"
    inv.responded_at = now()
    await session.flush()
    return inv


async def reject(
    session: AsyncSession, me: Patient, invitation_id: uuid.UUID
) -> FamilyInvitation:
    inv = await _invitation_for_invitee(session, me, invitation_id)
    await _require_open(session, inv)
    inv.status = "rejected"
    inv.responded_at = now()
    await session.flush()
    return inv


async def cancel(
    session: AsyncSession, me: Patient, invitation_id: uuid.UUID
) -> FamilyInvitation:
    inv = (
        await session.execute(
            select(FamilyInvitation)
            .where(
                FamilyInvitation.id == invitation_id,
                FamilyInvitation.inviter_patient_id == me.id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if inv is None:
        raise NotFoundError(MSG_NOT_FOUND)
    if inv.status == "pending" and inv.expires_at <= now():
        inv.status = "expired"
        await session.flush()
    if inv.status != "pending":
        raise ConflictError(
            MSG_INVITATION_EXPIRED if inv.status == "expired" else MSG_INVITATION_GONE
        )
    inv.status = "cancelled"
    inv.responded_at = now()
    await session.flush()
    return inv


# --- comparticion -----------------------------------------------------------


async def _require_membership(
    session: AsyncSession, me: Patient, message: str = MSG_NO_GROUP
) -> tuple[FamilyMembership, FamilyGroup]:
    mine = await my_membership(session, me.id)
    if mine is None:
        raise NotFoundError(message)
    return mine


async def _find_share(
    session: AsyncSession,
    group_id: uuid.UUID,
    owner_id: uuid.UUID,
    viewer_id: uuid.UUID,
) -> FamilyShare | None:
    return (
        await session.execute(
            select(FamilyShare).where(
                FamilyShare.group_id == group_id,
                FamilyShare.owner_patient_id == owner_id,
                FamilyShare.viewer_patient_id == viewer_id,
                FamilyShare.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def share(
    session: AsyncSession, me: Patient, member_patient_id: uuid.UUID
) -> FamilyShare:
    """Comparto MIS resultados con un miembro activo de MI grupo (idempotente)."""
    _, group = await _require_membership(session, me, MSG_NOT_FOUND)
    if member_patient_id == me.id or not await _is_active_member(
        session, group.id, member_patient_id
    ):
        raise NotFoundError(MSG_NOT_FOUND)
    found = await _find_share(session, group.id, me.id, member_patient_id)
    if found:
        return found
    try:
        async with session.begin_nested():
            created = FamilyShare(
                group_id=group.id,
                owner_patient_id=me.id,
                viewer_patient_id=member_patient_id,
                granted_at=now(),
            )
            session.add(created)
            await session.flush()
        return created
    except IntegrityError:  # carrera: ya la creo otra peticion
        found = await _find_share(session, group.id, me.id, member_patient_id)
        assert found is not None
        return found


async def unshare(
    session: AsyncSession, me: Patient, member_patient_id: uuid.UUID
) -> bool:
    """Revoca lo que YO comparto con ese miembro. Idempotente. `True` si revoco."""
    _, group = await _require_membership(session, me, MSG_NOT_FOUND)
    if member_patient_id == me.id:
        raise NotFoundError(MSG_NOT_FOUND)
    current = await _find_share(session, group.id, me.id, member_patient_id)
    if current is None:
        if not await _is_active_member(session, group.id, member_patient_id):
            raise NotFoundError(MSG_NOT_FOUND)
        return False
    current.revoked_at = now()
    await session.flush()
    return True


async def _revoke_shares(
    session: AsyncSession, group_id: uuid.UUID, patient_id: uuid.UUID
) -> None:
    await session.execute(
        update(FamilyShare)
        .where(
            FamilyShare.group_id == group_id,
            FamilyShare.revoked_at.is_(None),
            or_(
                FamilyShare.owner_patient_id == patient_id,
                FamilyShare.viewer_patient_id == patient_id,
            ),
        )
        .values(revoked_at=now())
    )


# --- salida y expulsion -----------------------------------------------------


async def _end_membership(
    session: AsyncSession, membership: FamilyMembership, status: str
) -> None:
    membership.status = status
    membership.left_at = now()
    await _revoke_shares(session, membership.group_id, membership.patient_id)
    await session.flush()


async def leave(session: AsyncSession, me: Patient) -> bool:
    """Sale del grupo. `True` si el grupo quedo sin miembros y se disolvio."""
    membership, group = await _require_membership(session, me)
    await _end_membership(session, membership, "left")
    if await active_members(session, group.id):
        return False
    group.dissolved_at = now()
    await session.execute(
        update(FamilyInvitation)
        .where(
            FamilyInvitation.group_id == group.id, FamilyInvitation.status == "pending"
        )
        .values(status="cancelled", responded_at=now())
    )
    await session.flush()
    return True


async def remove_member(
    session: AsyncSession, me: Patient, member_patient_id: uuid.UUID
) -> None:
    _, group = await _require_membership(session, me, MSG_NOT_FOUND)
    target = (
        await session.execute(
            select(FamilyMembership).where(
                FamilyMembership.group_id == group.id,
                FamilyMembership.patient_id == member_patient_id,
                FamilyMembership.status == "active",
            )
        )
    ).scalar_one_or_none()
    if target is None or member_patient_id == me.id:
        raise NotFoundError(MSG_NOT_FOUND)
    if group.created_by_patient_id != me.id:
        raise ForbiddenError("Solo quien creó el grupo puede quitar miembros.")
    await _end_membership(session, target, "removed")

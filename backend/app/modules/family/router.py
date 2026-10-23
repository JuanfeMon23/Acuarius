"""Grupo familiar: invitaciones, comparticion, salida y expulsion.

AUTORIZACION POR OBJETO: todo se resuelve contra el paciente de la sesion; un id
ajeno responde 404 neutro. Cada accion se audita sin datos de salud (solo ids).
"""

import uuid

from fastapi import APIRouter, Request, Response
from sqlalchemy.exc import IntegrityError

from app.core import audit, rate_limit, runtime_settings
from app.core.exceptions import ConflictError
from app.core.permissions import (
    FAMILY_INVITE,
    FAMILY_MANAGE,
    FAMILY_RESPOND,
    CanInviteFamily,
    CanManageFamily,
    CanRespondFamily,
    CanViewFamily,
)
from app.modules.account.deps import CurrentPatient, Session
from app.modules.family import service
from app.modules.family.names import DisplayNamesDep
from app.modules.family.overview import build_overview
from app.modules.family.schemas import (
    FamilyMeOut,
    InviteInput,
    InviteOutput,
    StatusOut,
)

router = APIRouter(tags=["familia"])


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _check_invite_rate(patient_id: uuid.UUID, ip: str) -> None:
    s = await runtime_settings.get_many(
        "family.invite_max_per_patient",
        "family.invite_max_per_ip",
        "family.invite_window_seconds",
    )
    rate_limit.enforce(
        "invite",
        (
            (f"patient:{patient_id}", s["family.invite_max_per_patient"]),
            (f"ip:{ip}", s["family.invite_max_per_ip"]),
        ),
        s["family.invite_window_seconds"],
    )


async def _commit(session: Session) -> None:
    try:
        await session.commit()
    except IntegrityError:  # red de seguridad ante una carrera no prevista
        await session.rollback()
        raise ConflictError(
            "No se pudo completar la acción. Inténtalo de nuevo."
        ) from None


@router.get("/me", response_model=FamilyMeOut)
async def family_me(
    session: Session, me: CurrentPatient, names: DisplayNamesDep, _u: CanViewFamily
) -> FamilyMeOut:
    out = await build_overview(session, me, names)
    await session.commit()  # persiste las expiraciones perezosas
    return out


@router.post("/invitations", status_code=202, response_model=InviteOutput)
async def invite(
    body: InviteInput,
    request: Request,
    session: Session,
    me: CurrentPatient,
    user: CanInviteFamily,
) -> InviteOutput:
    ip = _ip(request)
    await _check_invite_rate(me.id, ip)
    await service.invite(session, me, body.document_type, body.document_number)
    await _commit(session)
    # Auditoria SIN el documento consultado ni si la persona existe.
    await audit.record(
        FAMILY_INVITE,
        actor=user,
        entity_type="patient",
        entity_id=me.id,
        after={"action": "invite"},
        ip=ip,
    )
    return InviteOutput()


@router.post("/invitations/{invitation_id}/accept", response_model=StatusOut)
async def accept_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    session: Session,
    me: CurrentPatient,
    user: CanRespondFamily,
) -> StatusOut:
    inv = await service.accept(session, me, invitation_id)
    await _commit(session)
    await audit.record(
        FAMILY_RESPOND,
        actor=user,
        entity_type="family_invitation",
        entity_id=inv.id,
        after={"action": "accept", "group_id": str(inv.group_id)},
        ip=_ip(request),
    )
    return StatusOut(message="Te uniste al grupo familiar.")


@router.post("/invitations/{invitation_id}/reject", response_model=StatusOut)
async def reject_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    session: Session,
    me: CurrentPatient,
    user: CanRespondFamily,
) -> StatusOut:
    inv = await service.reject(session, me, invitation_id)
    await _commit(session)
    await audit.record(
        FAMILY_RESPOND,
        actor=user,
        entity_type="family_invitation",
        entity_id=inv.id,
        after={"action": "reject"},
        ip=_ip(request),
    )
    return StatusOut(message="Invitación rechazada.")


@router.post("/invitations/{invitation_id}/cancel", response_model=StatusOut)
async def cancel_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    session: Session,
    me: CurrentPatient,
    user: CanInviteFamily,
) -> StatusOut:
    inv = await service.cancel(session, me, invitation_id)
    await _commit(session)
    await audit.record(
        FAMILY_INVITE,
        actor=user,
        entity_type="family_invitation",
        entity_id=inv.id,
        after={"action": "cancel"},
        ip=_ip(request),
    )
    return StatusOut(message="Invitación cancelada.")


@router.put("/shares/{member_patient_id}", response_model=StatusOut)
async def put_share(
    member_patient_id: uuid.UUID,
    request: Request,
    session: Session,
    me: CurrentPatient,
    user: CanManageFamily,
) -> StatusOut:
    share = await service.share(session, me, member_patient_id)
    await _commit(session)
    await audit.record(
        FAMILY_MANAGE,
        actor=user,
        entity_type="family_share",
        entity_id=share.id,
        after={"action": "share", "viewer_patient_id": str(member_patient_id)},
        ip=_ip(request),
    )
    return StatusOut(message="Ahora compartes tus resultados con esta persona.")


@router.delete("/shares/{member_patient_id}", status_code=204)
async def delete_share(
    member_patient_id: uuid.UUID,
    request: Request,
    session: Session,
    me: CurrentPatient,
    user: CanManageFamily,
) -> Response:
    revoked = await service.unshare(session, me, member_patient_id)
    await _commit(session)
    await audit.record(
        FAMILY_MANAGE,
        actor=user,
        entity_type="patient",
        entity_id=member_patient_id,
        after={"action": "unshare", "revoked": revoked},
        ip=_ip(request),
    )
    return Response(status_code=204)


@router.post("/leave", response_model=StatusOut)
async def leave_group(
    request: Request, session: Session, me: CurrentPatient, user: CanManageFamily
) -> StatusOut:
    dissolved = await service.leave(session, me)
    await _commit(session)
    await audit.record(
        FAMILY_MANAGE,
        actor=user,
        entity_type="patient",
        entity_id=me.id,
        after={"action": "leave", "dissolved": dissolved},
        ip=_ip(request),
    )
    return StatusOut(message="Saliste del grupo familiar.")


@router.delete("/members/{patient_id}", status_code=204)
async def remove_member(
    patient_id: uuid.UUID,
    request: Request,
    session: Session,
    me: CurrentPatient,
    user: CanManageFamily,
) -> Response:
    await service.remove_member(session, me, patient_id)
    await _commit(session)
    await audit.record(
        FAMILY_MANAGE,
        actor=user,
        entity_type="patient",
        entity_id=patient_id,
        after={"action": "remove_member"},
        ip=_ip(request),
    )
    return Response(status_code=204)

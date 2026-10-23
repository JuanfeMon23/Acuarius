"""Resultados: se consultan a Incubus al momento (sin copias locales).

AUTORIZACION POR OBJETO: el documento consultado sale SIEMPRE del patient
resuelto en el servidor (la sesion o, con `patient_id`, un owner con share
activo hacia la sesion). El `order_number` nunca se confia solo: se exige que
figure en la lista de Incubus de ESE documento. Todo acceso se audita.
"""

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import StreamingResponse
from leo_sdk import LeoUser
from starlette.background import BackgroundTask

from app.core import audit
from app.core.exceptions import NotFoundError
from app.core.incubus import Incubus
from app.core.permissions import (
    RESULTS_DOWNLOAD,
    RESULTS_VIEW,
    CanDownloadResults,
    CanViewResults,
)
from app.modules.account.deps import CurrentPatient, Session
from app.modules.account.models import Patient
from app.modules.family.access import can_view

router = APIRouter(tags=["resultados"])

OrderNumber = Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]{1,40}$")]
PatientIdQuery = Annotated[uuid.UUID | None, Query()]
_NOT_FOUND = "Resultado no encontrado."


async def _resolve_target(
    session: Session,
    me: Patient,
    patient_id: uuid.UUID | None,
    user: LeoUser,
    tag: str,
    request: Request,
) -> Patient:
    """Paciente cuyos resultados se consultan. Sin share activo: 404 neutro
    (no revela si el paciente existe) y evento `denied`."""
    if patient_id is None or patient_id == me.id:
        return me
    target = await session.get(Patient, patient_id)
    if target is None or not await can_view(session, me.id, target.id):
        await audit.record(
            tag,
            actor=user,
            result="denied",
            entity_type="patient",
            entity_id=patient_id,
            reason="Acceso a paciente sin comparticion activa.",
            ip=request.client.host if request.client else None,
        )
        raise NotFoundError(_NOT_FOUND)
    return target


async def _ensure_owns(
    incubus: Incubus,
    target: Patient,
    order_number: str,
    user: LeoUser,
    tag: str,
    request: Request,
) -> None:
    if not await incubus.owns_order(
        target.document_type, target.document_number, order_number
    ):
        await audit.record(
            tag,
            actor=user,
            result="denied",
            entity_type="order",
            entity_id=order_number,
            reason="Orden que no pertenece al paciente consultado.",
            ip=request.client.host if request.client else None,
        )
        raise NotFoundError(_NOT_FOUND)


def _audit_after(me: Patient, target: Patient) -> dict:
    return {"patient_id": str(target.id), "own": target.id == me.id}


@router.get("")
async def list_results(
    request: Request,
    session: Session,
    me: CurrentPatient,
    incubus: Incubus,
    user: CanViewResults,
    patient_id: PatientIdQuery = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict:
    target = await _resolve_target(session, me, patient_id, user, RESULTS_VIEW, request)
    data = await incubus.list_orders(
        target.document_type, target.document_number, page, page_size
    )
    await audit.record(
        RESULTS_VIEW,
        actor=user,
        entity_type="patient",
        entity_id=target.id,
        after={**_audit_after(me, target), "action": "list"},
    )
    return data


@router.get("/{order_number}")
async def get_result(
    order_number: OrderNumber,
    request: Request,
    session: Session,
    me: CurrentPatient,
    incubus: Incubus,
    user: CanViewResults,
    patient_id: PatientIdQuery = None,
) -> dict:
    target = await _resolve_target(session, me, patient_id, user, RESULTS_VIEW, request)
    await _ensure_owns(incubus, target, order_number, user, RESULTS_VIEW, request)
    data = await incubus.get_order(order_number)
    if data is None:
        raise NotFoundError(_NOT_FOUND)
    await audit.record(
        RESULTS_VIEW,
        actor=user,
        entity_type="order",
        entity_id=order_number,
        after=_audit_after(me, target),
    )
    return data


@router.get("/{order_number}/report.pdf")
async def download_report(
    order_number: OrderNumber,
    request: Request,
    session: Session,
    me: CurrentPatient,
    incubus: Incubus,
    user: CanDownloadResults,
    patient_id: PatientIdQuery = None,
) -> StreamingResponse:
    target = await _resolve_target(
        session, me, patient_id, user, RESULTS_DOWNLOAD, request
    )
    await _ensure_owns(incubus, target, order_number, user, RESULTS_DOWNLOAD, request)
    upstream = await incubus.open_report(order_number)
    if upstream is None:
        raise NotFoundError(_NOT_FOUND)
    await audit.record(
        RESULTS_DOWNLOAD,
        actor=user,
        entity_type="order",
        entity_id=order_number,
        after=_audit_after(me, target),
    )
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", order_number)
    return StreamingResponse(
        upstream.aiter_bytes(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="resultados-{safe}.pdf"'
        },
        background=BackgroundTask(upstream.aclose),
    )

"""Alta con codigo de activacion (publica) y perfil de la sesion."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from leo_sdk import LeoUser
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import audit, rate_limit, runtime_settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import AppError, UpstreamError
from app.core.incubus import Incubus
from app.core.leo import auth
from app.core.password_policy import current_policy, enforce_password
from app.modules.account.deps import CurrentPatient, Session
from app.modules.account.display_name import derive_display_name
from app.modules.account.leo_users import (
    InvalidAccountData,
    LeoUsersDep,
    UsernameOrEmailTaken,
)
from app.modules.account.models import ActivationRecovery, Patient
from app.modules.account.profile import router as profile_router
from app.modules.account.schemas import (
    ActivateInput,
    ActivateOutput,
    MeOutput,
    PasswordPolicyOutput,
)

logger = logging.getLogger("app.account")
router = APIRouter(tags=["cuenta"])
router.include_router(profile_router)

ACTIVATE_TAG = "acuarius.account.activate"


class ActivationFailed(AppError):
    """Respuesta UNICA ante cualquier fallo de verificacion: no distingue codigo
    vencido, usado, documento o fecha incorrectos ni paciente ya registrado."""

    status_code = 400
    code = "activation_failed"

    def __init__(self) -> None:
        super().__init__(
            "No fue posible activar la cuenta con los datos ingresados. Verifica "
            "el código y tus datos, o consulta con el laboratorio."
        )


class ActivationNeedsRecovery(AppError):
    """El codigo ya se consumio pero la cuenta no se pudo crear."""

    status_code = 409
    code = "activation_recovery"

    def __init__(self, reference: str, message: str | None = None) -> None:
        super().__init__(
            message
            or "No pudimos terminar de crear tu cuenta. Tu código ya fue validado: "
            "comunícate con el laboratorio indicando la referencia para que lo "
            "resuelvan.",
            {"reference": reference},
        )


def get_recovery_sessions() -> async_sessionmaker[AsyncSession]:
    return AsyncSessionLocal


RecoverySessions = Annotated[
    async_sessionmaker[AsyncSession], Depends(get_recovery_sessions)
]


async def _recovery(
    sessions: async_sessionmaker[AsyncSession],
    reason: str,
    doc_type: str,
    doc_number: str,
    message: str | None = None,
) -> ActivationNeedsRecovery:
    """Caso para recuperacion manual: se persiste en `activation_recovery` con
    sesion y commit propios (la del request pudo hacer rollback). Se loguea SOLO
    referencia y motivo: ni documento, ni nombre, ni correo, ni contrasena. Si
    el insert falla, se loguea y la referencia se devuelve igual."""
    reference = uuid.uuid4().hex[:12]
    logger.error("activation_recovery reference=%s reason=%s", reference, reason)
    try:
        async with sessions() as own:
            own.add(
                ActivationRecovery(
                    reference=reference,
                    reason=reason,
                    patient_document_type=doc_type.strip().upper(),
                    patient_document_number=doc_number.strip(),
                )
            )
            await own.commit()
    except Exception:
        logger.exception(
            "activation_recovery_persist_failed reference=%s reason=%s",
            reference,
            reason,
        )
    return ActivationNeedsRecovery(reference, message)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _check_rate_limit(ip: str, doc_type: str, doc_number: str) -> None:
    s = await runtime_settings.get_many(
        "activation.max_per_ip_doc",
        "activation.max_per_doc",
        "activation.max_per_ip",
        "activation.window_seconds",
    )
    doc = f"{doc_type}:{doc_number}"
    rate_limit.enforce(
        "activation",
        (
            (f"ipdoc:{ip}:{doc}", s["activation.max_per_ip_doc"]),
            (f"doc:{doc}", s["activation.max_per_doc"]),
            (f"ip:{ip}", s["activation.max_per_ip"]),
        ),
        s["activation.window_seconds"],
    )


@router.post("/activate", status_code=201, response_model=ActivateOutput)
async def activate(
    body: ActivateInput,
    request: Request,
    session: Session,
    incubus: Incubus,
    leo_users: LeoUsersDep,
    recovery_sessions: RecoverySessions,
) -> ActivateOutput:
    ip = _client_ip(request)
    doc_type = body.document_type.upper()
    doc_number = body.document_number
    await _check_rate_limit(ip, doc_type, doc_number)
    await enforce_password(body.password.get_secret_value(), "password")

    # Ya registrado: misma respuesta neutra y el codigo NO se consume.
    exists = (
        await session.execute(
            select(Patient.id).where(
                Patient.document_type == doc_type,
                Patient.document_number == doc_number,
            )
        )
    ).first()
    if exists:
        raise ActivationFailed

    data = await incubus.verify_activation(
        {
            "code": body.code,
            "document_type": doc_type,
            "document_number": doc_number,
            "birth_date": body.birth_date.isoformat(),
        }
    )
    if data is None:
        raise ActivationFailed

    # --- desde aqui el codigo YA esta consumido ---
    first = " ".join(filter(None, [data.get("first_name"), data.get("second_name")]))
    last = " ".join(
        filter(None, [data.get("first_last_name"), data.get("second_last_name")])
    )
    try:
        created = await leo_users.create_patient(
            {
                "username": body.username,
                "email": body.email,
                "password": body.password.get_secret_value(),
                "document_type": doc_type,
                "document_number": doc_number,
                "first_name": first,
                "last_name": last,
            }
        )
    except UsernameOrEmailTaken:
        raise await _recovery(
            recovery_sessions,
            "leo_conflict",
            doc_type,
            doc_number,
            "Ese usuario o correo no está disponible. Tu código ya fue validado: "
            "comunícate con el laboratorio indicando la referencia.",
        ) from None
    except InvalidAccountData as exc:
        # Contrasena rechazada por Leo -> weak_password; otro campo (usuario/correo)
        # se trata como conflicto de cuenta.
        reason = (
            "leo_weak_password"
            if any(d.get("field") == "password" for d in exc.details)
            else "leo_conflict"
        )
        raise await _recovery(
            recovery_sessions, reason, doc_type, doc_number, exc.message
        ) from None
    except UpstreamError:
        raise await _recovery(
            recovery_sessions, "leo_unavailable", doc_type, doc_number
        ) from None

    try:
        patient = Patient(
            leo_user_id=created.id,
            document_type=doc_type,
            document_number=doc_number,
            birth_date=body.birth_date,
            display_name=derive_display_name(data),
        )
        session.add(patient)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise await _recovery(
            recovery_sessions, "db_error", doc_type, doc_number
        ) from None

    await audit.record(
        ACTIVATE_TAG,
        actor=None,
        entity_type="patient",
        entity_id=patient.id,
        after={"activation": "completed"},
        ip=ip,
    )
    return ActivateOutput(username=created.username)


@router.get("/me", response_model=MeOutput)
async def me(
    patient: CurrentPatient,
    user: Annotated[LeoUser, Depends(auth.current_person)],
) -> MeOutput:
    return MeOutput(
        patient_id=str(patient.id),
        username=user.username,
        name=user.name,
        email=user.email,
        document_type=patient.document_type,
        document_number=patient.document_number,
        birth_date=patient.birth_date,
        display_name=patient.display_name,
    )


POLICY_WINDOW_SECONDS = 60


@router.get("/password-policy", response_model=PasswordPolicyOutput)
async def password_policy(request: Request, response: Response) -> PasswordPolicyOutput:
    """PUBLICA: la politica vigente de Leo (activacion y perfil la muestran).
    Cacheable 30 s; limitada por IP."""
    limit = await runtime_settings.get("account.public_policy_per_window")
    rate_limit.enforce(
        "policy", ((f"ip:{_client_ip(request)}", limit),), POLICY_WINDOW_SECONDS
    )
    policy = await current_policy()
    response.headers["Cache-Control"] = "public, max-age=30"
    return PasswordPolicyOutput(**policy.model_dump())

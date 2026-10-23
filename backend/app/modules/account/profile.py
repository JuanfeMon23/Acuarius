"""Autogestion del paciente: perfil y contrasena, en nombre del usuario.

Proxy 1:1 a Leo (`LeoClient.update_user_profile` / `change_user_password`) con
el access token de la propia sesion; jamas se acepta un id ni un token del
cuerpo. Acuarius no guarda correo ni contrasena: solo `patients.display_name`.
Las contrasenas viajan como `SecretStr` y no se registran en logs/auditoria.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from leo_sdk import InvalidTokenError, LeoError, LeoUser, TooManyAttemptsError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.exceptions import AppError, RateLimitedError, UpstreamError
from app.core.leo import auth
from app.core.rate_limit import SlidingWindowLimiter
from app.modules.account.deps import CurrentPatient, Session
from app.modules.account.display_name import derive_display_name
from app.modules.account.leo_users import _safe_details
from app.modules.account.schemas import (
    PasswordChangeInput,
    ProfileOutput,
    ProfileUpdateInput,
)

logger = logging.getLogger("app.account.profile")
router = APIRouter()

limiter = SlidingWindowLimiter()
PROFILE_TAG = "acuarius.account.profile-update"
PASSWORD_TAG = "acuarius.account.password-change"

CurrentUser = Annotated[LeoUser, Depends(auth.current_person)]

# codigo de Leo -> (estado, mensaje propio). Mensajes fijos: no se reenvia texto
# de Leo (podria traer detalles internos).
_FORWARDED: dict[str, tuple[int, str]] = {
    "current_password_required": (
        422,
        "Para cambiar el correo debes indicar tu contraseña actual.",
    ),
    "invalid_current_password": (403, "La contraseña actual no es correcta."),
    "invalid_credentials": (403, "La contraseña actual no es correcta."),
    "duplicate": (409, "Ese correo ya está en uso."),
    "weak_password": (422, "La nueva contraseña no cumple los requisitos."),
    "same_password": (422, "La nueva contraseña debe ser distinta de la actual."),
    "validation_error": (422, "Revisa los datos enviados."),
}


class _Forwarded(AppError):
    def __init__(
        self, status_code: int, code: str, message: str, details: Any = None
    ) -> None:
        super().__init__(message, details)
        self.status_code = status_code
        self.code = code


def _translate(exc: LeoError) -> AppError:
    if isinstance(exc, InvalidTokenError) and exc.is_user_token:
        return _Forwarded(401, "not_authenticated", "Inicia sesión para continuar.")
    if isinstance(exc, TooManyAttemptsError):
        retry = exc.retry_after
        return RateLimitedError(
            "Demasiados intentos. Inténtalo de nuevo más tarde.",
            {"retry_after_seconds": retry} if retry else None,
            headers={"Retry-After": str(retry)} if retry else None,
        )
    known = _FORWARDED.get(exc.code)
    if known is None:
        logger.warning("leo_profile_error code=%s status=%s", exc.code, exc.status_code)
        return UpstreamError(
            "No se pudo completar la operación en este momento. Inténtalo de nuevo."
        )
    details: Any = None
    if exc.code == "duplicate":
        details = {"field": "email"}
    elif exc.code in ("weak_password", "validation_error"):
        details = _safe_details(exc.details) or None
    elif exc.code == "current_password_required":
        details = {"field": "current_password"}
    return _Forwarded(known[0], exc.code, known[1], details)


def _check_rate_limit(user: LeoUser) -> None:
    s = get_settings()
    retry = limiter.hit(
        f"user:{user.id}", s.profile_max_per_user, s.profile_window_seconds
    )
    if retry is not None:
        raise RateLimitedError(
            "Demasiados intentos. Inténtalo de nuevo más tarde.",
            {"retry_after_seconds": int(retry)},
            headers={"Retry-After": str(int(retry))},
        )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/profile", response_model=ProfileOutput)
async def get_profile(user: CurrentUser, _patient: CurrentPatient) -> ProfileOutput:
    return ProfileOutput(
        first_name=user.first_name or user.name,
        last_name=user.last_name,
        email=user.email,
        username=user.username,
    )


@router.patch("/profile", response_model=ProfileOutput)
async def update_profile(
    body: ProfileUpdateInput,
    request: Request,
    user: CurrentUser,
    patient: CurrentPatient,
    session: Session,
) -> ProfileOutput:
    _check_rate_limit(user)
    changed = ",".join(
        k for k in ("first_name", "last_name", "email") if getattr(body, k) is not None
    )
    try:
        profile = await auth.client.update_user_profile(
            user.access_token,
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            current_password=(
                body.current_password.get_secret_value()
                if body.current_password
                else None
            ),
        )
    except LeoError as exc:
        await audit.record(
            PROFILE_TAG,
            actor=user,
            entity_type="patient",
            entity_id=patient.id,
            result="error",
            reason=exc.code,
            ip=_ip(request),
        )
        raise _translate(exc) from None
    auth.sessions.forget(user.access_token)
    if body.first_name is not None or body.last_name is not None:
        await _sync_display_name(
            session, patient, profile.first_name, profile.last_name
        )
    await audit.record(
        PROFILE_TAG,
        actor=user,
        entity_type="patient",
        entity_id=patient.id,
        after={"fields": changed},
        ip=_ip(request),
    )
    return ProfileOutput(
        first_name=profile.first_name,
        last_name=profile.last_name,
        email=profile.email,
        username=profile.username,
    )


async def _sync_display_name(
    session: AsyncSession, patient: Any, first: str, last: str
) -> None:
    patient.display_name = derive_display_name(
        {"first_name": first, "first_last_name": last}
    )
    await session.commit()


@router.post("/password", status_code=204)
async def change_password(
    body: PasswordChangeInput,
    request: Request,
    user: CurrentUser,
    patient: CurrentPatient,
) -> Response:
    _check_rate_limit(user)
    try:
        await auth.client.change_user_password(
            user.access_token,
            body.current_password.get_secret_value(),
            body.new_password.get_secret_value(),
        )
    except LeoError as exc:
        await audit.record(
            PASSWORD_TAG,
            actor=user,
            entity_type="patient",
            entity_id=patient.id,
            result="error",
            reason=exc.code,
            ip=_ip(request),
        )
        raise _translate(exc) from None
    await audit.record(
        PASSWORD_TAG,
        actor=user,
        entity_type="patient",
        entity_id=patient.id,
        ip=_ip(request),
    )
    return Response(status_code=204)

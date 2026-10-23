"""Politica de contrasenas: la define Leo (`GET /auth/password-policy`, via
`LeoClient.password_policy()`, con cache de 30 s en el SDK). Acuarius no replica
reglas: solo valida ANTES de consumir el codigo de activacion o llamar a Leo.
Si Leo no responde, se aplica la politica estricta por defecto (12-128 y las
cuatro clases)."""

import logging

import httpx
from leo_sdk import LeoError, PasswordPolicy

from app.core.exceptions import ValidationAppError
from app.core.leo import auth

logger = logging.getLogger("app.password_policy")

STRICT_POLICY = PasswordPolicy()


def _messages(policy: PasswordPolicy) -> dict[str, str]:
    return {
        "too_short": f"debe tener al menos {policy.min_length} caracteres",
        "too_long": f"debe tener como máximo {policy.max_length} caracteres",
        "no_lowercase": "debe incluir una minúscula",
        "no_uppercase": "debe incluir una mayúscula",
        "no_digit": "debe incluir un dígito",
        "no_symbol": "debe incluir un símbolo",
    }


async def current_policy() -> PasswordPolicy:
    try:
        return await auth.client.password_policy()
    except (LeoError, httpx.HTTPError, ValueError):
        logger.warning("Leo no entregó la política de contraseñas; se usa la estricta.")
        return STRICT_POLICY


async def enforce_password(password: str, field: str) -> None:
    """422 `validation_error` (sin eco de la contrasena) si no cumple."""
    policy = await current_policy()
    codes = policy.check(password)
    if not codes:
        return
    messages = _messages(policy)
    raise ValidationAppError(
        "La contraseña no cumple los requisitos.",
        [
            {
                "field": field,
                "message": "La contraseña " + messages[code] + ".",
                "code": code,
            }
            for code in codes
        ],
    )

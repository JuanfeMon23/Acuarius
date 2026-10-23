"""Ajustes editables de Acuarius (tabla `settings`): registro de claves + store.

Los limites de intentos, la vigencia de invitaciones y la paginacion se
declaran AQUI y se leen en cada peticion con `await get("<clave>")` (cache en
proceso de ~10 s, invalidada al instante al editar). Si la BD falla o la fila
falta, se usa el default del registro (nunca un valor fuera de rango). El
modulo compartido es `leo_sdk.settings_store`; el router vive en
`app.modules.settings`.

Infraestructura (URLs, DB, CORS, credenciales) NO esta aqui: sigue en variables
de entorno (`app.core.config`).
"""

import logging
from typing import Any

from leo_sdk.settings_store import SettingDef, SettingsRegistry, SettingsStore

from app.core.config import LegacyPolicyEnv
from app.core.database import AsyncSessionLocal
from app.core.db.settings_model import SETTINGS_MODELS

logger = logging.getLogger("app.settings")

CACHE_TTL_SECONDS = 10.0


def _int(
    key: str,
    default: int,
    minimum: int,
    maximum: int,
    description: str,
    *,
    unit: str = "count",
    security: bool = False,
) -> SettingDef:
    return SettingDef(
        key,
        "int",
        default,
        description,
        min=minimum,
        max=maximum,
        unit=unit,
        requires_security=security,
    )


ACUARIUS_SETTINGS = SettingsRegistry(
    [
        _int(
            "activation.max_per_ip_doc",
            5,
            3,
            20,
            "Intentos de activación por ventana desde una IP para un mismo documento.",
            security=True,
        ),
        _int(
            "activation.max_per_doc",
            15,
            5,
            60,
            "Intentos de activación por ventana para un mismo documento (todas las IP).",
            security=True,
        ),
        _int(
            "activation.max_per_ip",
            30,
            10,
            200,
            "Intentos de activación por ventana desde una misma IP.",
            security=True,
        ),
        _int(
            "activation.window_seconds",
            900,
            60,
            3600,
            "Duración de la ventana de los límites de activación.",
            unit="seconds",
            security=True,
        ),
        _int(
            "profile.max_per_user",
            10,
            3,
            50,
            "Cambios de perfil o contraseña por ventana y por usuario.",
            security=True,
        ),
        _int(
            "profile.window_seconds",
            900,
            60,
            3600,
            "Duración de la ventana del límite de perfil y contraseña.",
            unit="seconds",
            security=True,
        ),
        _int(
            "family.invite_max_per_patient",
            20,
            5,
            100,
            "Invitaciones familiares por ventana y por paciente.",
            security=True,
        ),
        _int(
            "family.invite_max_per_ip",
            30,
            5,
            200,
            "Invitaciones familiares por ventana y por IP.",
            security=True,
        ),
        _int(
            "family.invite_window_seconds",
            3600,
            300,
            86400,
            "Duración de la ventana de los límites de invitaciones.",
            unit="seconds",
            security=True,
        ),
        _int(
            "family.invitation_ttl_days",
            7,
            1,
            30,
            "Días de vigencia de una invitación familiar.",
            unit="days",
        ),
        _int(
            "family.max_pending_per_group",
            10,
            1,
            50,
            "Invitaciones pendientes simultáneas por grupo familiar.",
        ),
        _int(
            "results.max_page_size",
            50,
            10,
            200,
            "Máximo de resultados por página en el listado.",
        ),
        _int(
            "account.public_policy_per_window",
            60,
            10,
            600,
            "Consultas de la política de contraseñas (pública) por minuto y por IP.",
        ),
    ]
)

store = SettingsStore(
    ACUARIUS_SETTINGS,
    AsyncSessionLocal,
    SETTINGS_MODELS,
    cache_ttl=CACHE_TTL_SECONDS,
)


async def get(key: str) -> Any:
    """Valor vigente del ajuste (con cache; nunca lanza por la BD)."""
    return await store.get(key)


async def get_many(*keys: str) -> dict[str, Any]:
    return await store.get_many(keys)


async def sync_on_startup() -> None:
    """Alinea la tabla con el registro (llamar al arrancar la API). Las
    variables antiguas (`LegacyPolicyEnv`) solo fijan el valor inicial de una
    clave que aun no existe. Si la BD no responde, la app arranca igual con
    los defaults (y el fallo queda en el log)."""
    try:
        result = await store.sync_registry(LegacyPolicyEnv().initial_values())
    except Exception:
        logger.exception("No se pudo sincronizar la tabla de ajustes al arrancar.")
        return
    if result.inserted or result.updated or result.adjusted:
        logger.info(
            "Ajustes sincronizados: %d nuevos, %d con metadatos actualizados, "
            "%d valores ajustados al rango.",
            len(result.inserted),
            len(result.updated),
            len(result.adjusted),
        )

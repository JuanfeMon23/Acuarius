"""Puerto de auditoria hacia Leo (`auth.audit` del SDK).

SIN datos de salud ni personales: solo ids, codigos y resultado. Nunca propaga
un fallo: el SDK encola y reintenta; lo que no se pueda enviar solo se loguea.

Limite conocido: el SDK atribuye el evento a un actor humano; los eventos sin
sesion (alta de cuenta) salen sin actor y Leo puede rechazarlos hasta aceptar
eventos anonimos de la app (ver reporte).
"""

import logging
from collections.abc import Mapping
from typing import Any

from leo_sdk import LeoUser

from app.core.leo import auth

logger = logging.getLogger("app.audit")


async def record(
    action_tag: str,
    *,
    actor: LeoUser | None,
    entity_type: str,
    entity_id: object,
    result: str = "ok",
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    reason: str | None = None,
    ip: str | None = None,
) -> None:
    try:
        await auth.audit.record(
            action_tag,
            result,
            entity_type=entity_type,
            entity_id=str(entity_id),
            changes=auth.audit.diff(before, after) if before or after else None,
            reason=reason,
            actor=actor,
            ip=ip,
        )
    except Exception:
        logger.exception("No se pudo registrar el evento de auditoria %s.", action_tag)

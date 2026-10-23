"""Rutas `/api/v1/settings` (router compartido del SDK + permisos de Leo y
auditoria de Acuarius)."""

from typing import Any

from leo_sdk import LeoUser
from leo_sdk.settings_store import (
    SettingsActor,
    SettingsRouterDeps,
    build_settings_router,
)

from app.core import audit, runtime_settings
from app.core.leo import auth
from app.core.permissions import (
    SETTINGS_EDIT,
    SETTINGS_EDIT_SECURITY,
    SETTINGS_VIEW,
)

UPDATE_TAG = "acuarius.settings.update"


def _actor_of(user: LeoUser) -> SettingsActor:
    return SettingsActor(user_id=user.id, username=user.username)


async def audit_update(
    user: LeoUser, key: str, before: Any, after: Any, reason: str
) -> None:
    """Evento `acuarius.settings.update` (valor anterior y nuevo, y el motivo)."""
    await audit.record(
        UPDATE_TAG,
        actor=user,
        entity_type="setting",
        entity_id=key,
        before={"value": before},
        after={"value": after},
        reason=reason,
    )


router = build_settings_router(
    runtime_settings.store,
    SettingsRouterDeps(
        view_dep=auth.require_action(SETTINGS_VIEW),
        edit_dep=auth.require_action(SETTINGS_EDIT),
        edit_security_dep=auth.require_action(SETTINGS_EDIT_SECURITY),
        audit=audit_update,
        actor_of=_actor_of,
    ),
)

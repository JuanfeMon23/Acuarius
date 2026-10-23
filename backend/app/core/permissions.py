"""Catalogo de modulos y acciones de Acuarius en Leo (`acuarius.<modulo>.<accion>`).

Se publica con `uv run python -m app.core.leo_sync`.
"""

from typing import Annotated

from leo_sdk import LeoUser

from app.core.leo import APP_SLUG, auth, catalog


def _module(slug: str, name: str, description: str) -> str:
    catalog.module(slug, name, description)
    return slug


def _action(module: str, verb: str, name: str, description: str) -> str:
    catalog.action(module, verb, name, description)
    return f"{APP_SLUG}.{module}.{verb}"


_RES = _module("results", "Resultados", "Resultados de laboratorio del paciente.")
RESULTS_VIEW = _action(
    _RES, "view", "Consultar resultados",
    "Ver el listado y el detalle de los resultados propios y compartidos.",
)  # fmt: skip
RESULTS_DOWNLOAD = _action(
    _RES, "download", "Descargar resultados",
    "Descargar el PDF de los resultados propios y compartidos.",
)  # fmt: skip

_FAM = _module(
    "family", "Grupo familiar", "Grupo familiar y comparticion de resultados."
)
FAMILY_VIEW = _action(
    _FAM, "view", "Consultar el grupo familiar",
    "Ver el grupo familiar, sus miembros y comparticiones.",
)  # fmt: skip
FAMILY_INVITE = _action(
    _FAM, "invite", "Invitar al grupo familiar",
    "Invitar a otro paciente al grupo familiar.",
)  # fmt: skip
FAMILY_RESPOND = _action(
    _FAM, "respond", "Responder invitaciones familiares",
    "Aceptar o rechazar una invitacion al grupo familiar.",
)  # fmt: skip
FAMILY_MANAGE = _action(
    _FAM, "manage", "Gestionar el grupo familiar",
    "Compartir o revocar resultados, salir del grupo o quitar miembros.",
)  # fmt: skip

_SET = _module("settings", "Ajustes", "Politicas operativas editables de Acuarius.")
SETTINGS_VIEW = _action(
    _SET, "view", "Consultar ajustes",
    "Ver los ajustes operativos y su historial de cambios.",
)  # fmt: skip
SETTINGS_EDIT = _action(
    _SET, "edit", "Editar ajustes",
    "Editar los ajustes operativos que no son de seguridad.",
)  # fmt: skip
SETTINGS_EDIT_SECURITY = _action(
    _SET, "edit-security", "Editar ajustes de seguridad",
    "Editar los limites de intentos (activacion, perfil, invitaciones).",
)  # fmt: skip

_one = auth.require_action
CanViewResults = Annotated[LeoUser, _one(RESULTS_VIEW)]
CanDownloadResults = Annotated[LeoUser, _one(RESULTS_DOWNLOAD)]
CanViewFamily = Annotated[LeoUser, _one(FAMILY_VIEW)]
CanInviteFamily = Annotated[LeoUser, _one(FAMILY_INVITE)]
CanRespondFamily = Annotated[LeoUser, _one(FAMILY_RESPOND)]
CanManageFamily = Annotated[LeoUser, _one(FAMILY_MANAGE)]
CanViewSettings = Annotated[LeoUser, _one(SETTINGS_VIEW)]
CanEditSettings = Annotated[LeoUser, _one(SETTINGS_EDIT)]
CanEditSecuritySettings = Annotated[LeoUser, _one(SETTINGS_EDIT_SECURITY)]

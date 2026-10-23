"""Aprovisionamiento de pacientes en Leo (`POST /users/service/patients`,
credencial de servicio, audiencia `leo`)."""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends

from app.core.exceptions import UpstreamError
from app.core.service_client import ServiceClient, leo_service


class UsernameOrEmailTaken(Exception):
    """Leo respondio 409 (generico: usuario o correo ya existe)."""


class InvalidAccountData(Exception):
    """Leo respondio 422 (p. ej. contrasena debil); `message`/`details` se muestran."""

    def __init__(self, message: str, details: list[dict[str, str]]):
        self.message = message
        self.details = details


@dataclass(frozen=True, slots=True)
class CreatedUser:
    id: UUID
    username: str


def _safe_details(raw: Any) -> list[dict[str, str]]:
    """Solo campo y mensaje; jamas el valor recibido."""
    out: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and isinstance(
                item.get("message", item.get("msg")), str
            ):
                field = item.get("field") or ".".join(
                    str(p) for p in (item.get("loc") or [])[1:]
                )
                out.append(
                    {
                        "field": str(field),
                        "message": item.get("message", item.get("msg")),
                    }
                )
    return out


class LeoUsers:
    def __init__(self, client: ServiceClient) -> None:
        self._c = client

    async def create_patient(self, body: dict[str, str]) -> CreatedUser:
        r = await self._c.request("POST", "/users/service/patients", json=body)
        if r.status_code in (200, 201):
            data = r.json()
            return CreatedUser(UUID(data["id"]), data["username"])
        if r.status_code == 409:
            raise UsernameOrEmailTaken
        if r.status_code == 422:
            try:
                payload = r.json()
            except ValueError:
                payload = {}
            message = payload.get("message")
            raise InvalidAccountData(
                message
                if isinstance(message, str)
                else "Revisa los datos de la cuenta.",
                _safe_details(payload.get("details")),
            )
        raise UpstreamError(
            "No se pudo crear la cuenta en este momento. Inténtalo de nuevo."
        )


def get_leo_users() -> LeoUsers:
    return LeoUsers(leo_service())


LeoUsersDep = Annotated[LeoUsers, Depends(get_leo_users)]

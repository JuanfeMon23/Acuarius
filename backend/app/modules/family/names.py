"""Nombre visible de un miembro: el `display_name` guardado en `patients`
(nombre de pila + iniciales del apellido, derivado al activar la cuenta)."""

from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select

from app.modules.account.deps import Session
from app.modules.account.models import Patient


class DisplayNames(Protocol):
    async def lookup(self, leo_user_ids: list[UUID]) -> dict[UUID, str]: ...


class DbDisplayNames:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def lookup(self, leo_user_ids: list[UUID]) -> dict[UUID, str]:
        if not leo_user_ids:
            return {}
        rows = await self._session.execute(
            select(Patient.leo_user_id, Patient.display_name).where(
                Patient.leo_user_id.in_(leo_user_ids)
            )
        )
        return dict(rows.all())


def get_display_names(session: Session) -> DisplayNames:
    return DbDisplayNames(session)


DisplayNamesDep = Annotated[DisplayNames, Depends(get_display_names)]

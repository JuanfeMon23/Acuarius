"""Paciente de la sesion: UNICA fuente del documento que se consulta a Incubus."""

from typing import Annotated

from fastapi import Depends
from leo_sdk import LeoUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import ForbiddenError
from app.core.leo import auth
from app.modules.account.models import Patient

Session = Annotated[AsyncSession, Depends(get_session)]


async def _current_patient(
    session: Session, user: Annotated[LeoUser, Depends(auth.current_person)]
) -> Patient:
    patient = (
        await session.execute(select(Patient).where(Patient.leo_user_id == user.id))
    ).scalar_one_or_none()
    if patient is None:
        raise ForbiddenError("Tu cuenta no tiene un perfil de paciente.")
    return patient


CurrentPatient = Annotated[Patient, Depends(_current_patient)]

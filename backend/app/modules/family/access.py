"""Regla de visibilidad entre pacientes: `viewer` ve a `owner` solo con un share
ACTIVO (no revocado) dentro de un grupo vigente donde AMBOS son miembros activos."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.family.models import FamilyGroup, FamilyMembership, FamilyShare


async def can_view(
    session: AsyncSession, viewer_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    mv = aliased(FamilyMembership)
    mo = aliased(FamilyMembership)
    query = select(
        exists()
        .where(
            FamilyShare.viewer_patient_id == viewer_id,
            FamilyShare.owner_patient_id == owner_id,
            FamilyShare.revoked_at.is_(None),
            FamilyGroup.id == FamilyShare.group_id,
            FamilyGroup.dissolved_at.is_(None),
            mv.group_id == FamilyShare.group_id,
            mv.patient_id == FamilyShare.viewer_patient_id,
            mv.status == "active",
            mo.group_id == FamilyShare.group_id,
            mo.patient_id == FamilyShare.owner_patient_id,
            mo.status == "active",
        )
        .correlate(None)
    )
    return bool((await session.execute(query)).scalar())

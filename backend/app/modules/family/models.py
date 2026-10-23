"""Modelos de `family`: grupo familiar, membresias, invitaciones y comparticiones.

La auditoria de accesos NO vive aqui (va a Leo). Las restricciones de integridad
(un solo grupo activo por paciente, una invitacion pendiente por destinatario,
etc.) estan en la BD, no solo en el backend.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base
from app.core.db.mixins import CreatedAt, UUIDv7PK

MEMBERSHIP_STATUSES = ("active", "left", "removed")
INVITATION_STATUSES = ("pending", "accepted", "rejected", "cancelled", "expired")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _patient_fk() -> ForeignKey:
    return ForeignKey("patients.id", ondelete="RESTRICT")


def _group_fk() -> ForeignKey:
    return ForeignKey("family_groups.id", ondelete="RESTRICT")


def _tstz(nullable: bool = False) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=nullable)


class FamilyGroup(UUIDv7PK, CreatedAt, Base):
    __tablename__ = "family_groups"
    __table_args__ = (
        CheckConstraint(
            "dissolved_at IS NULL OR dissolved_at >= created_at",
            name="dissolved_after_created",
        ),
    )

    created_by_patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _patient_fk(), nullable=False
    )
    dissolved_at: Mapped[datetime | None] = _tstz(nullable=True)


class FamilyMembership(UUIDv7PK, Base):
    __tablename__ = "family_memberships"
    __table_args__ = (
        CheckConstraint(_in("status", MEMBERSHIP_STATUSES), name="status_valid"),
        CheckConstraint(
            "(status = 'active' AND left_at IS NULL) "
            "OR (status <> 'active' AND left_at IS NOT NULL)",
            name="status_dates_coherent",
        ),
        CheckConstraint(
            "left_at IS NULL OR left_at >= joined_at", name="left_after_joined"
        ),
        # Un paciente solo puede tener UNA membresia activa (en cualquier grupo).
        Index(
            "uq_family_memberships_active_patient",
            "patient_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_family_memberships_group_id", "group_id"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _group_fk(), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _patient_fk(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    joined_at: Mapped[datetime] = _tstz()
    left_at: Mapped[datetime | None] = _tstz(nullable=True)


class FamilyInvitation(UUIDv7PK, CreatedAt, Base):
    __tablename__ = "family_invitations"
    __table_args__ = (
        CheckConstraint(
            "inviter_patient_id <> invitee_patient_id", name="inviter_not_invitee"
        ),
        CheckConstraint(_in("status", INVITATION_STATUSES), name="status_valid"),
        # 'expired' puede resolverse sin respuesta explicita (responded_at libre).
        CheckConstraint(
            "(status = 'pending' AND responded_at IS NULL) "
            "OR (status IN ('accepted', 'rejected', 'cancelled') "
            "AND responded_at IS NOT NULL) "
            "OR status = 'expired'",
            name="status_responded_coherent",
        ),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
        Index(
            "uq_family_invitations_pending_invitee",
            "group_id",
            "invitee_patient_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_family_invitations_invitee_patient_id", "invitee_patient_id"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _group_fk(), nullable=False
    )
    inviter_patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _patient_fk(), nullable=False
    )
    invitee_patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _patient_fk(), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), server_default=text("'pending'"), nullable=False
    )
    expires_at: Mapped[datetime] = _tstz()
    responded_at: Mapped[datetime | None] = _tstz(nullable=True)


class FamilyShare(UUIDv7PK, Base):
    """`owner` comparte sus resultados con `viewer`. Por defecto nadie."""

    __tablename__ = "family_shares"
    __table_args__ = (
        CheckConstraint(
            "owner_patient_id <> viewer_patient_id", name="owner_not_viewer"
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= granted_at",
            name="revoked_after_granted",
        ),
        Index(
            "uq_family_shares_active_owner_viewer",
            "group_id",
            "owner_patient_id",
            "viewer_patient_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("ix_family_shares_viewer_patient_id", "viewer_patient_id"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _group_fk(), nullable=False
    )
    owner_patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _patient_fk(), nullable=False
    )
    viewer_patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), _patient_fk(), nullable=False
    )
    granted_at: Mapped[datetime] = _tstz()
    revoked_at: Mapped[datetime | None] = _tstz(nullable=True)

"""Modelos de `account`. `Patient` es solo el vinculo con Leo (identidad y nombres
viven en Leo/Incubus; aqui no hay datos de salud ni nombres)."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base
from app.core.db.mixins import CreatedAt, UUIDv7PK


class Patient(UUIDv7PK, CreatedAt, Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("document_type", "document_number"),
        CheckConstraint(
            "char_length(display_name) >= 1", name="display_name_not_empty"
        ),
    )

    leo_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(16), nullable=False)
    document_number: Mapped[str] = mapped_column(String(32), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Nombre corto para mostrar a familiares (p.ej. "Ana P. G."); nunca nombre completo.
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)


RECOVERY_REASONS = (
    "leo_conflict",
    "leo_weak_password",
    "leo_unavailable",
    "db_error",
)


class ActivationRecovery(UUIDv7PK, CreatedAt, Base):
    """Activacion con codigo ya consumido pero cuenta no creada: cola para el
    personal. Dato minimo: el documento permite localizar al paciente; sin
    nombre, correo ni contrasena."""

    __tablename__ = "activation_recovery"
    __table_args__ = (
        CheckConstraint(
            "reason IN ({})".format(", ".join(repr(r) for r in RECOVERY_REASONS)),
            name="reason_valid",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= created_at",
            name="resolved_after_created",
        ),
        Index(
            "ix_activation_recovery_unresolved",
            "created_at",
            postgresql_where=text("resolved_at IS NULL"),
        ),
    )

    reference: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    patient_document_type: Mapped[str] = mapped_column(String(16), nullable=False)
    patient_document_number: Mapped[str] = mapped_column(String(32), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

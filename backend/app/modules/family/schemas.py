"""Entradas/salidas de `family`. Nunca documento ni correo de otras personas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InviteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: str = Field(min_length=1, max_length=8)
    document_number: str = Field(min_length=1, max_length=20)

    @field_validator("document_type", "document_number", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class InviteOutput(BaseModel):
    message: str = "Si la persona está registrada, recibirá la invitación."


class MemberOut(BaseModel):
    patient_id: UUID
    display_name: str
    is_me: bool
    is_creator: bool
    joined_at: datetime


class GroupOut(BaseModel):
    id: UUID
    created_by_me: bool
    members: list[MemberOut]


class ReceivedInvitationOut(BaseModel):
    id: UUID
    inviter_display_name: str
    created_at: datetime
    expires_at: datetime


class SentInvitationOut(BaseModel):
    id: UUID
    invitee_display_name: str
    created_at: datetime
    expires_at: datetime


class ShareOut(BaseModel):
    patient_id: UUID
    display_name: str
    granted_at: datetime


class FamilyMeOut(BaseModel):
    display_name: str
    group: GroupOut | None
    invitations_received: list[ReceivedInvitationOut]
    invitations_sent: list[SentInvitationOut]
    shares_given: list[ShareOut]
    shares_received: list[ShareOut]


class StatusOut(BaseModel):
    message: str

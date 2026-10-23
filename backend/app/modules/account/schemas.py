"""Entradas/salidas de `account`. Usuario y correo se validan aqui para rechazar
ANTES de consumir el codigo de un solo uso; la contrasena se valida contra la
politica de Leo (`app.core.password_policy`), no con reglas locales."""

import re
from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

USERNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9._-]{1,62})[a-z0-9]$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


class ActivateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32)
    document_type: str = Field(min_length=1, max_length=8)
    document_number: str = Field(min_length=1, max_length=20)
    birth_date: date
    username: str = Field(max_length=64)
    email: str = Field(max_length=254)
    password: SecretStr = Field(max_length=1024)

    @field_validator("code", "document_type", "document_number", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @field_validator("username", mode="before")
    @classmethod
    def _username(cls, v: object) -> object:
        v = v.strip().lower() if isinstance(v, str) else v
        if not isinstance(v, str) or not USERNAME_RE.match(v):
            raise ValueError(
                "el usuario debe tener 3-64 caracteres: minúsculas, dígitos y . _ -"
            )
        return v

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v: object) -> object:
        v = v.strip() if isinstance(v, str) else v
        if not isinstance(v, str) or not EMAIL_RE.match(v):
            raise ValueError("correo no válido")
        return v


class ActivateOutput(BaseModel):
    username: str
    message: str = "Cuenta creada. Ya puedes iniciar sesión."


class MeOutput(BaseModel):
    patient_id: str
    username: str
    name: str | None
    email: str | None
    document_type: str
    document_number: str
    birth_date: date
    display_name: str


class ProfileOutput(BaseModel):
    first_name: str
    last_name: str
    email: str
    username: str


class ProfileUpdateInput(BaseModel):
    """Solo estos 4 campos; el usuario sale de la sesion, nunca del cuerpo."""

    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    current_password: SecretStr | None = Field(default=None, max_length=1024)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _names(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v: object) -> object:
        if v is None:
            return v
        v = v.strip() if isinstance(v, str) else v
        if not isinstance(v, str) or not EMAIL_RE.match(v):
            raise ValueError("correo no válido")
        return v

    @model_validator(mode="after")
    def _not_empty(self) -> "ProfileUpdateInput":
        if not (self.first_name or self.last_name or self.email):
            raise ValueError("indica al menos un nombre, un apellido o un correo")
        return self


class PasswordChangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(max_length=1024)


class PasswordPolicyOutput(BaseModel):
    """Mismo cuerpo que `GET /auth/password-policy` de Leo."""

    min_length: int
    max_length: int
    require_lowercase: bool
    require_uppercase: bool
    require_digit: bool
    require_symbol: bool

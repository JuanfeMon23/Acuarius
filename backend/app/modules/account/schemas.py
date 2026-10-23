"""Entradas/salidas de `account`. La politica de usuario, correo y contrasena
replica la de Leo para rechazar ANTES de consumir el codigo de un solo uso."""

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

USERNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9._-]{1,62})[a-z0-9]$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


def password_weaknesses(password: str) -> list[str]:
    problems = []
    if not 12 <= len(password) <= 128:
        problems.append("debe tener entre 12 y 128 caracteres")
    if not any(c.islower() for c in password):
        problems.append("debe incluir una minúscula")
    if not any(c.isupper() for c in password):
        problems.append("debe incluir una mayúscula")
    if not any(c.isdigit() for c in password):
        problems.append("debe incluir un dígito")
    if all(c.isalnum() for c in password):
        problems.append("debe incluir un símbolo")
    return problems


class ActivateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32)
    document_type: str = Field(min_length=1, max_length=8)
    document_number: str = Field(min_length=1, max_length=20)
    birth_date: date
    username: str = Field(max_length=64)
    email: str = Field(max_length=254)
    password: SecretStr = Field(max_length=128)

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

    @field_validator("password")
    @classmethod
    def _password(cls, v: SecretStr) -> SecretStr:
        problems = password_weaknesses(v.get_secret_value())
        if problems:
            raise ValueError("La contraseña " + ", ".join(problems) + ".")
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

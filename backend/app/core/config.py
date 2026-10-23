"""Configuracion leida de `backend/.env`. Unico punto de acceso al entorno."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Obligatorias, sin defaults de entorno; las opcionales traen un valor seguro."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str
    # Origenes del frontend (coma). Con credenciales: cookies + DPoP.
    cors_origins: str
    # Base de la API de Incubus (sin /api/v1), p. ej. http://localhost:8001
    incubus_api_url: str

    # /docs y /openapi.json solo si se activa (desarrollo).
    docs_enabled: bool = False

    # Alta de cuenta: intentos por ventana (IP+documento / documento / IP).
    activation_max_per_ip_doc: int = 5
    activation_max_per_doc: int = 15
    activation_max_per_ip: int = 30
    activation_window_seconds: int = 900

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

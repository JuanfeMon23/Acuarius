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

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Variable heredada -> clave de ajuste que inicializa (ver `runtime_settings`).
LEGACY_POLICY_ENV: dict[str, str] = {
    "ACTIVATION_MAX_PER_IP_DOC": "activation.max_per_ip_doc",
    "ACTIVATION_MAX_PER_DOC": "activation.max_per_doc",
    "ACTIVATION_MAX_PER_IP": "activation.max_per_ip",
    "ACTIVATION_WINDOW_SECONDS": "activation.window_seconds",
    "PROFILE_MAX_PER_USER": "profile.max_per_user",
    "PROFILE_WINDOW_SECONDS": "profile.window_seconds",
}


class LegacyPolicyEnv(BaseSettings):
    """Variables de limites que existian antes de la tabla `settings`.

    Opcionales y NO documentadas como configuracion: si existen en el entorno
    (o en `.env`), `initial_values()` las entrega como valor inicial de las
    claves nuevas; el registro solo las usa al INSERTAR la clave, asi que
    despues la unica fuente es la BD. Un valor no numerico se ignora.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    activation_max_per_ip_doc: str | None = None
    activation_max_per_doc: str | None = None
    activation_max_per_ip: str | None = None
    activation_window_seconds: str | None = None
    profile_max_per_user: str | None = None
    profile_window_seconds: str | None = None

    def initial_values(self) -> dict[str, int]:
        values: dict[str, int] = {}
        for env_name, key in LEGACY_POLICY_ENV.items():
            raw = getattr(self, env_name.lower())
            if raw is None:
                continue
            try:
                values[key] = int(raw.strip())
            except ValueError:
                continue
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()

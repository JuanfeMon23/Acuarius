"""Tablas `settings` y `settings_history`: politicas operativas editables con
historial inmutable.

El esquema es el modulo compartido `leo_sdk.settings_store` (el mismo de las
demas apps). Acuarius NO tiene tabla de usuarios: `updated_by`/`changed_by`
guardan el `id` del usuario de Leo (UUID) SIN llave foranea (`user_pk=None`).
"""

from leo_sdk.settings_store import make_settings_models

from app.core.db.base import Base

_models = make_settings_models(Base, user_pk=None)
Setting = _models.Setting
SettingHistory = _models.SettingHistory
SETTINGS_MODELS = _models

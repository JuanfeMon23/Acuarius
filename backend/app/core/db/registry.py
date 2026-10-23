"""Importa los models de todos los modulos (fuente de `target_metadata`)."""

from app.core.db import settings_model as _settings  # noqa: F401
from app.core.db.base import Base
from app.modules.account import models as _account  # noqa: F401
from app.modules.family import models as _family  # noqa: F401

__all__ = ["Base"]

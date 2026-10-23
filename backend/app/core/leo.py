"""Integracion con Leo (SSO BFF, permisos) via `leo_sdk`.

Unico punto donde se crean `LeoSettings`, el `Catalog` y `LeoAuth`. El catalogo
de acciones vive en `app.core.permissions`. Cookies propias `acuarius_*`: en
desarrollo todos los servicios comparten `localhost` y las cookies no distinguen
puertos, asi que no se usan los nombres por defecto del SDK.
"""

from leo_sdk import Catalog, LeoAuth, LeoSettings

APP_SLUG = "acuarius"


class AcuariusLeoSettings(LeoSettings):
    access_cookie_name: str = "acuarius_access"
    refresh_cookie_name: str = "acuarius_refresh"
    flow_cookie_name: str = "acuarius_oauth"


settings = AcuariusLeoSettings()  # type: ignore[call-arg]  # entorno / backend/.env
catalog = Catalog(APP_SLUG)
auth = LeoAuth(settings, catalog=catalog)

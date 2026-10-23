"""App FastAPI de Acuarius: portal de pacientes (BFF de Leo + resultados de Incubus)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from leo_sdk import leo_router

from app.core import permissions  # noqa: F401  (declara el catalogo de tags)
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.leo import auth
from app.core.security import SecurityHeadersMiddleware
from app.core.service_client import close_service_clients
from app.modules.account.router import router as account_router
from app.modules.family.router import router as family_router
from app.modules.results.router import router as results_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Falla al arrancar si algun `require_action` usa un tag sin declarar. La
    # sincronizacion con Leo NO va aqui (ver `python -m app.core.leo_sync`).
    auth.check_catalog()
    try:
        yield
    finally:
        await close_service_clients()
        await auth.aclose()


settings = get_settings()
docs = "/docs" if settings.docs_enabled else None
app = FastAPI(
    title="Acuarius API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=docs,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(SecurityHeadersMiddleware, docs_enabled=settings.docs_enabled)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    # `DPoP`: prueba de posesion de la sesion de Leo en cada peticion.
    allow_headers=["Content-Type", "DPoP", "X-Request-ID"],
)

register_exception_handlers(app)
auth.install(app)  # errores de Leo con el formato {code, message, details}
app.include_router(leo_router(auth))  # /auth/login /callback /me /activity /logout

app.include_router(account_router, prefix="/api/v1/account")
app.include_router(results_router, prefix="/api/v1/results")
app.include_router(family_router, prefix="/api/v1/family")

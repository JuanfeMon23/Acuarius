"""Cabeceras de seguridad estrictas y `Cache-Control: no-store` en TODA respuesta
(las respuestas llevan datos de salud o de sesion; nada se cachea)."""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_BASE = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
}
_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
# Unica respuesta publica y sin datos personales que puede cachearse (la ruta
# fija su propio `Cache-Control`).
CACHEABLE_PATHS = ("/api/v1/account/password-policy",)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, docs_enabled: bool = False) -> None:
        self.app = app
        self.docs_enabled = docs_enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        skip_csp = self.docs_enabled and scope["path"].startswith(DOCS_PATHS)
        cacheable = scope["path"] in CACHEABLE_PATHS

        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                own_cache = headers.get("Cache-Control") if cacheable else None
                for key, value in _BASE.items():
                    headers[key] = value
                if own_cache and message["status"] == 200:
                    headers["Cache-Control"] = own_cache
                    del headers["Pragma"]
                if not skip_csp:
                    headers["Content-Security-Policy"] = _CSP
            await send(message)

        await self.app(scope, receive, wrapped)

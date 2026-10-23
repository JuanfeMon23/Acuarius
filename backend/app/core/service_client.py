"""Cliente HTTP de servicio compartido (Leo e Incubus) con tokens por audiencia.

`ServiceTokenProvider` (leo_sdk) obtiene y cachea en memoria el token
`client_credentials` por audiencia y reintenta UNA vez ante 401 con un token
nuevo. Aqui se agregan timeouts y la traduccion de fallos de red/Leo a
`UpstreamError`. Los tokens y secretos nunca se loguean.
"""

import logging
from functools import cache

import httpx
from leo_sdk import LeoError, ServiceTokenProvider

from app.core.config import get_settings
from app.core.exceptions import UpstreamError
from app.core.leo import auth
from app.core.leo import settings as leo_settings

logger = logging.getLogger("app.service_client")

LEO_AUDIENCE = "leo"
INCUBUS_AUDIENCE = "incubus"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class ServiceClient:
    def __init__(
        self,
        base_url: str,
        *,
        audience: str,
        tokens: ServiceTokenProvider | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.audience = audience
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=TIMEOUT,
            transport=transport,
            auth=tokens.auth(audience) if tokens else None,
            follow_redirects=False,
        )

    def _unavailable(self, exc: Exception) -> UpstreamError:
        logger.warning(
            "Servicio %s no disponible: %s", self.audience, type(exc).__name__
        )
        return UpstreamError(
            "Un servicio necesario no está disponible. Inténtalo de nuevo en un momento."
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        try:
            return await self._http.request(method, path, json=json, params=params)
        except (httpx.HTTPError, LeoError) as exc:
            raise self._unavailable(exc) from exc

    async def open_stream(self, method: str, path: str) -> httpx.Response:
        """Respuesta abierta (sin leer el cuerpo); quien la usa DEBE `aclose()`."""
        try:
            request = self._http.build_request(method, path)
            return await self._http.send(request, stream=True)
        except (httpx.HTTPError, LeoError) as exc:
            raise self._unavailable(exc) from exc

    async def aclose(self) -> None:
        await self._http.aclose()


@cache
def _tokens() -> ServiceTokenProvider:
    return ServiceTokenProvider(auth.client)


@cache
def incubus_service() -> ServiceClient:
    return ServiceClient(
        get_settings().incubus_api_url, audience=INCUBUS_AUDIENCE, tokens=_tokens()
    )


@cache
def leo_service() -> ServiceClient:
    return ServiceClient(
        leo_settings.leo_api_url, audience=LEO_AUDIENCE, tokens=_tokens()
    )


async def close_service_clients() -> None:
    for factory in (incubus_service, leo_service):
        if factory.cache_info().currsize:
            await factory().aclose()

"""Cliente de la API de entrega de Incubus (credencial de servicio, audiencia
`incubus`). Acuarius no guarda copias: todo se consulta al momento.

La autorizacion por objeto NO vive aqui: este cliente consulta lo que se le pide;
quien lo llama decide a que documento tiene derecho la sesion.
"""

from typing import Annotated, Any
from urllib.parse import quote

import httpx
from fastapi import Depends

from app.core.exceptions import RateLimitedError, UpstreamError
from app.core.service_client import ServiceClient, incubus_service

DELIVERY = "/api/v1/delivery"
SCAN_PAGE_SIZE = 50  # maximo que admite Incubus
SCAN_MAX_PAGES = 200


def _q(value: str) -> str:
    return quote(value, safe="")


class IncubusDelivery:
    def __init__(self, client: ServiceClient) -> None:
        self._c = client

    @staticmethod
    def _unexpected(response: httpx.Response) -> UpstreamError:
        return UpstreamError("No se pudo consultar el laboratorio. Inténtalo de nuevo.")

    async def verify_activation(self, payload: dict[str, Any]) -> dict | None:
        """Datos del paciente si el codigo coincide (y queda consumido); `None`
        ante cualquier rechazo de verificacion (misma respuesta para todos)."""
        r = await self._c.request("POST", f"{DELIVERY}/activation/verify", json=payload)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            raise RateLimitedError("Demasiados intentos. Inténtalo de nuevo más tarde.")
        if r.status_code in (400, 404, 422):
            return None
        raise self._unexpected(r)

    async def list_orders(
        self, document_type: str, document_number: str, page: int, page_size: int
    ) -> dict:
        r = await self._c.request(
            "GET",
            f"{DELIVERY}/patients/{_q(document_type)}/{_q(document_number)}/orders",
            params={"page": page, "page_size": page_size},
        )
        if r.status_code == 200:
            return r.json()
        raise self._unexpected(r)

    async def owns_order(
        self, document_type: str, document_number: str, order_number: str
    ) -> bool:
        """El `order_number` figura en la lista de Incubus de ESTE documento."""
        for page in range(1, SCAN_MAX_PAGES + 1):
            data = await self.list_orders(
                document_type, document_number, page, SCAN_PAGE_SIZE
            )
            items = data.get("items", [])
            if any(i.get("order_number") == order_number for i in items):
                return True
            if page * SCAN_PAGE_SIZE >= data.get("total", 0) or not items:
                return False
        return False

    async def get_order(self, order_number: str) -> dict | None:
        r = await self._c.request("GET", f"{DELIVERY}/orders/{_q(order_number)}")
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        raise self._unexpected(r)

    async def open_report(self, order_number: str) -> httpx.Response | None:
        """PDF como respuesta abierta (quien la recibe debe cerrarla)."""
        r = await self._c.open_stream(
            "GET", f"{DELIVERY}/orders/{_q(order_number)}/report.pdf"
        )
        if r.status_code == 200 and "pdf" in r.headers.get("content-type", ""):
            return r
        await r.aclose()
        if r.status_code == 404:
            return None
        raise self._unexpected(r)


def get_incubus() -> IncubusDelivery:
    return IncubusDelivery(incubus_service())


Incubus = Annotated[IncubusDelivery, Depends(get_incubus)]

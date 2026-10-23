"""Cabeceras, formato de errores, catalogo de tags, cookies y cliente de servicio."""

import httpx
import pytest
from leo_sdk import ServiceTokenProvider

from app.core import permissions as p
from app.core.exceptions import UpstreamError
from app.core.leo import auth, settings
from app.core.service_client import ServiceClient
from app.main import app


def test_catalog_has_the_six_tags():
    assert set(auth.catalog.tags) == {
        "acuarius.results.view",
        "acuarius.results.download",
        "acuarius.family.view",
        "acuarius.family.invite",
        "acuarius.family.respond",
        "acuarius.family.manage",
    }
    assert p.RESULTS_VIEW in auth.catalog.tags
    auth.check_catalog()


def test_own_cookie_names():
    assert settings.access_cookie_name == "acuarius_access"
    assert settings.refresh_cookie_name == "acuarius_refresh"
    assert settings.flow_cookie_name == "acuarius_oauth"


async def test_security_headers_and_no_store_everywhere(client):
    for path in ("/api/v1/results", "/nope", "/auth/me"):
        h = (await client.get(path)).headers
        assert h["cache-control"] == "no-store"
        assert h["x-content-type-options"] == "nosniff"
        assert h["x-frame-options"] == "DENY"
        assert h["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in h["content-security-policy"]
        assert "max-age" in h["strict-transport-security"]


async def test_error_format_and_no_input_echo(client):
    r = await client.post(
        "/api/v1/account/activate", json={"password": "SuperSecreta1!"}
    )
    assert r.status_code == 422
    assert set(r.json()) == {"code", "message", "details"}
    assert "SuperSecreta1!" not in r.text


async def test_unauthenticated_error_uses_standard_format(client, leo):
    leo.user = None
    r = await client.get("/api/v1/results")
    assert r.status_code == 401 and set(r.json()) == {"code", "message", "details"}


async def test_cors_is_closed(client):
    def preflight(origin: str):
        return client.options(
            "/api/v1/results",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )

    ok = await preflight("http://localhost:3300")
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3300"
    bad = await preflight("http://evil.example")
    assert "access-control-allow-origin" not in bad.headers


def test_exact_api_surface():
    paths = {x for x in app.openapi()["paths"] if x.startswith("/api")}
    assert paths == {
        "/api/v1/account/activate",
        "/api/v1/account/me",
        "/api/v1/account/profile",
        "/api/v1/account/password",
        "/api/v1/results",
        "/api/v1/results/{order_number}",
        "/api/v1/results/{order_number}/report.pdf",
        "/api/v1/family/me",
        "/api/v1/family/invitations",
        "/api/v1/family/invitations/{invitation_id}/accept",
        "/api/v1/family/invitations/{invitation_id}/reject",
        "/api/v1/family/invitations/{invitation_id}/cancel",
        "/api/v1/family/shares/{member_patient_id}",
        "/api/v1/family/leave",
        "/api/v1/family/members/{patient_id}",
    }


class _Creds:
    def __init__(self):
        self.n = 0

    async def client_credentials(self, audience):
        self.n += 1
        return type("T", (), {"access_token": f"tok-{self.n}", "expires_in": 300})()


async def test_service_client_retries_once_on_401_with_new_token():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        return httpx.Response(401 if len(seen) == 1 else 200, json={"ok": True})

    client = ServiceClient(
        "http://incubus.test",
        audience="incubus",
        tokens=ServiceTokenProvider(_Creds()),
        transport=httpx.MockTransport(handler),
    )
    r = await client.request("GET", "/x")
    assert r.status_code == 200 and seen == ["Bearer tok-1", "Bearer tok-2"]
    await client.request("GET", "/x")  # el token vigente se cachea
    assert seen[-1] == "Bearer tok-2"
    await client.aclose()


async def test_service_client_second_401_is_returned_not_looped():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401)

    c = ServiceClient(
        "http://x.test",
        audience="leo",
        tokens=ServiceTokenProvider(_Creds()),
        transport=httpx.MockTransport(handler),
    )
    assert (await c.request("GET", "/")).status_code == 401
    assert len(calls) == 2
    await c.aclose()


async def test_service_client_network_failure_is_upstream_error():
    def handler(request):
        raise httpx.ConnectError("boom")

    c = ServiceClient(
        "http://x.test", audience="leo", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(UpstreamError):
        await c.request("GET", "/")
    await c.aclose()

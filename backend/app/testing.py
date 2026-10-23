"""Dobles de prueba: Leo (sesion, auditoria, aprovisionamiento) e Incubus
(entrega) sobre `httpx.MockTransport`, y el cliente HTTP contra la app."""

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from leo_sdk import LeoError, LeoUser, UserProfile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_session
from app.core.incubus import IncubusDelivery, get_incubus
from app.core.leo import auth
from app.core.leo import catalog as leo_catalog
from app.core.service_client import ServiceClient
from app.main import app
from app.modules.account import profile as profile_module
from app.modules.account import router as account_router
from app.modules.account.leo_users import LeoUsers, get_leo_users
from app.modules.account.router import get_recovery_sessions


@dataclass
class FakeLeo:
    """Sesion actual (`user=None` -> 401) y eventos de auditoria recibidos."""

    user: LeoUser | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    # Autogestion delegada: llamadas recibidas y error a lanzar (`LeoError`).
    profile_calls: list[dict[str, Any]] = field(default_factory=list)
    password_calls: list[dict[str, Any]] = field(default_factory=list)
    fail_with: Exception | None = None

    def login(self, tags: Any = None, user_id: UUID | None = None) -> LeoUser:
        self.user = make_leo_user(leo_catalog.tags if tags is None else tags, user_id)
        return self.user


def make_leo_user(tags: Any, user_id: UUID | None = None) -> LeoUser:
    return LeoUser(
        id=user_id or uuid4(),
        username="paciente",
        name="Paciente Uno",
        first_name="Paciente",
        last_name="Uno",
        email="paciente@example.com",
        permissions=frozenset(tags),
        session_id=uuid4(),
        access_token="token-falso",
        jkt="jkt-falso",
    )


@pytest.fixture
def leo(monkeypatch: pytest.MonkeyPatch) -> FakeLeo:
    fake = FakeLeo()

    async def ingest_audit(payload: dict[str, Any]) -> None:
        fake.events.append(payload)

    async def current_user() -> LeoUser:
        if fake.user is None:
            raise LeoError("not_authenticated", "Inicia sesión para continuar.", 401)
        return fake.user

    async def update_user_profile(token: str, **fields: Any) -> UserProfile:
        fake.profile_calls.append({"token": token, **fields})
        if fake.fail_with:
            raise fake.fail_with
        u = fake.user
        assert u is not None
        return UserProfile(
            first_name=fields.get("first_name") or u.first_name,
            last_name=fields.get("last_name") or u.last_name,
            email=fields.get("email") or u.email,
            username=u.username,
        )

    async def change_user_password(token: str, current: str, new: str) -> None:
        fake.password_calls.append({"token": token, "current": current, "new": new})
        if fake.fail_with:
            raise fake.fail_with

    monkeypatch.setattr(auth.client, "ingest_audit", ingest_audit)
    monkeypatch.setattr(auth.client, "update_user_profile", update_user_profile)
    monkeypatch.setattr(auth.client, "change_user_password", change_user_password)
    app.dependency_overrides[auth.current_user] = current_user
    app.dependency_overrides[auth.current_person] = current_user
    auth.audit._queue.clear()
    yield fake
    app.dependency_overrides.pop(auth.current_user, None)
    app.dependency_overrides.pop(auth.current_person, None)


@dataclass
class FakeIncubus:
    """Entrega de Incubus: ordenes por documento, codigos validos y llamadas."""

    orders: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    codes: dict[tuple, dict] = field(default_factory=dict)
    consumed: set[tuple] = field(default_factory=set)
    calls: list[str] = field(default_factory=list)
    rate_limited: bool = False
    down: bool = False

    def add_activation(self, code, doc_type, doc_number, birth, **person) -> None:
        self.codes[(code, doc_type, doc_number, birth)] = {
            "first_name": "Ana",
            "second_name": "Maria",
            "first_last_name": "Perez",
            "second_last_name": "Gomez",
            "document_type": doc_type,
            "document_number": doc_number,
            "birth_date": birth,
            **person,
        }

    def owner_of(self, order_number: str) -> tuple[str, str] | None:
        return next((k for k, v in self.orders.items() if order_number in v), None)

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(f"{request.method} {path}")
        if self.down:
            return httpx.Response(503)
        base = "/api/v1/delivery"
        if request.method == "POST" and path == f"{base}/activation/verify":
            if self.rate_limited:
                return httpx.Response(429, json={"code": "rate_limited"})
            b = json.loads(request.content)
            key = (b["code"], b["document_type"], b["document_number"], b["birth_date"])
            if key in self.codes and key not in self.consumed:
                self.consumed.add(key)
                return httpx.Response(200, json=self.codes[key])
            return httpx.Response(404, json={"code": "not_found"})
        parts = path.removeprefix(base).strip("/").split("/")
        if parts[0] == "patients" and parts[-1] == "orders":
            numbers = self.orders.get((parts[1], parts[2]), [])
            page = int(request.url.params["page"])
            size = int(request.url.params["page_size"])
            chunk = numbers[(page - 1) * size : page * size]
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"order_number": n, "status": "finalizada"} for n in chunk
                    ],
                    "page": page,
                    "page_size": size,
                    "total": len(numbers),
                },
            )
        if parts[0] == "orders":
            owner = self.owner_of(parts[1])
            if owner is None:
                return httpx.Response(404)
            if parts[-1] == "report.pdf":
                return httpx.Response(
                    200,
                    content=b"%PDF-1.4 DOC-" + owner[1].encode(),
                    headers={"content-type": "application/pdf"},
                )
            return httpx.Response(
                200, json={"order_number": parts[1], "document_number": owner[1]}
            )
        return httpx.Response(404)


@dataclass
class FakeLeoUsers:
    """`POST /users/service/patients` de Leo."""

    mode: str = "ok"  # ok | conflict | weak | down
    bodies: list[dict] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/users/service/patients"
        self.bodies.append(json.loads(request.content))
        if self.mode == "conflict":
            return httpx.Response(409, json={"code": "conflict", "message": "x"})
        if self.mode == "weak":
            return httpx.Response(
                422,
                json={
                    "code": "validation_error",
                    "message": "Contraseña débil.",
                    "details": [{"field": "password", "message": "es muy común"}],
                },
            )
        if self.mode == "down":
            return httpx.Response(503)
        return httpx.Response(
            201, json={"id": str(uuid4()), "username": self.bodies[-1]["username"]}
        )


@pytest.fixture
def incubus() -> FakeIncubus:
    return FakeIncubus()


@pytest.fixture
def leo_users() -> FakeLeoUsers:
    return FakeLeoUsers()


@pytest_asyncio.fixture
async def client(
    session: AsyncSession,
    leo: FakeLeo,
    incubus: FakeIncubus,
    leo_users: FakeLeoUsers,
) -> AsyncGenerator[AsyncClient]:
    inc = IncubusDelivery(
        ServiceClient(
            "http://incubus.test",
            audience="incubus",
            transport=httpx.MockTransport(incubus.handler),
        )
    )
    users = LeoUsers(
        ServiceClient(
            "http://leo.test/api/v1",
            audience="leo",
            transport=httpx.MockTransport(leo_users.handler),
        )
    )

    async def _session() -> AsyncGenerator[AsyncSession]:
        yield session

    # Sesion propia de recuperacion, sobre la misma conexion de prueba (savepoint).
    recovery_maker = async_sessionmaker(
        bind=session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_recovery_sessions] = lambda: recovery_maker
    app.dependency_overrides[get_incubus] = lambda: inc
    app.dependency_overrides[get_leo_users] = lambda: users
    account_router.limiter.reset()
    profile_module.limiter.reset()
    transport = ASGITransport(app=app, client=("203.0.113.9", 5000))
    async with AsyncClient(transport=transport, base_url="http://acuarius.test") as c:
        yield c
    for dep in (get_session, get_recovery_sessions, get_incubus, get_leo_users):
        app.dependency_overrides.pop(dep, None)

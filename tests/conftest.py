"""Shared test fixtures.

Environment variables are set *before* application modules are imported, so settings,
engines and caches all point at the isolated test database and temporary storage.
"""

import os
import tempfile
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

TEST_ISSUER = "https://test-instance.clerk.accounts.dev"
TEST_ORIGIN = "http://localhost:3000"

os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL=os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://supportnova:supportnova@localhost:5432/supportnova_test",
    ),
    EMBEDDING_PROVIDER="hash",
    STORAGE_BACKEND="local",
    STORAGE_LOCAL_DIR=tempfile.mkdtemp(prefix="supportnova-test-"),
    CLERK_ISSUER=TEST_ISSUER,
    CLERK_AUTHORIZED_PARTIES=TEST_ORIGIN,
    BOOTSTRAP_ADMIN_EMAILS="founder@volthaven.test",
    CLERK_WEBHOOK_SIGNING_SECRET="",
    # A developer's .env may hold a real support mailbox; tests must never reach it.
    MAIL_IMAP_HOST="",
    MAIL_SMTP_HOST="",
    MAIL_USERNAME="",
    MAIL_PASSWORD="",
)

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from database.base import Base  # noqa: E402
from database.models import Role, User  # noqa: E402
from database.seed import load_taxonomy, seed_rules, seed_taxonomy  # noqa: E402
from database.session import get_sync_engine, sync_session  # noqa: E402
from security.clerk import ClerkTokenVerifier  # noqa: E402
from security.dependencies import get_token_verifier  # noqa: E402
from storefront.catalogue import sync_catalogue  # noqa: E402


@pytest.fixture(scope="session")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def verifier(rsa_key: rsa.RSAPrivateKey) -> ClerkTokenVerifier:
    public_key = rsa_key.public_key()
    return ClerkTokenVerifier(TEST_ISSUER, [TEST_ORIGIN], lambda _token: public_key)


@pytest.fixture(scope="session")
def make_token(rsa_key: rsa.RSAPrivateKey) -> Callable[..., str]:
    """Sign a Clerk-shaped session token with the test key."""

    def _make(
        sub: str = "user_test",
        *,
        email: str | None = None,
        name: str | None = None,
        azp: str | None = TEST_ORIGIN,
        issuer: str = TEST_ISSUER,
        expires_in: int = 300,
        key: Any = None,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": sub,
            "iss": issuer,
            "iat": now,
            "nbf": now,
            "exp": now + expires_in,
            "sid": "sess_test",
        }
        if azp is not None:
            claims["azp"] = azp
        if email:
            claims["email"] = email
        if name:
            claims["name"] = name
        return jwt.encode(claims, key or rsa_key, algorithm="RS256")

    return _make


# --------------------------------------------------------------------- database


@pytest.fixture(scope="session")
def database() -> Iterator[None]:
    engine = get_sync_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def clean_db(database: None) -> Iterator[None]:
    """Seeded taxonomy for each test; everything truncated afterwards."""
    with sync_session() as db:
        seed_taxonomy(db, load_taxonomy())
        seed_rules(db)
        sync_catalogue(db)
    yield
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with get_sync_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def create_user(clean_db: None) -> Callable[..., User]:
    def _create(role: Role, clerk_user_id: str | None = None, email: str | None = None) -> User:
        with sync_session() as db:
            user = User(
                clerk_user_id=clerk_user_id or f"user_{uuid.uuid4().hex[:12]}",
                email=email,
                role=role,
            )
            db.add(user)
        return user

    return _create


# -------------------------------------------------------------------------- app


@pytest.fixture
async def client(
    clean_db: None, verifier: ClerkTokenVerifier, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    from complaint_processing import service as complaint_service
    from knowledge_base import service
    from src.main import create_app

    enqueued: list[uuid.UUID] = []
    analyses: list[uuid.UUID] = []
    monkeypatch.setattr(service, "enqueue_ingest", enqueued.append)
    monkeypatch.setattr(
        complaint_service, "enqueue_analysis", lambda cid, _by=None: analyses.append(cid)
    )
    app = create_app()
    app.dependency_overrides[get_token_verifier] = lambda: verifier
    app.state.enqueued = enqueued
    app.state.analyses = analyses
    from bulk_import import service as import_service

    imports: list[str] = []
    monkeypatch.setattr(import_service, "enqueue_run", lambda bid: imports.append(str(bid)))
    app.state.imports = imports
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        http.app = app  # type: ignore[attr-defined]
        yield http


@pytest.fixture
def auth_headers(
    create_user: Callable[..., User], make_token: Callable[..., str]
) -> Callable[[Role], dict[str, str]]:
    """Create a user with the given role and return Authorization headers for them."""

    def _headers(role: Role) -> dict[str, str]:
        user = create_user(role)
        return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}

    return _headers

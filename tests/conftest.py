import os

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Debe establecerse ANTES de importar cualquier módulo de app
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")

from app.auth import COOKIE_NAME, create_session_cookie, hash_password  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.common import Base  # noqa: E402
from app.models.user import User  # noqa: E402

TEST_DATABASE_URL = "sqlite://"  # in-memory

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def auth_user(db):
    """Usuario de prueba ya persistido en la BD."""
    user = User(
        email="test@devhub.local",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_client(db, cookies: dict | None = None) -> TestClient:
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, cookies=cookies or {})
    return client


@pytest.fixture
def client(db, auth_user):
    """Cliente autenticado — úsalo en todos los tests funcionales."""
    cookies = {COOKIE_NAME: create_session_cookie(auth_user.id)}
    with _make_client(db, cookies) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client(db):
    """Cliente sin sesión — úsalo en tests de redirección / auth."""
    with _make_client(db) as c:
        yield c
    app.dependency_overrides.clear()

"""Tests del middleware CSRF doble-submit.

Estos tests construyen clientes sin el wrapper que inyecta CSRF automáticamente,
para poder probar casos negativos (sin token, con tokens distintos, etc.).
"""

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.middleware.csrf import CSRF_COOKIE, CSRF_HEADER, generate_csrf_token


@pytest.fixture
def bare_client(db) -> TestClient:
    """Cliente sin CSRF inyectado — para probar el middleware de frente."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_post_without_csrf_cookie_blocked(bare_client):
    res = bare_client.post("/login", data={"email": "x@y.z", "password": "z"})
    assert res.status_code == 403


def test_post_with_matching_cookie_and_header_passes(bare_client):
    token = generate_csrf_token()
    res = bare_client.post(
        "/login",
        data={"email": "x@y.z", "password": "z"},
        cookies={CSRF_COOKIE: token},
        headers={CSRF_HEADER: token},
    )
    assert res.status_code != 403


def test_post_with_mismatched_token_blocked(bare_client):
    res = bare_client.post(
        "/login",
        data={"email": "x@y.z", "password": "z"},
        cookies={CSRF_COOKIE: generate_csrf_token()},
        headers={CSRF_HEADER: generate_csrf_token()},
    )
    assert res.status_code == 403


def test_get_does_not_require_csrf(bare_client):
    res = bare_client.get("/login")
    assert res.status_code == 200


def test_extension_api_exempt_from_csrf(bare_client):
    res = bare_client.get("/api/extension/ping")
    assert res.status_code == 401
    assert "CSRF" not in res.json()["detail"]


def test_form_field_csrf_accepted(bare_client):
    token = generate_csrf_token()
    res = bare_client.post(
        "/login",
        data={"email": "x@y.z", "password": "z", "csrf_token": token},
        cookies={CSRF_COOKIE: token},
    )
    assert res.status_code != 403

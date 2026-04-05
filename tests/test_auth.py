"""Tests del sistema de autenticación."""

from app.auth import COOKIE_NAME, create_session_cookie, verify_password
from app.models.user import User


# ─── Páginas públicas ────────────────────────────────────────────────────────

def test_login_page(unauth_client):
    res = unauth_client.get("/login")
    assert res.status_code == 200
    assert b"Iniciar" in res.content


def test_register_page(unauth_client):
    res = unauth_client.get("/register")
    assert res.status_code == 200
    assert b"Crear cuenta" in res.content


def test_login_page_redirects_if_authenticated(client):
    res = client.get("/login", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/"


def test_register_page_redirects_if_authenticated(client):
    res = client.get("/register", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/"


# ─── Rutas protegidas redirigen sin sesión ────────────────────────────────────

def test_protected_route_redirects_to_login(unauth_client):
    res = unauth_client.get("/", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["location"]


def test_protected_api_redirects_to_login(unauth_client):
    res = unauth_client.get("/api/projects", follow_redirects=False)
    assert res.status_code == 302


# ─── Login ───────────────────────────────────────────────────────────────────

def test_login_success(unauth_client, auth_user):
    res = unauth_client.post("/login", data={
        "email": "test@devhub.local",
        "password": "password123",
    }, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/"
    assert COOKIE_NAME in res.cookies


def test_login_wrong_password(unauth_client, auth_user):
    res = unauth_client.post("/login", data={
        "email": "test@devhub.local",
        "password": "wrongpassword",
    })
    assert res.status_code == 401
    assert b"incorrectos" in res.content
    assert COOKIE_NAME not in res.cookies


def test_login_nonexistent_email(unauth_client):
    res = unauth_client.post("/login", data={
        "email": "noexiste@devhub.local",
        "password": "password123",
    })
    assert res.status_code == 401
    assert b"incorrectos" in res.content


def test_login_sets_httponly_cookie(unauth_client, auth_user):
    res = unauth_client.post("/login", data={
        "email": "test@devhub.local",
        "password": "password123",
    }, follow_redirects=False)
    # httponly se refleja en el Set-Cookie header
    set_cookie = res.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()


# ─── Register ────────────────────────────────────────────────────────────────

def test_register_creates_user(unauth_client, db):
    res = unauth_client.post("/register", data={
        "email": "nuevo@devhub.local",
        "password": "securepass",
        "password_confirm": "securepass",
    }, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/"
    assert COOKIE_NAME in res.cookies

    user = db.query(User).filter(User.email == "nuevo@devhub.local").first()
    assert user is not None
    assert verify_password("securepass", user.hashed_password)


def test_register_duplicate_email(unauth_client, auth_user):
    res = unauth_client.post("/register", data={
        "email": "test@devhub.local",
        "password": "securepass",
        "password_confirm": "securepass",
    })
    assert res.status_code == 409
    assert b"Ya existe" in res.content


def test_register_password_too_short(unauth_client):
    res = unauth_client.post("/register", data={
        "email": "nuevo@devhub.local",
        "password": "short",
        "password_confirm": "short",
    })
    assert res.status_code == 422
    assert b"8 caracteres" in res.content


def test_register_passwords_dont_match(unauth_client):
    res = unauth_client.post("/register", data={
        "email": "nuevo@devhub.local",
        "password": "securepass1",
        "password_confirm": "securepass2",
    })
    assert res.status_code == 422
    assert b"coinciden" in res.content


def test_register_email_normalized_to_lowercase(unauth_client, db):
    unauth_client.post("/register", data={
        "email": "NUEVO@DevHub.LOCAL",
        "password": "securepass",
        "password_confirm": "securepass",
    }, follow_redirects=False)
    user = db.query(User).filter(User.email == "nuevo@devhub.local").first()
    assert user is not None


# ─── Logout ──────────────────────────────────────────────────────────────────

def test_logout_clears_cookie(client):
    res = client.post("/logout", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login"
    # La cookie debe estar vacía o eliminada
    set_cookie = res.headers.get("set-cookie", "")
    assert COOKIE_NAME in set_cookie
    assert 'max-age=0' in set_cookie.lower() or 'expires' in set_cookie.lower()


def test_logout_response_has_expired_cookie(client):
    """El Set-Cookie de logout marca la cookie como expirada."""
    res = client.post("/logout", follow_redirects=False)
    set_cookie = res.headers.get("set-cookie", "")
    assert COOKIE_NAME in set_cookie
    # max-age=0 o expires en el pasado
    assert "max-age=0" in set_cookie.lower() or "expires" in set_cookie.lower()


# ─── Aislamiento de datos ─────────────────────────────────────────────────────

def test_user_cannot_see_other_users_projects(db, unauth_client):
    from app.auth import hash_password
    from app.models.project import Project

    # Crear dos usuarios
    user_a = User(email="a@test.local", hashed_password=hash_password("pass1234"), is_active=True)
    user_b = User(email="b@test.local", hashed_password=hash_password("pass1234"), is_active=True)
    db.add_all([user_a, user_b])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)

    # Proyecto del usuario A
    project = Project(name="Proyecto Privado", slug="proyecto-privado", user_id=user_a.id)
    db.add(project)
    db.commit()

    # Cliente autenticado como usuario B intenta acceder
    from app.database import get_db
    from app.main import app

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    cookie_b = {COOKIE_NAME: create_session_cookie(user_b.id)}
    with __import__("fastapi").testclient.TestClient(app, cookies=cookie_b) as client_b:
        res = client_b.get("/projects/proyecto-privado")
        assert res.status_code == 404
    app.dependency_overrides.clear()

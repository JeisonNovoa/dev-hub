"""Tests del 2FA (TOTP): activación, login web en dos pasos y candado en la extensión."""

from datetime import datetime, timezone

import pyotp

from app.auth import create_totp_pending_token


def _enable_totp(db, user) -> pyotp.TOTP:
    """Activa 2FA directamente en BD y devuelve el generador de códigos."""
    secret = pyotp.random_base32()
    user.totp_secret = secret
    user.totp_confirmed_at = datetime.now(timezone.utc)
    db.commit()
    return pyotp.TOTP(secret)


# ─── Activación desde /seguridad ─────────────────────────────────────────────

def test_security_page_renders(client):
    res = client.get("/seguridad")
    assert res.status_code == 200
    assert "Activar 2FA" in res.text


def test_totp_setup_and_confirm_flow(client, db, auth_user):
    # Iniciar: genera secreto sin confirmar y muestra el QR
    res = client.post("/ui/seguridad/2fa/iniciar")
    assert res.status_code == 200
    assert "<svg" in res.text  # QR
    db.refresh(auth_user)
    assert auth_user.totp_secret and not auth_user.totp_confirmed_at

    # Confirmar con código inválido: sigue pendiente
    res = client.post("/ui/seguridad/2fa/confirmar", data={"code": "000000"})
    assert "Código incorrecto" in res.text
    db.refresh(auth_user)
    assert not auth_user.totp_enabled

    # Confirmar con código válido: queda activo
    code = pyotp.TOTP(auth_user.totp_secret).now()
    res = client.post("/ui/seguridad/2fa/confirmar", data={"code": code})
    assert "2FA activado" in res.text
    db.refresh(auth_user)
    assert auth_user.totp_enabled


def test_totp_cancel_pending_setup(client, db, auth_user):
    client.post("/ui/seguridad/2fa/iniciar")
    client.post("/ui/seguridad/2fa/cancelar")
    db.refresh(auth_user)
    assert auth_user.totp_secret is None


def test_totp_disable_requires_valid_code(client, db, auth_user):
    totp = _enable_totp(db, auth_user)

    res = client.post("/ui/seguridad/2fa/desactivar", data={"code": "000000"})
    assert "no se desactivó" in res.text
    db.refresh(auth_user)
    assert auth_user.totp_enabled

    client.post("/ui/seguridad/2fa/desactivar", data={"code": totp.now()})
    db.refresh(auth_user)
    assert not auth_user.totp_enabled


# ─── Login web en dos pasos ──────────────────────────────────────────────────

def test_login_without_2fa_unchanged(unauth_client, auth_user):
    res = unauth_client.post(
        "/login",
        data={"email": "test@devhub.local", "password": "password123"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert "session" in res.cookies


def test_login_with_2fa_requires_second_step(unauth_client, db, auth_user):
    totp = _enable_totp(db, auth_user)

    # Paso 1: contraseña correcta NO entrega sesión, muestra el paso del código
    res = unauth_client.post(
        "/login",
        data={"email": "test@devhub.local", "password": "password123"},
        follow_redirects=False,
    )
    assert res.status_code == 200
    assert "session" not in res.cookies
    assert "pending_token" in res.text

    # Extraer el token del formulario
    import re
    token = re.search(r'name="pending_token" value="([^"]+)"', res.text).group(1)

    # Paso 2 con código malo: 401 y sin sesión
    res = unauth_client.post("/login/2fa", data={"pending_token": token, "code": "000000"})
    assert res.status_code == 401
    assert "session" not in res.cookies

    # Paso 2 con código válido: sesión creada
    res = unauth_client.post(
        "/login/2fa",
        data={"pending_token": token, "code": totp.now()},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert "session" in res.cookies


def test_login_2fa_rejects_tampered_token(unauth_client, db, auth_user):
    _enable_totp(db, auth_user)
    res = unauth_client.post(
        "/login/2fa",
        data={"pending_token": "token-falso", "code": "123456"},
        follow_redirects=False,
    )
    # Token inválido: de vuelta al login, sin sesión
    assert res.status_code == 303
    assert res.headers["location"] == "/login"
    assert "session" not in res.cookies


def test_login_2fa_token_is_not_a_session(unauth_client, db, auth_user):
    """El token pendiente NO debe servir como cookie de sesión."""
    _enable_totp(db, auth_user)
    token = create_totp_pending_token(auth_user.id)
    res = unauth_client.get("/", cookies={"session": token}, follow_redirects=False)
    assert res.status_code == 302  # redirige a /login: no autentica


# ─── Login de la extensión con 2FA ───────────────────────────────────────────

def test_extension_login_requires_totp_when_enabled(client, db, auth_user):
    totp = _enable_totp(db, auth_user)

    # Sin código → 401 con mensaje que la extensión usa para revelar el campo
    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local", "password": "password123",
    })
    assert res.status_code == 401
    assert "2FA" in res.json()["detail"]

    # Código malo → 401
    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local", "password": "password123", "totp_code": "000000",
    })
    assert res.status_code == 401

    # Código válido → token
    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local", "password": "password123", "totp_code": totp.now(),
    })
    assert res.status_code == 200
    assert res.json()["token"].startswith("dvh_")


def test_extension_login_without_2fa_unchanged(client):
    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local", "password": "password123",
    })
    assert res.status_code == 200

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


# ─── Anti-replay TOTP (S8) ───────────────────────────────────────────────────

def test_totp_code_cannot_be_reused_for_login(unauth_client, db, auth_user):
    """Tras un login exitoso, el mismo código no puede usarse otra vez."""
    from app.routers.api.extension import _LOGIN_ATTEMPTS  # noqa: F401 (import para clear)
    from app.routers.api import extension as _ext
    _ext._LOGIN_ATTEMPTS.clear()

    totp = _enable_totp(db, auth_user)
    code = totp.now()

    # Primer login con este código → OK.
    res = unauth_client.post("/api/extension/login", json={
        "email": "test@devhub.local",
        "password": "password123",
        "totp_code": code,
    })
    assert res.status_code == 200

    # Limpiar rate-limit entre llamadas (10/min).
    _ext._LOGIN_ATTEMPTS.clear()

    # Reusar el MISMO código en otra petición → 401.
    res = unauth_client.post("/api/extension/login", json={
        "email": "test@devhub.local",
        "password": "password123",
        "totp_code": code,
    })
    assert res.status_code == 401


def test_totp_window_stored_after_successful_login(db, auth_user):
    """Verifica que last_totp_window se setea al verificar un código."""
    from app.auth import verify_totp_for_user
    totp = _enable_totp(db, auth_user)
    code = totp.now()
    assert auth_user.last_totp_window is None
    assert verify_totp_for_user(auth_user, code) is True
    db.commit()
    db.refresh(auth_user)
    assert auth_user.last_totp_window is not None
    # El código ya no sirve.
    assert verify_totp_for_user(auth_user, code) is False


def test_totp_next_window_accepted(db, auth_user):
    """_totp_window_for devuelve la ventana correcta para un código dado."""
    import time as _time
    from app.auth import _totp_window_for
    totp = _enable_totp(db, auth_user)
    now = _time.time()
    # Código generado para la ventana actual.
    current_window = int(now // 30)
    code = totp.at(current_window * 30)
    window = _totp_window_for(code, auth_user.totp_secret, for_time=now)
    # Debe caer dentro de la ventana actual (o ±1 por la tolerancia).
    assert window is not None
    assert abs(window - current_window) <= 1


def test_totp_disable_clears_last_window(client, db, auth_user):
    """Al desactivar 2FA, last_totp_window se reinicia."""
    totp = _enable_totp(db, auth_user)
    # Simular un uso previo backdateando last_totp_window a la ventana anterior.
    import time as _time
    auth_user.last_totp_window = int(_time.time() // 30) - 2
    db.commit()
    db.refresh(auth_user)
    # Desactivar con código fresco de la ventana actual
    res = client.post("/ui/seguridad/2fa/desactivar", data={"code": totp.now()})
    assert "desactivado" in res.text or res.status_code == 200
    db.refresh(auth_user)
    assert auth_user.last_totp_window is None

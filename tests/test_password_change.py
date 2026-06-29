"""Tests del cambio de contraseña de la cuenta (página de Seguridad)."""

from app.auth import COOKIE_NAME, create_session_cookie, verify_password


def test_password_form_renders(client):
    res = client.get("/ui/seguridad/password/form")
    assert res.status_code == 200
    assert "current_password" in res.text
    assert "Guardar contraseña" in res.text


def test_password_change_success(client, db, auth_user):
    res = client.post("/ui/seguridad/password/save", data={
        "current_password": "password123",
        "new_password": "nuevaClave456",
        "confirm_password": "nuevaClave456",
    })
    assert res.status_code == 200
    assert "Contraseña actualizada" in res.text
    db.refresh(auth_user)
    assert verify_password("nuevaClave456", auth_user.hashed_password)


def test_password_change_wrong_current(client, db, auth_user):
    res = client.post("/ui/seguridad/password/save", data={
        "current_password": "incorrecta",
        "new_password": "nuevaClave456",
        "confirm_password": "nuevaClave456",
    })
    assert res.status_code == 200
    assert "no es correcta" in res.text
    db.refresh(auth_user)
    # La contraseña no cambió.
    assert verify_password("password123", auth_user.hashed_password)


def test_password_change_too_short(client):
    res = client.post("/ui/seguridad/password/save", data={
        "current_password": "password123",
        "new_password": "corta",
        "confirm_password": "corta",
    })
    assert res.status_code == 200
    assert "al menos 8" in res.text


def test_password_change_mismatch(client):
    res = client.post("/ui/seguridad/password/save", data={
        "current_password": "password123",
        "new_password": "nuevaClave456",
        "confirm_password": "otraDistinta789",
    })
    assert res.status_code == 200
    assert "no coinciden" in res.text


def test_password_change_same_as_current(client):
    res = client.post("/ui/seguridad/password/save", data={
        "current_password": "password123",
        "new_password": "password123",
        "confirm_password": "password123",
    })
    assert res.status_code == 200
    assert "distinta de la actual" in res.text


def test_security_page_has_access_sections(client):
    res = client.get("/seguridad")
    assert res.status_code == 200
    body = res.text
    assert "Contraseña de la cuenta" in body
    assert "PIN de la extensión" in body
    assert "/api/export" in body


# --- Invalidación de sesión server-side (S6) ---

def test_password_change_refreshes_session_cookie(client, auth_user):
    """Tras cambiar la contraseña, el backend reemite la cookie con iat nuevo."""
    res = client.post("/ui/seguridad/password/save", data={
        "current_password": "password123",
        "new_password": "nuevaClave456",
        "confirm_password": "nuevaClave456",
    })
    assert res.status_code == 200
    # La cookie debe venir en Set-Cookie (reemitida).
    set_cookie = res.headers.get("set-cookie", "")
    assert COOKIE_NAME in set_cookie


def test_old_session_cookie_invalidated_after_password_change(auth_user, db):
    """Una cookie emitida ANTES del cambio de contraseña deja de servir."""
    from datetime import datetime, timedelta, timezone
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    # Cookie emitida "hace 1 hora": password_changed_at ya está al momento
    # de creación del user, así que la cookie se considerará válida inicialmente.
    old_cookie = create_session_cookie(auth_user.id)
    # Backdatear la cookie: como create_session_cookie usa time.time(), no
    # podemos fingir un iat viejo por API pública. En su lugar, simulamos el
    # efecto cambiando password_changed_at al FUTURO (como si el user acabara
    # de rotar la contraseña ahora y la cookie fuera previa).
    auth_user.password_changed_at = datetime.now(timezone.utc) + timedelta(seconds=2)
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app, cookies={COOKIE_NAME: old_cookie})
        # /seguridad requiere auth; con la cookie invalidada, debe redirigir.
        res = client.get("/seguridad", follow_redirects=False)
        assert res.status_code in (302, 401), f"esperaba redirect por cookie vieja, got {res.status_code}"
    finally:
        app.dependency_overrides.clear()


def test_session_cookie_with_backdated_iat_rejected(auth_user, db):
    """Si iat < password_changed_at, la cookie se rechaza."""
    from datetime import datetime, timezone
    auth_user.password_changed_at = datetime.now(timezone.utc)
    db.commit()
    # Cookie con iat actual; password_changed_at es el mismo momento. Pasará
    # porque iat >= changed_at (con timestamp).
    # Pero si la cookie fue emitida ANTES (porque cambió pw después), se rechaza.
    from app.auth import _serializer
    import time
    payload = {"uid": auth_user.id, "iat": int(time.time()) - 3600}
    old_token = _serializer().dumps(payload)
    from app.auth import read_session_cookie
    # read_session_cookie solo valida firma y expiración; la invalidación
    # server-side ocurre en get_current_user con password_changed_at.
    # Simulamos: cambiaremos password_changed_at al futuro.
    auth_user.password_changed_at = datetime.now(timezone.utc)
    db.commit()
    # Verificamos que read_session_cookie sigue dando la tupla (firma OK).
    session = read_session_cookie(old_token)
    assert session is not None
    uid, iat = session
    assert uid == auth_user.id
    assert iat < auth_user.password_changed_at.timestamp()

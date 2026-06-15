"""Tests del cambio de contraseña de la cuenta (página de Seguridad)."""

from app.auth import verify_password


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

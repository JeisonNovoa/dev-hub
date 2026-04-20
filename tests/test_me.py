def test_get_me(client):
    res = client.get("/api/me")
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "test@devhub.local"
    assert data["is_active"] is True
    assert "id" in data


def test_update_email(client):
    res = client.put("/api/me", json={"email": "nuevo@example.com"})
    assert res.status_code == 200
    assert res.json()["email"] == "nuevo@example.com"


def test_update_email_same(client):
    # Usar el mismo email (el suyo propio) no debe fallar
    res = client.put("/api/me", json={"email": "test@example.com"})
    assert res.status_code == 200


def test_change_password_ok(client):
    res = client.post("/api/me/password", json={
        "current_password": "password123",
        "new_password": "nuevaclave456",
    })
    assert res.status_code == 204


def test_change_password_wrong_current(client):
    res = client.post("/api/me/password", json={
        "current_password": "incorrecta",
        "new_password": "nuevaclave456",
    })
    assert res.status_code == 400


def test_change_password_too_short(client):
    res = client.post("/api/me/password", json={
        "current_password": "password123",
        "new_password": "corta",
    })
    assert res.status_code == 422


def test_me_unauthenticated(unauth_client):
    res = unauth_client.get("/api/me", follow_redirects=False)
    assert res.status_code in (401, 302)

def test_create_credential(client):
    res = client.post("/api/credentials", json={
        "label": "Google personal",
        "username": "user@gmail.com",
        "password": "secreto123",
        "category": "personal",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["label"] == "Google personal"
    assert data["category"] == "personal"


def test_list_credentials(client):
    client.post("/api/credentials", json={"label": "A", "category": "personal"})
    client.post("/api/credentials", json={"label": "B", "category": "work"})
    res = client.get("/api/credentials")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_filter_by_category(client):
    client.post("/api/credentials", json={"label": "Personal", "category": "personal"})
    client.post("/api/credentials", json={"label": "Trabajo", "category": "work"})
    res = client.get("/api/credentials?category=personal")
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["category"] == "personal"


def test_search_credentials(client):
    client.post("/api/credentials", json={"label": "Cartesia AI", "username": "dev@email.com"})
    client.post("/api/credentials", json={"label": "ElevenLabs", "username": "other@email.com"})
    res = client.get("/api/credentials?search=Cartesia")
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["label"] == "Cartesia AI"


def test_update_credential(client):
    r = client.post("/api/credentials", json={"label": "Old", "category": "personal"})
    cred_id = r.json()["id"]
    res = client.put(f"/api/credentials/{cred_id}", json={"label": "New", "category": "work"})
    assert res.status_code == 200
    assert res.json()["label"] == "New"


def test_delete_credential(client):
    r = client.post("/api/credentials", json={"label": "To Delete", "category": "personal"})
    cred_id = r.json()["id"]
    res = client.delete(f"/api/credentials/{cred_id}")
    assert res.status_code == 204
    assert client.get(f"/api/credentials/{cred_id}").status_code == 404


# --- Página de credenciales: higiene plegable, chips y señal de stale ---

def test_is_stale_helper():
    from datetime import datetime, timedelta, timezone

    from app.routers.ui.credentials import is_stale

    assert is_stale(None) is False
    assert is_stale(datetime.now(timezone.utc)) is False
    assert is_stale(datetime.now(timezone.utc) - timedelta(days=200)) is True


def test_credentials_page_shows_hygiene_and_chips(client):
    # Dos credenciales que comparten contraseña → reutilizada.
    client.post("/api/credentials", json={"label": "Gmail", "username": "a@x.com", "password": "Verano2023!", "category": "personal"})
    client.post("/api/credentials", json={"label": "Netflix", "username": "a@x.com", "password": "Verano2023!", "category": "personal"})
    client.post("/api/credentials", json={"label": "GitHub", "username": "dev", "password": "Gh!9x$Kp2mLq7w", "category": "work"})

    res = client.get("/credentials")
    assert res.status_code == 200
    body = res.text
    # Resumen de higiene presente con sus secciones
    assert "higiene" in body
    assert "reutilizadas" in body
    assert "sin rotar" in body
    # Chips de categoría con contadores
    assert "cat-chip" in body
    # Subtítulo de la bóveda
    assert "Bóveda local" in body


def test_credentials_page_sorts_by_updated_at(client):
    client.post("/api/credentials", json={"label": "Z", "category": "work"})
    res = client.get("/credentials?sort=updated_at&order=desc")
    assert res.status_code == 200

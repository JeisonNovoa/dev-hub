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
    assert len(res.json()) == 2


def test_filter_by_category(client):
    client.post("/api/credentials", json={"label": "Personal", "category": "personal"})
    client.post("/api/credentials", json={"label": "Trabajo", "category": "work"})
    res = client.get("/api/credentials?category=personal")
    assert len(res.json()) == 1
    assert res.json()[0]["category"] == "personal"


def test_search_credentials(client):
    client.post("/api/credentials", json={"label": "Cartesia AI", "username": "dev@email.com"})
    client.post("/api/credentials", json={"label": "ElevenLabs", "username": "other@email.com"})
    res = client.get("/api/credentials?search=Cartesia")
    assert len(res.json()) == 1
    assert res.json()[0]["label"] == "Cartesia AI"


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

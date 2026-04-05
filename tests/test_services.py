def test_create_service(client):
    client.post("/api/projects", json={"name": "Mi App"})
    r = client.get("/api/projects/mi-app")
    project_id = r.json()["id"]
    res = client.post("/api/services", json={
        "name": "Cartesia AI",
        "url": "https://cartesia.ai",
        "category": "ai",
        "project_id": project_id,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Cartesia AI"
    assert data["category"] == "ai"


def test_list_services_all(client):
    client.post("/api/services", json={"name": "ElevenLabs", "category": "ai"})
    client.post("/api/services", json={"name": "Render", "category": "hosting"})
    res = client.get("/api/services")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_list_services_filter_by_project(client):
    client.post("/api/projects", json={"name": "Proyecto A"})
    client.post("/api/projects", json={"name": "Proyecto B"})
    id_a = client.get("/api/projects/proyecto-a").json()["id"]
    id_b = client.get("/api/projects/proyecto-b").json()["id"]
    client.post("/api/services", json={"name": "S1", "project_id": id_a})
    client.post("/api/services", json={"name": "S2", "project_id": id_b})
    res = client.get(f"/api/services?project_id={id_a}")
    assert len(res.json()) == 1
    assert res.json()[0]["name"] == "S1"


def test_get_service(client):
    r = client.post("/api/services", json={"name": "Neon DB", "category": "database"})
    service_id = r.json()["id"]
    res = client.get(f"/api/services/{service_id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Neon DB"


def test_update_service(client):
    r = client.post("/api/services", json={"name": "Old Name", "category": "other"})
    service_id = r.json()["id"]
    res = client.put(f"/api/services/{service_id}", json={"name": "New Name", "category": "ai"})
    assert res.status_code == 200
    assert res.json()["name"] == "New Name"
    assert res.json()["category"] == "ai"


def test_delete_service(client):
    r = client.post("/api/services", json={"name": "To Delete"})
    service_id = r.json()["id"]
    res = client.delete(f"/api/services/{service_id}")
    assert res.status_code == 204
    assert client.get(f"/api/services/{service_id}").status_code == 404


def test_service_not_found(client):
    assert client.get("/api/services/9999").status_code == 404
    assert client.put("/api/services/9999", json={"name": "X"}).status_code == 404
    assert client.delete("/api/services/9999").status_code == 404

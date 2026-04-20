def test_search_by_name(client):
    client.post("/api/projects", json={"name": "FastAPI App"})
    client.post("/api/projects", json={"name": "Django App"})
    res = client.get("/api/projects?search=fastapi")
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "FastAPI App"


def test_search_by_description(client):
    client.post("/api/projects", json={"name": "Proj A", "description": "Uses PostgreSQL"})
    client.post("/api/projects", json={"name": "Proj B", "description": "Uses MySQL"})
    res = client.get("/api/projects?search=postgres")
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Proj A"


def test_search_by_tech_stack(client):
    client.post("/api/projects", json={"name": "Proj A", "tech_stack": ["FastAPI", "Redis"]})
    client.post("/api/projects", json={"name": "Proj B", "tech_stack": ["Django"]})
    res = client.get("/api/projects?search=redis")
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Proj A"


def test_search_by_notes(client):
    client.post("/api/projects", json={"name": "Proj A", "notes": "Deploy en Render"})
    client.post("/api/projects", json={"name": "Proj B", "notes": "Deploy en Fly.io"})
    res = client.get("/api/projects?search=render")
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Proj A"


def test_search_no_results(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.get("/api/projects?search=zzznomatch")
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_search_combined_with_status(client):
    client.post("/api/projects", json={"name": "App activa", "status": "active"})
    client.post("/api/projects", json={"name": "App pausada", "status": "paused"})
    res = client.get("/api/projects?search=app&status=active")
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "active"

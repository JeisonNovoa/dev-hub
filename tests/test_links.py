def test_list_links_empty(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.get("/api/projects/mi-app/links")
    assert res.status_code == 200
    assert res.json() == []


def test_create_link(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.post("/api/projects/mi-app/links", json={
        "label": "Dashboard Render",
        "url": "https://dashboard.render.com",
        "category": "dashboard",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["label"] == "Dashboard Render"
    assert data["category"] == "dashboard"


def test_list_links(client):
    client.post("/api/projects", json={"name": "Mi App"})
    client.post("/api/projects/mi-app/links", json={"label": "Repo", "url": "https://github.com/x/y", "category": "repo"})
    client.post("/api/projects/mi-app/links", json={"label": "Docs", "url": "https://docs.example.com", "category": "docs"})
    res = client.get("/api/projects/mi-app/links")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_update_link(client):
    client.post("/api/projects", json={"name": "Mi App"})
    r = client.post("/api/projects/mi-app/links", json={"label": "Old", "url": "https://old.com", "category": "other"})
    link_id = r.json()["id"]
    res = client.put(f"/api/projects/mi-app/links/{link_id}", json={"label": "New", "url": "https://new.com", "category": "prod"})
    assert res.status_code == 200
    assert res.json()["label"] == "New"
    assert res.json()["category"] == "prod"


def test_delete_link(client):
    client.post("/api/projects", json={"name": "Mi App"})
    r = client.post("/api/projects/mi-app/links", json={"label": "To Delete", "url": "https://x.com", "category": "other"})
    link_id = r.json()["id"]
    res = client.delete(f"/api/projects/mi-app/links/{link_id}")
    assert res.status_code == 204
    res = client.get("/api/projects/mi-app/links")
    assert len(res.json()) == 0


def test_link_project_not_found(client):
    res = client.get("/api/projects/no-existe/links")
    assert res.status_code == 404


def test_link_not_found(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.put("/api/projects/mi-app/links/9999", json={"label": "X", "url": "https://x.com"})
    assert res.status_code == 404


def test_delete_link_cascades_with_project(client):
    client.post("/api/projects", json={"name": "Mi App"})
    client.post("/api/projects/mi-app/links", json={"label": "Repo", "url": "https://github.com/x/y"})
    client.delete("/api/projects/mi-app")
    res = client.get("/api/projects/mi-app/links")
    assert res.status_code == 404

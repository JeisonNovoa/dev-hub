def test_export_empty_db(client):
    res = client.get("/api/export")
    assert res.status_code == 200
    data = res.json()
    assert data["projects"] == []
    assert data["credentials"] == []
    assert data["services"] == []


def test_export_with_full_data(client):
    # Proyecto con env var, comando y link
    client.post("/api/projects", json={"name": "Proyecto Export", "tech_stack": ["FastAPI"]})
    client.post("/api/projects/proyecto-export/env-vars", json={"key": "PORT", "value": "8000"})
    client.post("/api/projects/proyecto-export/commands", json={
        "label": "Start", "command": "uvicorn app.main:app", "order": 0, "type": "start"
    })
    client.post("/api/projects/proyecto-export/links", json={
        "label": "Repo", "url": "https://github.com/x/y", "category": "repo"
    })
    # Repo
    client.post("/api/projects/proyecto-export/repos", json={"name": "backend"})

    # Credencial
    client.post("/api/credentials", json={"label": "Render", "username": "user@mail.com", "category": "work"})

    # Servicio
    client.post("/api/services", json={"name": "Neon DB", "category": "database"})

    res = client.get("/api/export")
    assert res.status_code == 200
    data = res.json()

    assert len(data["projects"]) == 1
    project = data["projects"][0]
    assert project["name"] == "Proyecto Export"
    assert len(project["env_vars"]) == 1
    assert len(project["commands"]) == 1
    assert len(project["links"]) == 1
    assert len(project["repos"]) == 1

    assert len(data["credentials"]) == 1
    assert data["credentials"][0]["label"] == "Render"

    assert len(data["services"]) == 1
    assert data["services"][0]["name"] == "Neon DB"


def test_export_multiple_projects(client):
    client.post("/api/projects", json={"name": "Alpha"})
    client.post("/api/projects", json={"name": "Beta"})
    res = client.get("/api/export")
    assert len(res.json()["projects"]) == 2

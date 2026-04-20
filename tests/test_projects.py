def test_create_project(client):
    res = client.post("/api/projects", json={"name": "Mi App", "tech_stack": ["FastAPI"]})
    assert res.status_code == 201
    data = res.json()
    assert data["slug"] == "mi-app"
    assert data["status"] == "active"
    assert data["tech_stack"] == ["FastAPI"]


def test_create_project_duplicate_slug(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.post("/api/projects", json={"name": "Mi App"})
    assert res.status_code == 409


def test_get_project(client):
    client.post("/api/projects", json={"name": "Test Project"})
    res = client.get("/api/projects/test-project")
    assert res.status_code == 200
    assert res.json()["name"] == "Test Project"


def test_list_projects(client):
    client.post("/api/projects", json={"name": "Proyecto A"})
    client.post("/api/projects", json={"name": "Proyecto B"})
    res = client.get("/api/projects")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_patch_project_status(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.patch("/api/projects/mi-app", json={"status": "paused"})
    assert res.status_code == 200
    assert res.json()["status"] == "paused"


def test_delete_project(client):
    client.post("/api/projects", json={"name": "Para Borrar"})
    res = client.delete("/api/projects/para-borrar")
    assert res.status_code == 204
    assert client.get("/api/projects/para-borrar").status_code == 404


def test_create_env_var(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.post("/api/projects/mi-app/env-vars", json={"key": "DATABASE_URL", "value": "sqlite:///test.db"})
    assert res.status_code == 201
    assert res.json()["key"] == "DATABASE_URL"


def test_create_command(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.post("/api/projects/mi-app/commands", json={
        "label": "Iniciar", "command": "uvicorn app.main:app --reload", "order": 0, "type": "start"
    })
    assert res.status_code == 201
    assert res.json()["type"] == "start"


def test_project_detail_includes_relations(client):
    client.post("/api/projects", json={"name": "Mi App"})
    client.post("/api/projects/mi-app/env-vars", json={"key": "PORT", "value": "8000"})
    client.post("/api/projects/mi-app/commands", json={"label": "Run", "command": "uvicorn ...", "order": 0, "type": "start"})
    res = client.get("/api/projects/mi-app")
    assert res.status_code == 200
    data = res.json()
    assert len(data["env_vars"]) == 1
    assert len(data["commands"]) == 1


def test_update_env_var(client):
    client.post("/api/projects", json={"name": "Mi App"})
    r = client.post("/api/projects/mi-app/env-vars", json={"key": "OLD_KEY", "value": "old"})
    env_id = r.json()["id"]
    res = client.put(f"/api/projects/mi-app/env-vars/{env_id}", json={"key": "NEW_KEY", "value": "new"})
    assert res.status_code == 200
    assert res.json()["key"] == "NEW_KEY"


def test_delete_env_var(client):
    client.post("/api/projects", json={"name": "Mi App"})
    r = client.post("/api/projects/mi-app/env-vars", json={"key": "TO_DELETE", "value": "val"})
    env_id = r.json()["id"]
    res = client.delete(f"/api/projects/mi-app/env-vars/{env_id}")
    assert res.status_code == 204
    res = client.get("/api/projects/mi-app/env-vars")
    assert len(res.json()) == 0


def test_list_env_vars(client):
    client.post("/api/projects", json={"name": "Mi App"})
    client.post("/api/projects/mi-app/env-vars", json={"key": "A", "value": "1"})
    client.post("/api/projects/mi-app/env-vars", json={"key": "B", "value": "2"})
    res = client.get("/api/projects/mi-app/env-vars")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_update_command(client):
    client.post("/api/projects", json={"name": "Mi App"})
    r = client.post("/api/projects/mi-app/commands", json={
        "label": "Old", "command": "old_cmd", "order": 0, "type": "start"
    })
    cmd_id = r.json()["id"]
    res = client.put(f"/api/projects/mi-app/commands/{cmd_id}", json={
        "label": "New", "command": "new_cmd", "type": "build"
    })
    assert res.status_code == 200
    assert res.json()["label"] == "New"
    assert res.json()["type"] == "build"


def test_delete_command(client):
    client.post("/api/projects", json={"name": "Mi App"})
    r = client.post("/api/projects/mi-app/commands", json={
        "label": "Temp", "command": "temp_cmd", "order": 0, "type": "other"
    })
    cmd_id = r.json()["id"]
    res = client.delete(f"/api/projects/mi-app/commands/{cmd_id}")
    assert res.status_code == 204
    res = client.get("/api/projects/mi-app/commands")
    assert len(res.json()) == 0


def test_list_commands(client):
    client.post("/api/projects", json={"name": "Mi App"})
    client.post("/api/projects/mi-app/commands", json={"label": "A", "command": "cmd_a", "order": 0, "type": "start"})
    client.post("/api/projects/mi-app/commands", json={"label": "B", "command": "cmd_b", "order": 1, "type": "build"})
    res = client.get("/api/projects/mi-app/commands")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_project_not_found(client):
    assert client.get("/api/projects/no-existe").status_code == 404
    assert client.patch("/api/projects/no-existe", json={"status": "paused"}).status_code == 404
    assert client.delete("/api/projects/no-existe").status_code == 404

def test_create_repo(client):
    client.post("/api/projects", json={"name": "English Code"})
    res = client.post("/api/projects/english-code/repos", json={
        "name": "englishcode-ai-chatbot-backend",
        "local_path": "C:/Users/jeiso/Desktop/englishcode/englishcode-ai-chatbot-backend",
        "github_url": "https://github.com/Teilur-Engineering/englishcode-ai-chatbot-backend",
        "description": "API principal Django 5",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["slug"] == "englishcode-ai-chatbot-backend"
    assert data["local_path"] is not None


def test_list_repos(client):
    client.post("/api/projects", json={"name": "English Code"})
    client.post("/api/projects/english-code/repos", json={"name": "Repo A"})
    client.post("/api/projects/english-code/repos", json={"name": "Repo B"})
    res = client.get("/api/projects/english-code/repos")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_get_repo_detail(client):
    client.post("/api/projects", json={"name": "English Code"})
    client.post("/api/projects/english-code/repos", json={"name": "test-agents-1"})
    res = client.get("/api/projects/english-code/repos/test-agents-1")
    assert res.status_code == 200
    data = res.json()
    assert "commands" in data
    assert "env_vars" in data


def test_repo_commands(client):
    client.post("/api/projects", json={"name": "English Code"})
    client.post("/api/projects/english-code/repos", json={"name": "test-agents-1"})
    res = client.post("/api/projects/english-code/repos/test-agents-1/commands", json={
        "label": "Iniciar agente",
        "command": "python main.py",
        "order": 0,
        "type": "start",
    })
    assert res.status_code == 201
    assert res.json()["type"] == "start"


def test_repo_env_vars(client):
    client.post("/api/projects", json={"name": "English Code"})
    client.post("/api/projects/english-code/repos", json={"name": "test-agents-1"})
    res = client.post("/api/projects/english-code/repos/test-agents-1/env-vars", json={
        "key": "CARTESIA_API_KEY",
        "value": "sk-xxxx",
    })
    assert res.status_code == 201
    assert res.json()["key"] == "CARTESIA_API_KEY"


def test_delete_repo_cascades(client):
    client.post("/api/projects", json={"name": "English Code"})
    client.post("/api/projects/english-code/repos", json={"name": "test-agents-1"})
    client.post("/api/projects/english-code/repos/test-agents-1/commands", json={
        "label": "Run", "command": "python main.py", "order": 0, "type": "start"
    })
    res = client.delete("/api/projects/english-code/repos/test-agents-1")
    assert res.status_code == 204
    assert client.get("/api/projects/english-code/repos/test-agents-1").status_code == 404

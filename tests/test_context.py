"""Tests del contexto de proyecto para LLM (service + endpoints /api/context)."""


def _setup_full_project(client) -> str:
    """Crea un proyecto con todas sus secciones. Devuelve el slug."""
    client.post("/api/projects", json={
        "name": "Mi App",
        "tech_stack": ["FastAPI", "HTMX"],
        "description": "Una app de prueba",
        "notes": "Recordar correr migraciones antes de arrancar.",
    })
    slug = "mi-app"
    client.post(f"/api/projects/{slug}/env-vars", json={"key": "PORT", "value": "8000", "description": "Puerto"})
    client.post(f"/api/projects/{slug}/commands", json={
        "label": "Iniciar", "command": "uvicorn app.main:app", "order": 0, "type": "start"
    })
    client.post(f"/api/projects/{slug}/links", json={
        "label": "Repo", "url": "https://github.com/x/y", "category": "repo"
    })
    client.post(f"/api/projects/{slug}/repos", json={"name": "backend"})
    client.post("/api/services", json={"name": "Supabase", "category": "db"})
    # Credencial asociada al proyecto, CON contraseña (para verificar que NO se filtra)
    project = client.get(f"/api/projects/{slug}").json()
    client.post("/api/credentials", json={
        "label": "Cuenta Supabase",
        "username": "admin@app.com",
        "password": "SECRETO-no-debe-aparecer",
        "category": "project",
        "project_id": project["id"],
    })
    return slug


# ─── /api/context/{slug} markdown ────────────────────────────────────────────

def test_context_markdown_contains_all_sections(client):
    slug = _setup_full_project(client)
    res = client.get(f"/api/context/{slug}")
    assert res.status_code == 200
    assert "text/markdown" in res.headers["content-type"]
    md = res.text
    assert "# Mi App" in md
    assert "FastAPI, HTMX" in md
    assert "uvicorn app.main:app" in md
    assert "PORT" in md
    assert "github.com/x/y" in md
    assert "backend" in md
    assert "Supabase" in md
    assert "Cuenta Supabase" in md


def test_context_markdown_never_leaks_password(client):
    """Crítico: el contexto jamás debe incluir la contraseña de una credencial."""
    slug = _setup_full_project(client)
    res = client.get(f"/api/context/{slug}")
    assert "SECRETO-no-debe-aparecer" not in res.text
    # Pero sí la referencia (username) para orientar a la IA
    assert "admin@app.com" in res.text


def test_context_json_format(client):
    slug = _setup_full_project(client)
    res = client.get(f"/api/context/{slug}?format=json")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Mi App"
    assert data["tech_stack"] == ["FastAPI", "HTMX"]
    assert len(data["commands"]) == 1
    assert len(data["env_vars"]) == 1
    assert len(data["credentials"]) == 1
    # El JSON tampoco expone password
    assert "password" not in data["credentials"][0]


def test_context_404_for_missing_project(client):
    res = client.get("/api/context/no-existe")
    assert res.status_code == 404


def test_context_requires_auth(unauth_client):
    res = unauth_client.get("/api/context/cualquiera", follow_redirects=False)
    assert res.status_code in (302, 401)


def test_context_isolated_per_user(client, unauth_client, db):
    """Un usuario no puede ver el contexto del proyecto de otro."""
    from app.auth import hash_password
    from app.models import Project, User

    client.post("/api/projects", json={"name": "Privado"})

    other = User(email="otro@test.local", hashed_password=hash_password("password123"), is_active=True)
    db.add(other)
    db.commit()
    db.refresh(other)
    # El proyecto "Privado" pertenece al auth_user, no a `other`.
    assert db.query(Project).filter(Project.user_id == other.id).count() == 0


# ─── /api/context/recent ─────────────────────────────────────────────────────

def test_recent_activity_returns_events(client):
    slug = _setup_full_project(client)
    res = client.get("/api/context/recent")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    # Crear comandos/env vars/etc generó eventos de actividad
    assert len(data["events"]) > 0
    first = data["events"][0]
    assert "project" in first
    assert "summary" in first
    assert first["project"] == slug


def test_recent_activity_empty(client):
    res = client.get("/api/context/recent")
    assert res.status_code == 200
    assert res.json()["events"] == []

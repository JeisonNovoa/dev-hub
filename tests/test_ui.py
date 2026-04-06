"""Tests para los routers UI (HTML responses) y los endpoints del design del proyecto."""


# ─── Helpers ────────────────────────────────────────────────────────────────

def _create_project(client, name="Test Project"):
    client.post("/api/projects", json={"name": name})
    return name.lower().replace(" ", "-")


def _create_env_var(client, slug, key="DATABASE_URL", value="sqlite:///test.db"):
    r = client.post(f"/api/projects/{slug}/env-vars", json={"key": key, "value": value})
    return r.json()["id"]


def _create_command(client, slug, label="Start", command="uvicorn app.main:app"):
    r = client.post(f"/api/projects/{slug}/commands", json={
        "label": label, "command": command, "order": 0, "type": "start"
    })
    return r.json()["id"]


def _create_link(client, slug, label="Repo", url="https://github.com/x/y"):
    r = client.post(f"/api/projects/{slug}/links", json={
        "label": label, "url": url, "category": "repo"
    })
    return r.json()["id"]


def _create_credential(client, label="Google", category="personal"):
    r = client.post("/api/credentials", json={
        "label": label, "username": "user@mail.com", "category": category
    })
    return r.json()["id"]


# ─── Dashboard ───────────────────────────────────────────────────────────────

def test_dashboard_page_empty(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"proyectos" in res.content.lower()


def test_dashboard_page_with_projects(client):
    _create_project(client, "Alpha Project")
    _create_project(client, "Beta Project")
    res = client.get("/")
    assert res.status_code == 200
    assert b"Alpha Project" in res.content


def test_dashboard_search(client):
    _create_project(client, "FastAPI Service")
    res = client.get("/ui/dashboard/cards?q=fastapi")
    assert res.status_code == 200
    assert b"FastAPI Service" in res.content


def test_dashboard_search_no_results(client):
    _create_project(client, "FastAPI Service")
    res = client.get("/ui/dashboard/cards?q=nonexistent")
    assert res.status_code == 200


def test_dashboard_filter_active(client):
    _create_project(client, "Active App")
    res = client.get("/ui/dashboard/cards?status=active")
    assert res.status_code == 200
    assert b"Active App" in res.content


def test_dashboard_filter_archived(client):
    _create_project(client, "Old App")
    client.patch("/api/projects/old-app", json={"status": "archived"})
    res = client.get("/ui/dashboard/cards?status=archived")
    assert res.status_code == 200
    assert b"Old App" in res.content


def test_create_project_form_normal(client):
    res = client.post("/ui/projects/new", data={
        "name": "Nueva App",
        "description": "Una descripción",
        "tech_stack_raw": "FastAPI, React",
    }, follow_redirects=False)
    assert res.status_code in (302, 303)


def test_create_project_form_htmx(client):
    res = client.post("/ui/projects/new", data={
        "name": "Nueva App HTMX",
        "description": "",
        "tech_stack_raw": "",
    }, headers={"HX-Request": "true"})
    assert res.status_code == 200
    assert "HX-Redirect" in res.headers


# ─── Project detail ───────────────────────────────────────────────────────────

def test_project_detail_page(client):
    slug = _create_project(client)
    res = client.get(f"/projects/{slug}")
    assert res.status_code == 200
    assert b"Test Project" in res.content


def test_project_detail_404(client):
    res = client.get("/projects/no-existe")
    assert res.status_code == 404


# ─── Header del proyecto ──────────────────────────────────────────────────────

def test_project_header_view(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/header/view")
    assert res.status_code == 200


def test_project_header_edit(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/header/edit")
    assert res.status_code == 200


def test_project_header_save(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/header/save", data={
        "name": "Updated Name",
        "description": "Nueva descripción",
        "tech_stack_raw": "Django, PostgreSQL",
    })
    assert res.status_code == 200
    assert b"Updated Name" in res.content


# ─── Env vars UI ─────────────────────────────────────────────────────────────

def test_env_var_new_form(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/env-vars/new")
    assert res.status_code == 200


def test_env_var_cancel_new(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/env-vars/cancel-new")
    assert res.status_code == 200
    assert res.content == b""


def test_env_var_new_submit(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/env-vars/new", data={
        "key": "SECRET_KEY",
        "value": "supersecret",
        "description": "Clave secreta",
    })
    assert res.status_code == 200
    assert b"SECRET_KEY" in res.content


def test_env_var_edit_form(client):
    slug = _create_project(client)
    env_id = _create_env_var(client, slug)
    res = client.get(f"/ui/projects/{slug}/env-vars/{env_id}/edit")
    assert res.status_code == 200


def test_env_var_view(client):
    slug = _create_project(client)
    env_id = _create_env_var(client, slug)
    res = client.get(f"/ui/projects/{slug}/env-vars/{env_id}/view")
    assert res.status_code == 200
    assert b"DATABASE_URL" in res.content


def test_env_var_edit_404(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/env-vars/9999/edit")
    assert res.status_code == 404


# ─── Commands UI ─────────────────────────────────────────────────────────────

def test_command_new_form(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/commands/new")
    assert res.status_code == 200


def test_command_new_submit(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/commands/new", data={
        "label": "Start Dev",
        "command": "uvicorn app.main:app --reload",
        "order": "0",
        "type": "start",
    })
    assert res.status_code == 200
    assert b"Start Dev" in res.content


def test_command_edit_form(client):
    slug = _create_project(client)
    cmd_id = _create_command(client, slug)
    res = client.get(f"/ui/projects/{slug}/commands/{cmd_id}/edit")
    assert res.status_code == 200


def test_command_view(client):
    slug = _create_project(client)
    cmd_id = _create_command(client, slug)
    res = client.get(f"/ui/projects/{slug}/commands/{cmd_id}/view")
    assert res.status_code == 200


def test_command_edit_404(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/commands/9999/edit")
    assert res.status_code == 404


# ─── Links UI ────────────────────────────────────────────────────────────────

def test_link_new_form(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/links/new")
    assert res.status_code == 200


def test_link_new_submit(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/links/new", data={
        "label": "GitHub Repo",
        "url": "https://github.com/x/y",
        "category": "repo",
    })
    assert res.status_code == 200
    assert b"GitHub Repo" in res.content


def test_link_edit_form(client):
    slug = _create_project(client)
    link_id = _create_link(client, slug)
    res = client.get(f"/ui/projects/{slug}/links/{link_id}/edit")
    assert res.status_code == 200


def test_link_view(client):
    slug = _create_project(client)
    link_id = _create_link(client, slug)
    res = client.get(f"/ui/projects/{slug}/links/{link_id}/view")
    assert res.status_code == 200


def test_link_edit_404(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/links/9999/edit")
    assert res.status_code == 404


# ─── Notes UI ────────────────────────────────────────────────────────────────

def test_notes_view(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/notes/view")
    assert res.status_code == 200


def test_notes_edit(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/notes/edit")
    assert res.status_code == 200


def test_notes_save(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/notes/save", data={
        "notes": "# Notas\n\nEsto es una nota en **markdown**."
    })
    assert res.status_code == 200


def test_notes_save_empty(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/notes/save", data={"notes": ""})
    assert res.status_code == 200


# ─── Services UI ─────────────────────────────────────────────────────────────

def test_service_new_form(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/services/new")
    assert res.status_code == 200


def test_service_cancel_new(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/services/cancel-new")
    assert res.status_code == 200
    assert res.content == b""


def test_service_new_submit(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/services/new", data={
        "name": "Cartesia AI",
        "category": "ai",
        "url": "https://cartesia.ai",
        "notes": "",
    })
    assert res.status_code == 200
    assert b"Cartesia AI" in res.content


def test_service_edit_form(client):
    slug = _create_project(client)
    client.post(f"/ui/projects/{slug}/services/new", data={
        "name": "Neon DB", "category": "database", "url": "", "notes": ""
    })
    project = client.get(f"/api/projects/{slug}").json()
    services = client.get("/api/services").json()
    service_id = services[0]["id"]
    res = client.get(f"/ui/projects/{slug}/services/{service_id}/edit")
    assert res.status_code == 200


def test_service_view(client):
    slug = _create_project(client)
    client.post(f"/ui/projects/{slug}/services/new", data={
        "name": "Render", "category": "hosting", "url": "https://render.com", "notes": ""
    })
    services = client.get("/api/services").json()
    service_id = services[0]["id"]
    res = client.get(f"/ui/projects/{slug}/services/{service_id}/view")
    assert res.status_code == 200


# ─── Repos UI ────────────────────────────────────────────────────────────────

def test_repo_new_form(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/repos/new")
    assert res.status_code == 200


def test_repo_new_submit(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/repos/new", data={
        "name": "backend",
        "local_path": "C:/projects/backend",
        "github_url": "https://github.com/x/backend",
        "description": "API principal",
    })
    assert res.status_code == 200
    assert b"backend" in res.content


def test_repo_edit_form(client):
    slug = _create_project(client)
    client.post(f"/api/projects/{slug}/repos", json={"name": "my-repo"})
    repos = client.get(f"/api/projects/{slug}/repos").json()
    repo_id = repos[0]["id"]
    res = client.get(f"/ui/projects/{slug}/repos/{repo_id}/edit")
    assert res.status_code == 200


def test_repo_view(client):
    slug = _create_project(client)
    client.post(f"/api/projects/{slug}/repos", json={"name": "my-repo"})
    repos = client.get(f"/api/projects/{slug}/repos").json()
    repo_id = repos[0]["id"]
    res = client.get(f"/ui/projects/{slug}/repos/{repo_id}/view")
    assert res.status_code == 200


# ─── Credenciales del proyecto (UI inline) ───────────────────────────────────

def test_project_credential_new_form(client):
    slug = _create_project(client)
    res = client.get(f"/ui/projects/{slug}/credentials/new")
    assert res.status_code == 200


def test_project_credential_new_submit_email(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/credentials/new", data={
        "label": "Supabase",
        "username": "user@mail.com",
        "password": "secret123",
        "url": "https://supabase.com",
        "login_via": "email",
    })
    assert res.status_code == 200
    assert b"Supabase" in res.content


def test_project_credential_new_submit_google(client):
    slug = _create_project(client)
    res = client.post(f"/ui/projects/{slug}/credentials/new", data={
        "label": "Render",
        "username": "",
        "password": "",
        "url": "https://render.com",
        "login_via": "google",
    })
    assert res.status_code == 200
    assert b"Render" in res.content


def test_project_credential_edit_form(client):
    slug = _create_project(client)
    client.post(f"/ui/projects/{slug}/credentials/new", data={
        "label": "Neon", "username": "user@mail.com", "login_via": "email"
    })
    creds = client.get("/api/credentials").json()
    cred_id = creds[0]["id"]
    res = client.get(f"/ui/projects/{slug}/credentials/{cred_id}/edit")
    assert res.status_code == 200


def test_project_credential_save(client):
    slug = _create_project(client)
    client.post(f"/ui/projects/{slug}/credentials/new", data={
        "label": "Neon", "username": "old@mail.com", "login_via": "email"
    })
    creds = client.get("/api/credentials").json()
    cred_id = creds[0]["id"]
    res = client.post(f"/ui/projects/{slug}/credentials/{cred_id}/save", data={
        "label": "Neon DB",
        "username": "new@mail.com",
        "password": "newpass",
        "url": "https://neon.tech",
        "login_via": "email",
        "notes": "conexión principal",
    })
    assert res.status_code == 200
    assert b"Neon DB" in res.content


def test_project_credential_view(client):
    slug = _create_project(client)
    client.post(f"/ui/projects/{slug}/credentials/new", data={
        "label": "Stripe", "username": "admin@mail.com", "login_via": "email"
    })
    creds = client.get("/api/credentials").json()
    cred_id = creds[0]["id"]
    res = client.get(f"/ui/projects/{slug}/credentials/{cred_id}/view")
    assert res.status_code == 200


# ─── Credenciales globales (UI /credentials) ─────────────────────────────────

def test_credentials_page(client):
    res = client.get("/credentials")
    assert res.status_code == 200


def test_credentials_page_with_data(client):
    _create_credential(client, "Google", "personal")
    _create_credential(client, "GitHub", "work")
    res = client.get("/credentials")
    assert res.status_code == 200
    assert b"Google" in res.content


def test_credentials_page_htmx_returns_rows(client):
    _create_credential(client)
    res = client.get("/credentials?q=google", headers={"HX-Request": "true"})
    assert res.status_code == 200


def test_credentials_filter_category(client):
    _create_credential(client, "Personal Cred", "personal")
    _create_credential(client, "Work Cred", "work")
    res = client.get("/credentials?category=personal")
    assert res.status_code == 200
    assert b"Personal Cred" in res.content


def test_credential_create_form(client):
    res = client.post("/ui/credentials/new", data={
        "label": "New Cred",
        "username": "user@x.com",
        "password": "pass123",
        "url": "https://example.com",
        "category": "personal",
        "login_via": "email",
    }, follow_redirects=False)
    assert res.status_code in (302, 303)


def test_credential_edit_form_ui(client):
    cred_id = _create_credential(client)
    res = client.get(f"/ui/credentials/{cred_id}/edit")
    assert res.status_code == 200


def test_credential_view_ui(client):
    cred_id = _create_credential(client)
    res = client.get(f"/ui/credentials/{cred_id}/view")
    assert res.status_code == 200


def test_credential_save_ui(client):
    cred_id = _create_credential(client, "Old Label", "personal")
    res = client.post(f"/ui/credentials/{cred_id}/save", data={
        "label": "Updated Label",
        "username": "new@x.com",
        "password": "newpass",
        "url": "https://x.com",
        "category": "work",
        "login_via": "email",
        "notes": "",
        "project_id": "",
    })
    assert res.status_code == 200
    assert b"Updated Label" in res.content


def test_credential_edit_404_ui(client):
    res = client.get("/ui/credentials/9999/edit")
    assert res.status_code == 404



# ─── Repo commands y env-vars (UI) ───────────────────────────────────────────

def test_repo_command_new_form(client):
    slug = _create_project(client)
    client.post(f"/api/projects/{slug}/repos", json={"name": "my-repo"})
    repos = client.get(f"/api/projects/{slug}/repos").json()
    repo_id = repos[0]["id"]
    res = client.get(f"/ui/projects/{slug}/repos/{repo_id}/commands/new")
    assert res.status_code == 200


def test_repo_command_new_submit(client):
    slug = _create_project(client)
    client.post(f"/api/projects/{slug}/repos", json={"name": "my-repo"})
    repos = client.get(f"/api/projects/{slug}/repos").json()
    repo_id = repos[0]["id"]
    res = client.post(f"/ui/projects/{slug}/repos/{repo_id}/commands/new", data={
        "label": "Run Tests",
        "command": "pytest tests/",
        "order": "0",
        "type": "test",
    })
    assert res.status_code == 200
    assert b"Run Tests" in res.content


def test_repo_env_var_new_form(client):
    slug = _create_project(client)
    client.post(f"/api/projects/{slug}/repos", json={"name": "my-repo"})
    repos = client.get(f"/api/projects/{slug}/repos").json()
    repo_id = repos[0]["id"]
    res = client.get(f"/ui/projects/{slug}/repos/{repo_id}/env-vars/new")
    assert res.status_code == 200


def test_repo_env_var_new_submit(client):
    slug = _create_project(client)
    client.post(f"/api/projects/{slug}/repos", json={"name": "my-repo"})
    repos = client.get(f"/api/projects/{slug}/repos").json()
    repo_id = repos[0]["id"]
    res = client.post(f"/ui/projects/{slug}/repos/{repo_id}/env-vars/new", data={
        "key": "REDIS_URL",
        "value": "redis://localhost:6379",
        "description": "",
    })
    assert res.status_code == 200
    assert b"REDIS_URL" in res.content

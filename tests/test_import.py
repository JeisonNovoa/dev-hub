"""Tests de importación de proyectos: API, UI (pegar/subir), parseo leniente y aislamiento."""

import io
import json

FULL_PAYLOAD = {
    "name": "Proyecto Importado",
    "description": "App de prueba",
    "tech_stack": ["FastAPI", "React"],
    "status": "active",
    "notes": "# Notas\nalgo",
    "commands": [
        {"label": "Iniciar", "command": "uvicorn app.main:app --reload", "type": "start", "order": 0},
        {"label": "Tests", "command": "pytest", "type": "other", "order": 1},
    ],
    "env_vars": [
        {"key": "DATABASE_URL", "value": "", "description": "URL de Postgres"},
    ],
    "links": [
        {"label": "Repo", "url": "https://github.com/x/y", "category": "repo"},
    ],
    "repos": [
        {
            "name": "backend",
            "github_url": "https://github.com/x/y",
            "local_path": "C:/dev/backend",
            "commands": [{"label": "Migrar", "command": "alembic upgrade head", "type": "migration"}],
            "env_vars": [{"key": "SECRET_KEY", "value": ""}],
        }
    ],
    "services": [
        {"name": "Supabase", "url": "https://supabase.com", "category": "db"},
    ],
}


# ─── API: POST /api/projects/import ──────────────────────────────────────────

def test_api_import_full_payload(client):
    res = client.post("/api/projects/import", json=FULL_PAYLOAD)
    assert res.status_code == 201
    body = res.json()
    assert body["project"]["slug"] == "proyecto-importado"
    assert body["counts"] == {"commands": 3, "env_vars": 2, "links": 1, "repos": 1, "services": 1}
    assert body["skipped"] == []

    detail = client.get("/api/projects/proyecto-importado").json()
    assert detail["name"] == "Proyecto Importado"
    assert len(detail["commands"]) == 3  # incluye los del repo
    assert len(detail["links"]) == 1


def test_api_import_minimal(client):
    res = client.post("/api/projects/import", json={"name": "Minimo"})
    assert res.status_code == 201
    assert res.json()["counts"] == {"commands": 0, "env_vars": 0, "links": 0, "repos": 0, "services": 0}


def test_api_import_requires_name(client):
    res = client.post("/api/projects/import", json={"description": "sin nombre"})
    assert res.status_code == 422
    assert "name" in res.json()["detail"]


def test_api_import_duplicate_creates_suffixed_slug(client):
    client.post("/api/projects/import", json={"name": "Duplicado"})
    res = client.post("/api/projects/import", json={"name": "Duplicado"})
    assert res.status_code == 201
    assert res.json()["project"]["slug"] == "duplicado-2"
    # El original sigue intacto
    assert client.get("/api/projects/duplicado").status_code == 200


def test_api_import_skips_invalid_items_keeps_rest(client):
    payload = {
        "name": "Con Errores",
        "links": [
            {"label": "Bueno", "url": "https://ok.com", "category": "docs"},
            {"label": "Malo", "url": "ftp://invalido"},
            {"url": "https://sin-label.com"},
        ],
        "commands": [
            {"label": "OK", "command": "echo hola"},
            {"label": "Sin comando"},
        ],
    }
    res = client.post("/api/projects/import", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["counts"]["links"] == 1
    assert body["counts"]["commands"] == 1
    assert len(body["skipped"]) == 3


def test_api_import_normalizes_out_of_range_values(client):
    payload = {
        "name": "Normalizado",
        "status": "inventado",
        "commands": [{"label": "X", "command": "x", "type": "raro"}],
        "services": [{"name": "S", "category": "categoria-falsa"}],
    }
    res = client.post("/api/projects/import", json=payload)
    assert res.status_code == 201
    assert res.json()["project"]["status"] == "active"
    detail = client.get(f"/api/projects/{res.json()['project']['slug']}").json()
    assert detail["commands"][0]["type"] == "other"


# ─── UI: POST /ui/import ─────────────────────────────────────────────────────

def test_ui_import_paste_json_redirects(client):
    res = client.post(
        "/ui/import",
        data={"json_text": json.dumps(FULL_PAYLOAD)},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert res.headers["location"].startswith("/projects/proyecto-importado")


def test_ui_import_htmx_returns_hx_redirect(client):
    res = client.post(
        "/ui/import",
        data={"json_text": json.dumps({"name": "Via HTMX"})},
        headers={"HX-Request": "true"},
    )
    assert res.status_code == 200
    assert res.headers["HX-Redirect"] == "/projects/via-htmx"


def test_ui_import_file_upload(client):
    content = json.dumps(FULL_PAYLOAD).encode()
    res = client.post(
        "/ui/import",
        files={"file": ("devhub.json", io.BytesIO(content), "application/json")},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert client.get("/api/projects/proyecto-importado").status_code == 200


def test_ui_import_tolerates_code_fence(client):
    fenced = "```json\n" + json.dumps({"name": "Con Fence"}) + "\n```"
    res = client.post("/ui/import", data={"json_text": fenced}, follow_redirects=False)
    assert res.status_code == 303


def test_ui_import_invalid_json_shows_error(client):
    res = client.post("/ui/import", data={"json_text": "{esto no es json"})
    assert res.status_code == 200
    assert "JSON inválido".encode() in res.content


def test_ui_import_empty_shows_error(client):
    res = client.post("/ui/import", data={"json_text": "   "})
    assert res.status_code == 200
    assert b"Pega el JSON" in res.content


def test_ui_import_prompt_endpoint(client):
    res = client.get("/ui/import/prompt")
    assert res.status_code == 200
    assert b"env_vars" in res.content
    assert b"UNICAMENTE un objeto JSON" in res.content


def test_dashboard_shows_import_modal(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b'id="import-modal"' in res.content
    assert b'id="import-prompt-text"' in res.content


# ─── Aislamiento por usuario ─────────────────────────────────────────────────

def test_imported_project_belongs_to_current_user(client, db, auth_user):
    client.post("/api/projects/import", json={"name": "Mio"})
    from app.models import Project

    project = db.query(Project).filter(Project.slug == "mio").first()
    assert project is not None
    assert project.user_id == auth_user.id

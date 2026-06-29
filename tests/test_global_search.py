"""Tests de la búsqueda global por API (/api/lookup) — cross-entity para la IA."""


def test_global_search_finds_project(client):
    client.post("/api/projects", json={"name": "Cartesia Voice", "tech_stack": ["FastAPI"]})
    res = client.get("/api/lookup?q=cartesia")
    assert res.status_code == 200
    data = res.json()
    labels = [r["label"] for r in data["results"]]
    assert any("Cartesia" in lbl for lbl in labels)
    project_hits = [r for r in data["results"] if r["type"] == "project"]
    assert len(project_hits) == 1
    assert project_hits[0]["slug"] == "cartesia-voice"


def test_global_search_finds_credential(client):
    client.post("/api/credentials", json={"label": "OpenAI API Key", "username": "me@x.com"})
    res = client.get("/api/lookup?q=openai")
    data = res.json()
    cred_hits = [r for r in data["results"] if r["type"] == "credential"]
    assert len(cred_hits) == 1
    assert cred_hits[0]["label"] == "OpenAI API Key"
    # Nunca expone la contraseña en resultados de búsqueda
    assert "password" not in cred_hits[0]


def test_global_search_finds_service(client):
    client.post("/api/services", json={"name": "Supabase Prod", "category": "db"})
    res = client.get("/api/lookup?q=supabase")
    data = res.json()
    svc_hits = [r for r in data["results"] if r["type"] == "service"]
    assert len(svc_hits) == 1
    assert svc_hits[0]["label"] == "Supabase Prod"


def test_global_search_cross_entity(client):
    """Un mismo término puede aparecer en varias entidades."""
    client.post("/api/projects", json={"name": "Stripe Integration"})
    client.post("/api/credentials", json={"label": "Stripe Dashboard", "username": "me@x.com"})
    client.post("/api/services", json={"name": "Stripe", "category": "deploy"})
    res = client.get("/api/lookup?q=stripe")
    data = res.json()
    types = {r["type"] for r in data["results"]}
    assert types == {"project", "credential", "service"}
    assert data["total"] == 3


def test_global_search_empty_query(client):
    res = client.get("/api/lookup?q=")
    assert res.status_code == 422  # q es requerido y no vacío


def test_global_search_no_results(client):
    res = client.get("/api/lookup?q=nadaquecoincida")
    assert res.status_code == 200
    assert res.json()["results"] == []


def test_global_search_requires_auth(unauth_client):
    res = unauth_client.get("/api/lookup?q=algo", follow_redirects=False)
    assert res.status_code in (302, 401)


def test_global_search_isolated_per_user(client, db):
    """La búsqueda solo devuelve datos del usuario autenticado."""
    from app.auth import hash_password
    from app.models import Project, User

    other = User(email="otro2@test.local", hashed_password=hash_password("password123"), is_active=True)
    db.add(other)
    db.commit()
    db.refresh(other)
    # Proyecto de OTRO usuario
    db.add(Project(user_id=other.id, name="Secreto Ajeno", slug="secreto-ajeno", status="active"))
    db.commit()

    res = client.get("/api/lookup?q=secreto")
    assert res.json()["results"] == []

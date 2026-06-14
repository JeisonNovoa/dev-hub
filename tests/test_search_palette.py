"""Tests del command palette global (/api/search) y copia de secretos."""

import pytest

from app.models import Command, Credential, Project, QuickLink


@pytest.fixture
def seeded(db, auth_user):
    """Un proyecto con link prod + comando, y una credencial, para buscar."""
    project = Project(
        user_id=auth_user.id,
        name="voice-agent",
        slug="voice-agent",
        description="Agente de voz con Cartesia",
        tech_stack=["Python", "Cartesia"],
        status="active",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    db.add_all([
        QuickLink(project_id=project.id, label="Producción", url="https://voice.fly.dev", category="prod"),
        Command(project_id=project.id, label="Iniciar", command="python -m agent.run", type="start"),
    ])
    db.add(Credential(
        user_id=auth_user.id,
        label="Cartesia",
        username="jeison@gmail.com",
        password="s3cr3t",
        url="https://cartesia.ai",
        category="personal",
        login_via="email",
    ))
    db.commit()
    return project


def test_search_requires_auth(unauth_client):
    res = unauth_client.get("/api/search?q=voice", follow_redirects=False)
    assert res.status_code == 302  # redirige a login


def test_empty_query_returns_no_groups(client):
    res = client.get("/api/search?q=")
    assert res.status_code == 200
    assert res.json() == {"groups": []}


def test_search_finds_project_and_link_and_command(client, seeded):
    res = client.get("/api/search?q=voice")
    assert res.status_code == 200
    groups = {g["label"]: g["items"] for g in res.json()["groups"]}
    assert "proyectos" in groups
    assert groups["proyectos"][0]["title"] == "voice-agent"
    assert groups["proyectos"][0]["action"] == "navigate"
    # El link de prod y el comando también matchean por nombre de proyecto.
    assert "links" in groups
    assert groups["links"][0]["action"] == "open"
    assert "comandos" in groups
    assert groups["comandos"][0]["action"] == "copy"
    assert groups["comandos"][0]["value"] == "python -m agent.run"


def test_search_finds_credential_without_password(client, seeded):
    res = client.get("/api/search?q=cartesia")
    groups = {g["label"]: g["items"] for g in res.json()["groups"]}
    assert "credenciales" in groups
    cred = groups["credenciales"][0]
    assert cred["title"] == "Cartesia"
    assert cred["action"] == "copy-secret"
    assert cred["hasPassword"] is True
    assert "password" not in cred  # nunca se filtra la contraseña en la búsqueda


def test_search_scoped_to_user(client, db, seeded):
    """Datos de otro usuario no aparecen."""
    from app.auth import hash_password
    from app.models import User

    other = User(email="other@x.com", hashed_password=hash_password("x"), is_active=True)
    db.add(other)
    db.commit()
    db.add(Project(user_id=other.id, name="secreto-ajeno", slug="secreto-ajeno", status="active"))
    db.commit()

    res = client.get("/api/search?q=secreto-ajeno")
    assert res.json() == {"groups": []}


def test_copy_secret_returns_password(client, seeded):
    # Localizar el id de la credencial sembrada.
    res = client.get("/api/search?q=cartesia")
    groups = {g["label"]: g["items"] for g in res.json()["groups"]}
    cred_id = groups["credenciales"][0]["credId"]
    secret = client.get(f"/api/search/credential/{cred_id}/secret?field=password")
    assert secret.status_code == 200
    assert secret.json() == {"ok": True, "value": "s3cr3t"}


def test_copy_secret_other_user_forbidden(client, db, seeded):
    from app.auth import hash_password
    from app.models import User

    other = User(email="o2@x.com", hashed_password=hash_password("x"), is_active=True)
    db.add(other)
    db.commit()
    cred = Credential(user_id=other.id, label="Ajena", username="a", password="p", url="https://x.com")
    db.add(cred)
    db.commit()
    db.refresh(cred)

    res = client.get(f"/api/search/credential/{cred.id}/secret")
    assert res.json()["ok"] is False

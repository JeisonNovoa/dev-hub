"""Tests del registro de actividad de proyectos (ProjectEvent / timeline)."""

import pytest

from app.models import Project, ProjectEvent
from app.utils.activity import build_summary, log_event


@pytest.fixture
def project(db, auth_user):
    p = Project(user_id=auth_user.id, name="dev-hub", slug="dev-hub", status="active")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _events(db, project_id):
    return (
        db.query(ProjectEvent)
        .filter(ProjectEvent.project_id == project_id)
        .order_by(ProjectEvent.created_at.desc())
        .all()
    )


# --- build_summary (formato del texto) ---

def test_build_summary_entities():
    assert build_summary("created", "env_var", "DATABASE_URL") == "Agregó env var DATABASE_URL"
    assert build_summary("updated", "command", "Levantar API") == "Editó comando Levantar API"
    assert build_summary("deleted", "credential", "Supabase") == "Eliminó credencial Supabase"


def test_build_summary_project_ignores_name():
    assert build_summary("created", "project", None) == "Creó el proyecto"
    assert build_summary("updated", "project", "lo-que-sea") == "Editó el proyecto"


def test_build_summary_truncates_long_name():
    summary = build_summary("created", "command", "x" * 500)
    assert len(summary) <= 255


# --- log_event (persistencia) ---

def test_log_event_persists(db, project):
    log_event(db, project.id, "created", "env_var", "SECRET_KEY")
    db.commit()
    events = _events(db, project.id)
    assert len(events) == 1
    assert events[0].summary == "Agregó env var SECRET_KEY"
    assert events[0].entity == "env_var"
    assert events[0].action == "created"


# --- integración: endpoints registran actividad ---

def test_creating_env_var_logs_event(client, project, db):
    res = client.post(
        f"/ui/projects/{project.slug}/env-vars/new",
        data={"key": "API_KEY", "value": "x", "description": ""},
    )
    assert res.status_code == 200
    events = _events(db, project.id)
    assert any(e.entity == "env_var" and "API_KEY" in e.summary for e in events)


def test_creating_command_logs_event(client, project, db):
    res = client.post(
        f"/ui/projects/{project.slug}/commands/new",
        data={"label": "Levantar", "command": "uvicorn app:app", "type": "start", "order": 0},
    )
    assert res.status_code == 200
    events = _events(db, project.id)
    assert any(e.entity == "command" and "Levantar" in e.summary for e in events)


def test_editing_project_header_logs_event(client, project, db):
    res = client.post(
        f"/ui/projects/{project.slug}/header/save",
        data={"name": "dev-hub", "description": "nueva desc", "tech_stack_raw": "FastAPI"},
    )
    assert res.status_code == 200
    events = _events(db, project.id)
    assert any(e.entity == "project" and e.action == "updated" for e in events)


def test_detail_page_renders_with_activity(client, project, db):
    log_event(db, project.id, "created", "command", "Levantar API")
    db.commit()
    res = client.get(f"/projects/{project.slug}")
    assert res.status_code == 200
    assert "actividad" in res.text
    assert "Levantar API" in res.text

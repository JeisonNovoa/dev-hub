"""Test de integración del servidor MCP contra la app real (in-process).

Verifica la cadena completa: tool MCP → httpx → ruta API → BD. El servidor MCP
vive en mcp/server.py; lo importamos y le inyectamos un cliente httpx que apunta
a la app FastAPI en proceso (ASGITransport), autenticado con un token de
extensión real.

Si el SDK de MCP no está instalado, los tests se saltan (el server core ya está
cubierto por los tests de la API; esto valida el wrapper MCP end-to-end).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("mcp") is None,
    reason="SDK de MCP no instalado",
)

_MCP_SERVER_PATH = Path(__file__).resolve().parent.parent / "mcp" / "server.py"


@pytest.fixture
def mcp_server(client, monkeypatch):
    """Importa mcp/server.py y lo cablea a la app en proceso con token real.

    `client` (fixture global) ya tiene la app con get_db override y un usuario
    autenticado; le pedimos un token de extensión y hacemos que el servidor MCP
    use un httpx.Client con ASGITransport contra esa misma app.
    """
    # Token de extensión para el usuario de prueba.
    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local", "password": "password123", "name": "mcp-test",
    })
    assert res.status_code == 200
    token = res.json()["token"]

    # Importar el módulo del servidor MCP por ruta (no está en el paquete app).
    spec = importlib.util.spec_from_file_location("devhub_mcp_server", _MCP_SERVER_PATH)
    server = importlib.util.module_from_spec(spec)
    sys.modules["devhub_mcp_server"] = server
    spec.loader.exec_module(server)

    # El servidor MCP usa un httpx.Client SÍNCRONO. ASGITransport solo soporta
    # async, así que reutilizamos el TestClient (sync, respaldado por la app con
    # el get_db override ya activo via la fixture `client`). TestClient expone la
    # misma interfaz .request() que usa el servidor MCP.
    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    def _fake_client():
        return TestClient(
            fastapi_app,
            base_url="http://testserver",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )

    monkeypatch.setattr(server, "_client", _fake_client)
    return server


def test_mcp_list_projects(mcp_server, client):
    client.post("/api/projects", json={"name": "Proyecto MCP", "tech_stack": ["FastAPI"]})
    projects = mcp_server.list_projects()
    assert any(p["slug"] == "proyecto-mcp" for p in projects)


def test_mcp_register_project_then_get_context(mcp_server):
    """Escritura + lectura vía MCP: registra un proyecto y trae su contexto."""
    created = mcp_server.register_project(
        name="Voz IA", description="App de voz", tech_stack=["FastAPI", "Cartesia"]
    )
    assert created["slug"] == "voz-ia"

    ctx = mcp_server.get_context("voz-ia")
    assert "# Voz IA" in ctx
    assert "Cartesia" in ctx


def test_mcp_add_env_var_and_command(mcp_server):
    mcp_server.register_project(name="Backend API")
    env = mcp_server.add_env_var("backend-api", key="PORT", value="8000", description="Puerto")
    assert env["key"] == "PORT"
    cmd = mcp_server.add_command("backend-api", label="Iniciar", command="uvicorn app:app", type="start")
    assert cmd["label"] == "Iniciar"

    ctx = mcp_server.get_context("backend-api")
    assert "PORT" in ctx
    assert "uvicorn app:app" in ctx


def test_mcp_search_cross_entity(mcp_server, client):
    client.post("/api/projects", json={"name": "Stripe App"})
    client.post("/api/credentials", json={"label": "Stripe Key", "username": "me@x.com"})
    results = mcp_server.search("stripe")
    types = {r["type"] for r in results}
    assert "project" in types
    assert "credential" in types


def test_mcp_recent_activity(mcp_server):
    mcp_server.register_project(name="Activo")
    mcp_server.add_command("activo", label="Build", command="make build")
    events = mcp_server.recent_activity()
    assert len(events) > 0
    assert any(e["project"] == "activo" for e in events)


def test_mcp_invalid_token_raises(client, monkeypatch):
    """Un token inválido debe producir un error legible, no un crash."""
    spec = importlib.util.spec_from_file_location("devhub_mcp_server2", _MCP_SERVER_PATH)
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)

    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    def _bad_client():
        return TestClient(
            fastapi_app,
            base_url="http://testserver",
            headers={"Authorization": "Bearer dvh_token-invalido"},
            follow_redirects=False,
        )

    monkeypatch.setattr(server, "_client", _bad_client)
    with pytest.raises(RuntimeError, match="Token inválido o expirado"):
        server.list_projects()

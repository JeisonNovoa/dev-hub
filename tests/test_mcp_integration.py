"""Test de integración del servidor MCP contra la app real (in-process).

Verifica la cadena completa: tool MCP → client.request → ruta API → BD. Las
tools viven en mcp/tools.py y usan el cliente compartido mcp/client.py; les
inyectamos un TestClient (sync) apuntando a la app FastAPI en proceso,
autenticado con un token de extensión real.

Si el SDK de MCP no está instalado, los tests se saltan (el core de la API ya
está cubierto por otros tests; esto valida el wrapper MCP end-to-end).
"""

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest


def _mcp_sdk_available() -> bool:
    """True solo si el SDK de MCP está realmente instalado.

    OJO: no basta con find_spec("mcp") — la carpeta mcp/ de este repo puede
    hacer sombra al paquete. Verificamos el submódulo real del SDK
    (mcp.server.fastmcp), que solo existe si el paquete pip está instalado.
    """
    try:
        return importlib.util.find_spec("mcp.server.fastmcp") is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


pytestmark = pytest.mark.skipif(
    not _mcp_sdk_available(),
    reason="SDK de MCP no instalado",
)

_MCP_DIR = Path(__file__).resolve().parent.parent / "mcp"


def _load_mcp_modules():
    """Importa client.py y tools.py del directorio mcp/ (no son parte del paquete app)."""
    if str(_MCP_DIR) not in sys.path:
        sys.path.insert(0, str(_MCP_DIR))
    import client  # noqa: PLC0415
    import tools  # noqa: PLC0415
    importlib.reload(client)
    importlib.reload(tools)
    return client, tools


def _collect_tools(tools_module):
    """Registra las tools en un FastMCP temporal y devuelve {nombre: función}.

    FastMCP no expone las funciones crudas, así que las capturamos con un doble
    de mcp.tool() que las guarda en un dict mientras delega en el real.
    """
    from mcp.server.fastmcp import FastMCP

    registry: dict = {}
    real_mcp = FastMCP("test")
    real_tool = real_mcp.tool

    def capturing_tool(*args, **kwargs):
        deco = real_tool(*args, **kwargs)

        def wrapper(fn):
            registry[fn.__name__] = fn
            return deco(fn)

        return wrapper

    real_mcp.tool = capturing_tool
    tools_module.register(real_mcp)
    return registry


@pytest.fixture
def mcp_tools(client, monkeypatch):
    """Devuelve el dict de tools del MCP, cableadas a la app en proceso.

    `client` (fixture global) ya tiene la app con get_db override y un usuario
    autenticado; le pedimos un token de extensión real y parcheamos client._client
    para que las tools hablen con esa misma app vía TestClient (sync).
    """
    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local", "password": "password123", "name": "mcp-test",
    })
    assert res.status_code == 200
    token = res.json()["token"]

    client_mod, tools_mod = _load_mcp_modules()

    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    def _fake_client():
        return TestClient(
            fastapi_app,
            base_url="http://testserver",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )

    monkeypatch.setattr(client_mod, "_client", _fake_client)
    return _collect_tools(tools_mod)


# ─── Lectura ──────────────────────────────────────────────────────────────────

def test_mcp_list_projects(mcp_tools, client):
    client.post("/api/projects", json={"name": "Proyecto MCP", "tech_stack": ["FastAPI"]})
    projects = mcp_tools["list_projects"]()
    assert any(p["slug"] == "proyecto-mcp" for p in projects)


def test_mcp_register_project_then_get_context(mcp_tools):
    created = mcp_tools["register_project"](
        name="Voz IA", description="App de voz", tech_stack=["FastAPI", "Cartesia"]
    )
    assert created["slug"] == "voz-ia"
    ctx = mcp_tools["get_context"]("voz-ia")
    assert "# Voz IA" in ctx
    assert "Cartesia" in ctx


def test_mcp_add_env_var_and_command(mcp_tools):
    mcp_tools["register_project"](name="Backend API")
    env = mcp_tools["add_env_var"]("backend-api", key="PORT", value="8000", description="Puerto")
    assert env["key"] == "PORT"
    cmd = mcp_tools["add_command"]("backend-api", label="Iniciar", command="uvicorn app:app", type="start")
    assert cmd["label"] == "Iniciar"
    ctx = mcp_tools["get_context"]("backend-api")
    assert "PORT" in ctx
    assert "uvicorn app:app" in ctx


def test_mcp_search_cross_entity(mcp_tools, client):
    client.post("/api/projects", json={"name": "Stripe App"})
    client.post("/api/credentials", json={"label": "Stripe Key", "username": "me@x.com"})
    results = mcp_tools["search"]("stripe")
    types = {r["type"] for r in results}
    assert "project" in types
    assert "credential" in types


def test_mcp_recent_activity(mcp_tools):
    mcp_tools["register_project"](name="Activo")
    mcp_tools["add_command"]("activo", label="Build", command="make build")
    events = mcp_tools["recent_activity"]()
    assert len(events) > 0
    assert any(e["project"] == "activo" for e in events)


# ─── Escritura nueva (update / delete) ──────────────────────────────────────────

def test_mcp_update_project(mcp_tools):
    mcp_tools["register_project"](name="Para Editar")
    updated = mcp_tools["update_project"]("para-editar", description="Nueva desc", status="paused")
    assert updated["description"] == "Nueva desc"
    assert updated["status"] == "paused"


def test_mcp_update_and_delete_command(mcp_tools):
    mcp_tools["register_project"](name="CmdProj")
    cmd = mcp_tools["add_command"]("cmdproj", label="Viejo", command="echo viejo")
    upd = mcp_tools["update_command"]("cmdproj", cmd["id"], label="Nuevo")
    assert upd["label"] == "Nuevo"
    msg = mcp_tools["delete_command"]("cmdproj", cmd["id"])
    assert "eliminado" in msg.lower()


def test_mcp_links_crud(mcp_tools):
    mcp_tools["register_project"](name="LinkProj")
    link = mcp_tools["add_link"]("linkproj", label="Repo", url="https://github.com/x/y", category="repo")
    assert link["label"] == "Repo"
    upd = mcp_tools["update_link"]("linkproj", link["id"], label="Repo principal")
    assert upd["label"] == "Repo principal"
    msg = mcp_tools["delete_link"]("linkproj", link["id"])
    assert "eliminado" in msg.lower()


def test_mcp_services_crud(mcp_tools):
    svc = mcp_tools["add_service"](name="Fly.io", category="deploy", url="https://fly.io")
    assert svc["name"] == "Fly.io"
    services = mcp_tools["list_services"]()
    assert any(s["name"] == "Fly.io" for s in services)
    upd = mcp_tools["update_service"](svc["id"], notes="Hosting de prod")
    assert upd["notes"] == "Hosting de prod"
    msg = mcp_tools["delete_service"](svc["id"])
    assert "eliminado" in msg.lower()


def test_mcp_credentials_crud(mcp_tools):
    cred = mcp_tools["add_credential"](label="OpenAI", username="me@x.com", password="secreto", category="work")
    assert cred["label"] == "OpenAI"
    creds = mcp_tools["list_credentials"](search="openai")
    assert any(c["label"] == "OpenAI" for c in creds)
    # La lista nunca trae la contraseña en claro.
    assert all("password" not in c for c in creds)
    upd = mcp_tools["update_credential"](cred["id"], notes="Cuenta de la empresa")
    assert upd["notes"] == "Cuenta de la empresa"
    msg = mcp_tools["delete_credential"](cred["id"])
    assert "papelera" in msg.lower()


def test_mcp_repos_crud(mcp_tools):
    mcp_tools["register_project"](name="MonoRepo")
    repo = mcp_tools["add_repo"]("monorepo", name="backend", github_url="https://github.com/x/be")
    assert repo["name"] == "backend"
    upd = mcp_tools["update_repo"]("monorepo", repo["slug"], description="API principal")
    assert upd["description"] == "API principal"
    msg = mcp_tools["delete_repo"]("monorepo", repo["slug"])
    assert "eliminado" in msg.lower()


# ─── Auth ───────────────────────────────────────────────────────────────────────

def test_mcp_invalid_token_raises(client, monkeypatch):
    """Un token inválido debe producir un error legible, no un crash."""
    client_mod, tools_mod = _load_mcp_modules()

    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    def _bad_client():
        return TestClient(
            fastapi_app,
            base_url="http://testserver",
            headers={"Authorization": "Bearer dvh_token-invalido"},
            follow_redirects=False,
        )

    monkeypatch.setattr(client_mod, "_client", _bad_client)
    tools_registry = _collect_tools(tools_mod)
    with pytest.raises(RuntimeError, match="Token inválido o expirado"):
        tools_registry["list_projects"]()

"""Servidor MCP para Dev Hub.

Expone la API REST de Dev Hub como herramientas MCP para que Claude Code (u otro
cliente MCP) pueda leer y escribir en el hub sin copy-paste manual.

Autenticación: usa un token de extensión Bearer (dvh_...). Se obtiene una sola
vez desde la web (Seguridad → Tokens de extensión) o vía
POST /api/extension/login, y se pasa por la variable de entorno DEVHUB_TOKEN.

Config (variables de entorno):
    DEVHUB_TOKEN     token Bearer de extensión (obligatorio)
    DEVHUB_BASE_URL  URL de la app (default: https://dev-hub-whry8q.fly.dev)

Uso: ver README.md de esta carpeta.
"""

from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

DEFAULT_BASE_URL = "https://dev-hub-whry8q.fly.dev"
_TIMEOUT = 20.0

mcp = FastMCP("dev-hub")


def _base_url() -> str:
    return os.environ.get("DEVHUB_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _token() -> str:
    token = os.environ.get("DEVHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Falta DEVHUB_TOKEN. Genera un token de extensión en la web "
            "(Seguridad → Tokens de extensión) y expórtalo como DEVHUB_TOKEN."
        )
    return token


def _client() -> httpx.Client:
    # follow_redirects=False: si el token no vale, la API redirige a /login (302).
    # Queremos ver ese 302 como fallo de auth, no seguirlo hasta la página HTML.
    return httpx.Client(
        base_url=_base_url(),
        headers={"Authorization": f"Bearer {_token()}"},
        timeout=_TIMEOUT,
        follow_redirects=False,
    )


def _request(method: str, path: str, **kwargs) -> dict | list | str:
    """Llama a la API de Dev Hub y devuelve el cuerpo (json o texto).

    Lanza un mensaje legible si la API responde con error, para que el cliente
    MCP lo muestre en vez de un traceback.
    """
    with _client() as client:
        resp = client.request(method, path, **kwargs)
    # 401 (extension endpoints) o 302→/login (resto de la API): token no válido.
    if resp.status_code == 401 or (resp.status_code in (302, 307) and "/login" in resp.headers.get("location", "")):
        raise RuntimeError("Token inválido o expirado. Genera uno nuevo en la web.")
    if resp.status_code == 404:
        raise RuntimeError(f"No encontrado: {path}")
    if resp.status_code >= 400:
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            detail = resp.text[:200]
        raise RuntimeError(f"Error {resp.status_code} en {path}: {detail}")
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        return resp.json()
    return resp.text


# ─── Tools de lectura ────────────────────────────────────────────────────────


@mcp.tool()
def list_projects(status: str | None = None, search: str | None = None) -> list[dict]:
    """Lista los proyectos del usuario. Filtra por status (active|paused|archived)
    o por texto con `search`. Devuelve nombre, slug, status y stack."""
    params = {}
    if status:
        params["status"] = status
    if search:
        params["search"] = search
    data = _request("GET", "/api/projects", params=params)
    items = data["items"] if isinstance(data, dict) else data
    return [
        {"name": p["name"], "slug": p["slug"], "status": p["status"], "tech_stack": p.get("tech_stack", [])}
        for p in items
    ]


@mcp.tool()
def get_context(slug: str) -> str:
    """Devuelve el contexto completo de un proyecto en markdown: comandos, env
    vars, links, repos, servicios y credenciales (sin contraseñas). Úsalo para
    'retomar' un proyecto. `slug` es el identificador del proyecto."""
    return _request("GET", f"/api/context/{slug}")


@mcp.tool()
def search(q: str) -> list[dict]:
    """Busca un término across proyectos, credenciales y servicios del usuario.
    Útil para '¿dónde uso la API key de X?'. Devuelve resultados tipados
    (type: project|credential|service). Nunca expone contraseñas."""
    data = _request("GET", "/api/lookup", params={"q": q})
    return data["results"] if isinstance(data, dict) else data


@mcp.tool()
def recent_activity() -> list[dict]:
    """Devuelve la actividad reciente del usuario across proyectos (qué se
    creó/editó y cuándo). Útil para proponer retomar el trabajo más reciente."""
    data = _request("GET", "/api/context/recent")
    return data["events"] if isinstance(data, dict) else data


# ─── Tools de escritura ──────────────────────────────────────────────────────


@mcp.tool()
def register_project(
    name: str,
    description: str | None = None,
    tech_stack: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """Registra un proyecto nuevo en Dev Hub. Devuelve el proyecto creado con su
    slug. Para añadirle comandos/env vars usa luego add_command / add_env_var."""
    body = {"name": name, "description": description, "tech_stack": tech_stack or [], "notes": notes}
    return _request("POST", "/api/projects", json=body)


@mcp.tool()
def add_env_var(slug: str, key: str, value: str = "", description: str | None = None) -> dict:
    """Agrega una variable de entorno a un proyecto. Deja `value` vacío para
    secretos (la idea es documentar la KEY, no guardar el secreto en claro)."""
    body = {"key": key, "value": value, "description": description}
    return _request("POST", f"/api/projects/{slug}/env-vars", json=body)


@mcp.tool()
def add_command(slug: str, label: str, command: str, type: str = "other", order: int = 0) -> dict:
    """Agrega un comando a un proyecto. `type` puede ser start|migration|build|other."""
    body = {"label": label, "command": command, "type": type, "order": order}
    return _request("POST", f"/api/projects/{slug}/commands", json=body)


if __name__ == "__main__":
    mcp.run()

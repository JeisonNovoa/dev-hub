"""Tools del MCP de Dev Hub — CRUD completo sobre la API REST.

Cada función decorada con @mcp.tool() se expone a Claude Code. Agrupadas por
entidad: proyectos, comandos, env vars, links, servicios, repos, credenciales.

Política de alcance: crear y actualizar todo; borrar lo permitido por la API
(proyectos y credenciales van a la papelera/soft-delete). NUNCA se exponen
contraseñas en claro.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from client import clean_body, request


def register(mcp: FastMCP) -> None:
    """Registra todas las tools en la instancia FastMCP dada."""

    # ─── Proyectos ───────────────────────────────────────────────────────────

    @mcp.tool()
    def list_projects(status: str | None = None, search: str | None = None) -> list[dict]:
        """Lista los proyectos del usuario. Filtra por status (active|paused|
        archived) o por texto con `search`. Devuelve nombre, slug, status y stack."""
        params = clean_body({"status": status, "search": search})
        data = request("GET", "/api/projects", params=params)
        items = data["items"] if isinstance(data, dict) else data
        return [
            {"name": p["name"], "slug": p["slug"], "status": p["status"], "tech_stack": p.get("tech_stack", [])}
            for p in items
        ]

    @mcp.tool()
    def get_context(slug: str) -> str:
        """Contexto completo de un proyecto en markdown: comandos, env vars, links,
        repos, servicios y credenciales (sin contraseñas). Úsalo para 'retomar' un
        proyecto."""
        return request("GET", f"/api/context/{slug}")

    @mcp.tool()
    def get_project(slug: str) -> dict:
        """Detalle JSON de un proyecto (env vars, comandos y links estructurados).
        Para markdown legible usa get_context."""
        return request("GET", f"/api/projects/{slug}")

    @mcp.tool()
    def register_project(
        name: str,
        description: str | None = None,
        tech_stack: list[str] | None = None,
        status: str = "active",
        notes: str | None = None,
    ) -> dict:
        """Crea un proyecto nuevo. Devuelve el proyecto con su slug. Luego usa
        add_command / add_env_var / add_link para poblarlo."""
        body = {
            "name": name,
            "description": description,
            "tech_stack": tech_stack or [],
            "status": status,
            "notes": notes,
        }
        return request("POST", "/api/projects", json=body)

    @mcp.tool()
    def update_project(
        slug: str,
        name: str | None = None,
        description: str | None = None,
        tech_stack: list[str] | None = None,
        status: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Actualiza campos de un proyecto (solo los que pases). status puede ser
        active|paused|archived. tech_stack reemplaza la lista completa."""
        body = clean_body({
            "name": name,
            "description": description,
            "tech_stack": tech_stack,
            "status": status,
            "notes": notes,
        })
        return request("PATCH", f"/api/projects/{slug}", json=body)

    @mcp.tool()
    def delete_project(slug: str) -> str:
        """Mueve un proyecto a la papelera (soft-delete, recuperable 30 días desde
        la web). No lo borra definitivamente."""
        request("DELETE", f"/api/projects/{slug}")
        return f"Proyecto '{slug}' movido a la papelera."

    # ─── Comandos ────────────────────────────────────────────────────────────

    @mcp.tool()
    def add_command(slug: str, label: str, command: str, type: str = "other", order: int = 0) -> dict:
        """Agrega un comando a un proyecto. type: start|migration|build|other."""
        body = {"label": label, "command": command, "type": type, "order": order}
        return request("POST", f"/api/projects/{slug}/commands", json=body)

    @mcp.tool()
    def update_command(
        slug: str,
        cmd_id: int,
        label: str | None = None,
        command: str | None = None,
        type: str | None = None,
        order: int | None = None,
    ) -> dict:
        """Actualiza un comando por su id (solo los campos que pases)."""
        body = clean_body({"label": label, "command": command, "type": type, "order": order})
        return request("PUT", f"/api/projects/{slug}/commands/{cmd_id}", json=body)

    @mcp.tool()
    def delete_command(slug: str, cmd_id: int) -> str:
        """Elimina un comando de un proyecto por su id."""
        request("DELETE", f"/api/projects/{slug}/commands/{cmd_id}")
        return f"Comando {cmd_id} eliminado de '{slug}'."

    # ─── Variables de entorno ────────────────────────────────────────────────

    @mcp.tool()
    def add_env_var(slug: str, key: str, value: str = "", description: str | None = None) -> dict:
        """Agrega una env var a un proyecto. Deja value vacío para secretos
        (documenta la KEY, no guardes el secreto en claro)."""
        body = {"key": key, "value": value, "description": description}
        return request("POST", f"/api/projects/{slug}/env-vars", json=body)

    @mcp.tool()
    def update_env_var(
        slug: str,
        env_id: int,
        key: str | None = None,
        value: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Actualiza una env var por su id (solo los campos que pases)."""
        body = clean_body({"key": key, "value": value, "description": description})
        return request("PUT", f"/api/projects/{slug}/env-vars/{env_id}", json=body)

    @mcp.tool()
    def delete_env_var(slug: str, env_id: int) -> str:
        """Elimina una env var de un proyecto por su id."""
        request("DELETE", f"/api/projects/{slug}/env-vars/{env_id}")
        return f"Env var {env_id} eliminada de '{slug}'."

    # ─── Links ───────────────────────────────────────────────────────────────

    @mcp.tool()
    def add_link(slug: str, label: str, url: str, category: str = "other") -> dict:
        """Agrega un link rápido a un proyecto. category: dashboard|repo|staging|
        prod|docs|monitoring|other."""
        body = {"label": label, "url": url, "category": category}
        return request("POST", f"/api/projects/{slug}/links", json=body)

    @mcp.tool()
    def update_link(
        slug: str,
        link_id: int,
        label: str | None = None,
        url: str | None = None,
        category: str | None = None,
    ) -> dict:
        """Actualiza un link por su id (solo los campos que pases)."""
        body = clean_body({"label": label, "url": url, "category": category})
        return request("PUT", f"/api/projects/{slug}/links/{link_id}", json=body)

    @mcp.tool()
    def delete_link(slug: str, link_id: int) -> str:
        """Elimina un link de un proyecto por su id."""
        request("DELETE", f"/api/projects/{slug}/links/{link_id}")
        return f"Link {link_id} eliminado de '{slug}'."

    # ─── Repos ───────────────────────────────────────────────────────────────

    @mcp.tool()
    def add_repo(
        slug: str,
        name: str,
        github_url: str | None = None,
        local_path: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Agrega un repo a un proyecto (para monorepos o proyectos multi-repo)."""
        body = clean_body({
            "name": name,
            "github_url": github_url,
            "local_path": local_path,
            "description": description,
        })
        return request("POST", f"/api/projects/{slug}/repos", json=body)

    @mcp.tool()
    def update_repo(
        slug: str,
        repo_slug: str,
        name: str | None = None,
        github_url: str | None = None,
        local_path: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Actualiza un repo por su repo_slug (solo los campos que pases)."""
        body = clean_body({
            "name": name,
            "github_url": github_url,
            "local_path": local_path,
            "description": description,
        })
        return request("PUT", f"/api/projects/{slug}/repos/{repo_slug}", json=body)

    @mcp.tool()
    def delete_repo(slug: str, repo_slug: str) -> str:
        """Elimina un repo de un proyecto por su repo_slug."""
        request("DELETE", f"/api/projects/{slug}/repos/{repo_slug}")
        return f"Repo '{repo_slug}' eliminado de '{slug}'."

    # ─── Servicios ───────────────────────────────────────────────────────────

    @mcp.tool()
    def list_services() -> list[dict]:
        """Lista los servicios externos del usuario (Supabase, Fly.io, OpenAI…)."""
        data = request("GET", "/api/services")
        return data["items"] if isinstance(data, dict) else data

    @mcp.tool()
    def add_service(
        name: str,
        category: str = "other",
        url: str | None = None,
        notes: str | None = None,
        project_id: int | None = None,
    ) -> dict:
        """Crea un servicio externo. category: ai|auth|storage|db|deploy|messaging|
        monitoring|other. Pasa project_id para asociarlo a un proyecto."""
        body = clean_body({
            "name": name,
            "category": category,
            "url": url,
            "notes": notes,
            "project_id": project_id,
        })
        return request("POST", "/api/services", json=body)

    @mcp.tool()
    def update_service(
        service_id: int,
        name: str | None = None,
        category: str | None = None,
        url: str | None = None,
        notes: str | None = None,
        project_id: int | None = None,
    ) -> dict:
        """Actualiza un servicio por su id (solo los campos que pases)."""
        body = clean_body({
            "name": name,
            "category": category,
            "url": url,
            "notes": notes,
            "project_id": project_id,
        })
        return request("PUT", f"/api/services/{service_id}", json=body)

    @mcp.tool()
    def delete_service(service_id: int) -> str:
        """Elimina un servicio por su id."""
        request("DELETE", f"/api/services/{service_id}")
        return f"Servicio {service_id} eliminado."

    # ─── Credenciales ────────────────────────────────────────────────────────

    @mcp.tool()
    def list_credentials(search: str | None = None, category: str | None = None) -> list[dict]:
        """Lista credenciales (sin contraseñas en claro). Filtra por texto o
        category (personal|work|project)."""
        params = clean_body({"search": search, "category": category})
        data = request("GET", "/api/credentials", params=params)
        items = data["items"] if isinstance(data, dict) else data
        return [
            {
                "id": c["id"],
                "label": c["label"],
                "username": c.get("username"),
                "url": c.get("url"),
                "category": c.get("category"),
            }
            for c in items
        ]

    @mcp.tool()
    def add_credential(
        label: str,
        username: str | None = None,
        password: str | None = None,
        url: str | None = None,
        category: str = "project",
        notes: str | None = None,
        project_id: int | None = None,
        service_id: int | None = None,
    ) -> dict:
        """Crea una credencial. La contraseña se cifra en reposo. category:
        personal|work|project. Asóciala con project_id o service_id."""
        body = clean_body({
            "label": label,
            "username": username,
            "password": password,
            "url": url,
            "category": category,
            "notes": notes,
            "project_id": project_id,
            "service_id": service_id,
        })
        return request("POST", "/api/credentials", json=body)

    @mcp.tool()
    def update_credential(
        cred_id: int,
        label: str | None = None,
        username: str | None = None,
        password: str | None = None,
        url: str | None = None,
        category: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Actualiza una credencial por su id (solo los campos que pases). Pasa
        password solo si quieres cambiarla."""
        body = clean_body({
            "label": label,
            "username": username,
            "password": password,
            "url": url,
            "category": category,
            "notes": notes,
        })
        return request("PUT", f"/api/credentials/{cred_id}", json=body)

    @mcp.tool()
    def delete_credential(cred_id: int) -> str:
        """Mueve una credencial a la papelera (soft-delete, recuperable desde la web)."""
        request("DELETE", f"/api/credentials/{cred_id}")
        return f"Credencial {cred_id} movida a la papelera."

    # ─── Búsqueda y actividad ────────────────────────────────────────────────

    @mcp.tool()
    def search(q: str) -> list[dict]:
        """Busca un término across proyectos, credenciales y servicios. Resultados
        tipados (type: project|credential|service). Nunca expone contraseñas."""
        data = request("GET", "/api/lookup", params={"q": q})
        return data["results"] if isinstance(data, dict) else data

    @mcp.tool()
    def recent_activity() -> list[dict]:
        """Actividad reciente across proyectos (qué se creó/editó y cuándo)."""
        data = request("GET", "/api/context/recent")
        return data["events"] if isinstance(data, dict) else data

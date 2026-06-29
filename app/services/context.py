"""Contexto de proyecto orientado a LLM.

Convierte un proyecto (con sus comandos, env vars, links, repos, servicios y
credenciales) en una representación densa y lista para pegar en un prompt de
Claude/Cursor. El objetivo es que la IA pueda "retomar" un proyecto sin que el
usuario tenga que copiar datos a mano.

SEGURIDAD: este contexto NUNCA incluye contraseñas. Las credenciales aparecen
solo como referencia (label, username, url) para que la IA sepa que existen y
con qué cuenta; el secreto se obtiene aparte por el endpoint dedicado, que
registra el acceso. Las env vars sí muestran su valor: son del propio usuario
y forman parte del contexto operativo (puertos, flags, URLs). El que quiera
ocultar un secreto en una env var ya lo guarda con value vacío.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.models import Project, User


def _load_project(db: Session, slug: str, user_id: int) -> Project | None:
    """Trae un proyecto con todas sus relaciones en una sola pasada (anti-N+1)."""
    return (
        db.query(Project)
        .options(
            selectinload(Project.commands),
            selectinload(Project.env_vars),
            selectinload(Project.links),
            selectinload(Project.repos),
            selectinload(Project.services),
            selectinload(Project.credentials),
        )
        .filter(
            Project.slug == slug,
            Project.user_id == user_id,
            Project.deleted_at.is_(None),
        )
        .first()
    )


def build_context_dict(project: Project) -> dict:
    """Representación estructurada del proyecto, sin secretos."""
    return {
        "name": project.name,
        "slug": project.slug,
        "status": project.status,
        "description": project.description,
        "tech_stack": project.tech_stack or [],
        "notes": project.notes,
        "commands": [
            {"label": c.label, "command": c.command, "type": c.type, "order": c.order}
            for c in sorted(project.commands, key=lambda c: c.order)
        ],
        "env_vars": [
            {"key": e.key, "value": e.value, "description": e.description}
            for e in project.env_vars
        ],
        "links": [
            {"label": link.label, "url": link.url, "category": link.category}
            for link in project.links
        ],
        "repos": [
            {
                "name": r.name,
                "github_url": r.github_url,
                "local_path": r.local_path,
                "description": r.description,
                "commands": [
                    {"label": c.label, "command": c.command, "type": c.type}
                    for c in sorted(r.commands, key=lambda c: c.order)
                ],
                "env_vars": [
                    {"key": e.key, "value": e.value, "description": e.description}
                    for e in r.env_vars
                ],
            }
            for r in project.repos
        ],
        "services": [
            {"name": s.name, "url": s.url, "category": s.category, "notes": s.notes}
            for s in project.services
        ],
        # Credenciales: solo referencia, jamás la contraseña.
        "credentials": [
            {"label": c.label, "username": c.username, "url": c.url, "category": c.category}
            for c in project.credentials
            if c.deleted_at is None
        ],
    }


def _render_kv_list(items: list[dict], key: str, value: str, extra: str | None = None) -> list[str]:
    lines = []
    for it in items:
        line = f"- `{it[key]}`"
        if it.get(value):
            line += f": {it[value]}"
        if extra and it.get(extra):
            line += f" — {it[extra]}"
        lines.append(line)
    return lines


def render_markdown(ctx: dict) -> str:
    """Renderiza el contexto como markdown denso para pegar en un prompt."""
    out: list[str] = [f"# {ctx['name']}"]
    meta = f"**Estado:** {ctx['status']}"
    if ctx["tech_stack"]:
        meta += f" · **Stack:** {', '.join(ctx['tech_stack'])}"
    out.append(meta)
    if ctx["description"]:
        out.append(f"\n{ctx['description']}")

    if ctx["commands"]:
        out.append("\n## Comandos")
        for c in ctx["commands"]:
            out.append(f"- **{c['label']}** (`{c['type']}`): `{c['command']}`")

    if ctx["env_vars"]:
        out.append("\n## Variables de entorno")
        out.extend(_render_kv_list(ctx["env_vars"], "key", "value", "description"))

    if ctx["links"]:
        out.append("\n## Links")
        for link in ctx["links"]:
            out.append(f"- [{link['label']}]({link['url']}) ({link['category']})")

    for repo in ctx["repos"]:
        out.append(f"\n## Repo: {repo['name']}")
        if repo["description"]:
            out.append(repo["description"])
        if repo["github_url"]:
            out.append(f"- GitHub: {repo['github_url']}")
        if repo["local_path"]:
            out.append(f"- Local: `{repo['local_path']}`")
        if repo["commands"]:
            out.append("**Comandos:**")
            for c in repo["commands"]:
                out.append(f"- **{c['label']}** (`{c['type']}`): `{c['command']}`")
        if repo["env_vars"]:
            out.append("**Env vars:**")
            out.extend(_render_kv_list(repo["env_vars"], "key", "value", "description"))

    if ctx["services"]:
        out.append("\n## Servicios externos")
        for s in ctx["services"]:
            line = f"- **{s['name']}** ({s['category']})"
            if s.get("url"):
                line += f" — {s['url']}"
            if s.get("notes"):
                line += f" · {s['notes']}"
            out.append(line)

    if ctx["credentials"]:
        out.append("\n## Credenciales (referencia, sin contraseñas)")
        for c in ctx["credentials"]:
            line = f"- **{c['label']}**"
            if c.get("username"):
                line += f" — usuario: `{c['username']}`"
            if c.get("url"):
                line += f" ({c['url']})"
            out.append(line)

    if ctx["notes"]:
        out.append("\n## Notas")
        out.append(ctx["notes"])

    return "\n".join(out)


def get_project_context(db: Session, user: User, slug: str) -> tuple[dict, str] | None:
    """Devuelve (dict_estructurado, markdown) del proyecto, o None si no existe."""
    project = _load_project(db, slug, user.id)
    if project is None:
        return None
    ctx = build_context_dict(project)
    return ctx, render_markdown(ctx)

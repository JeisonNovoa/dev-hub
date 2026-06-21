"""Búsqueda global unificada para el command palette (⌘K).

Devuelve JSON con proyectos, credenciales, links y comandos del usuario que
coincidan con la consulta, cada uno con una acción directa (abrir / copiar /
ir a) para resolver los flujos diarios sin cambiar de página. No expone
contraseñas: el palette copia secretos a través del endpoint existente que ya
registra el acceso.
"""

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import Command, Credential, Project, QuickLink, User
from app.services.search import project_search_filter
from app.utils.url import extract_domain

router = APIRouter()
logger = logging.getLogger(__name__)

# Tope por grupo: el palette muestra lo más relevante, no un volcado completo.
_PER_GROUP_LIMIT = 6


@router.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Página de búsqueda dedicada (fallback sin teclado / enlace directo)."""
    return templates.TemplateResponse("search/results.html", {"request": request, "current_user": current_user})


@router.get("/api/search")
def global_search(
    q: str = Query("", min_length=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Búsqueda unificada para el palette. Agrupa por tipo y limita por grupo."""
    query = q.strip()
    if not query:
        return {"groups": []}

    like = f"%{query}%"
    uid = current_user.id

    # --- Proyectos ---
    base = db.query(Project).filter(
        Project.user_id == uid,
        Project.deleted_at.is_(None),
    )
    base = project_search_filter(base, query)
    projects = (
        base.order_by(Project.updated_at.desc())
        .limit(_PER_GROUP_LIMIT)
        .all()
    )
    project_items = [
        {
            "type": "project",
            "title": p.name,
            "subtitle": p.description or f"{len(p.commands)} cmds · {len(p.links)} links",
            "action": "navigate",
            "href": f"/projects/{p.slug}",
        }
        for p in projects
    ]

    # --- Credenciales (sin contraseña; copiar pwd usa el endpoint con log) ---
    credentials = (
        db.query(Credential)
        .filter(
            Credential.user_id == uid,
            Credential.deleted_at.is_(None),
            Credential.label.ilike(like) | Credential.username.ilike(like) | Credential.url.ilike(like),
        )
        .order_by(Credential.label)
        .limit(_PER_GROUP_LIMIT)
        .all()
    )
    credential_items = [
        {
            "type": "credential",
            "title": c.label,
            "subtitle": c.username or (extract_domain(c.url) if c.url else ""),
            "action": "copy-secret",
            "credId": c.id,
            "href": f"/credentials/{c.id}",
            "hasPassword": bool(c.password) and c.login_via == "email",
            "loginVia": c.login_via,
        }
        for c in credentials
    ]

    # --- Links rápidos de proyectos (abrir prod/dashboard/docs…) ---
    links = (
        db.query(QuickLink)
        .join(Project, QuickLink.project_id == Project.id)
        .filter(
            Project.user_id == uid,
            Project.deleted_at.is_(None),
            QuickLink.label.ilike(like)
            | QuickLink.url.ilike(like)
            | QuickLink.category.ilike(like)
            | Project.name.ilike(like),
        )
        .order_by(QuickLink.category)
        .limit(_PER_GROUP_LIMIT)
        .all()
    )
    link_items = [
        {
            "type": "link",
            "title": f"{ln.category} · {ln.project.name}" if ln.category != "other" else ln.label,
            "subtitle": extract_domain(ln.url) or ln.url,
            "action": "open",
            "href": ln.url,
        }
        for ln in links
    ]

    # --- Comandos (copiar al portapapeles) ---
    commands = (
        db.query(Command)
        .join(Project, Command.project_id == Project.id)
        .filter(
            Project.user_id == uid,
            Project.deleted_at.is_(None),
            Command.label.ilike(like) | Command.command.ilike(like) | Project.name.ilike(like),
        )
        .order_by(Command.type)
        .limit(_PER_GROUP_LIMIT)
        .all()
    )
    command_items = [
        {
            "type": "command",
            "title": cmd.label,
            "subtitle": f"{cmd.project.name} · {cmd.command}",
            "action": "copy",
            "value": cmd.command,
        }
        for cmd in commands
    ]

    groups = []
    if project_items:
        groups.append({"label": "proyectos", "items": project_items})
    if credential_items:
        groups.append({"label": "credenciales", "items": credential_items})
    if link_items:
        groups.append({"label": "links", "items": link_items})
    if command_items:
        groups.append({"label": "comandos", "items": command_items})

    return {"groups": groups}


@router.get("/api/search/credential/{cred_id}/secret")
def credential_secret_for_palette(
    cred_id: int,
    field: str = Query("password"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Devuelve usuario o contraseña en claro para copiar desde el palette.

    Acceso registrado en logs, igual que el endpoint de la extensión.
    """
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == current_user.id, Credential.deleted_at.is_(None))
        .first()
    )
    if not cred:
        return {"ok": False, "error": "Credencial no encontrada"}
    logger.info("Secreto copiado desde palette: cred=%d user=%d field=%s", cred.id, current_user.id, field)
    value = cred.username if field == "username" else cred.password
    return {"ok": True, "value": value or ""}

"""Página de detalle del proyecto (GET /projects/{slug}).

Renderiza la vista completa con todas las secciones. Las acciones inline
(env vars, comandos, links, etc.) viven en sus propios módulos.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.jinja import templates
from app.models import Command, ProjectEvent, Service, User
from app.utils.projects import primary_link

router = APIRouter()

_CREDENTIAL_STALE_DAYS = 180


def _is_stale(moment: datetime | None) -> bool:
    if moment is None:
        return False
    aware = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - aware > timedelta(days=_CREDENTIAL_STALE_DAYS)


@router.get("/projects/{slug}", response_class=HTMLResponse)
def project_detail(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    commands_by_type: dict[str, list[Command]] = {}
    for cmd in project.commands:
        if cmd.repo_id is None:
            commands_by_type.setdefault(cmd.type, []).append(cmd)
    project_env_vars = [ev for ev in project.env_vars if ev.repo_id is None]
    global_services = (
        db.query(Service)
        .filter(Service.user_id == current_user.id, Service.project_id.is_(None))
        .order_by(Service.category, Service.name)
        .all()
    )

    start_cmds = sorted(commands_by_type.get("start", []), key=lambda c: c.order)
    start_command = start_cmds[0].command if start_cmds else None
    primary = primary_link(project)
    events = (
        db.query(ProjectEvent)
        .filter(ProjectEvent.project_id == project.id)
        .order_by(ProjectEvent.created_at.desc())
        .limit(8)
        .all()
    )
    stale_creds = [c for c in project.credentials if c.password and _is_stale(c.updated_at)]

    return templates.TemplateResponse(
        "project/detail.html",
        {
            "request": request,
            "project": project,
            "commands_by_type": commands_by_type,
            "project_env_vars": project_env_vars,
            "global_services": global_services,
            "start_command": start_command,
            "primary_link": primary,
            "events": events,
            "stale_creds": stale_creds,
            "current_user": current_user,
        },
    )

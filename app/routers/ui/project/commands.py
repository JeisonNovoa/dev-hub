"""Comandos: alta inline y edición de comandos del proyecto y de repos."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.jinja import templates
from app.models import Command, Repo, User
from app.utils.activity import log_event

router = APIRouter()


@router.get("/ui/projects/{slug}/commands/new", response_class=HTMLResponse)
def command_new_form(slug: str, request: Request, type: str = "start") -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/command_new.html",
        {"request": request, "slug": slug, "type": type},
    )


@router.post("/ui/projects/{slug}/commands/new", response_class=HTMLResponse)
def command_new_submit(
    slug: str,
    request: Request,
    label: str = Form(...),
    command: str = Form(...),
    order: int = Form(0),
    type: str = Form("start"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    cmd = Command(project_id=project.id, label=label, command=command, order=order, type=type)
    db.add(cmd)
    log_event(db, project.id, "created", "command", label)
    db.commit()
    db.refresh(cmd)
    return templates.TemplateResponse(
        "project/partials/command_row.html",
        {"request": request, "cmd": cmd, "project": project},
    )


@router.get("/ui/projects/{slug}/commands/{cmd_id}/edit", response_class=HTMLResponse)
def command_edit_form(
    slug: str, cmd_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    cmd = db.query(Command).filter(Command.id == cmd_id, Command.project_id == project.id).first()
    if not cmd:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/command_edit.html",
        {"request": request, "cmd": cmd, "project": project},
    )


@router.get("/ui/projects/{slug}/commands/{cmd_id}/view", response_class=HTMLResponse)
def command_view(
    slug: str, cmd_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    cmd = db.query(Command).filter(Command.id == cmd_id, Command.project_id == project.id).first()
    if not cmd:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/command_row.html",
        {"request": request, "cmd": cmd, "project": project},
    )


# ---- Comandos de repo ----

@router.get("/ui/projects/{slug}/repos/{repo_id}/commands/new", response_class=HTMLResponse)
def repo_command_new_form(slug: str, repo_id: int, request: Request, type: str = "start") -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/repo_command_new.html",
        {"request": request, "slug": slug, "repo_id": repo_id, "type": type},
    )


@router.post("/ui/projects/{slug}/repos/{repo_id}/commands/new", response_class=HTMLResponse)
def repo_command_new_submit(
    slug: str,
    repo_id: int,
    request: Request,
    label: str = Form(...),
    command: str = Form(...),
    order: int = Form(0),
    type: str = Form("start"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    repo = db.query(Repo).filter(Repo.id == repo_id, Repo.project_id == project.id).first()
    if not repo:
        raise HTTPException(status_code=404)
    cmd = Command(project_id=project.id, repo_id=repo.id, label=label, command=command, order=order, type=type)
    db.add(cmd)
    log_event(db, project.id, "created", "command", f"{repo.name} · {label}")
    db.commit()
    db.refresh(cmd)
    return templates.TemplateResponse(
        "project/partials/command_row.html",
        {"request": request, "cmd": cmd, "project": project},
    )

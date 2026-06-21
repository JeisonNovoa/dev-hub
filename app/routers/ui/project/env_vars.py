"""Env vars: alta inline y edición de variables de entorno del proyecto y de repos."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.jinja import templates
from app.models import EnvVariable, Repo, User
from app.utils.activity import log_event

router = APIRouter()


@router.get("/ui/projects/{slug}/env-vars/new", response_class=HTMLResponse)
def env_var_new_form(slug: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/env_var_new.html",
        {"request": request, "slug": slug},
    )


@router.post("/ui/projects/{slug}/env-vars/new", response_class=HTMLResponse)
def env_var_new_submit(
    slug: str,
    request: Request,
    key: str = Form(...),
    value: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    env_var = EnvVariable(
        project_id=project.id,
        key=key,
        value=value or None,
        description=description or None,
    )
    db.add(env_var)
    log_event(db, project.id, "created", "env_var", key)
    db.commit()
    db.refresh(env_var)
    return templates.TemplateResponse(
        "project/partials/env_var_row.html",
        {"request": request, "env_var": env_var, "project": project},
    )


@router.get("/ui/projects/{slug}/env-vars/cancel-new", response_class=HTMLResponse)
def env_var_cancel_new(slug: str) -> HTMLResponse:
    return HTMLResponse("")


@router.get("/ui/projects/{slug}/env-vars/{env_id}/edit", response_class=HTMLResponse)
def env_var_edit_form(
    slug: str, env_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    env_var = db.query(EnvVariable).filter(EnvVariable.id == env_id, EnvVariable.project_id == project.id).first()
    if not env_var:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/env_var_edit.html",
        {"request": request, "env_var": env_var, "project": project},
    )


@router.get("/ui/projects/{slug}/env-vars/{env_id}/view", response_class=HTMLResponse)
def env_var_view(
    slug: str, env_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    env_var = db.query(EnvVariable).filter(EnvVariable.id == env_id, EnvVariable.project_id == project.id).first()
    if not env_var:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/env_var_row.html",
        {"request": request, "env_var": env_var, "project": project},
    )


# ---- Env vars de repo ----

@router.get("/ui/projects/{slug}/repos/{repo_id}/env-vars/new", response_class=HTMLResponse)
def repo_env_var_new_form(slug: str, repo_id: int, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/repo_env_var_new.html",
        {"request": request, "slug": slug, "repo_id": repo_id},
    )


@router.post("/ui/projects/{slug}/repos/{repo_id}/env-vars/new", response_class=HTMLResponse)
def repo_env_var_new_submit(
    slug: str,
    repo_id: int,
    request: Request,
    key: str = Form(...),
    value: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    repo = db.query(Repo).filter(Repo.id == repo_id, Repo.project_id == project.id).first()
    if not repo:
        raise HTTPException(status_code=404)
    env_var = EnvVariable(
        project_id=project.id,
        repo_id=repo.id,
        key=key,
        value=value or None,
        description=description or None,
    )
    db.add(env_var)
    log_event(db, project.id, "created", "env_var", f"{repo.name} · {key}")
    db.commit()
    db.refresh(env_var)
    return templates.TemplateResponse(
        "project/partials/env_var_row.html",
        {"request": request, "env_var": env_var, "project": project},
    )

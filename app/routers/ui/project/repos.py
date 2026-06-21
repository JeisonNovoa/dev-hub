"""Repos del proyecto: alta inline y edición."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from slugify import slugify
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.jinja import templates
from app.models import Repo, User
from app.utils.activity import log_event

router = APIRouter()


@router.get("/ui/projects/{slug}/repos/new", response_class=HTMLResponse)
def repo_new_form(slug: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/repo_new.html",
        {"request": request, "slug": slug},
    )


@router.post("/ui/projects/{slug}/repos/new", response_class=HTMLResponse)
def repo_new_submit(
    slug: str,
    request: Request,
    name: str = Form(...),
    local_path: str = Form(""),
    github_url: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    repo_slug = slugify(name)
    repo = Repo(
        project_id=project.id,
        name=name,
        slug=repo_slug,
        local_path=local_path or None,
        github_url=github_url or None,
        description=description or None,
    )
    db.add(repo)
    log_event(db, project.id, "created", "repo", name)
    db.commit()
    db.refresh(repo)
    return templates.TemplateResponse(
        "project/partials/repo_card.html",
        {"request": request, "repo": repo, "project": project},
    )


@router.get("/ui/projects/{slug}/repos/{repo_id}/edit", response_class=HTMLResponse)
def repo_edit_form(
    slug: str, repo_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    repo = db.query(Repo).filter(Repo.id == repo_id, Repo.project_id == project.id).first()
    if not repo:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/repo_edit.html",
        {"request": request, "repo": repo, "project": project},
    )


@router.get("/ui/projects/{slug}/repos/{repo_id}/view", response_class=HTMLResponse)
def repo_view(
    slug: str, repo_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    repo = db.query(Repo).filter(Repo.id == repo_id, Repo.project_id == project.id).first()
    if not repo:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/repo_card.html",
        {"request": request, "repo": repo, "project": project},
    )

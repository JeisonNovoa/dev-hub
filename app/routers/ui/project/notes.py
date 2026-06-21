"""Notas del proyecto (markdown): edición inline."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.jinja import templates
from app.models import User

router = APIRouter()


@router.get("/ui/projects/{slug}/notes/view", response_class=HTMLResponse)
def notes_view(
    slug: str, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    return templates.TemplateResponse(
        "project/partials/notes_view.html",
        {"request": request, "project": project},
    )


@router.get("/ui/projects/{slug}/notes/edit", response_class=HTMLResponse)
def notes_edit(
    slug: str, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    return templates.TemplateResponse(
        "project/partials/notes_edit.html",
        {"request": request, "project": project},
    )


@router.post("/ui/projects/{slug}/notes/save", response_class=HTMLResponse)
def notes_save(
    slug: str,
    request: Request,
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    project.notes = notes or None
    db.commit()
    db.refresh(project)
    return templates.TemplateResponse(
        "project/partials/notes_view.html",
        {"request": request, "project": project},
    )

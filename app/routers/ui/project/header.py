"""Header del proyecto: edición inline del nombre, descripción y tech stack."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.jinja import templates
from app.models import User
from app.utils.activity import log_event

router = APIRouter()


@router.get("/ui/projects/{slug}/header/view", response_class=HTMLResponse)
def project_header_view(
    slug: str, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    return templates.TemplateResponse(
        "project/partials/project_header.html",
        {"request": request, "project": project},
    )


@router.get("/ui/projects/{slug}/header/edit", response_class=HTMLResponse)
def project_header_edit(
    slug: str, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    return templates.TemplateResponse(
        "project/partials/project_header_edit.html",
        {"request": request, "project": project},
    )


@router.post("/ui/projects/{slug}/header/save", response_class=HTMLResponse)
def project_header_save(
    slug: str,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    tech_stack_raw: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    project.name = name
    project.description = description or None
    project.tech_stack = [t.strip() for t in tech_stack_raw.split(",") if t.strip()]
    log_event(db, project.id, "updated", "project")
    db.commit()
    db.refresh(project)
    return templates.TemplateResponse(
        "project/partials/project_header.html",
        {"request": request, "project": project},
    )

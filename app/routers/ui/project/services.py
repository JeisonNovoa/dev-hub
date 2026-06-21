"""Servicios asociados al proyecto: alta inline y edición."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.jinja import templates
from app.models import Service, User
from app.utils.activity import log_event

router = APIRouter()


@router.get("/ui/projects/{slug}/services/cancel-new", response_class=HTMLResponse)
def service_cancel_new(slug: str) -> HTMLResponse:
    return HTMLResponse("")


@router.get("/ui/projects/{slug}/services/new", response_class=HTMLResponse)
def service_new_form(slug: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/service_new.html",
        {"request": request, "slug": slug},
    )


@router.post("/ui/projects/{slug}/services/new", response_class=HTMLResponse)
def service_new_submit(
    slug: str,
    request: Request,
    name: str = Form(...),
    category: str = Form("other"),
    url: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    service = Service(
        project_id=project.id,
        user_id=current_user.id,
        name=name,
        category=category,
        url=url or None,
        notes=notes or None,
    )
    db.add(service)
    log_event(db, project.id, "created", "service", name)
    db.commit()
    db.refresh(service)
    return templates.TemplateResponse(
        "project/partials/service_row.html",
        {"request": request, "service": service, "project": project},
    )


@router.get("/ui/projects/{slug}/services/{service_id}/edit", response_class=HTMLResponse)
def service_edit_form(
    slug: str, service_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    service = db.query(Service).filter(Service.id == service_id, Service.project_id == project.id).first()
    if not service:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/service_edit.html",
        {"request": request, "service": service, "project": project},
    )


@router.get("/ui/projects/{slug}/services/{service_id}/view", response_class=HTMLResponse)
def service_view(
    slug: str, service_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    service = db.query(Service).filter(Service.id == service_id, Service.project_id == project.id).first()
    if not service:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/service_row.html",
        {"request": request, "service": service, "project": project},
    )

"""Quick links: alta inline y edición."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.jinja import templates
from app.models import QuickLink, User
from app.utils.activity import log_event

router = APIRouter()


@router.get("/ui/projects/{slug}/links/new", response_class=HTMLResponse)
def link_new_form(slug: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/link_new.html",
        {"request": request, "slug": slug},
    )


@router.post("/ui/projects/{slug}/links/new", response_class=HTMLResponse)
def link_new_submit(
    slug: str,
    request: Request,
    label: str = Form(...),
    url: str = Form(...),
    category: str = Form("other"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    link = QuickLink(project_id=project.id, label=label, url=url, category=category)
    db.add(link)
    log_event(db, project.id, "created", "link", label)
    db.commit()
    db.refresh(link)
    return templates.TemplateResponse(
        "project/partials/link_row.html",
        {"request": request, "link": link, "project": project},
    )


@router.get("/ui/projects/{slug}/links/{link_id}/edit", response_class=HTMLResponse)
def link_edit_form(
    slug: str, link_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.project_id == project.id).first()
    if not link:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/link_edit.html",
        {"request": request, "link": link, "project": project},
    )


@router.get("/ui/projects/{slug}/links/{link_id}/view", response_class=HTMLResponse)
def link_view(
    slug: str, link_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.project_id == project.id).first()
    if not link:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/link_row.html",
        {"request": request, "link": link, "project": project},
    )

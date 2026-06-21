"""Listado de credenciales /credentials con filtros, higiene y conteos."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import Credential, Project, User
from app.routers.ui.credentials._shared import is_stale, query_credentials

router = APIRouter()


@router.get("/credentials", response_class=HTMLResponse)
def credentials_page(
    request: Request,
    q: str = "",
    category: str = "",
    project_id: str = "",
    sort: str = "label",
    order: str = "asc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    if sort not in ("label", "category", "created_at", "updated_at"):
        sort = "label"
    if order not in ("asc", "desc"):
        order = "asc"
    pid = int(project_id) if project_id.strip().isdigit() else None
    credentials = query_credentials(q, category, pid, current_user.id, db, sort, order)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "credentials/partials/credential_results.html",
            {"request": request, "credentials": credentials, "current_user": current_user},
        )

    # Toda la bóveda (sin filtros) para los conteos por categoría y la higiene.
    all_creds = (
        db.query(Credential)
        .filter(Credential.user_id == current_user.id, Credential.deleted_at.is_(None))
        .all()
    )
    category_counts = {
        "all": len(all_creds),
        "work": sum(1 for c in all_creds if c.category == "work"),
        "personal": sum(1 for c in all_creds if c.category == "personal"),
        "project": sum(1 for c in all_creds if c.category == "project"),
    }

    from app.services.password_hygiene import analyze

    report = analyze(all_creds)
    stale = [c for c in all_creds if c.password and is_stale(c.updated_at)]

    trash_count = (
        db.query(Credential)
        .filter(Credential.user_id == current_user.id, Credential.deleted_at.isnot(None))
        .count()
    )
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id, Project.deleted_at.is_(None))
        .order_by(Project.name)
        .all()
    )
    return templates.TemplateResponse(
        "credentials/index.html",
        {
            "request": request,
            "credentials": credentials,
            "q": q,
            "category_filter": category,
            "project_filter": project_id,
            "sort": sort,
            "order": order,
            "trash_count": trash_count,
            "projects": projects,
            "category_counts": category_counts,
            "hygiene": report,
            "stale_creds": stale,
            "current_user": current_user,
        },
    )


@router.get("/credentials/trash", response_class=HTMLResponse)
def trash_page() -> RedirectResponse:
    return RedirectResponse(url="/trash", status_code=301)

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from slugify import slugify
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import Project, User
from app.models.project import TRASH_RETENTION_DAYS

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    q: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    base_query = db.query(Project).filter(Project.user_id == current_user.id, Project.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        base_query = base_query.filter(Project.name.ilike(like) | Project.description.ilike(like))

    all_projects = base_query.all()
    status_counts = {
        "all": len(all_projects),
        "active": sum(1 for p in all_projects if p.status == "active"),
        "paused": sum(1 for p in all_projects if p.status == "paused"),
        "archived": sum(1 for p in all_projects if p.status == "archived"),
    }

    projects = [p for p in all_projects if not status or p.status == status]
    projects.sort(key=lambda p: p.name)

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "projects": projects,
            "q": q,
            "status_filter": status,
            "status_counts": status_counts,
            "current_user": current_user,
        },
    )


@router.get("/projects/trash", response_class=HTMLResponse)
def projects_trash_page() -> RedirectResponse:
    return RedirectResponse(url="/trash", status_code=301)


@router.post("/ui/projects/{slug}/trash", response_class=HTMLResponse)
def trash_project(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = (
        db.query(Project)
        .filter(Project.slug == slug, Project.user_id == current_user.id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        raise HTTPException(status_code=404)
    project.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Proyecto movido a papelera: '%s'", slug)
    # Desde el dashboard (target = card), la card desaparece sin recargar
    # Desde el detalle del proyecto, redirige al dashboard
    if request.headers.get("HX-Target") == f"proj-card-{slug}":
        return HTMLResponse("")
    return HTMLResponse("", headers={"HX-Redirect": "/"})


@router.post("/ui/projects/{slug}/restore", response_class=HTMLResponse)
def restore_project(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = (
        db.query(Project)
        .filter(Project.slug == slug, Project.user_id == current_user.id, Project.deleted_at.isnot(None))
        .first()
    )
    if not project:
        raise HTTPException(status_code=404)
    project.deleted_at = None
    db.commit()
    logger.info("Proyecto restaurado: '%s'", slug)
    return HTMLResponse("")


@router.post("/ui/projects/{slug}/permanent", response_class=HTMLResponse)
def permanent_delete_project(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = (
        db.query(Project)
        .filter(Project.slug == slug, Project.user_id == current_user.id, Project.deleted_at.isnot(None))
        .first()
    )
    if not project:
        raise HTTPException(status_code=404)
    name = project.name
    db.delete(project)
    db.commit()
    logger.info("Proyecto eliminado permanentemente: '%s'", name)
    return HTMLResponse("")


@router.get("/ui/projects/{slug}/edit-modal", response_class=HTMLResponse)
def project_edit_modal(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = (
        db.query(Project)
        .filter(Project.slug == slug, Project.user_id == current_user.id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "partials/project_edit_modal.html",
        {"request": request, "project": project},
    )


@router.post("/ui/projects/{slug}/edit-save", response_class=HTMLResponse)
def project_edit_save(
    slug: str,
    request: Request,
    name: str = Form(...),
    status: str = Form("active"),
    description: str = Form(""),
    tech_stack_raw: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    project = (
        db.query(Project)
        .filter(Project.slug == slug, Project.user_id == current_user.id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        raise HTTPException(status_code=404)
    project.name = name
    project.status = status if status in ("active", "paused", "archived") else "active"
    project.description = description or None
    project.tech_stack = [t.strip() for t in tech_stack_raw.split(",") if t.strip()]
    db.commit()
    logger.info("Proyecto editado desde dashboard: '%s'", slug)
    return Response(status_code=200, headers={"HX-Redirect": "/"})


@router.post("/ui/projects/new")
def create_project_form(
    request: Request,
    name: str = Form(...),
    status: str = Form("active"),
    description: str = Form(""),
    tech_stack_raw: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    slug = slugify(name)
    tech_stack = [t.strip() for t in tech_stack_raw.split(",") if t.strip()]
    project = Project(
        name=name,
        slug=slug,
        status=status if status in ("active", "paused", "archived") else "active",
        description=description or None,
        tech_stack=tech_stack,
        user_id=current_user.id,
    )
    db.add(project)
    db.commit()
    logger.info("Proyecto creado desde UI: '%s'", project.slug)
    if request.headers.get("HX-Request"):
        return Response(status_code=200, headers={"HX-Redirect": f"/projects/{project.slug}"})
    return RedirectResponse(url=f"/projects/{project.slug}", status_code=303)


@router.get("/ui/dashboard/cards", response_class=HTMLResponse)
def dashboard_cards(
    request: Request,
    q: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    base_query = db.query(Project).filter(Project.user_id == current_user.id, Project.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        base_query = base_query.filter(Project.name.ilike(like) | Project.description.ilike(like))

    all_projects = base_query.all()
    status_counts = {
        "all": len(all_projects),
        "active": sum(1 for p in all_projects if p.status == "active"),
        "paused": sum(1 for p in all_projects if p.status == "paused"),
        "archived": sum(1 for p in all_projects if p.status == "archived"),
    }

    projects = [p for p in all_projects if not status or p.status == status]
    projects.sort(key=lambda p: p.name)

    return templates.TemplateResponse(
        "partials/project_cards.html",
        {
            "request": request,
            "projects": projects,
            "status_counts": status_counts,
            "status_filter": status,
            "current_user": current_user,
        },
    )


def _purge_expired_projects(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=TRASH_RETENTION_DAYS)
    expired = (
        db.query(Project)
        .filter(Project.deleted_at.isnot(None), Project.deleted_at < cutoff)
        .all()
    )
    count = len(expired)
    for project in expired:
        db.delete(project)
    if count:
        db.commit()
        logger.info("Papelera: %d proyecto(s) expirado(s) eliminado(s) permanentemente", count)
    return count

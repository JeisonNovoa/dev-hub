import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from slugify import slugify
from sqlalchemy.orm import Session

from app.database import get_db
from app.jinja import templates
from app.models import Project

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, q: str = "", status: str = "", db: Session = Depends(get_db)) -> HTMLResponse:
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(Project.name.ilike(like) | Project.description.ilike(like))
    projects = query.order_by(Project.name).all()
    return templates.TemplateResponse(
        "dashboard/index.html",
        {"request": request, "projects": projects, "q": q, "status_filter": status},
    )


@router.post("/ui/projects/new")
def create_project_form(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    tech_stack_raw: str = Form(""),
    db: Session = Depends(get_db),
) -> Response:
    slug = slugify(name)
    tech_stack = [t.strip() for t in tech_stack_raw.split(",") if t.strip()]
    project = Project(
        name=name,
        slug=slug,
        description=description or None,
        tech_stack=tech_stack,
    )
    db.add(project)
    db.commit()
    logger.info("Proyecto creado desde UI: '%s'", project.slug)
    # HTMX: navegar sin reload. Fallback para peticiones normales.
    if request.headers.get("HX-Request"):
        return Response(status_code=200, headers={"HX-Redirect": f"/projects/{project.slug}"})
    return RedirectResponse(url=f"/projects/{project.slug}", status_code=303)


@router.get("/ui/dashboard/cards", response_class=HTMLResponse)
def dashboard_cards(request: Request, q: str = "", status: str = "", db: Session = Depends(get_db)) -> HTMLResponse:
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(Project.name.ilike(like) | Project.description.ilike(like))
    projects = query.order_by(Project.name).all()
    return templates.TemplateResponse(
        "partials/project_cards.html",
        {"request": request, "projects": projects},
    )

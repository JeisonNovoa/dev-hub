from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import Credential, Project, QuickLink, Service, User

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    results: dict = {"projects": [], "credentials": [], "services": [], "links": []}
    if q:
        like = f"%{q}%"
        results["projects"] = db.query(Project).filter(
            Project.user_id == current_user.id,
            Project.name.ilike(like) | Project.description.ilike(like),
        ).all()
        results["credentials"] = db.query(Credential).filter(
            Credential.user_id == current_user.id,
            Credential.label.ilike(like) | Credential.username.ilike(like),
        ).all()
        results["services"] = db.query(Service).filter(
            Service.user_id == current_user.id,
            Service.name.ilike(like),
        ).all()
        # Links pertenecen a proyectos del usuario
        user_project_ids = db.query(Project.id).filter(Project.user_id == current_user.id).scalar_subquery()
        results["links"] = db.query(QuickLink).filter(
            QuickLink.project_id.in_(user_project_ids),
            QuickLink.label.ilike(like) | QuickLink.url.ilike(like),
        ).all()

    return templates.TemplateResponse(
        "search/results.html",
        {"request": request, "q": q, "results": results, "current_user": current_user},
    )

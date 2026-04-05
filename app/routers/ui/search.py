from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.jinja import templates
from app.models import Credential, Project, QuickLink, Service

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = "", db: Session = Depends(get_db)) -> HTMLResponse:
    results: dict = {"projects": [], "credentials": [], "services": [], "links": []}
    if q:
        like = f"%{q}%"
        results["projects"] = db.query(Project).filter(
            Project.name.ilike(like) | Project.description.ilike(like)
        ).all()
        results["credentials"] = db.query(Credential).filter(
            Credential.label.ilike(like) | Credential.username.ilike(like)
        ).all()
        results["services"] = db.query(Service).filter(Service.name.ilike(like)).all()
        results["links"] = db.query(QuickLink).filter(
            QuickLink.label.ilike(like) | QuickLink.url.ilike(like)
        ).all()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "search/results.html",
            {"request": request, "q": q, "results": results},
        )
    return templates.TemplateResponse(
        "search/results.html",
        {"request": request, "q": q, "results": results},
    )

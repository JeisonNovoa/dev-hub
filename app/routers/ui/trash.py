import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import Credential, Project, User
from app.models.credential import TRASH_RETENTION_DAYS
from app.routers.ui.credentials import _purge_expired
from app.routers.ui.dashboard import _purge_expired_projects

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/trash", response_class=HTMLResponse)
def trash_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    _purge_expired_projects(db)
    _purge_expired(db)
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id, Project.deleted_at.isnot(None))
        .order_by(Project.deleted_at)
        .all()
    )
    credentials = (
        db.query(Credential)
        .filter(Credential.user_id == current_user.id, Credential.deleted_at.isnot(None))
        .order_by(Credential.deleted_at)
        .all()
    )
    return templates.TemplateResponse(
        "trash.html",
        {
            "request": request,
            "projects": projects,
            "credentials": credentials,
            "trash_days": TRASH_RETENTION_DAYS,
            "current_user": current_user,
        },
    )


@router.get("/ui/trash/count", response_class=HTMLResponse)
def trash_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    total = (
        db.query(Project)
        .filter(Project.user_id == current_user.id, Project.deleted_at.isnot(None))
        .count()
        + db.query(Credential)
        .filter(Credential.user_id == current_user.id, Credential.deleted_at.isnot(None))
        .count()
    )
    if total:
        return HTMLResponse(
            f'<span class="text-xs px-1.5 py-0.5 rounded-full bg-surface-border text-gray-400 font-mono leading-none">{total}</span>'
        )
    return HTMLResponse("")

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, read_session_cookie
from app.database import get_db
from app.models import Project, User

logger = logging.getLogger(__name__)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        user_id = read_session_cookie(token)
        if user_id is not None:
            user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
            if user:
                return user
    # Para peticiones HTMX devolvemos un header HX-Redirect en vez de 302 estándar
    if request.headers.get("HX-Request"):
        raise HTTPException(
            status_code=401,
            headers={"HX-Redirect": "/login"},
        )
    raise HTTPException(
        status_code=302,
        headers={"Location": "/login"},
    )


def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = read_session_cookie(token)
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()


def get_project_or_404(slug: str, db: Session, current_user: User) -> Project:
    project = (
        db.query(Project)
        .filter(Project.slug == slug, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        logger.warning("Proyecto no encontrado: '%s' (user_id=%s)", slug, current_user.id)
        raise HTTPException(status_code=404, detail=f"Proyecto '{slug}' no encontrado")
    return project

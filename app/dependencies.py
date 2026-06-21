import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, hash_extension_token, read_session_cookie
from app.database import get_db
from app.models import ExtensionToken, Project, User

logger = logging.getLogger(__name__)


def _as_utc(dt: datetime) -> datetime:
    """Normaliza un datetime a aware-UTC.

    SQLite descarta tzinfo pese a DateTime(timezone=True), así que algunos
    valores llegan naive. Asumimos que naive == UTC (que es como se guardan).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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


def get_user_from_extension_token(request: Request, db: Session = Depends(get_db)) -> User:
    """Autentica peticiones de la extensión vía header Authorization: Bearer <token>.

    Rechaza tokens revocados o expirados. Un token expirado no se borra: queda
    en BD para auditoría, pero deja de aceptar peticiones.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de extensión requerido")
    token = auth[len("Bearer "):].strip()
    record = (
        db.query(ExtensionToken)
        .filter(
            ExtensionToken.token_hash == hash_extension_token(token),
            ExtensionToken.revoked_at.is_(None),
        )
        .first()
    )
    if not record:
        logger.warning("Token de extensión inválido o revocado")
        raise HTTPException(status_code=401, detail="Token inválido o revocado")
    if _as_utc(record.expires_at) <= datetime.now(timezone.utc):
        logger.warning("Token de extensión expirado: id=%d user=%d", record.id, record.user_id)
        raise HTTPException(status_code=401, detail="Token expirado, vuelve a iniciar sesión")
    user = db.query(User).filter(User.id == record.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    record.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return user


def get_project_or_404(slug: str, db: Session, current_user: User) -> Project:
    project = (
        db.query(Project)
        .filter(Project.slug == slug, Project.user_id == current_user.id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        logger.warning("Proyecto no encontrado: '%s' (user_id=%s)", slug, current_user.id)
        raise HTTPException(status_code=404, detail=f"Proyecto '{slug}' no encontrado")
    return project

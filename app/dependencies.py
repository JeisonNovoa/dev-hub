import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
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


def _user_from_session_cookie(request: Request, db: Session) -> User | None:
    """Valida la cookie de sesión. Devuelve el User o None si no hay/no vale."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    session = read_session_cookie(token)
    if session is None:
        return None
    user_id, iat = session
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user and _session_still_valid(iat, user):
        return user
    return None


def _user_from_bearer_token(request: Request, db: Session) -> User | None:
    """Valida el header Authorization: Bearer <token> de extensión.

    Devuelve el User si el token existe, no está revocado ni expirado y el
    usuario está activo; None en cualquier otro caso. No lanza: los callers
    deciden qué hacer ante un fallo. Registra last_used_at en cada uso válido.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
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
        return None
    if _as_utc(record.expires_at) <= datetime.now(timezone.utc):
        return None
    user = db.query(User).filter(User.id == record.user_id, User.is_active.is_(True)).first()
    if not user:
        return None
    record.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Autentica vía cookie de sesión o, como fallback, token Bearer de extensión.

    El doble mecanismo permite que tanto el navegador (cookie) como Claude Code /
    el servidor MCP (token Bearer) usen toda la API /api/* con la misma dependencia.
    """
    user = _user_from_session_cookie(request, db)
    if user is not None:
        return user
    user = _user_from_bearer_token(request, db)
    if user is not None:
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
    session = read_session_cookie(token)
    if session is None:
        return None
    user_id, iat = session
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user or not _session_still_valid(iat, user):
        return None
    return user


def _session_still_valid(iat: int, user: User) -> bool:
    """True si la cookie fue emitida DESPUÉS del último cambio de contraseña."""
    if iat <= 0:
        # Cookie legacy sin iat: la aceptamos pero marcamos como inválida en
        # el siguiente cambio de contraseña. Mientras tanto, pasa.
        return True
    changed_at = _as_utc(user.password_changed_at)
    # Convertimos password_changed_at a epoch segundos para comparar con iat.
    return iat >= int(changed_at.timestamp())


def get_user_from_extension_token(request: Request, db: Session = Depends(get_db)) -> User:
    """Exige un token Bearer de extensión válido (endpoints /api/extension/*).

    A diferencia de get_current_user, NO acepta cookie de sesión: la extensión
    solo tiene el token. Lanza 401 si falta o no vale.
    """
    if not request.headers.get("Authorization", "").startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de extensión requerido")
    user = _user_from_bearer_token(request, db)
    if user is None:
        logger.warning("Token de extensión inválido, revocado o expirado")
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return user


def get_project_or_404(slug: str, db: Session, current_user: User) -> Project:
    # selectinload para evitar N+1: el detalle del proyecto accede a
    # commands, env_vars, links, credentials, repos, services. Sin esto
    # cada acceso dispara un round-trip a la BD (en Supabase con latencia
    # de red se nota especialmente).
    from sqlalchemy.orm import selectinload

    project = (
        db.query(Project)
        .options(
            selectinload(Project.commands),
            selectinload(Project.env_vars),
            selectinload(Project.links),
            selectinload(Project.credentials),
            selectinload(Project.repos),
            selectinload(Project.services),
        )
        .filter(Project.slug == slug, Project.user_id == current_user.id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        logger.warning("Proyecto no encontrado: '%s' (user_id=%s)", slug, current_user.id)
        raise HTTPException(status_code=404, detail=f"Proyecto '{slug}' no encontrado")
    return project

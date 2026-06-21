"""Helpers compartidos entre los routers UI de credenciales."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Credential

# Una credencial se considera "sin rotar" si no se ha tocado en este lapso.
_CREDENTIAL_STALE_DAYS = 180

_SORT_COLS = {
    "label": Credential.label,
    "category": Credential.category,
    "created_at": Credential.created_at,
    "updated_at": Credential.updated_at,
}


def is_stale(moment: datetime | None) -> bool:
    if moment is None:
        return False
    aware = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - aware > timedelta(days=_CREDENTIAL_STALE_DAYS)


def get_active_credential_or_404(cred_id: int, user_id: int, db: Session) -> Credential:
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == user_id, Credential.deleted_at.is_(None))
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404)
    return cred


def apply_credential_form(
    cred: Credential,
    label: str,
    username: str,
    password: str,
    url: str,
    category: str,
    login_via: str,
    notes: str,
    project_id: str,
) -> None:
    cred.label = label
    cred.username = username or None
    cred.password = password or None
    cred.url = url or None
    cred.category = category
    cred.login_via = login_via
    cred.notes = notes or None
    cred.project_id = int(project_id) if project_id.strip() else None


def query_credentials(
    q: str, category: str, project_id: int | None, user_id: int, db: Session, sort: str = "label", order: str = "asc"
) -> list[Credential]:
    query = db.query(Credential).filter(Credential.user_id == user_id, Credential.deleted_at.is_(None))
    if category:
        query = query.filter(Credential.category == category)
    if project_id is not None:
        query = query.filter(Credential.project_id == project_id)
    if q:
        like = f"%{q}%"
        query = query.filter(Credential.label.ilike(like) | Credential.username.ilike(like))
    col = _SORT_COLS.get(sort, Credential.label)
    query = query.order_by(col.desc() if order == "desc" else col.asc())
    return query.all()


def detail_card_context(cred: Credential, request, db: Session, user) -> dict:
    """Contexto del detalle: credencial + análisis de seguridad + señal de rotación."""
    from app.services.password_hygiene import analyze_credential

    all_creds = (
        db.query(Credential)
        .filter(Credential.user_id == user.id, Credential.deleted_at.is_(None))
        .all()
    )
    return {
        "request": request,
        "cred": cred,
        "security": analyze_credential(cred, all_creds),
        "stale": is_stale(cred.updated_at),
        "current_user": user,
    }

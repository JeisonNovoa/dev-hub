import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import Credential, User
from app.models.credential import TRASH_RETENTION_DAYS

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/credentials", response_class=HTMLResponse)
def credentials_page(
    request: Request,
    q: str = "",
    category: str = "work",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    credentials = _query_credentials(q, category, current_user.id, db)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "credentials/partials/credential_rows.html",
            {"request": request, "credentials": credentials, "current_user": current_user},
        )
    trash_count = (
        db.query(Credential)
        .filter(Credential.user_id == current_user.id, Credential.deleted_at.isnot(None))
        .count()
    )
    return templates.TemplateResponse(
        "credentials/index.html",
        {
            "request": request,
            "credentials": credentials,
            "q": q,
            "category_filter": category,
            "trash_count": trash_count,
            "current_user": current_user,
        },
    )


@router.get("/credentials/trash", response_class=HTMLResponse)
def trash_page() -> RedirectResponse:
    return RedirectResponse(url="/trash", status_code=301)


@router.post("/ui/credentials/{cred_id}/trash", response_class=HTMLResponse)
def trash_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == current_user.id, Credential.deleted_at.is_(None))
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404)
    cred.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Credencial movida a papelera: '%s' (id=%d)", cred.label, cred_id)
    return HTMLResponse("")


@router.post("/ui/credentials/{cred_id}/restore", response_class=HTMLResponse)
def restore_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == current_user.id, Credential.deleted_at.isnot(None))
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404)
    cred.deleted_at = None
    db.commit()
    logger.info("Credencial restaurada: '%s' (id=%d)", cred.label, cred_id)
    return HTMLResponse("")


@router.post("/ui/credentials/{cred_id}/permanent", response_class=HTMLResponse)
def permanent_delete_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == current_user.id, Credential.deleted_at.isnot(None))
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404)
    label = cred.label
    db.delete(cred)
    db.commit()
    logger.info("Credencial eliminada permanentemente: '%s' (id=%d)", label, cred_id)
    return HTMLResponse("")


@router.post("/ui/credentials/new", response_class=RedirectResponse, status_code=303)
def create_credential_form(
    label: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    url: str = Form(""),
    category: str = Form("work"),
    login_via: str = Form("email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    cred = Credential(
        label=label,
        username=username or None,
        password=password or None,
        url=url or None,
        category=category,
        login_via=login_via,
        user_id=current_user.id,
    )
    db.add(cred)
    db.commit()
    return RedirectResponse(url="/credentials", status_code=303)


@router.get("/ui/credentials/{cred_id}/edit", response_class=HTMLResponse)
def credential_edit_form(
    cred_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == current_user.id, Credential.deleted_at.is_(None))
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "credentials/partials/credential_edit_row.html",
        {"request": request, "cred": cred, "current_user": current_user},
    )


@router.get("/ui/credentials/{cred_id}/view", response_class=HTMLResponse)
def credential_view(
    cred_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == current_user.id, Credential.deleted_at.is_(None))
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "credentials/partials/credential_row.html",
        {"request": request, "cred": cred, "current_user": current_user},
    )


@router.post("/ui/credentials/{cred_id}/save", response_class=HTMLResponse)
def credential_save(
    cred_id: int,
    request: Request,
    label: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    url: str = Form(""),
    category: str = Form("work"),
    login_via: str = Form("email"),
    notes: str = Form(""),
    project_id: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == current_user.id, Credential.deleted_at.is_(None))
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404)
    cred.label = label
    cred.username = username or None
    cred.password = password or None
    cred.url = url or None
    cred.category = category
    cred.login_via = login_via
    cred.notes = notes or None
    cred.project_id = int(project_id) if project_id.strip() else None
    db.commit()
    db.refresh(cred)
    return templates.TemplateResponse(
        "credentials/partials/credential_row.html",
        {"request": request, "cred": cred, "current_user": current_user},
    )


def _query_credentials(q: str, category: str, user_id: int, db: Session) -> list[Credential]:
    query = db.query(Credential).filter(Credential.user_id == user_id, Credential.deleted_at.is_(None))
    if category:
        query = query.filter(Credential.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(Credential.label.ilike(like) | Credential.username.ilike(like))
    return query.order_by(Credential.label).all()


def _purge_expired(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=TRASH_RETENTION_DAYS)
    expired = (
        db.query(Credential)
        .filter(Credential.deleted_at.isnot(None), Credential.deleted_at < cutoff)
    )
    count = expired.count()
    if count:
        expired.delete(synchronize_session=False)
        db.commit()
        logger.info("Papelera: %d credencial(es) expirada(s) eliminada(s) permanentemente", count)
    return count

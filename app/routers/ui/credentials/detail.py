"""Detalle de credenciales: página, panel de seguridad, edición inline, lifecycle."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import Credential, User
from app.routers.ui.credentials._shared import (
    apply_credential_form,
    detail_card_context,
    get_active_credential_or_404,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/credentials/{cred_id}", response_class=HTMLResponse)
def credential_detail_page(
    cred_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = get_active_credential_or_404(cred_id, current_user.id, db)
    return templates.TemplateResponse(
        "credentials/detail.html",
        detail_card_context(cred, request, db, current_user),
    )


@router.get("/ui/credentials/{cred_id}/detail-card", response_class=HTMLResponse)
def credential_detail_card(
    cred_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = get_active_credential_or_404(cred_id, current_user.id, db)
    return templates.TemplateResponse(
        "credentials/partials/detail_card.html",
        detail_card_context(cred, request, db, current_user),
    )


@router.get("/ui/credentials/{cred_id}/detail-edit", response_class=HTMLResponse)
def credential_detail_edit(
    cred_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = get_active_credential_or_404(cred_id, current_user.id, db)
    return templates.TemplateResponse(
        "credentials/partials/detail_edit.html",
        {"request": request, "cred": cred, "current_user": current_user},
    )


@router.post("/ui/credentials/{cred_id}/detail-save", response_class=HTMLResponse)
def credential_detail_save(
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
    cred = get_active_credential_or_404(cred_id, current_user.id, db)
    apply_credential_form(cred, label, username, password, url, category, login_via, notes, project_id)
    db.commit()
    db.refresh(cred)
    return templates.TemplateResponse(
        "credentials/partials/detail_card.html",
        detail_card_context(cred, request, db, current_user),
    )


@router.post("/ui/credentials/{cred_id}/trash", response_class=HTMLResponse)
def trash_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = get_active_credential_or_404(cred_id, current_user.id, db)
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

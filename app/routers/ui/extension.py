"""Página de gestión de la extensión del navegador (tokens activos, revocación)."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import ExtensionToken, User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/extension", response_class=HTMLResponse)
def extension_settings_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    tokens = (
        db.query(ExtensionToken)
        .filter(ExtensionToken.user_id == current_user.id, ExtensionToken.revoked_at.is_(None))
        .order_by(ExtensionToken.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "extension/settings.html",
        {"request": request, "tokens": tokens, "current_user": current_user},
    )


@router.post("/ui/extension/tokens/{token_id}/revoke", response_class=HTMLResponse)
def revoke_token_ui(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    record = (
        db.query(ExtensionToken)
        .filter(
            ExtensionToken.id == token_id,
            ExtensionToken.user_id == current_user.id,
            ExtensionToken.revoked_at.is_(None),
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404)
    record.revoked_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Token de extensión revocado desde la web: id=%d user=%d", token_id, current_user.id)
    return HTMLResponse("")

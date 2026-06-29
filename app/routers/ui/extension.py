"""Página de gestión de la extensión del navegador (tokens activos, revocación)."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import ExtensionToken, User
from app.services import extension_tokens as ext_token_service

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_TOKEN_NAME_LEN = 100


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


@router.post("/ui/extension/tokens/generate", response_class=HTMLResponse)
def generate_token_ui(
    request: Request,
    name: str = Form("Claude Code"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Genera un token de extensión desde la web (para Claude Code / MCP).

    El usuario ya está autenticado por sesión, así que no se le re-pide
    contraseña ni 2FA: igual que GitHub al crear un Personal Access Token.
    Devuelve un fragmento HTML que muestra el token UNA sola vez para copiarlo.
    """
    clean_name = (name or "Claude Code").strip()[:_MAX_TOKEN_NAME_LEN] or "Claude Code"
    token, expires_at = ext_token_service.create_token(db, current_user, clean_name)
    db.commit()
    logger.info("Token generado desde la web: user_id=%s (%s)", current_user.id, clean_name)
    return templates.TemplateResponse(
        "extension/partials/token_generated.html",
        {
            "request": request,
            "token": token,
            "name": clean_name,
            "expires_at": expires_at,
            "current_user": current_user,
        },
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

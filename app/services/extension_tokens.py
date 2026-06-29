"""Creación de tokens de extensión, compartida entre el login de la extensión
y la generación desde la web (para Claude Code / MCP).

Centraliza la política de tokens (TTL, límite FIFO, hashing) para que ambos
puntos de entrada se comporten igual y no haya lógica duplicada.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth import generate_extension_token, hash_extension_token
from app.models import ExtensionToken, User
from app.models.extension_token import DEFAULT_TOKEN_TTL_DAYS, MAX_ACTIVE_TOKENS

logger = logging.getLogger(__name__)


def create_token(db: Session, user: User, name: str) -> tuple[str, datetime]:
    """Crea un token de extensión para el usuario y devuelve (token_claro, expires_at).

    El token en claro se devuelve UNA sola vez; en BD queda solo su hash. Si el
    usuario ya tiene MAX_ACTIVE_TOKENS activos, revoca el más viejo (FIFO) antes
    de crear el nuevo. NO hace commit: lo decide el caller.
    """
    token = generate_extension_token()
    active = (
        db.query(ExtensionToken)
        .filter(
            ExtensionToken.user_id == user.id,
            ExtensionToken.revoked_at.is_(None),
            ExtensionToken.expires_at > datetime.now(timezone.utc),
        )
        .order_by(ExtensionToken.created_at.asc())
        .all()
    )
    if len(active) >= MAX_ACTIVE_TOKENS:
        for old in active[: len(active) - MAX_ACTIVE_TOKENS + 1]:
            old.revoked_at = datetime.now(timezone.utc)
            logger.info("Token viejo revocado por FIFO user_id=%s id=%d", user.id, old.id)

    expires_at = datetime.now(timezone.utc) + timedelta(days=DEFAULT_TOKEN_TTL_DAYS)
    db.add(
        ExtensionToken(
            user_id=user.id,
            token_hash=hash_extension_token(token),
            name=name,
            expires_at=expires_at,
        )
    )
    logger.info("Token de extensión creado para user_id=%s (%s)", user.id, name)
    return token, expires_at

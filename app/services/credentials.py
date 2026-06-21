"""Servicio de credenciales — lógica compartida entre la API REST
(/api/credentials) y la API de la extensión (/api/extension/credentials).

Antes el CRUD vivía duplicado en routers/api/credentials.py y
routers/api/extension.py con pequeñas diferencias (normalización de URL,
manejo de valores vacíos). Aquí unificamos la lógica para que ambos
entry points se comporten igual.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Credential, User

logger = logging.getLogger(__name__)


def normalize_url(url: str | None) -> str | None:
    """Asegura que una URL tenga esquema http(s). None/vacío → None."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def get_owned_or_404(db: Session, cred_id: int, user_id: int) -> Credential:
    """Devuelve la credencial si existe, pertenece al usuario y no está borrada."""
    cred = (
        db.query(Credential)
        .filter(
            Credential.id == cred_id,
            Credential.user_id == user_id,
            Credential.deleted_at.is_(None),
        )
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    return cred


def create(
    db: Session,
    user: User,
    *,
    label: str,
    username: str | None = None,
    password: str | None = None,
    url: str | None = None,
    category: str = "personal",
    login_via: str = "email",
    notes: str | None = None,
    service_id: int | None = None,
    project_id: int | None = None,
) -> Credential:
    """Crea una credencial normalizando URL y limpiando vacíos.

    Los valores "" se tratan como None para no persistir strings vacíos.
    """
    cred = Credential(
        user_id=user.id,
        label=label,
        username=username or None,
        password=password or None,
        url=normalize_url(url),
        category=category or "personal",
        login_via=login_via or "email",
        notes=notes or None,
        service_id=service_id,
        project_id=project_id,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    logger.info("Credencial creada: '%s' (id=%d, user=%d)", cred.label, cred.id, user.id)
    return cred


def update(db: Session, cred: Credential, fields: dict[str, Any]) -> Credential:
    """Actualiza los campos dados en la credencial.

    Normaliza URL si está presente. Vacía strings → None. No commitea (caller
    decide cuándo).
    """
    if "url" in fields:
        fields["url"] = normalize_url(fields["url"]) if fields["url"] else None
    for field, value in fields.items():
        if isinstance(value, str) and value == "":
            value = None
        setattr(cred, field, value)
    db.commit()
    db.refresh(cred)
    logger.info("Credencial actualizada: id=%d", cred.id)
    return cred


def soft_delete(db: Session, cred: Credential) -> None:
    """Marca la credencial como borrada (deleted_at = ahora)."""
    cred.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Credencial movida a papelera: '%s' (id=%d)", cred.label, cred.id)


def mark_used(db: Session, cred: Credential) -> None:
    """Registra el acceso al secreto (autofill, copiar, ver). Alimenta el
    orden por uso reciente de la bóveda."""
    cred.last_used_at = datetime.now(timezone.utc)
    db.commit()

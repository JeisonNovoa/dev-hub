"""API para la extensión del navegador (autofill de credenciales).

Autenticación por token Bearer (ver get_user_from_extension_token). El token se
obtiene una única vez vía /login con email+contraseña y es revocable desde la web.
El único endpoint que expone contraseñas en claro es /credentials/{id}/secret.
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.auth import generate_extension_token, hash_extension_token, verify_password, verify_totp_for_user
from app.database import get_db
from app.dependencies import _as_utc, get_current_user, get_user_from_extension_token
from app.limiter import limiter
from app.models import Credential, ExtensionToken, User
from app.models.extension_token import DEFAULT_TOKEN_TTL_DAYS, MAX_ACTIVE_TOKENS
from app.utils.url import domains_match, extract_domain

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Rate-limit por email (contra IP compartida en Render) ---
#
# slowapi usa get_remote_address, que en Render siempre ve la IP del proxy. Un
# atacante que prueba contraseñas no se topa con el bucket de IP. Añadimos un
# contador en memoria por email con ventana de 1 minuto. Suficiente para app
# personal; si escala, migrar a Redis.
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_LOGIN_WINDOW = 60  # segundos
_LOGIN_MAX_ATTEMPTS = 10


def _check_email_rate_limit(email: str) -> None:
    now = time.monotonic()
    key = email.lower().strip()
    attempts = _LOGIN_ATTEMPTS[key]
    # Poda entradas viejas.
    _LOGIN_ATTEMPTS[key] = [t for t in attempts if now - t < _LOGIN_WINDOW]
    _LOGIN_ATTEMPTS[key].append(now)
    if len(_LOGIN_ATTEMPTS[key]) > _LOGIN_MAX_ATTEMPTS:
        logger.warning("Rate limit por email excedido: %s", key)
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos para esta cuenta. Intenta en un minuto.",
        )


# --- Schemas ---

class ExtensionLogin(BaseModel):
    email: str
    password: str
    name: str = Field(default="Extensión", max_length=100)
    totp_code: str | None = None
    recovery_code: str | None = None


_VALID_LOGIN_VIA = {"email", "google", "github", "microsoft", "other"}


class ExtensionCredentialCreate(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    username: str | None = None
    password: str | None = None
    url: str
    category: str = "personal"
    login_via: str = "email"
    notes: str | None = None

    @field_validator("login_via", mode="before")
    @classmethod
    def normalize_login_via(cls, v: object) -> str:
        return v if v in _VALID_LOGIN_VIA else "email"


class ExtensionCredentialUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    username: str | None = None
    password: str | None = None
    url: str | None = None
    category: str | None = None
    login_via: str | None = None
    notes: str | None = None

    @field_validator("login_via", mode="before")
    @classmethod
    def normalize_login_via(cls, v: object) -> str | None:
        if v is None:
            return None
        return v if v in _VALID_LOGIN_VIA else "email"


# --- Auth de la extensión ---

@router.post("/login")
@limiter.limit("10/minute")
def extension_login(
    request: Request,
    data: ExtensionLogin,
    db: Session = Depends(get_db),
) -> dict:
    """Login desde la extensión: valida email+contraseña y entrega un token nuevo.

    El token en claro se devuelve UNA sola vez; en BD queda solo su hash.
    """
    _check_email_rate_limit(data.email)

    user = db.query(User).filter(User.email == data.email.lower().strip()).first()
    if not user or not user.is_active or not verify_password(data.password, user.hashed_password):
        logger.warning("Login de extensión fallido para email: %s", data.email)
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    # Con 2FA activo, la extensión también exige el código (si no, sería un bypass).
    if user.totp_enabled:
        from app.services.recovery_codes import use_recovery_code
        used_recovery = False
        if data.recovery_code and data.recovery_code.strip():
            used_recovery = use_recovery_code(db, user, data.recovery_code)
            if not used_recovery:
                raise HTTPException(status_code=401, detail="Código de recuperación inválido o ya usado")
        elif not data.totp_code:
            raise HTTPException(status_code=401, detail="Se requiere el código 2FA")
        elif not verify_totp_for_user(user, data.totp_code):
            logger.warning("Código 2FA incorrecto en login de extensión: user_id=%s", user.id)
            raise HTTPException(status_code=401, detail="Código 2FA incorrecto")
        # Si usó recovery, ya quedó persistido por use_recovery_code.

    token = generate_extension_token()
    # Limite de tokens activos: si el usuario ya tiene MAX_ACTIVE_TOKENS,
    # revocamos el más viejo (FIFO) antes de crear el nuevo.
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
            name=data.name,
            expires_at=expires_at,
        )
    )
    db.commit()
    logger.info("Token de extensión creado para user_id=%s (%s)", user.id, data.name)
    return {"token": token, "email": user.email, "expires_at": expires_at.isoformat()}


@router.get("/ping")
def extension_ping(current_user: User = Depends(get_user_from_extension_token)) -> dict:
    return {"ok": True, "email": current_user.email}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def extension_logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_extension_token),
) -> None:
    """Revoca el token con el que se hizo esta misma petición."""
    token = request.headers.get("Authorization", "")[len("Bearer "):].strip()
    record = (
        db.query(ExtensionToken)
        .filter(ExtensionToken.token_hash == hash_extension_token(token))
        .first()
    )
    if record:
        record.revoked_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Token de extensión revocado (logout) user_id=%s", current_user.id)


# --- Credenciales para autofill ---

@router.get("/credentials")
def list_vault(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_extension_token),
) -> dict:
    """Toda la bóveda para poblar el popup. Sin contraseñas (se piden por /secret).

    Ordenada por uso reciente: lo que más usas sale arriba; lo nunca usado, al
    final por nombre.
    """
    creds = (
        db.query(Credential)
        .filter(Credential.user_id == current_user.id, Credential.deleted_at.is_(None))
        .order_by(Credential.last_used_at.desc().nulls_last(), Credential.label)
        .all()
    )
    return {
        "items": [
            {
                "id": c.id,
                "label": c.label,
                "username": c.username,
                "url": c.url,
                "domain": extract_domain(c.url),
                "category": c.category,
                "login_via": c.login_via,
                "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
                # El popup lo necesita para no borrar las notas al editar.
                "notes": c.notes,
            }
            for c in creds
        ]
    }


@router.get("/credentials/match")
def match_credentials(
    domain: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_extension_token),
) -> dict:
    """Credenciales cuyo dominio coincide EXACTAMENTE con el de la página.

    No incluye contraseñas — solo lo necesario para listar opciones de autofill.
    """
    candidates = (
        db.query(Credential)
        .filter(
            Credential.user_id == current_user.id,
            Credential.deleted_at.is_(None),
            Credential.url.isnot(None),
        )
        # La cuenta que más usas en el dominio sale primera en el dropdown.
        .order_by(Credential.last_used_at.desc().nulls_last(), Credential.label)
        .all()
    )
    items = [
        {"id": c.id, "label": c.label, "username": c.username, "login_via": c.login_via}
        for c in candidates
        if domains_match(c.url, domain)
    ]
    return {"items": items, "domain": extract_domain(domain)}


@router.get("/credentials/{cred_id}/secret")
def credential_secret(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_extension_token),
) -> dict:
    """Devuelve usuario y contraseña en claro para rellenar. Acceso registrado en logs."""
    cred = (
        db.query(Credential)
        .filter(
            Credential.id == cred_id,
            Credential.user_id == current_user.id,
            Credential.deleted_at.is_(None),
        )
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    # Acceder al secreto = uso real (autofill, copiar o ver la contraseña):
    # alimenta el orden por uso reciente de la bóveda y el dropdown.
    cred.last_used_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Secreto de credencial accedido vía extensión: id=%d user=%d", cred.id, current_user.id)
    return {"id": cred.id, "username": cred.username, "password": cred.password}


@router.post("/credentials", status_code=status.HTTP_201_CREATED)
def create_credential_from_extension(
    data: ExtensionCredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_extension_token),
) -> dict:
    """Guarda una credencial detectada por la extensión (flujo '¿Guardar en DevHub?')."""
    url = data.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    cred = Credential(
        user_id=current_user.id,
        label=data.label,
        username=data.username or None,
        password=data.password or None,
        url=url,
        category=data.category or "personal",
        login_via=data.login_via,
        notes=data.notes or None,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    logger.info("Credencial creada vía extensión: '%s' (id=%d)", cred.label, cred.id)
    return {"id": cred.id, "label": cred.label}


def _get_owned_credential(cred_id: int, user_id: int, db: Session) -> Credential:
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == user_id, Credential.deleted_at.is_(None))
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    return cred


@router.patch("/credentials/{cred_id}")
def update_credential_from_extension(
    cred_id: int,
    data: ExtensionCredentialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_extension_token),
) -> dict:
    cred = _get_owned_credential(cred_id, current_user.id, db)
    fields = data.model_dump(exclude_unset=True)
    if "url" in fields and fields["url"]:
        url = fields["url"].strip()
        fields["url"] = url if url.startswith(("http://", "https://")) else "https://" + url
    for field, value in fields.items():
        setattr(cred, field, value if value != "" else None)
    db.commit()
    db.refresh(cred)
    logger.info("Credencial editada vía extensión: id=%d user=%d", cred.id, current_user.id)
    return {"id": cred.id, "label": cred.label}


@router.delete("/credentials/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential_from_extension(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_extension_token),
) -> None:
    from datetime import datetime, timezone
    cred = _get_owned_credential(cred_id, current_user.id, db)
    cred.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Credencial movida a papelera vía extensión: id=%d user=%d", cred.id, current_user.id)


# --- Gestión de tokens desde la web (cookie de sesión, no token) ---

@router.get("/tokens")
def list_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    now = datetime.now(timezone.utc)
    tokens = (
        db.query(ExtensionToken)
        .filter(ExtensionToken.user_id == current_user.id, ExtensionToken.revoked_at.is_(None))
        .order_by(ExtensionToken.created_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "created_at": t.created_at,
                "last_used_at": t.last_used_at,
                "expires_at": t.expires_at,
                "expired": _as_utc(t.expires_at) <= now,
            }
            for t in tokens
        ]
    }


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
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
        raise HTTPException(status_code=404, detail="Token no encontrado")
    record.revoked_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Token de extensión revocado desde la web: id=%d user=%d", token_id, current_user.id)

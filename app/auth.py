import hashlib
import secrets
import time
from functools import lru_cache
from typing import Any

import pyotp
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.config import settings

COOKIE_NAME = "session"
_SESSION_SALT = "session"
_TOTP_PENDING_SALT = "2fa-pending"
_TOTP_PENDING_MAX_AGE = 300  # 5 minutos para completar el segundo paso del login
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


@lru_cache(maxsize=1)
def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=_SESSION_SALT)


def create_session_cookie(user_id: int) -> str:
    """Cookie con payload {uid, iat}.

    iat = issued-at (epoch segundos). Si el usuario cambia su contraseña o
    activa 2FA, password_changed_at se actualiza y cualquier cookie con
    iat anterior queda inválida al comparar.
    """
    payload = {"uid": user_id, "iat": int(time.time())}
    return _serializer().dumps(payload)


def read_session_cookie(token: str, max_age: int = 86400 * 30) -> tuple[int, int] | None:
    """Devuelve (user_id, iat) si la cookie es válida y no expiró."""
    try:
        payload: Any = _serializer().loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
    # Backward-compat: cookies viejas tenían solo el int del user_id.
    if isinstance(payload, int):
        return payload, 0
    if isinstance(payload, dict):
        uid = payload.get("uid")
        iat = payload.get("iat", 0)
        if isinstance(uid, int):
            return uid, int(iat) if iat else 0
    return None


# --- 2FA (TOTP) ---

@lru_cache(maxsize=1)
def _totp_pending_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=_TOTP_PENDING_SALT)


def create_totp_pending_token(user_id: int) -> str:
    """Token firmado que prueba que la contraseña ya fue validada (paso 1 del login)."""
    return _totp_pending_serializer().dumps(user_id)


def read_totp_pending_token(token: str) -> int | None:
    try:
        return _totp_pending_serializer().loads(token, max_age=_TOTP_PENDING_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None


def verify_totp(secret: str, code: str) -> bool:
    """Verifica un código TOTP con tolerancia de ±30s de desfase de reloj."""
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# --- Tokens de la extensión del navegador ---
# Se guarda solo el hash SHA-256; el token en claro se entrega una única vez.

def generate_extension_token() -> str:
    return "dvh_" + secrets.token_urlsafe(32)


def hash_extension_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

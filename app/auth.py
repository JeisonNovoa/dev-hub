import hashlib
import secrets
from functools import lru_cache

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.config import settings

COOKIE_NAME = "session"
_SESSION_SALT = "session"
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


@lru_cache(maxsize=1)
def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=_SESSION_SALT)


def create_session_cookie(user_id: int) -> str:
    return _serializer().dumps(user_id)


def read_session_cookie(token: str, max_age: int = 86400 * 30) -> int | None:
    try:
        return _serializer().loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None


# --- Tokens de la extensión del navegador ---
# Se guarda solo el hash SHA-256; el token en claro se entrega una única vez.

def generate_extension_token() -> str:
    return "dvh_" + secrets.token_urlsafe(32)


def hash_extension_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

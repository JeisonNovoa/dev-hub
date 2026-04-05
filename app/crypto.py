import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    from app.config import settings
    return Fernet(settings.encryption_key.encode())


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        # Valor en texto plano (datos previos al cifrado) — se devuelve tal cual.
        # Al próximo guardado quedará cifrado.
        logger.warning("Valor de credencial no cifrado encontrado — migración pendiente")
        return value


class EncryptedText(TypeDecorator):
    """Columna Text que cifra en escritura y descifra en lectura de forma transparente."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return decrypt(value)

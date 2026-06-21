import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)

# Todo token Fernet (versión 0x80) empieza así en base64.
_FERNET_PREFIX = "gAAAAA"

# Cota para deshacer cifrados anidados (datos doblemente cifrados por migraciones).
_MAX_UNWRAP_DEPTH = 3


@lru_cache(maxsize=1)
def _fernets() -> tuple[Fernet, ...]:
    """Clave primaria + claves antiguas (OLD_ENCRYPTION_KEYS), en ese orden.

    Se cifra siempre con la primaria; las antiguas solo sirven para descifrar
    datos guardados antes de una rotación de clave.
    """
    from app.config import settings

    keys = [settings.encryption_key, *settings.old_encryption_keys_list]
    return tuple(Fernet(k.encode()) for k in keys)


def looks_encrypted(value: str | None) -> bool:
    return bool(value) and value.startswith(_FERNET_PREFIX)


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernets()[0].encrypt(value.encode()).decode()


def _decrypt_once(value: str) -> str | None:
    for fernet in _fernets():
        try:
            return fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            continue
    return None


def decrypt(value: str | None) -> str | None:
    if value is None:
        return None

    plain = _decrypt_once(value)
    if plain is None:
        if looks_encrypted(value):
            # El valor parecía cifrado pero ninguna clave lo descifra. Antes
            # devolvíamos el token crudo, lo que podía filtrarse a la UI como
            # si fuera la contraseña real. Ahora devolvemos un marcador claro
            # para que el usuario lo vea y pueda reparar (rotar claves o
            # reingresar la credencial). No lanzamos excepción porque rompería
            # queries enteros por una sola fila corrupta.
            logger.warning(
                "Valor cifrado con una clave desconocida — devolviendo marcador. "
                "Agrega la clave original en OLD_ENCRYPTION_KEYS y corre "
                "scripts/reencrypt_credentials.py para repararlo de forma permanente."
            )
            return "[ERROR: no se pudo descifrar — rota claves o reingresa la credencial]"
        # Dato en texto plano (anterior al cifrado) — se devuelve tal cual.
        return value

    # Deshacer doble cifrado: si lo descifrado sigue siendo un token nuestro,
    # descifrar de nuevo (ocurre cuando una migración envió ciphertext como plaintext).
    depth = 0
    while looks_encrypted(plain) and depth < _MAX_UNWRAP_DEPTH:
        inner = _decrypt_once(plain)
        if inner is None:
            break
        plain = inner
        depth += 1
    return plain


class EncryptedText(TypeDecorator):
    """Columna Text que cifra en escritura y descifra en lectura de forma transparente."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return decrypt(value)

"""
Script one-shot para cifrar contraseñas que ya estén en texto plano en la base de datos.

Ejecutar UNA sola vez tras añadir ENCRYPTION_KEY al entorno:

    python scripts/encrypt_existing_credentials.py

Es seguro ejecutarlo varias veces: los valores ya cifrados se detectan y se omiten.
"""

import sys
from pathlib import Path

# Añadir el directorio raíz al path para poder importar app
sys.path.insert(0, str(Path(__file__).parent.parent))

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, text

from app.config import settings
from app.crypto import encrypt

fernet = Fernet(settings.encryption_key.encode())


def is_encrypted(value: str) -> bool:
    try:
        fernet.decrypt(value.encode())
        return True
    except InvalidToken:
        return False


def main() -> None:
    engine = create_engine(settings.database_url)

    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, password FROM credentials WHERE password IS NOT NULL")).fetchall()

    if not rows:
        print("No hay credenciales con contraseña. Nada que migrar.")
        return

    plaintext_count = 0
    already_encrypted = 0

    with engine.begin() as conn:
        for row_id, password in rows:
            if is_encrypted(password):
                already_encrypted += 1
                continue
            encrypted = encrypt(password)
            conn.execute(
                text("UPDATE credentials SET password = :pwd WHERE id = :id"),
                {"pwd": encrypted, "id": row_id},
            )
            plaintext_count += 1

    print(f"Migración completa:")
    print(f"  Cifradas ahora: {plaintext_count}")
    print(f"  Ya estaban cifradas: {already_encrypted}")


if __name__ == "__main__":
    main()

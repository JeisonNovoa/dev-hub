"""Rota la contraseña del usuario admin@devhub.local.

Pide la nueva contraseña por getpass (no se muestra en pantalla) y la actualiza
en la BD apuntada por DATABASE_URL del .env. También refresca password_changed_at
para invalidar sesiones viejas (cuando S6 esté implementado).

Uso:
    .venv/Scripts/python scripts/rotate_admin_password.py
"""

from __future__ import annotations

import getpass
import sys

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User

ADMIN_EMAIL = "admin@devhub.local"


def main() -> int:
    print(f"Rotando contraseña para {ADMIN_EMAIL}")
    print("La BD apuntada por DATABASE_URL será modificada.")
    try:
        new_pw = getpass.getpass("Nueva contraseña (no se muestra): ")
    except (EOFError, KeyboardInterrupt):
        print("\nAbortado.")
        return 1

    if len(new_pw) < 12:
        print("ERROR: mínimo 12 caracteres.", file=sys.stderr)
        return 1
    if new_pw.lower() in {"changeme", "password", "admin", "12345678"}:
        print("ERROR: contraseña demasiado débil.", file=sys.stderr)
        return 1

    confirm = getpass.getpass("Confirma la nueva contraseña: ")
    if confirm != new_pw:
        print("ERROR: las contraseñas no coinciden.", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not user:
            print(f"ERROR: usuario {ADMIN_EMAIL} no existe.", file=sys.stderr)
            return 1
        user.hashed_password = hash_password(new_pw)
        # password_changed_at se añadirá en S6; si la columna aún no existe,
        # este bloque es un no-op silencioso.
        try:
            from datetime import datetime, timezone

            user.password_changed_at = datetime.now(timezone.utc)
        except AttributeError:
            pass
        db.commit()
        print(f"OK: contraseña actualizada para user_id={user.id}")
        print("Si S6 está aplicado, todas las sesiones viejas quedan invalidadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Re-cifra todas las contraseñas de credenciales con la ENCRYPTION_KEY actual.

Cuándo usarlo: cuando las contraseñas se muestran como tokens cifrados
(gAAAAA...). Eso significa que fueron cifradas con OTRA clave (rotaste la
clave, o la migración las dobló-cifró). Pasa la(s) clave(s) vieja(s) en
OLD_ENCRYPTION_KEYS para que el script pueda recuperarlas y re-cifrarlas
con la clave actual.

Uso apuntando a producción (PowerShell):
    $env:DATABASE_URL        = "postgresql+psycopg2://...supabase..."
    $env:ENCRYPTION_KEY      = "<clave ACTUAL de produccion (Render)>"
    $env:OLD_ENCRYPTION_KEYS = "<clave vieja, p. ej. la de tu .env local>"
    .venv\\Scripts\\python scripts/reencrypt_credentials.py --dry-run
    .venv\\Scripts\\python scripts/reencrypt_credentials.py

Opciones:
    --dry-run   muestra qué haría sin escribir nada
    --yes       no pide confirmación interactiva
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.crypto import _fernets, decrypt, looks_encrypted
from app.models import Credential

from cryptography.fernet import InvalidToken


def _mask(key: str) -> str:
    return f"{key[:6]}…{key[-4:]}" if len(key) > 12 else "***"


def _decrypted_with_primary(raw: str) -> str | None:
    try:
        return _fernets()[0].decrypt(raw.encode()).decode()
    except InvalidToken:
        return None


def reencrypt(dry_run: bool, assume_yes: bool) -> int:
    print(f"\nBase de datos : {settings.database_url.split('@')[-1]}")
    print(f"Clave primaria: {_mask(settings.encryption_key)}")
    old_keys = settings.old_encryption_keys_list
    print(f"Claves viejas : {', '.join(_mask(k) for k in old_keys) if old_keys else '(ninguna)'}")
    if dry_run:
        print("Modo          : DRY RUN (no se escribe nada)")

    if not dry_run and not assume_yes:
        answer = input("\n¿Re-cifrar las credenciales de esta base de datos? [y/N] ").strip().lower()
        if answer not in ("y", "yes", "s", "si", "sí"):
            print("Cancelado.")
            return 1

    engine = create_engine(settings.database_url)
    db = sessionmaker(bind=engine)()

    # SQL textual para leer el valor CRUDO almacenado, sin pasar por EncryptedText.
    rows = db.execute(text("SELECT id, label, password FROM credentials ORDER BY id")).all()

    ok = fixed = unrecoverable = empty = 0
    try:
        for row in rows:
            raw = row.password
            if not raw:
                empty += 1
                continue

            plain = decrypt(raw)

            if plain == raw and looks_encrypted(raw):
                unrecoverable += 1
                print(f"  ! IRRECUPERABLE  #{row.id} {row.label} — ninguna clave la descifra")
                continue

            # Ya está cifrada con la clave primaria en una sola capa → nada que hacer.
            if _decrypted_with_primary(raw) == plain:
                ok += 1
                continue

            fixed += 1
            reason = "texto plano" if not looks_encrypted(raw) else "clave vieja o doble cifrado"
            print(f"  > re-cifrando   #{row.id} {row.label} ({reason})")
            if not dry_run:
                # El UPDATE pasa por EncryptedText → cifra con la clave primaria.
                db.execute(update(Credential).where(Credential.id == row.id).values(password=plain))

        if not dry_run:
            db.commit()
    finally:
        db.close()

    print(f"\nResultado: {ok} ya correctas, {fixed} re-cifradas, {unrecoverable} irrecuperables, {empty} sin contraseña")
    if unrecoverable:
        print(
            "\nLas irrecuperables fueron cifradas con una clave que no está ni en ENCRYPTION_KEY"
            "\nni en OLD_ENCRYPTION_KEYS. Busca la clave original (¿la de tu .env local viejo?)"
            "\ny vuelve a correr el script agregándola a OLD_ENCRYPTION_KEYS."
        )
    if dry_run and fixed:
        print("\nDRY RUN: corre de nuevo sin --dry-run para aplicar los cambios.")
    return 0


if __name__ == "__main__":
    sys.exit(reencrypt(dry_run="--dry-run" in sys.argv, assume_yes="--yes" in sys.argv))

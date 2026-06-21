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
from app.crypto import _decrypt_once, _fernets, looks_encrypted
from app.models import Credential

from cryptography.fernet import InvalidToken


def _mask(key: str) -> str:
    return f"{key[:6]}…{key[-4:]}" if len(key) > 12 else "***"


def _decrypted_with_primary(raw: str) -> str | None:
    try:
        return _fernets()[0].decrypt(raw.encode()).decode()
    except InvalidToken:
        return None


def _recover_plain(raw: str) -> str | None:
    """Intenta descifrar con todas las claves y deshacer doble cifrado.

    Devuelve el plaintext si lo logra, o None si ninguna clave lo descifra.
    No llama a app.crypto.decrypt() porque esa función devuelve un marcador
    para el caso irrecuperable; aquí necesitamos distinguir None.
    """
    # Si no parece cifrado, es plaintext (dato previo al cifrado) → tal cual.
    if not looks_encrypted(raw):
        return raw
    plain = _decrypt_once(raw)
    if plain is None:
        return None
    depth = 0
    while looks_encrypted(plain) and depth < 3:
        inner = _decrypt_once(plain)
        if inner is None:
            break
        plain = inner
        depth += 1
    return plain


def _process_rows(rows, write_fn) -> tuple[int, int, int, int]:
    """Recorre filas (id, label, password cruda), decide acción y escribe.

    Devuelve (ok, fixed, unrecoverable, empty).
    write_fn(cred_id, value) persiste el valor re-cifrado; en dry-run es no-op.
    """
    ok = fixed = unrecoverable = empty = 0
    for row in rows:
        raw = row.password
        if not raw:
            empty += 1
            continue

        plain = _recover_plain(raw)

        if plain is None and looks_encrypted(raw):
            unrecoverable += 1
            print(f"  ! IRRECUPERABLE  #{row.id} {row.label} — ninguna clave la descifra")
            continue

        # Ya está cifrada con la clave primaria en una sola capa → nada que hacer.
        if (
            _decrypted_with_primary(raw) is not None
            and plain is not None
            and _decrypted_with_primary(raw) == plain
        ):
            ok += 1
            continue

        fixed += 1
        reason = "texto plano" if not looks_encrypted(raw) else "clave vieja o doble cifrado"
        print(f"  > re-cifrando   #{row.id} {row.label} ({reason})")
        # Pasamos el plaintext al write_fn; EncryptedText.process_bind_param
        # lo re-cifrará con la clave primaria. Pasar el ciphertext ya cifrado
        # produciría doble cifrado.
        write_fn(row.id, plain)
    return ok, fixed, unrecoverable, empty


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
    # En modo apply todo el loop corre dentro de una sola transacción: si algo
    # falla a mitad, rollback (importante cuando se corre contra Postgres
    # compartido local+prod mientras hay tráfico de lecturas). En dry-run no
    # abrimos transacción porque no escribimos nada.
    ok = fixed = unrecoverable = empty = 0
    try:
        rows = db.execute(
            text("SELECT id, label, password FROM credentials ORDER BY id")
        ).all()

        def _write_apply(cred_id: int, value: str | None) -> None:
            db.execute(
                update(Credential).where(Credential.id == cred_id).values(password=value)
            )

        write_fn = (lambda *_a, **_kw: None) if dry_run else _write_apply
        ok, fixed, unrecoverable, empty = _process_rows(rows, write_fn=write_fn)

        if dry_run:
            db.rollback()  # nada que commitear
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise
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

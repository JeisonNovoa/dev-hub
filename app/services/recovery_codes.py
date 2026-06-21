"""Generación y verificación de códigos de recuperación de 2FA.

Los códigos son strings tipo `XXXX-XXXX-XXXX` (10 caracteres alfanuméricos sin
0/O/1/I/L para evitar ambigüedades). Se guardan hasheados con bcrypt (igual
que las contraseñas) — nunca en claro.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.models import RecoveryCode, User

# Alfabeto sin caracteres ambiguos (sin 0/O/1/I/L).
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_RECOVERY_CODE_COUNT = 10


def generate_recovery_codes() -> list[str]:
    """Devuelve 10 códigos nuevos en claro. Cada uno formateado XXXX-XXXX-XXXX."""
    codes: list[str] = []
    for _ in range(_RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(12))
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}")
    return codes


def regenerate_for_user(db: Session, user: User) -> list[str]:
    """Invalida todos los recovery codes viejos del usuario y crea 10 nuevos.

    Devuelve los 10 códigos en claro — el caller debe mostrarlos una sola vez.
    """
    now = datetime.now(timezone.utc)
    db.query(RecoveryCode).filter(
        RecoveryCode.user_id == user.id,
        RecoveryCode.used_at.is_(None),
    ).update({RecoveryCode.used_at: now})
    codes = generate_recovery_codes()
    for code in codes:
        db.add(RecoveryCode(user_id=user.id, code_hash=hash_password(code)))
    db.commit()
    return codes


def use_recovery_code(db: Session, user: User, code: str) -> bool:
    """Verifica y consume un recovery code. Devuelve True si era válido.

    Si el código coincide con uno no usado, lo marca como usado y devuelve True.
    Si no coincide con ninguno (o ya fueron todos usados), devuelve False.
    """
    code = code.strip().upper()
    if not code:
        return False
    candidates = (
        db.query(RecoveryCode)
        .filter(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))
        .all()
    )
    for candidate in candidates:
        if verify_password(code, candidate.code_hash):
            candidate.used_at = datetime.now(timezone.utc)
            db.commit()
            return True
    return False


def remaining_count(db: Session, user: User) -> int:
    """Cuántos recovery codes le quedan sin usar al usuario."""
    return (
        db.query(RecoveryCode)
        .filter(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))
        .count()
    )

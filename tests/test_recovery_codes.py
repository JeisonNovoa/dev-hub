"""Tests de recovery codes de 2FA (S7)."""

from datetime import datetime, timezone

import pyotp

from app.models import RecoveryCode
from app.services.recovery_codes import (
    generate_recovery_codes,
    regenerate_for_user,
    remaining_count,
    use_recovery_code,
)


def _enable_totp(db, user):
    secret = pyotp.random_base32()
    user.totp_secret = secret
    user.totp_confirmed_at = datetime.now(timezone.utc)
    db.commit()
    return secret


def test_generate_recovery_codes_format():
    codes = generate_recovery_codes()
    assert len(codes) == 10
    for code in codes:
        # Formato XXXX-XXXX-XXXX (12 chars + 2 guiones = 14)
        assert len(code) == 14
        assert code[4] == "-" and code[9] == "-"
        # Sin caracteres ambiguos
        for ch in code:
            assert ch == "-" or ch in "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    # Todos únicos
    assert len(set(codes)) == 10


def test_regenerate_creates_10_codes_hashed(db, auth_user):
    _enable_totp(db, auth_user)
    codes = regenerate_for_user(db, auth_user)
    assert len(codes) == 10
    # En BD quedan 10 hashes, ninguno coincide con el código en claro.
    rows = db.query(RecoveryCode).filter(RecoveryCode.user_id == auth_user.id).all()
    assert len(rows) == 10
    for row, code in zip(rows, codes):
        assert row.code_hash != code
        assert row.used_at is None


def test_use_recovery_code_marks_used(db, auth_user):
    _enable_totp(db, auth_user)
    codes = regenerate_for_user(db, auth_user)
    one = codes[0]
    assert use_recovery_code(db, auth_user, one) is True
    # No se puede reusar.
    assert use_recovery_code(db, auth_user, one) is False
    assert remaining_count(db, auth_user) == 9


def test_use_recovery_code_invalid(db, auth_user):
    _enable_totp(db, auth_user)
    regenerate_for_user(db, auth_user)
    assert use_recovery_code(db, auth_user, "AAAA-BBBB-CCCC") is False


def test_regenerate_invalidates_old(db, auth_user):
    _enable_totp(db, auth_user)
    codes_v1 = regenerate_for_user(db, auth_user)
    codes_v2 = regenerate_for_user(db, auth_user)
    # Códigos v1 ya no sirven.
    assert use_recovery_code(db, auth_user, codes_v1[0]) is False
    # Códigos v2 sí.
    assert use_recovery_code(db, auth_user, codes_v2[0]) is True


def test_use_recovery_code_case_insensitive(db, auth_user):
    _enable_totp(db, auth_user)
    codes = regenerate_for_user(db, auth_user)
    one = codes[0]
    assert use_recovery_code(db, auth_user, one.lower()) is True


def test_web_login_accepts_recovery_code(unauth_client, db, auth_user):
    """En el paso 2FA, un recovery code válido autentica igual que un TOTP."""
    import re
    _enable_totp(db, auth_user)
    codes = regenerate_for_user(db, auth_user)

    # Paso 1: contraseña
    res = unauth_client.post(
        "/login",
        data={"email": "test@devhub.local", "password": "password123"},
        follow_redirects=False,
    )
    token = re.search(r'name="pending_token" value="([^"]+)"', res.text).group(1)

    # Paso 2: recovery code en vez de TOTP
    res = unauth_client.post(
        "/login/2fa",
        data={"pending_token": token, "code": "", "recovery_code": codes[0]},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert "session" in res.cookies


def test_web_login_rejects_used_recovery_code(unauth_client, db, auth_user):
    import re
    _enable_totp(db, auth_user)
    codes = regenerate_for_user(db, auth_user)
    # Consumir uno primero.
    use_recovery_code(db, auth_user, codes[0])

    res = unauth_client.post(
        "/login",
        data={"email": "test@devhub.local", "password": "password123"},
        follow_redirects=False,
    )
    token = re.search(r'name="pending_token" value="([^"]+)"', res.text).group(1)
    res = unauth_client.post(
        "/login/2fa",
        data={"pending_token": token, "code": "", "recovery_code": codes[0]},
        follow_redirects=False,
    )
    assert res.status_code == 401
    assert "session" not in res.cookies


def test_extension_login_accepts_recovery_code(client, db, auth_user):
    from app.routers.api import extension as _ext
    _ext._LOGIN_ATTEMPTS.clear()
    _enable_totp(db, auth_user)
    codes = regenerate_for_user(db, auth_user)

    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local",
        "password": "password123",
        "recovery_code": codes[0],
    })
    assert res.status_code == 200
    assert res.json()["token"].startswith("dvh_")

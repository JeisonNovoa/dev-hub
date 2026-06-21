"""Test de integración de scripts/reencrypt_credentials.py contra un SQLite temporal."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text

from app import crypto
from app.config import settings
from app.models.common import Base

from scripts.reencrypt_credentials import reencrypt


@pytest.fixture
def scratch_db(tmp_path, monkeypatch):
    db_path = tmp_path / "scratch.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "database_url", url)
    crypto._fernets.cache_clear()
    yield engine
    crypto._fernets.cache_clear()
    engine.dispose()


def _insert_raw(engine, label: str, raw_password: str | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO credentials (label, password, category, login_via, created_at, updated_at) "
                "VALUES (:label, :pw, 'personal', 'email', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"label": label, "pw": raw_password},
        )


def _raw_passwords(engine) -> dict[str, str | None]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT label, password FROM credentials")).all()
    return {r.label: r.password for r in rows}


def test_reencrypt_fixes_old_key_plaintext_and_double(scratch_db, monkeypatch):
    old_key = Fernet.generate_key().decode()
    old_fernet = Fernet(old_key.encode())

    _insert_raw(scratch_db, "con-clave-vieja", old_fernet.encrypt(b"pass-vieja").decode())
    _insert_raw(scratch_db, "texto-plano", "pass-plano")
    _insert_raw(scratch_db, "ya-correcta", crypto.encrypt("pass-ok"))
    doble = crypto.encrypt(old_fernet.encrypt(b"pass-doble").decode())
    _insert_raw(scratch_db, "doble-cifrado", doble)
    _insert_raw(scratch_db, "sin-password", None)

    monkeypatch.setattr(settings, "old_encryption_keys", old_key)
    crypto._fernets.cache_clear()

    assert reencrypt(dry_run=False, assume_yes=True) == 0

    raw = _raw_passwords(scratch_db)
    primary = Fernet(settings.encryption_key.encode())
    assert primary.decrypt(raw["con-clave-vieja"].encode()).decode() == "pass-vieja"
    assert primary.decrypt(raw["texto-plano"].encode()).decode() == "pass-plano"
    assert primary.decrypt(raw["ya-correcta"].encode()).decode() == "pass-ok"
    assert primary.decrypt(raw["doble-cifrado"].encode()).decode() == "pass-doble"
    assert raw["sin-password"] is None


def test_reencrypt_reports_unrecoverable_without_touching_it(scratch_db):
    foreign = Fernet(Fernet.generate_key()).encrypt(b"perdida").decode()
    _insert_raw(scratch_db, "irrecuperable", foreign)

    assert reencrypt(dry_run=False, assume_yes=True) == 0

    # No debe modificarse: sigue siendo el mismo token ajeno.
    assert _raw_passwords(scratch_db)["irrecuperable"] == foreign


def test_dry_run_does_not_write(scratch_db, monkeypatch):
    old_key = Fernet.generate_key().decode()
    token = Fernet(old_key.encode()).encrypt(b"x").decode()
    _insert_raw(scratch_db, "vieja", token)

    monkeypatch.setattr(settings, "old_encryption_keys", old_key)
    crypto._fernets.cache_clear()

    assert reencrypt(dry_run=True, assume_yes=True) == 0
    assert _raw_passwords(scratch_db)["vieja"] == token


def test_reencrypt_rollback_on_failure(scratch_db, monkeypatch):
    """Si el script falla a mitad, la BD queda consistente (rollback)."""
    old_key = Fernet.generate_key().decode()
    token = Fernet(old_key.encode()).encrypt(b"pass1").decode()
    _insert_raw(scratch_db, "cred-a", token)
    _insert_raw(scratch_db, "cred-b", "plaintext-pass")

    monkeypatch.setattr(settings, "old_encryption_keys", old_key)
    crypto._fernets.cache_clear()

    # Patchear el write_fn para que falle en la segunda llamada.
    import scripts.reencrypt_credentials as rc
    original = rc._process_rows
    call_count = {"n": 0}

    def failing_write(cred_id, value):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            raise RuntimeError("boom")

    def patched(rows, write_fn):
        return original(rows, write_fn=failing_write)

    monkeypatch.setattr(rc, "_process_rows", patched)

    import pytest as _pytest
    with _pytest.raises(RuntimeError):
        reencrypt(dry_run=False, assume_yes=True)

    # La BD no debe tener cambios parciales: cred-b sigue plaintext,
    # cred-a sigue con su token viejo.
    raw = _raw_passwords(scratch_db)
    assert raw["cred-b"] == "plaintext-pass"
    assert raw["cred-a"] == token

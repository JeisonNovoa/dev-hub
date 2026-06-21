"""Tests unitarios del CredentialService (app/services/credentials.py)."""

from app.models import Credential
from app.services import credentials as svc


def test_normalize_url_adds_scheme():
    assert svc.normalize_url("cartesia.ai") == "https://cartesia.ai"
    assert svc.normalize_url("http://x.com") == "http://x.com"
    assert svc.normalize_url("https://y.com") == "https://y.com"


def test_normalize_url_handles_empty():
    assert svc.normalize_url(None) is None
    assert svc.normalize_url("") is None
    assert svc.normalize_url("   ") is None


def test_create_normalizes_url_and_blanks(db, auth_user):
    cred = svc.create(
        db, auth_user,
        label="Cartesia",
        username="",
        password="secreta",
        url="cartesia.ai",
    )
    assert cred.url == "https://cartesia.ai"
    assert cred.username is None  # "" → None
    assert cred.password == "secreta"


def test_get_owned_or_404_returns_owned(db, auth_user):
    cred = svc.create(db, auth_user, label="X", url="https://x.com")
    fetched = svc.get_owned_or_404(db, cred.id, auth_user.id)
    assert fetched.id == cred.id


def test_get_owned_or_404_other_user(db, auth_user):
    """Credencial de otro usuario no se encuentra."""
    from app.auth import hash_password
    from app.models import User
    other = User(email="other@test.local", hashed_password=hash_password("p"), is_active=True)
    db.add(other)
    db.flush()
    cred = Credential(label="Ajena", user_id=other.id, password="x", url="https://x.com")
    db.add(cred)
    db.commit()
    import pytest
    with pytest.raises(Exception):  # HTTPException 404
        svc.get_owned_or_404(db, cred.id, auth_user.id)


def test_get_owned_or_404_deleted(db, auth_user):
    """Credencial en papelera no se encuentra."""
    cred = svc.create(db, auth_user, label="X", url="https://x.com")
    svc.soft_delete(db, cred)
    import pytest
    with pytest.raises(Exception):
        svc.get_owned_or_404(db, cred.id, auth_user.id)


def test_update_normalizes_url(db, auth_user):
    cred = svc.create(db, auth_user, label="X", url="https://x.com")
    svc.update(db, cred, {"url": "nuevo.com", "label": "Nuevo"})
    assert cred.url == "https://nuevo.com"
    assert cred.label == "Nuevo"


def test_update_blanks_empty_string(db, auth_user):
    cred = svc.create(db, auth_user, label="X", username="user@x.com")
    svc.update(db, cred, {"username": ""})
    assert cred.username is None


def test_soft_delete_marks_deleted_at(db, auth_user):
    cred = svc.create(db, auth_user, label="X", url="https://x.com")
    assert cred.deleted_at is None
    svc.soft_delete(db, cred)
    assert cred.deleted_at is not None


def test_mark_used_sets_last_used_at(db, auth_user):
    cred = svc.create(db, auth_user, label="X", url="https://x.com")
    assert cred.last_used_at is None
    svc.mark_used(db, cred)
    assert cred.last_used_at is not None

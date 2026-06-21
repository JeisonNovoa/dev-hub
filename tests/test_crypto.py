"""Tests de app/crypto.py: roundtrip, fallback multi-clave y doble cifrado."""

import logging

import pytest
from cryptography.fernet import Fernet

from app import crypto
from app.config import settings


@pytest.fixture
def fresh_keys(monkeypatch):
    """Limpia el cache de Fernets antes y después de manipular settings."""
    crypto._fernets.cache_clear()
    yield monkeypatch
    crypto._fernets.cache_clear()


def test_encrypt_decrypt_roundtrip(fresh_keys):
    assert crypto.decrypt(crypto.encrypt("hunter2")) == "hunter2"


def test_none_passthrough(fresh_keys):
    assert crypto.encrypt(None) is None
    assert crypto.decrypt(None) is None


def test_quotes_and_unicode_roundtrip(fresh_keys):
    value = "pa'ss\"word`+ñ€ {{x}}"
    assert crypto.decrypt(crypto.encrypt(value)) == value


def test_plaintext_value_returned_as_is(fresh_keys):
    # Datos anteriores al cifrado (texto plano) no deben romperse.
    assert crypto.decrypt("plaintext-password") == "plaintext-password"


def test_decrypt_with_old_key_fallback(fresh_keys):
    old_key = Fernet.generate_key().decode()
    ciphertext = Fernet(old_key.encode()).encrypt(b"secreto-viejo").decode()

    # Sin la clave vieja configurada → devuelve un marcador claro (no el token).
    result = crypto.decrypt(ciphertext)
    assert result != ciphertext
    assert "no se pudo descifrar" in result

    fresh_keys.setattr(settings, "old_encryption_keys", old_key)
    crypto._fernets.cache_clear()
    assert crypto.decrypt(ciphertext) == "secreto-viejo"


def test_unwrap_double_encryption(fresh_keys):
    old_key = Fernet.generate_key().decode()
    inner = Fernet(old_key.encode()).encrypt(b"secreto-doble").decode()
    # Simula la migración que re-cifró un ciphertext con la clave actual.
    outer = crypto.encrypt(inner)

    fresh_keys.setattr(settings, "old_encryption_keys", old_key)
    crypto._fernets.cache_clear()
    assert crypto.decrypt(outer) == "secreto-doble"


def test_unknown_key_logs_warning(fresh_keys, caplog):
    foreign = Fernet(Fernet.generate_key()).encrypt(b"x").decode()
    with caplog.at_level(logging.WARNING, logger="app.crypto"):
        result = crypto.decrypt(foreign)
    assert result != foreign  # no filtra el token crudo
    assert "no se pudo descifrar" in result
    assert any("OLD_ENCRYPTION_KEYS" in r.message for r in caplog.records)


def test_looks_encrypted(fresh_keys):
    assert crypto.looks_encrypted(crypto.encrypt("x"))
    assert not crypto.looks_encrypted("password normal")
    assert not crypto.looks_encrypted(None)
    assert not crypto.looks_encrypted("")

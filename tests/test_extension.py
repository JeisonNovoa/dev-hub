"""Tests de la API de la extensión: login/token, match por dominio, secret, guardado y revocación."""

import pytest


@pytest.fixture
def ext_token(client):
    """Token de extensión válido para el usuario de prueba."""
    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local",
        "password": "password123",
        "name": "Chrome de prueba",
    })
    assert res.status_code == 200
    return res.json()["token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_credential(client, label: str, url: str, password: str = "secreta123") -> int:
    res = client.post("/api/credentials", json={
        "label": label,
        "username": "user@mail.com",
        "password": password,
        "url": url,
        "category": "personal",
    })
    assert res.status_code == 201
    return res.json()["id"]


# ─── Login y token ───────────────────────────────────────────────────────────

def test_login_returns_token_once(client):
    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local", "password": "password123",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["token"].startswith("dvh_")
    assert body["email"] == "test@devhub.local"


def test_login_wrong_password(client):
    res = client.post("/api/extension/login", json={
        "email": "test@devhub.local", "password": "incorrecta",
    })
    assert res.status_code == 401


def test_ping_with_valid_token(client, ext_token):
    res = client.get("/api/extension/ping", headers=_bearer(ext_token))
    assert res.status_code == 200
    assert res.json()["email"] == "test@devhub.local"


def test_ping_without_token(client):
    # client tiene cookie de sesión, pero ping exige Bearer token
    res = client.get("/api/extension/ping")
    assert res.status_code == 401


def test_ping_with_invalid_token(client):
    res = client.get("/api/extension/ping", headers=_bearer("dvh_token-falso"))
    assert res.status_code == 401


def test_logout_revokes_token(client, ext_token):
    assert client.post("/api/extension/logout", headers=_bearer(ext_token)).status_code == 204
    assert client.get("/api/extension/ping", headers=_bearer(ext_token)).status_code == 401


# ─── Match por dominio exacto ────────────────────────────────────────────────

def test_match_exact_domain(client, ext_token):
    cred_id = _create_credential(client, "Cartesia", "https://cartesia.ai/login")
    res = client.get("/api/extension/credentials/match?domain=cartesia.ai", headers=_bearer(ext_token))
    assert res.status_code == 200
    items = res.json()["items"]
    assert [i["id"] for i in items] == [cred_id]
    # No expone la contraseña en el listado
    assert "password" not in items[0]


def test_match_subdomain_of_saved_domain(client, ext_token):
    _create_credential(client, "Cartesia", "https://cartesia.ai")
    res = client.get("/api/extension/credentials/match?domain=play.cartesia.ai", headers=_bearer(ext_token))
    assert len(res.json()["items"]) == 1


def test_match_rejects_lookalike_domain(client, ext_token):
    _create_credential(client, "Cartesia", "https://cartesia.ai")
    for fake in ("cartesia.ai.evil.com", "no-cartesia.ai", "cartesiaai.com", "cartesia.io"):
        res = client.get(f"/api/extension/credentials/match?domain={fake}", headers=_bearer(ext_token))
        assert res.json()["items"] == [], f"no debería matchear {fake}"


def test_match_multiple_accounts_same_domain(client, ext_token):
    _create_credential(client, "GitHub personal", "https://github.com")
    _create_credential(client, "GitHub trabajo", "https://github.com/login")
    res = client.get("/api/extension/credentials/match?domain=github.com", headers=_bearer(ext_token))
    assert len(res.json()["items"]) == 2


# ─── Secret ──────────────────────────────────────────────────────────────────

def test_secret_returns_decrypted_password(client, ext_token):
    cred_id = _create_credential(client, "Cartesia", "https://cartesia.ai", password="mi-clave-123")
    res = client.get(f"/api/extension/credentials/{cred_id}/secret", headers=_bearer(ext_token))
    assert res.status_code == 200
    assert res.json()["password"] == "mi-clave-123"


def test_secret_requires_token(client):
    cred_id = _create_credential(client, "X", "https://x.com")
    assert client.get(f"/api/extension/credentials/{cred_id}/secret").status_code == 401


def test_secret_other_users_credential_404(client, ext_token, db):
    from app.auth import hash_password
    from app.models import Credential, User

    other = User(email="otro@test.local", hashed_password=hash_password("password123"), is_active=True)
    db.add(other)
    db.flush()
    cred = Credential(label="Ajena", user_id=other.id, password="secreto", url="https://x.com")
    db.add(cred)
    db.commit()

    res = client.get(f"/api/extension/credentials/{cred.id}/secret", headers=_bearer(ext_token))
    assert res.status_code == 404


# ─── Guardar desde la extensión ──────────────────────────────────────────────

def test_create_credential_from_extension(client, ext_token, auth_user, db):
    res = client.post("/api/extension/credentials", json={
        "label": "cartesia.ai",
        "username": "nuevo@mail.com",
        "password": "clave-nueva",
        "url": "cartesia.ai",
    }, headers=_bearer(ext_token))
    assert res.status_code == 201

    from app.models import Credential
    cred = db.query(Credential).filter(Credential.id == res.json()["id"]).first()
    assert cred.user_id == auth_user.id
    assert cred.url == "https://cartesia.ai"
    assert cred.password == "clave-nueva"  # descifrado transparente


# ─── Bóveda completa, editar y eliminar ──────────────────────────────────────

def test_list_vault(client, ext_token):
    _create_credential(client, "Cartesia", "https://cartesia.ai")
    _create_credential(client, "GitHub", "https://github.com")
    res = client.get("/api/extension/credentials", headers=_bearer(ext_token))
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 2
    # Incluye dominio para el favicon, nunca la contraseña
    assert {i["domain"] for i in items} == {"cartesia.ai", "github.com"}
    assert all("password" not in i for i in items)


def test_update_credential_from_extension(client, ext_token):
    cred_id = _create_credential(client, "Viejo", "https://x.com")
    res = client.patch(
        f"/api/extension/credentials/{cred_id}",
        json={"label": "Nuevo", "category": "work"},
        headers=_bearer(ext_token),
    )
    assert res.status_code == 200
    detail = client.get(f"/api/credentials/{cred_id}").json()
    assert detail["label"] == "Nuevo"
    assert detail["category"] == "work"


def test_delete_credential_from_extension(client, ext_token):
    cred_id = _create_credential(client, "Borrar", "https://x.com")
    assert client.delete(f"/api/extension/credentials/{cred_id}", headers=_bearer(ext_token)).status_code == 204
    # Ya no aparece en la bóveda
    items = client.get("/api/extension/credentials", headers=_bearer(ext_token)).json()["items"]
    assert all(i["id"] != cred_id for i in items)


def test_vault_requires_token(client):
    assert client.get("/api/extension/credentials").status_code == 401


# ─── Última vez usada (orden por uso reciente) ───────────────────────────────

def test_secret_access_marks_last_used(client, ext_token, db):
    from app.models import Credential

    cred_id = _create_credential(client, "Usada", "https://usada.com")
    assert db.query(Credential).get(cred_id).last_used_at is None

    client.get(f"/api/extension/credentials/{cred_id}/secret", headers=_bearer(ext_token))
    db.expire_all()
    assert db.query(Credential).get(cred_id).last_used_at is not None


def test_vault_orders_by_recent_use_nulls_last(client, ext_token):
    id_a = _create_credential(client, "AAA nunca usada", "https://a.com")
    id_b = _create_credential(client, "ZZZ usada", "https://z.com")

    # Usar la ZZZ: debe pasar al frente pese al orden alfabético
    client.get(f"/api/extension/credentials/{id_b}/secret", headers=_bearer(ext_token))

    items = client.get("/api/extension/credentials", headers=_bearer(ext_token)).json()["items"]
    assert [i["id"] for i in items] == [id_b, id_a]
    assert items[0]["last_used_at"] is not None
    assert items[1]["last_used_at"] is None


def test_match_orders_most_used_first(client, ext_token):
    id_a = _create_credential(client, "Cuenta A", "https://github.com")
    id_b = _create_credential(client, "Cuenta B", "https://github.com")

    client.get(f"/api/extension/credentials/{id_b}/secret", headers=_bearer(ext_token))

    items = client.get(
        "/api/extension/credentials/match?domain=github.com", headers=_bearer(ext_token)
    ).json()["items"]
    assert [i["id"] for i in items] == [id_b, id_a]


def test_create_oauth_credential_from_extension(client, ext_token):
    res = client.post("/api/extension/credentials", json={
        "label": "deepgram.com",
        "username": "yo@gmail.com",
        "url": "https://deepgram.com",
        "login_via": "google",
    }, headers=_bearer(ext_token))
    assert res.status_code == 201
    detail = client.get(f"/api/credentials/{res.json()['id']}").json()
    assert detail["login_via"] == "google"
    assert detail["password"] is None


def test_create_credential_normalizes_invalid_login_via(client, ext_token):
    res = client.post("/api/extension/credentials", json={
        "label": "x", "url": "https://x.com", "login_via": "facebook-falso",
    }, headers=_bearer(ext_token))
    assert res.status_code == 201
    detail = client.get(f"/api/credentials/{res.json()['id']}").json()
    assert detail["login_via"] == "email"


# ─── Gestión de tokens desde la web (cookie) ─────────────────────────────────

def test_list_and_revoke_tokens_via_web(client, ext_token):
    res = client.get("/api/extension/tokens")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Chrome de prueba"

    token_id = items[0]["id"]
    assert client.delete(f"/api/extension/tokens/{token_id}").status_code == 204
    # El token revocado deja de servir
    assert client.get("/api/extension/ping", headers=_bearer(ext_token)).status_code == 401
    assert client.get("/api/extension/tokens").json()["items"] == []

"""Tests de la generación de tokens de extensión desde la web (para Claude/MCP)."""

from app.models import ExtensionToken


def test_generate_token_from_web_returns_token_once(client, auth_user, db):
    res = client.post("/ui/extension/tokens/generate", data={"name": "Claude Code"})
    assert res.status_code == 200
    # El token en claro aparece una vez en el HTML devuelto.
    assert "dvh_" in res.text
    assert "Claude Code" in res.text
    # En BD queda solo el hash, no el token en claro.
    tokens = db.query(ExtensionToken).filter(ExtensionToken.user_id == auth_user.id).all()
    assert len(tokens) == 1
    assert tokens[0].name == "Claude Code"
    assert not tokens[0].token_hash.startswith("dvh_")


def test_generated_token_actually_works(client, auth_user):
    """El token generado desde la web debe autenticar contra la API."""
    res = client.post("/ui/extension/tokens/generate", data={"name": "MCP"})
    # Extraer el token del HTML (está dentro del <code id="generated-token-value">).
    import re
    match = re.search(r"dvh_[A-Za-z0-9_\-]+", res.text)
    assert match, "no se encontró el token en la respuesta"
    token = match.group(0)

    # Usarlo como Bearer contra un endpoint de la API (auth dual).
    ping = client.get("/api/extension/ping", headers={"Authorization": f"Bearer {token}"})
    assert ping.status_code == 200
    assert ping.json()["email"] == auth_user.email


def test_generate_token_default_name(client):
    res = client.post("/ui/extension/tokens/generate", data={})
    assert res.status_code == 200
    assert "Claude Code" in res.text


def test_generate_token_requires_auth(unauth_client):
    res = unauth_client.post("/ui/extension/tokens/generate", data={"name": "x"}, follow_redirects=False)
    assert res.status_code in (302, 401)


def test_generated_token_appears_in_device_list(client):
    client.post("/ui/extension/tokens/generate", data={"name": "Mi Claude"})
    page = client.get("/extension")
    assert page.status_code == 200
    assert "Mi Claude" in page.text

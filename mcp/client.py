"""Cliente HTTP compartido contra la API de Dev Hub.

Centraliza auth (token Bearer), manejo de errores y la construcción del cliente
httpx para que todas las tools del MCP hablen con la API de la misma forma.
"""

from __future__ import annotations

import os

import httpx

DEFAULT_BASE_URL = "https://dev-hub-whry8q.fly.dev"
_TIMEOUT = 20.0


def base_url() -> str:
    return os.environ.get("DEVHUB_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _token() -> str:
    token = os.environ.get("DEVHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Falta DEVHUB_TOKEN. Genera un token en la web "
            "(Extensión → conectar Claude Code / MCP) y expórtalo como DEVHUB_TOKEN."
        )
    return token


def _client() -> httpx.Client:
    # follow_redirects=False: si el token no vale, la API redirige a /login (302).
    # Queremos ver ese 302 como fallo de auth, no seguirlo hasta la página HTML.
    return httpx.Client(
        base_url=base_url(),
        headers={"Authorization": f"Bearer {_token()}"},
        timeout=_TIMEOUT,
        follow_redirects=False,
    )


def request(method: str, path: str, **kwargs) -> dict | list | str | None:
    """Llama a la API de Dev Hub y devuelve el cuerpo (json, texto, o None en 204).

    Lanza un RuntimeError con mensaje legible si la API responde con error, para
    que el cliente MCP lo muestre en vez de un traceback.
    """
    with _client() as client:
        resp = client.request(method, path, **kwargs)
    # 401 (endpoints de extensión) o 302→/login (resto de la API): token no válido.
    if resp.status_code == 401 or (
        resp.status_code in (302, 307) and "/login" in resp.headers.get("location", "")
    ):
        raise RuntimeError("Token inválido o expirado. Genera uno nuevo en la web.")
    if resp.status_code == 404:
        raise RuntimeError(f"No encontrado: {path}")
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            detail = resp.text[:200]
        raise RuntimeError(f"Error {resp.status_code} en {path}: {detail}")
    if resp.status_code == 204 or not resp.content:
        return None
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        return resp.json()
    return resp.text


def clean_body(data: dict) -> dict:
    """Quita claves con valor None para no pisar campos con null en PATCH/PUT."""
    return {k: v for k, v in data.items() if v is not None}

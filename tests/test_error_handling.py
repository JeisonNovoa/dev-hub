"""Tests del manejo global de errores 500 y del health check de readiness.

El handler global asegura que un fallo inesperado (cualquier excepción que no
sea HTTPException) devuelva una respuesta limpia: un fragmento HTML para
peticiones HTMX (para no romper la UI) y JSON para el resto. Sin esto, una
excepción no controlada inyectaría el traceback de Starlette en el DOM.
"""

from fastapi import APIRouter

from app.main import app

# Router de prueba que revienta a propósito. Se registra una sola vez a nivel
# de módulo; las rutas viven solo durante esta sesión de tests.
_boom_router = APIRouter()


@_boom_router.get("/__boom__")
def _boom():
    raise RuntimeError("explosión deliberada para el test")


app.include_router(_boom_router)


def test_unhandled_exception_returns_clean_json(raising_client):
    """Una excepción no controlada en una petición normal → JSON 500, sin traceback."""
    resp = raising_client.get("/__boom__")
    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body
    # No debe filtrar el mensaje interno de la excepción.
    assert "explosión deliberada" not in body["detail"]
    assert "RuntimeError" not in body["detail"]


def test_unhandled_exception_returns_html_fragment_for_htmx(raising_client):
    """En una petición HTMX → fragmento HTML 500 (no JSON, no traceback)."""
    resp = raising_client.get("/__boom__", headers={"HX-Request": "true"})
    assert resp.status_code == 500
    assert "text/html" in resp.headers["content-type"]
    assert "RuntimeError" not in resp.text
    assert "explosión deliberada" not in resp.text
    # El fragmento debe traer algún texto de error visible para el usuario.
    assert "error" in resp.text.lower()


def test_http_exception_is_not_swallowed_by_global_handler(client):
    """El handler global NO debe interferir con los 404 normales de HTTPException."""
    resp = client.get("/api/projects/no-existe")
    assert resp.status_code == 404
    assert "no encontrado" in resp.json()["detail"].lower()


def test_health_liveness_does_not_touch_db(unauth_client):
    """/health es liveness puro: responde ok sin autenticación ni BD."""
    resp = unauth_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_health_ready_checks_db(unauth_client):
    """/health/ready ejecuta un SELECT 1: con BD sana devuelve ok."""
    resp = unauth_client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["database"] == "ok"

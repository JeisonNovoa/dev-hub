"""Protección CSRF por doble-submit cookie.

Patrón estándar para apps HTMX:

1. Al servir cualquier página autenticada, el backend setea una cookie
   `csrf_token` legible por JS (no HttpOnly, SameSite=Lax).
2. En el navegador, app.js lee esa cookie y la manda como header
   `X-CSRFToken` en cada petición.
3. Este middleware verifica que en POST/PATCH/PUT/DELETE el header coincida
   con la cookie. Un sitio malicioso que intente forzar un POST cross-site
   no puede leer la cookie (CORS) y por tanto no puede reproducir el header.

SameSite=Lax ya bloquea la mayoría de CSRF, pero Lax no cubre todos los
casos (algunos navegadores viejos, subdominios, navegación con GET
"mutante"). El doble-submit cierra esos huecos.

Exclusiones:
- `/api/extension/*` se autentica por Bearer token, no por cookie. CSRF no
  aplica porque no hay cookie que forzar.
- `/health` no muta estado.
- LOGIN/REGISTER mismos: la cookie CSRF se setea al cargar la página GET,
  antes de enviar el POST, así que sí aplica la verificación.
"""

from __future__ import annotations

import hmac
import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRFToken"
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Prefijos de rutas que NO requieren CSRF (usan auth distinta o no mutan).
_EXEMPT_PREFIXES = ("/api/extension", "/health")


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str, secure: bool) -> None:
    """Setea la cookie CSRF. No HttpOnly para que JS pueda leerla."""
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=86400 * 30,
        httponly=False,
        samesite="lax",
        secure=secure,
        path="/",
    )


def csrf_token_is_valid(cookie_value: str | None, header_value: str | None) -> bool:
    """Comparación con hmac.compare_digest para evitar timing attacks."""
    if not cookie_value or not header_value:
        return False
    if len(cookie_value) != len(header_value):
        return False
    return hmac.compare_digest(cookie_value, header_value)


class CsrfMiddleware(BaseHTTPMiddleware):
    """Valida CSRF por doble-submit cookie en métodos no seguros.

    Acepta el token por header X-CSRFToken (HTMX) o por campo de form
    `csrf_token` (forms nativos login/register/logout). En ambos casos el
    valor se compara con la cookie csrf_token — no con un secreto server-side,
    que es el truco del doble-submit: el atacante cross-site no puede leer
    la cookie (CORS), así que no puede reproducir el header ni el field.

    Leer el form en el middleware consume el body; lo cacheamos para que el
    endpoint downstream siga recibiendo los datos.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        is_unsafe = request.method in _UNSAFE_METHODS
        is_exempt = any(path.startswith(p) for p in _EXEMPT_PREFIXES)

        if is_unsafe and not is_exempt:
            cookie_token = request.cookies.get(CSRF_COOKIE)
            header_token = request.headers.get(CSRF_HEADER)
            if not header_token:
                # Form nativo (no HTMX): buscar el token en el body.
                header_token = await _read_csrf_from_form(request)
            if not csrf_token_is_valid(cookie_token, header_token):
                if request.headers.get("HX-Request"):
                    return Response(
                        content='<p class="text-red-400 text-sm font-mono px-2">CSRF: token inválido. Recarga la página.</p>',
                        status_code=403,
                        media_type="text/html",
                    )
                return Response(
                    content='{"detail":"CSRF token inválido o ausente"}',
                    status_code=403,
                    media_type="application/json",
                )

        return await call_next(request)


async def _read_csrf_from_form(request: Request) -> str | None:
    """Lee csrf_token de un form POST, cacheando el body para el endpoint."""
    ct = request.headers.get("content-type", "")
    if not (ct.startswith("application/x-www-form-urlencoded")
            or ct.startswith("multipart/form-data")):
        return None
    # Consumimos el body una sola vez; starlette no permite releerlo.
    body = await request.body()
    # Reemplazamos receive() para que el endpoint pueda volver a leer el body.
    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}
    request._receive = receive
    try:
        form = await request.form()
        return form.get("csrf_token")
    except Exception:
        return None

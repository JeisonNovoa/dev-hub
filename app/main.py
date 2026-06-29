import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.limiter import limiter
from app.logging_config import configure_logging
from app.middleware.csrf import CSRF_COOKIE, CsrfMiddleware, generate_csrf_token, set_csrf_cookie
from app.routers.api import commands, context, credentials, env_vars, export, extension, links, me, projects, repos
from app.routers.api import search as api_search
from app.routers.api import services
from app.routers.ui import auth as ui_auth
from app.routers.ui import credentials as ui_credentials
from app.routers.ui import dashboard, project as ui_project, trash as ui_trash
from app.routers.ui import extension as ui_extension
from app.routers.ui import import_project as ui_import
from app.routers.ui import search as ui_search
from app.routers.ui import security as ui_security

configure_logging(debug=settings.debug)

logger = logging.getLogger(__name__)

_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://unpkg.com 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://t3.gstatic.com https://icons.duckduckgo.com; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = _CSP
        # Cookie CSRF doble-submit: si el navegador no la tiene, se setea en
        # cualquier respuesta. app.js la leerá y la mandará como X-CSRFToken.
        if CSRF_COOKIE not in request.cookies:
            set_csrf_cookie(
                response,
                generate_csrf_token(),
                secure=settings.cookies_secure,
            )
        return response


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<p class="text-red-400 text-sm font-mono px-2">Demasiadas solicitudes. Espera un momento.</p>',
            status_code=429,
        )
    return JSONResponse(
        {"detail": f"Límite de solicitudes superado: {exc.detail}. Intenta de nuevo en un momento."},
        status_code=429,
    )


async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Atrapa cualquier excepción no-HTTP para no exponer el traceback.

    Loguea el error completo en el servidor (con stack), pero al cliente solo
    le devuelve un mensaje genérico: un fragmento HTML para HTMX (así la UI
    muestra un aviso en vez de romperse) y JSON para el resto.
    """
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<p class="text-red-400 text-sm font-mono px-2">'
            "Ocurrió un error. Recarga la página e intenta de nuevo.</p>",
            status_code=500,
        )
    return JSONResponse(
        {"detail": "Error interno del servidor. Intenta de nuevo más tarde."},
        status_code=500,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import SessionLocal
    from app.services.trash import purge_expired_credentials, purge_expired_projects
    db = SessionLocal()
    try:
        purge_expired_projects(db)
        purge_expired_credentials(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_exception_handler(Exception, _unhandled_exception_handler)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CsrfMiddleware)

logger.info("Iniciando %s", settings.app_name)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health", tags=["health"])
def health() -> dict:
    """Liveness barato (sin BD): usado por monitores externos y health checks de Fly.io."""
    return {"ok": True}


@app.get("/health/ready", tags=["health"])
def health_ready() -> JSONResponse:
    """Readiness: verifica que la BD responde (SELECT 1).

    A diferencia de /health, distingue "el proceso vive" de "el proceso puede
    atender". Si Supabase está caído, devuelve 503 para que un monitor externo
    lo detecte en vez de ver la app como sana mientras los usuarios reciben 500.
    """
    from sqlalchemy import text

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return JSONResponse({"ok": True, "database": "ok"})
    except Exception:
        logger.exception("Health check de readiness falló: la BD no responde")
        return JSONResponse(
            {"ok": False, "database": "error"},
            status_code=503,
        )
    finally:
        db.close()

# Auth — rutas públicas (login, register, logout)
app.include_router(ui_auth.router)

# API routers — devuelven JSON
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(env_vars.router, prefix="/api/projects/{slug}/env-vars", tags=["env-vars"])
app.include_router(commands.router, prefix="/api/projects/{slug}/commands", tags=["commands"])
app.include_router(links.router, prefix="/api/projects/{slug}/links", tags=["links"])
app.include_router(repos.router, prefix="/api/projects/{slug}/repos", tags=["repos"])
app.include_router(services.router, prefix="/api/services", tags=["services"])
app.include_router(credentials.router, prefix="/api/credentials", tags=["credentials"])
app.include_router(me.router, prefix="/api/me", tags=["me"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(context.router, prefix="/api/context", tags=["context"])
app.include_router(api_search.router, prefix="/api/lookup", tags=["lookup"])
app.include_router(extension.router, prefix="/api/extension", tags=["extension"])

# UI routers — devuelven HTML
app.include_router(ui_trash.router)
app.include_router(dashboard.router)
app.include_router(ui_project.router)
app.include_router(ui_credentials.router)
app.include_router(ui_import.router)
app.include_router(ui_extension.router)
app.include_router(ui_security.router)
app.include_router(ui_search.router)

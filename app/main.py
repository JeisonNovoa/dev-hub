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
from app.routers.api import commands, credentials, env_vars, export, links, projects, repos, services
from app.routers.ui import auth as ui_auth
from app.routers.ui import credentials as ui_credentials
from app.routers.ui import dashboard, project_detail, trash as ui_trash

configure_logging(debug=settings.debug)

logger = logging.getLogger(__name__)

_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://unpkg.com 'unsafe-eval'; "
    "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import SessionLocal
    from app.routers.ui.credentials import _purge_expired
    from app.routers.ui.dashboard import _purge_expired_projects
    db = SessionLocal()
    try:
        _purge_expired(db)
        _purge_expired_projects(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SecurityHeadersMiddleware)

logger.info("Iniciando %s", settings.app_name)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

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
app.include_router(export.router, prefix="/api/export", tags=["export"])

# UI routers — devuelven HTML
app.include_router(ui_trash.router)
app.include_router(dashboard.router)
app.include_router(project_detail.router)
app.include_router(ui_credentials.router)

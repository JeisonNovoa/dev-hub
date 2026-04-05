import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.logging_config import configure_logging
from app.routers.api import commands, credentials, env_vars, export, links, projects, repos, services
from app.routers.ui import credentials as ui_credentials
from app.routers.ui import dashboard, project_detail, search

configure_logging(debug=settings.debug)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

logger.info("Iniciando %s", settings.app_name)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

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
app.include_router(dashboard.router)
app.include_router(project_detail.router)
app.include_router(ui_credentials.router)
app.include_router(search.router)

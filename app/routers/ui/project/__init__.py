"""Routers UI del detalle de proyecto, partidos por feature.

Cada submódulo define su propio APIRouter; este __init__.py los combina en
uno solo que main.py incluye con un único include_router. Mantiene la firma
pública idéntica a cuando todo vivía en project_detail.py.
"""

from fastapi import APIRouter

from app.routers.ui.project import (
    commands,
    credentials,
    detail,
    env_vars,
    header,
    links,
    notes,
    repos,
    services,
)

# Router colectivo — main.py sigue haciendo include_router(project_detail.router).
router = APIRouter()
for sub in (detail, env_vars, commands, links, services, header, notes, repos, credentials):
    router.include_router(sub.router)

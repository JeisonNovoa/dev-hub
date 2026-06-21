"""Routers UI de credenciales, partidos por feature.

Submódulos:
  - list:     listado /credentials con filtros, higiene inline y conteos
  - detail:   /credentials/{id}, panel de seguridad, edición inline
  - hygiene:  /credentials/higiene + chequeo HIBP
  - forms:    /ui/credentials/{new,edit,view,save} (acciones de tabla)
  - _shared:  helpers compartidos (is_stale, query builder, apply form)

Mantiene la firma pública de app.routers.ui.credentials:
  from app.routers.ui.credentials import is_stale  # sigue funcionando
  app.include_router(credentials.router)            # router colectivo
"""

from fastapi import APIRouter

from app.routers.ui.credentials import detail, forms, hygiene, listing
from app.routers.ui.credentials._shared import is_stale  # re-export para back-compat

router = APIRouter()
for sub in (listing, hygiene, detail, forms):
    router.include_router(sub.router)

__all__ = ["router", "is_stale"]

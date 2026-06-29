"""Búsqueda global por API (/api/search) — cross-entity, orientada a la IA."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services import global_search

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    summary="Búsqueda global cross-entity",
    description=(
        "Busca un término en proyectos, credenciales y servicios del usuario y "
        "devuelve resultados tipados (type: project|credential|service). Útil "
        "para que la IA encuentre dónde se usa algo across todo el hub. Nunca "
        "expone contraseñas."
    ),
)
def search(
    q: str = Query(..., min_length=1, description="Término de búsqueda"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    results = global_search.search_all(db, current_user, q)
    return {"query": q, "total": len(results), "results": results}

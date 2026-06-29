"""Endpoints de contexto orientados a LLM / Claude Code.

Pensados para que una IA pueda "retomar" un proyecto sin copiar datos a mano:
- GET /api/context/{slug}   → el proyecto entero en markdown (o JSON denso)
- GET /api/context/recent   → en qué estuviste trabajando últimamente

Reutilizan la autenticación estándar (cookie de sesión o token de extensión
no aplica aquí: estos son endpoints de la API web, protegidos por sesión).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Project, ProjectEvent, User
from app.services import context as context_service

router = APIRouter()
logger = logging.getLogger(__name__)

_RECENT_LIMIT_DEFAULT = 20
_RECENT_LIMIT_MAX = 100


@router.get(
    "/recent",
    summary="Actividad reciente del usuario",
    description=(
        "Devuelve los últimos eventos de actividad across todos los proyectos "
        "del usuario (qué se creó/editó/eliminó y cuándo). Útil para que la IA "
        "sepa en qué se estuvo trabajando y proponga retomar ese trabajo."
    ),
)
def recent_activity(
    limit: int = Query(_RECENT_LIMIT_DEFAULT, ge=1, le=_RECENT_LIMIT_MAX),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    events = (
        db.query(ProjectEvent)
        .join(Project, ProjectEvent.project_id == Project.id)
        .filter(Project.user_id == current_user.id, Project.deleted_at.is_(None))
        .order_by(ProjectEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "events": [
            {
                "project": e.project.slug,
                "project_name": e.project.name,
                "action": e.action,
                "entity": e.entity,
                "summary": e.summary,
                "at": e.created_at.isoformat(),
            }
            for e in events
        ]
    }


@router.get(
    "/{slug}",
    summary="Contexto completo de un proyecto para LLM",
    description=(
        "Devuelve todo el contexto operativo de un proyecto (comandos, env vars, "
        "links, repos, servicios y credenciales como referencia) en markdown "
        "listo para pegar en un prompt, o como JSON denso con `?format=json`. "
        "NUNCA incluye contraseñas de credenciales."
    ),
    response_class=PlainTextResponse,
)
def project_context(
    slug: str,
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = context_service.get_project_context(db, current_user, slug)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Proyecto '{slug}' no encontrado")
    ctx, markdown = result
    if format == "json":
        from fastapi.responses import JSONResponse

        return JSONResponse(ctx)
    return PlainTextResponse(markdown, media_type="text/markdown; charset=utf-8")

"""Registro de actividad de proyectos (timeline del detalle).

`log_event` es el único punto de entrada: el router lo llama tras crear/editar/
borrar una entidad del proyecto, antes del commit, para que actividad y cambio
compartan transacción. Mantener el texto aquí deja el formato consistente.
"""

import logging

from sqlalchemy.orm import Session

from app.models import ProjectEvent

logger = logging.getLogger(__name__)

_VERB = {"created": "Agregó", "updated": "Editó", "deleted": "Eliminó"}

_ENTITY_LABEL = {
    "project": "el proyecto",
    "command": "comando",
    "env_var": "env var",
    "repo": "repo",
    "link": "link",
    "service": "servicio",
    "credential": "credencial",
}

# Dot de color por entidad (clase Tailwind) para el timeline del detalle.
EVENT_DOT = {
    "project": "bg-accent",
    "command": "bg-green-400",
    "env_var": "bg-yellow-400",
    "repo": "bg-blue-400",
    "link": "bg-purple-400",
    "service": "bg-orange-400",
    "credential": "bg-red-400",
}

_MAX_SUMMARY = 255


def build_summary(action: str, entity: str, name: str | None) -> str:
    verb = _VERB.get(action, action)
    label = _ENTITY_LABEL.get(entity, entity)
    if entity == "project":
        return f"{'Creó' if action == 'created' else verb} {label}"
    text = f"{verb} {label}"
    if name:
        text += f" {name}"
    return text[:_MAX_SUMMARY]


def log_event(db: Session, project_id: int, action: str, entity: str, name: str | None = None) -> None:
    """Registra un evento de actividad sin hacer commit (lo hace el caller, para
    que actividad y cambio sean atómicos). Nunca lanza: la actividad es accesoria."""
    try:
        db.add(
            ProjectEvent(
                project_id=project_id,
                action=action,
                entity=entity,
                summary=build_summary(action, entity, name),
            )
        )
    except Exception:
        logger.exception("No se pudo registrar evento de actividad (project_id=%s)", project_id)

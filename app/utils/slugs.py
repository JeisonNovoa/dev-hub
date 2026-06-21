"""Helpers de slugs únicos para proyectos y repos.

Antes había dos copias de esta lógica (routers/ui/dashboard.py y
services/import_project.py) con pequeñas diferencias (empezar en 2 vs en 1).
Unificamos en una sola función que empieza en 2 — el primer candidato es el
base sin sufijo, y solo añadimos -N si choca.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Project


def unique_project_slug(db: Session, base_slug: str, user_id: int) -> str:
    """Devuelve un slug único para el usuario, añadiendo -N si hace falta.

    base_slug ya debe pasar por slugify(). Si está vacío o solo signos,
    el caller debe defaultear a 'proyecto' antes de llamar.
    """
    candidate = base_slug
    counter = 2
    while (
        db.query(Project)
        .filter(Project.slug == candidate, Project.user_id == user_id)
        .first()
    ):
        candidate = f"{base_slug}-{counter}"
        counter += 1
    return candidate


def unique_repo_slug(name: str, used: set[str]) -> str:
    """Devuelve un slug de repo único dentro del set `used` y lo agrega al set.

    `used` se muta: el caller pasa un set de slugs ya tomados.
    """
    from slugify import slugify

    base = slugify(name) or "repo"
    candidate = base
    counter = 2
    while candidate in used:
        candidate = f"{base}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate

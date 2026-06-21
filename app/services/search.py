"""Query de búsqueda de proyectos por texto libre.

Antes había 3 copias casi idénticas de este filter (routers/api/projects.py,
routers/ui/dashboard.py, routers/ui/search.py). Las unificamos aquí.

El match busca en name, description, notes y tech_stack con ilike
(case-insensitive). search.py usaba solo 3 campos (sin notes) — incluimos
notes para consistencia; no rompe nada y mejora el recall.
"""

from __future__ import annotations

from sqlalchemy import Text, cast
from sqlalchemy.orm import Session

from app.models import Project


def project_search_filter(query: "Session.query[Project]", term: str | None):
    """Añade un filter de texto a la query dada. Si term es None/vacío, no-op.

    Devuelve la query modificada para encadenamiento.
    """
    if not term:
        return query
    like = f"%{term}%"
    return query.filter(
        Project.name.ilike(like)
        | Project.description.ilike(like)
        | Project.notes.ilike(like)
        | cast(Project.tech_stack, Text).ilike(like)
    )

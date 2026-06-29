"""Búsqueda global cross-entity para la API (/api/search).

Busca un término en proyectos, credenciales y servicios del usuario y devuelve
una lista unificada de resultados tipados. Pensado para que la IA pueda
responder "¿dónde uso la API key de OpenAI?" sin recorrer endpoint por endpoint.

SEGURIDAD: los resultados de credenciales nunca incluyen la contraseña, solo
label/username/url como referencia.
"""

from __future__ import annotations

from sqlalchemy import Text, cast
from sqlalchemy.orm import Session

from app.models import Credential, Project, Service, User


def _search_projects(db: Session, user_id: int, like: str) -> list[dict]:
    rows = (
        db.query(Project)
        .filter(
            Project.user_id == user_id,
            Project.deleted_at.is_(None),
            Project.name.ilike(like)
            | Project.description.ilike(like)
            | Project.notes.ilike(like)
            | cast(Project.tech_stack, Text).ilike(like),
        )
        .order_by(Project.name)
        .all()
    )
    return [
        {
            "type": "project",
            "label": p.name,
            "slug": p.slug,
            "detail": p.description,
            "url": f"/projects/{p.slug}",
        }
        for p in rows
    ]


def _search_credentials(db: Session, user_id: int, like: str) -> list[dict]:
    rows = (
        db.query(Credential)
        .filter(
            Credential.user_id == user_id,
            Credential.deleted_at.is_(None),
            Credential.label.ilike(like)
            | Credential.username.ilike(like)
            | Credential.url.ilike(like)
            | Credential.notes.ilike(like),
        )
        .order_by(Credential.label)
        .all()
    )
    return [
        {
            "type": "credential",
            "label": c.label,
            "detail": c.username,
            "url": c.url,
            "category": c.category,
        }
        for c in rows
    ]


def _search_services(db: Session, user_id: int, like: str) -> list[dict]:
    rows = (
        db.query(Service)
        .filter(
            Service.user_id == user_id,
            Service.name.ilike(like) | Service.url.ilike(like) | Service.notes.ilike(like),
        )
        .order_by(Service.name)
        .all()
    )
    return [
        {
            "type": "service",
            "label": s.name,
            "detail": s.notes,
            "url": s.url,
            "category": s.category,
        }
        for s in rows
    ]


def search_all(db: Session, user: User, term: str) -> list[dict]:
    """Busca el término en proyectos, credenciales y servicios del usuario."""
    like = f"%{term.strip()}%"
    return (
        _search_projects(db, user.id, like)
        + _search_credentials(db, user.id, like)
        + _search_services(db, user.id, like)
    )

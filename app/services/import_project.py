"""Importación de un proyecto completo desde un ProjectImport ya validado.

Frontera limpia: entra un ProjectImport (sin importar de dónde salió — JSON pegado,
archivo subido, o a futuro texto estructurado por una IA server-side) y sale el
proyecto creado con todos sus hijos. Nunca modifica datos existentes: si el slug
choca, se genera uno nuevo con sufijo.
"""

import logging

from slugify import slugify
from sqlalchemy.orm import Session

from app.models import Command, EnvVariable, Project, QuickLink, Repo, Service
from app.schemas.import_project import ProjectImport

logger = logging.getLogger(__name__)


def _unique_project_slug(name: str, user_id: int, db: Session) -> str:
    base = slugify(name) or "proyecto"
    candidate = base
    n = 1
    while db.query(Project).filter(Project.slug == candidate, Project.user_id == user_id).first():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def _unique_repo_slug(name: str, used: set[str]) -> str:
    base = slugify(name) or "repo"
    candidate = base
    n = 1
    while candidate in used:
        n += 1
        candidate = f"{base}-{n}"
    used.add(candidate)
    return candidate


def import_project(data: ProjectImport, user_id: int, db: Session) -> tuple[Project, dict[str, int]]:
    """Crea el proyecto y todo su árbol en una sola transacción.

    Devuelve el proyecto creado y el conteo de items creados por tipo.
    """
    slug = _unique_project_slug(data.name, user_id, db)
    project = Project(
        name=data.name,
        slug=slug,
        description=data.description,
        tech_stack=data.tech_stack,
        status=data.status,
        notes=data.notes,
        user_id=user_id,
    )
    db.add(project)
    db.flush()

    for cmd in data.commands:
        db.add(Command(project_id=project.id, label=cmd.label, command=cmd.command, order=cmd.order, type=cmd.type))

    for ev in data.env_vars:
        db.add(EnvVariable(project_id=project.id, key=ev.key, value=ev.value or None, description=ev.description))

    for link in data.links:
        db.add(QuickLink(project_id=project.id, label=link.label, url=link.url, category=link.category))

    repo_cmd_count = 0
    repo_env_count = 0
    used_repo_slugs: set[str] = set()
    for r in data.repos:
        repo = Repo(
            project_id=project.id,
            name=r.name,
            slug=_unique_repo_slug(r.name, used_repo_slugs),
            local_path=r.local_path,
            github_url=r.github_url,
            description=r.description,
        )
        db.add(repo)
        db.flush()
        for cmd in r.commands:
            db.add(Command(
                project_id=project.id, repo_id=repo.id,
                label=cmd.label, command=cmd.command, order=cmd.order, type=cmd.type,
            ))
            repo_cmd_count += 1
        for ev in r.env_vars:
            db.add(EnvVariable(
                project_id=project.id, repo_id=repo.id,
                key=ev.key, value=ev.value or None, description=ev.description,
            ))
            repo_env_count += 1

    for svc in data.services:
        db.add(Service(
            user_id=user_id, project_id=project.id,
            name=svc.name, url=svc.url, category=svc.category, notes=svc.notes,
        ))

    db.commit()
    db.refresh(project)

    counts = {
        "commands": len(data.commands) + repo_cmd_count,
        "env_vars": len(data.env_vars) + repo_env_count,
        "links": len(data.links),
        "repos": len(data.repos),
        "services": len(data.services),
    }
    logger.info("Proyecto importado: '%s' (user=%d) %s", project.slug, user_id, counts)
    return project, counts

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Project

logger = logging.getLogger(__name__)


def get_project_or_404(slug: str, db: Session) -> Project:
    project = db.query(Project).filter(Project.slug == slug).first()
    if not project:
        logger.warning("Proyecto no encontrado: '%s'", slug)
        raise HTTPException(status_code=404, detail=f"Proyecto '{slug}' no encontrado")
    return project

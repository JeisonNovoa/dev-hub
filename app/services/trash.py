"""Purga de items expirados de la papelera.

Credenciales y proyectos en papelera (deleted_at != None) se eliminan
permanentemente tras TRASH_RETENTION_DAYS. Antes estas funciones vivían en
routers/ui/credentials.py y routers/ui/dashboard.py como privadas; un router
importando privados de otro router es señal de que pertenecen a un service.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Credential, Project

logger = logging.getLogger(__name__)


def purge_expired_credentials(db: Session) -> int:
    """Elimina permanentemente credenciales que llevan en papelera > retención."""
    from app.models.credential import TRASH_RETENTION_DAYS

    cutoff = datetime.now(timezone.utc) - timedelta(days=TRASH_RETENTION_DAYS)
    expired = db.query(Credential).filter(
        Credential.deleted_at.isnot(None), Credential.deleted_at < cutoff
    )
    count = expired.count()
    if count:
        expired.delete(synchronize_session=False)
        db.commit()
        logger.info("Papelera: %d credencial(es) expirada(s) eliminada(s) permanentemente", count)
    return count


def purge_expired_projects(db: Session) -> int:
    """Elimina permanentemente proyectos que llevan en papelera > retención."""
    from app.models.project import TRASH_RETENTION_DAYS

    cutoff = datetime.now(timezone.utc) - timedelta(days=TRASH_RETENTION_DAYS)
    expired = (
        db.query(Project)
        .filter(Project.deleted_at.isnot(None), Project.deleted_at < cutoff)
        .all()
    )
    count = len(expired)
    for project in expired:
        db.delete(project)
    if count:
        db.commit()
        logger.info("Papelera: %d proyecto(s) expirado(s) eliminado(s) permanentemente", count)
    return count

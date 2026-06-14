from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.common import Base


class ProjectEvent(Base):
    """Evento de actividad de un proyecto (timeline del detalle).

    Se registra automáticamente al crear/editar/borrar comandos, env vars, repos,
    links, servicios y credenciales, además de cambios en el proyecto mismo.
    No usa TimestampMixin: solo importa el instante en que ocurrió (created_at).
    """

    __tablename__ = "project_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # action: created | updated | deleted (verbo del evento)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    # entity: project | command | env_var | repo | link | service | credential
    entity: Mapped[str] = mapped_column(String(20), nullable=False)
    # Descripción legible ya formada, p. ej. "Agregó env var SUPABASE_URL".
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    project: Mapped["Project"] = relationship()  # type: ignore[name-defined]

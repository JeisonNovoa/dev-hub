from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.common import Base, TimestampMixin


class Service(Base, TimestampMixin):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30), default="other", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    project: Mapped["Project | None"] = relationship(back_populates="services")  # type: ignore[name-defined]
    credentials: Mapped[list["Credential"]] = relationship(back_populates="service")  # type: ignore[name-defined]

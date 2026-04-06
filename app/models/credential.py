from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.crypto import EncryptedText
from app.models.common import Base, TimestampMixin

TRASH_RETENTION_DAYS = 30


class Credential(Base, TimestampMixin):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    password: Mapped[str | None] = mapped_column(EncryptedText)
    url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20), default="project", nullable=False)
    login_via: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    service: Mapped["Service | None"] = relationship(back_populates="credentials")  # type: ignore[name-defined]
    project: Mapped["Project | None"] = relationship(back_populates="credentials")  # type: ignore[name-defined]

    @property
    def days_until_purge(self) -> int | None:
        if self.deleted_at is None:
            return None
        now = datetime.now(timezone.utc)
        deleted = self.deleted_at if self.deleted_at.tzinfo else self.deleted_at.replace(tzinfo=timezone.utc)
        return max(0, (deleted + timedelta(days=TRASH_RETENTION_DAYS) - now).days)

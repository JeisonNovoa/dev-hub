from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.crypto import EncryptedText
from app.models.common import Base, TimestampMixin


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

    service: Mapped["Service | None"] = relationship(back_populates="credentials")  # type: ignore[name-defined]
    project: Mapped["Project | None"] = relationship(back_populates="credentials")  # type: ignore[name-defined]

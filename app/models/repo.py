from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.common import Base, TimestampMixin


class Repo(Base, TimestampMixin):
    __tablename__ = "repos"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_project_repo_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    local_path: Mapped[str | None] = mapped_column(Text)
    github_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    project: Mapped["Project"] = relationship(back_populates="repos")  # type: ignore[name-defined]
    commands: Mapped[list["Command"]] = relationship(  # type: ignore[name-defined]
        back_populates="repo",
        foreign_keys="Command.repo_id",
        order_by="Command.order",
    )
    env_vars: Mapped[list["EnvVariable"]] = relationship(  # type: ignore[name-defined]
        back_populates="repo",
        foreign_keys="EnvVariable.repo_id",
        order_by="EnvVariable.key",
    )

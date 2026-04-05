from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.common import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    env_vars: Mapped[list["EnvVariable"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="EnvVariable.key",
        foreign_keys="EnvVariable.project_id",
    )
    commands: Mapped[list["Command"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Command.order",
        foreign_keys="Command.project_id",
    )
    links: Mapped[list["QuickLink"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    repos: Mapped[list["Repo"]] = relationship(  # type: ignore[name-defined]
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Repo.name",
    )
    services: Mapped[list["Service"]] = relationship(back_populates="project")  # type: ignore[name-defined]
    credentials: Mapped[list["Credential"]] = relationship(back_populates="project")  # type: ignore[name-defined]


class EnvVariable(Base, TimestampMixin):
    __tablename__ = "env_variables"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    repo_id: Mapped[int | None] = mapped_column(
        ForeignKey("repos.id", ondelete="SET NULL"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    project: Mapped["Project"] = relationship(
        back_populates="env_vars", foreign_keys=[project_id]
    )
    repo: Mapped["Repo | None"] = relationship(  # type: ignore[name-defined]
        back_populates="env_vars", foreign_keys="EnvVariable.repo_id"
    )


class Command(Base, TimestampMixin):
    __tablename__ = "commands"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    repo_id: Mapped[int | None] = mapped_column(
        ForeignKey("repos.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="other", nullable=False)

    project: Mapped["Project"] = relationship(
        back_populates="commands", foreign_keys=[project_id]
    )
    repo: Mapped["Repo | None"] = relationship(  # type: ignore[name-defined]
        back_populates="commands", foreign_keys="Command.repo_id"
    )


class QuickLink(Base, TimestampMixin):
    __tablename__ = "quick_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="other", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="links")

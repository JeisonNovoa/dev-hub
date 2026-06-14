"""Helpers de presentación para el dashboard de proyectos.

Decoran cada proyecto con datos derivados que el template necesita pero que no
viven en el modelo: texto de actividad relativo ("hoy", "hace 3 días"), el
comando de inicio para el botón "start" y el link de producción para abrir prod.
Se mantienen aquí (no en el template) para que la lógica sea testeable y los
templates queden declarativos.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.project import Project

# Prioridad de links para el botón "abrir" rápido de cada card/fila.
_PRIMARY_LINK_ORDER = ("prod", "staging", "dashboard", "docs", "repo", "other")


def relative_activity(moment: datetime | None) -> str:
    """Texto humano de actividad: 'hoy', 'ayer', 'hace N días/semanas/meses'."""
    if moment is None:
        return "—"
    now = datetime.now(timezone.utc)
    aware = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    days = (now.date() - aware.date()).days
    if days <= 0:
        return "hoy"
    if days == 1:
        return "ayer"
    if days < 7:
        return f"hace {days} días"
    if days < 30:
        weeks = days // 7
        return f"hace {weeks} sem" if weeks == 1 else f"hace {weeks} sems"
    if days < 365:
        months = days // 30
        return f"hace {months} mes" if months == 1 else f"hace {months} meses"
    years = days // 365
    return f"hace {years} año" if years == 1 else f"hace {years} años"


def is_recent(moment: datetime | None, *, within_days: int = 7) -> bool:
    if moment is None:
        return False
    now = datetime.now(timezone.utc)
    aware = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return (now - aware).days < within_days


def start_command(project: Project) -> str | None:
    """Primer comando de inicio del proyecto (type='start'), si existe."""
    starts = [c for c in project.commands if c.type == "start"]
    chosen = min(starts, key=lambda c: c.order) if starts else None
    return chosen.command if chosen else None


def primary_link(project: Project):
    """Link más relevante para abrir rápido (prioriza prod, luego staging…)."""
    if not project.links:
        return None
    by_priority = sorted(
        project.links,
        key=lambda link: _PRIMARY_LINK_ORDER.index(link.category)
        if link.category in _PRIMARY_LINK_ORDER
        else len(_PRIMARY_LINK_ORDER),
    )
    return by_priority[0]


@dataclass(frozen=True)
class ProjectView:
    """Vista lista para el template: el proyecto más sus campos derivados."""

    project: Project
    activity: str
    recent: bool
    start: str | None
    primary_url: str | None
    primary_label: str | None
    n_repos: int
    n_cmds: int
    n_envs: int
    n_links: int


def decorate(project: Project) -> ProjectView:
    link = primary_link(project)
    return ProjectView(
        project=project,
        activity=relative_activity(project.updated_at),
        recent=is_recent(project.updated_at),
        start=start_command(project),
        primary_url=link.url if link else None,
        primary_label=link.category if link else None,
        n_repos=len(project.repos),
        n_cmds=len(project.commands),
        n_envs=len(project.env_vars),
        n_links=len(project.links),
    )

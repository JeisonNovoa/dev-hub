"""Tests unitarios puros (sin BD) de app/utils/.

Cubre: app/utils/activity.py (build_summary) y app/utils/projects.py
(relative_activity, is_recent, start_command, primary_link).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.utils.activity import build_summary
from app.utils.projects import (
    is_recent,
    primary_link,
    relative_activity,
    start_command,
)


# ─── activity.build_summary ─────────────────────────────────────────────────

def test_build_summary_project_created():
    assert build_summary("created", "project", None) == "Creó el proyecto"


def test_build_summary_project_updated():
    assert build_summary("updated", "project", None) == "Editó el proyecto"


def test_build_summary_command_with_name():
    assert build_summary("created", "command", "npm start") == "Agregó comando npm start"


def test_build_summary_truncates_long_names():
    long = "x" * 500
    summary = build_summary("created", "command", long)
    assert len(summary) <= 255


def test_build_summary_unknown_entity_uses_raw():
    # Entidad no listada: usa el string crudo como label.
    assert build_summary("updated", "x_entity", None) == "Editó x_entity"


# ─── projects.relative_activity ──────────────────────────────────────────────

def test_relative_activity_none():
    assert relative_activity(None) == "—"


def test_relative_activity_today():
    now = datetime.now(timezone.utc)
    assert relative_activity(now) == "hoy"


def test_relative_activity_yesterday():
    now = datetime.now(timezone.utc) - timedelta(days=1)
    assert relative_activity(now) == "ayer"


def test_relative_activity_days():
    now = datetime.now(timezone.utc) - timedelta(days=3)
    assert relative_activity(now) == "hace 3 días"


def test_relative_activity_weeks():
    now = datetime.now(timezone.utc) - timedelta(days=14)
    assert relative_activity(now) == "hace 2 sems"


def test_relative_activity_months():
    now = datetime.now(timezone.utc) - timedelta(days=60)
    assert relative_activity(now) == "hace 2 meses"


def test_relative_activity_years():
    now = datetime.now(timezone.utc) - timedelta(days=400)
    assert relative_activity(now) == "hace 1 año"


# ─── projects.is_recent ─────────────────────────────────────────────────────

def test_is_recent_true():
    now = datetime.now(timezone.utc)
    assert is_recent(now) is True


def test_is_recent_false_for_old():
    old = datetime.now(timezone.utc) - timedelta(days=30)
    assert is_recent(old) is False


def test_is_recent_none_is_false():
    assert is_recent(None) is False


def test_is_recent_custom_window():
    past = datetime.now(timezone.utc) - timedelta(days=10)
    assert is_recent(past, within_days=15) is True
    assert is_recent(past, within_days=5) is False


# ─── projects.start_command ─────────────────────────────────────────────────

def _cmd(order: int, type_: str, command: str):
    return SimpleNamespace(order=order, type=type_, command=command)


def test_start_command_picks_first_by_order():
    project = SimpleNamespace(commands=[_cmd(2, "start", "make up"), _cmd(1, "start", "npm start")])
    assert start_command(project) == "npm start"


def test_start_command_no_starts():
    project = SimpleNamespace(commands=[_cmd(1, "test", "pytest")])
    assert start_command(project) is None


def test_start_command_empty():
    project = SimpleNamespace(commands=[])
    assert start_command(project) is None


# ─── projects.primary_link ──────────────────────────────────────────────────

def _link(category: str, url: str):
    return SimpleNamespace(category=category, url=url)


def test_primary_link_prefers_prod_over_staging():
    project = SimpleNamespace(links=[
        _link("staging", "https://stg.x.com"),
        _link("prod", "https://x.com"),
    ])
    assert primary_link(project).url == "https://x.com"


def test_primary_link_no_links():
    project = SimpleNamespace(links=[])
    assert primary_link(project) is None


def test_primary_link_unknown_category_goes_last():
    project = SimpleNamespace(links=[
        _link("custom", "https://custom.com"),
        _link("docs", "https://docs.x.com"),
    ])
    # docs tiene prioridad definida (3er lugar); custom no → custom va último.
    assert primary_link(project).url == "https://docs.x.com"

"""Build a Router for CLI/API use from the project config, profile and overrides."""

from __future__ import annotations

from typing import Any

from tizita.events import default_bus
from tizita.providers.profiles import load_selection
from tizita.providers.registry import Registry, load_env
from tizita.providers.router import Router
from tizita.runlog import RunLog
from tizita.util import Project


def make_router(
    project: Project,
    profile: str | None = None,
    overrides: list[str] | None = None,
    console: Any = None,
    run_id: str | None = None,
) -> Router:
    env = load_env(project)
    registry = Registry.load(project, env)
    sel = load_selection(project, env, profile, overrides)
    runlog = RunLog(project.runs, run_id=run_id, profile=sel.profile)
    bus = default_bus(project, runlog.run_id, console)
    return Router(registry, sel, project=project, runlog=runlog, bus=bus)

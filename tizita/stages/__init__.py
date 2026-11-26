"""Stage handlers. Each module exposes `run(ctx, unit, key) -> Outcome`; `HANDLERS` maps stage
name -> handler for the stages implemented so far (the runner skips the rest)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tizita.cache import Manifest


@dataclass
class Ctx:
    sb: dict
    project: Any  # tizita.util.Project
    router: Any  # tizita.providers.router.Router
    manifest: Manifest
    bus: Any


@dataclass
class Outcome:
    path: Path
    provider: dict | None = None  # {"name","model","params"} of the provider actually used
    is_fallback: bool = False
    primary_provider: str | None = None
    calls: int = 0  # provider calls made (0 for pure deterministic stages)
    candidates: list[Path] | None = None  # multi-candidate artifacts (references, music)


def _handlers() -> dict[str, Callable[[Ctx, Any, str], Outcome]]:
    from tizita.stages import (
        assemble,
        keyframes,
        music,
        narration,
        qa,
        radio_cut,
        references,
        shots,
        subtitles,
        timing,
    )

    return {
        "narration": narration.run,
        "timing": timing.run,
        "subtitles": subtitles.run,
        "radio_cut": radio_cut.run,
        "references": references.run,
        "keyframes": keyframes.run,
        "shots": shots.run,
        "music": music.run,
        "assemble": assemble.run,
        "qa": qa.run,
    }


def handlers() -> dict[str, Callable[[Ctx, Any, str], Outcome]]:
    return _handlers()

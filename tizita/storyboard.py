"""Storyboard contract: load, JSON Schema validation, semantic lint (SPEC §5), config access."""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import asdict, dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator

from tizita.consent import consent_problem, load_registry
from tizita.util import PACKAGE_ROOT, Project

Level = Literal["error", "warning"]

# Ethiopic word space (U+1361) and full stop (U+1362) separate words too.
_WORD_SPLIT = re.compile(r"[\s፡።፣፤፥፦]+")


@dataclass
class Issue:
    level: Level
    code: str
    path: str
    message: str


@dataclass
class LintReport:
    issues: list[Issue] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, level: Level, code: str, path: str, message: str) -> None:
        self.issues.append(Issue(level, code, path, message))

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "issues": [asdict(i) for i in self.issues],
            "stats": self.stats,
        }


# ---------------------------------------------------------------- loading


def load_storyboard(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@cache
def _schema_validator(schema_path: str) -> Draft202012Validator:
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def storyboard_validator() -> Draft202012Validator:
    return _schema_validator(str(PACKAGE_ROOT / "schema" / "storyboard.schema.json"))


def validate_schema(data: dict) -> list[Issue]:
    issues = []
    for err in sorted(storyboard_validator().iter_errors(data), key=lambda e: list(e.path)):
        path = "/".join(str(p) for p in err.path) or "(root)"
        issues.append(Issue("error", "schema", path, err.message))
    return issues


def load_config(project: Project, name: str) -> dict:
    """config/<name>.yaml, falling back to the package copy, then {}."""
    for base in (project.config, PACKAGE_ROOT / "config"):
        p = base / f"{name}.yaml"
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


# ---------------------------------------------------------------- helpers


def count_words(text: str) -> int:
    return sum(1 for t in _WORD_SPLIT.split(text or "") if any(c.isalnum() for c in t))


def wrap_subtitle(text: str, width: int) -> list[str]:
    return textwrap.wrap(text or "", width=width, break_long_words=False) or [""]


def planned_total_s(sb: dict) -> float:
    return round(
        sum(float(s["duration_s"]) for s in sb["shots"]) + float(sb["end_card"]["duration_s"]), 3
    )


def i2v_shots(sb: dict) -> list[str]:
    return [s["id"] for s in sb["shots"] if s["motion"]["mode"] == "i2v"]


# ---------------------------------------------------------------- lint (SPEC §5.2)


def lint(
    sb: dict,
    project: Project,
    *,
    measured: dict | None = None,
    registry: dict[str, dict] | None = None,
) -> LintReport:
    """Schema first; semantic rules only run on a schema-valid storyboard.

    `measured` (from the timing stage, M2) may hold `total_s` and `narration_s: {shot: secs}`;
    when present, measured values replace the planned estimates.
    """
    report = LintReport()
    report.issues.extend(validate_schema(sb))
    if report.errors:
        return report

    pipeline = load_config(project, "pipeline")
    assembly = load_config(project, "assembly")
    registry = load_registry(project.consents) if registry is None else registry
    measured = measured or {}
    shots = sb["shots"]

    # shot count + ids + reasons
    lo, hi = pipeline.get("shots", {}).get("min", 8), pipeline.get("shots", {}).get("max", 12)
    if not lo <= len(shots) <= hi:
        report.add("error", "shot_count", "shots", f"{len(shots)} shots; need {lo}-{hi}.")
    _unique(report, "shots", [s["id"] for s in shots])
    _unique(report, "references", [r["id"] for r in sb["references"]])
    _unique(report, "music.cues", [c["id"] for c in sb["music"]["cues"]])
    for s in shots:
        if len(s["reason"].strip()) < 10:
            report.add(
                "error",
                "reason_short",
                f"shots[{s['id']}].reason",
                "Every shot needs a reason of at least 10 characters (why this shot exists).",
            )

    # durations
    dmin, dmax = (
        pipeline.get("duration_s", {}).get("min", 60),
        pipeline.get("duration_s", {}).get("max", 90),
    )
    total = planned_total_s(sb)
    report.stats["planned_total_s"] = total
    if not dmin <= total <= dmax:
        report.add(
            "error",
            "planned_total",
            "shots[].duration_s",
            f"Planned total {total:.1f} s (shots + end card) is outside {dmin}-{dmax} s.",
        )
    if "total_s" in measured:
        m = float(measured["total_s"])
        report.stats["measured_total_s"] = m
        if not dmin <= m <= dmax:
            report.add(
                "error",
                "measured_total",
                "timing",
                f"Measured total {m:.1f} s is outside {dmin}-{dmax} s. Trim narration or shots.",
            )

    # narration pace (warning)
    limit = float(sb["voice"]["pace_wps_limit"])
    narr_measured = measured.get("narration_s", {})
    for s in shots:
        words = count_words(s["narration"]["text_am"])
        secs = float(narr_measured.get(s["id"], s["duration_s"]))
        basis = "measured audio" if s["id"] in narr_measured else "planned duration"
        if words and secs > 0 and words / secs > limit:
            report.add(
                "warning",
                "pace",
                f"shots[{s['id']}].narration.text_am",
                f"{words} words in {secs:.1f} s ({basis}) = {words / secs:.2f} w/s "
                f"> limit {limit}. Shorten the line or lengthen the shot.",
            )

    # cross references
    characters = sb["style"]["characters"]
    ref_ids = {r["id"] for r in sb["references"]}
    cue_ids = {c["id"] for c in sb["music"]["cues"]}
    for name, ch in characters.items():
        if ch.get("reference_id") and ch["reference_id"] not in ref_ids:
            report.add(
                "error",
                "unknown_reference",
                f"style.characters.{name}.reference_id",
                f"Reference {ch['reference_id']!r} does not exist.",
            )
    for s in shots:
        for c in s.get("characters", []):
            if c not in characters:
                report.add(
                    "error",
                    "unknown_character",
                    f"shots[{s['id']}].characters",
                    f"Character {c!r} is not defined in style.characters.",
                )
        for r in s.get("references", []):
            if r not in ref_ids:
                report.add(
                    "error",
                    "unknown_reference",
                    f"shots[{s['id']}].references",
                    f"Reference {r!r} does not exist.",
                )
        if s.get("music_cue") and s["music_cue"] not in cue_ids:
            report.add(
                "error",
                "unknown_cue",
                f"shots[{s['id']}].music_cue",
                f"Music cue {s['music_cue']!r} does not exist.",
            )

    # consent (hard error)
    for r in sb["references"]:
        if problem := consent_problem(r, registry):
            report.add("error", "consent", f"references[{r['id']}]", problem)

    # uploads
    for s in shots:
        kf = s["keyframe"]
        if kf["source"] == "upload":
            up = kf.get("upload_path")
            if not up or not (project.root / up).is_file():
                report.add(
                    "error",
                    "upload_missing",
                    f"shots[{s['id']}].keyframe.upload_path",
                    f"keyframe.source is 'upload' but {up!r} does not exist.",
                )

    # subtitle fit (warning)
    subs = assembly.get("subtitles", {})
    width, max_lines = int(subs.get("max_chars_per_line", 40)), int(subs.get("max_lines", 2))
    for s in shots:
        lines = wrap_subtitle(s["narration"]["text_en"], width)
        if len(lines) > max_lines:
            report.add(
                "warning",
                "subtitle_fit",
                f"shots[{s['id']}].narration.text_en",
                f"Subtitle wraps to {len(lines)} lines at {width} chars (max {max_lines}).",
            )

    # i2v vs GPU budget (warning)
    gpu = pipeline.get("gpu", {})
    n_i2v = len(i2v_shots(sb))
    est_min = n_i2v * float(gpu.get("minutes_per_i2v_shot", 6))
    report.stats.update({"i2v_shots": n_i2v, "est_gpu_minutes": est_min})
    max_shots = gpu.get("max_i2v_shots")
    budget_min = gpu.get("budget_minutes")
    if (max_shots is not None and n_i2v > max_shots) or (
        budget_min is not None and est_min > budget_min
    ):
        report.add(
            "warning",
            "gpu_budget",
            "shots[].motion.mode",
            f"{n_i2v} i2v shots ≈ {est_min:.0f} GPU min; budget is {max_shots} shots / "
            f"{budget_min} min. Switch some shots to kenburns.",
        )

    report.stats["shots"] = len(shots)
    return report


def _unique(report: LintReport, path: str, ids: list[str]) -> None:
    seen: set[str] = set()
    for i in ids:
        if i in seen:
            report.add("error", "duplicate_id", path, f"Duplicate id {i!r}.")
        seen.add(i)

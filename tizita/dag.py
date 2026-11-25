"""Stage graph, per-stage field declarations, dirty detection and `tizita plan` (SPEC §6).

Each stage declares exactly which storyboard fields it reads (`fields`) and which upstream
artifacts it consumes (`upstream`). Only those enter its cache key, so editing one narration line
dirties one TTS unit plus the deterministic project stages downstream, and nothing else.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tizita.cache import Manifest, ManifestEntry, cache_key, field_hashes, provider_ident
from tizita.storyboard import load_config
from tizita.util import Project, sha256_file

PROJECT = "project"

# Bump a stage's version when its code changes what it produces.
STAGE_VERSIONS: dict[str, int] = {
    "narration": 1,
    "timing": 1,
    "subtitles": 1,
    "radio_cut": 1,
    "references": 1,
    "keyframes": 1,
    "shots": 1,
    "music": 1,
    "assemble": 1,
    "qa": 1,
}

# Topological order (SPEC §6.1 dependency order). `director` is interactive and not planned.
STAGE_ORDER = [
    "narration",
    "timing",
    "subtitles",
    "radio_cut",
    "references",
    "keyframes",
    "shots",
    "music",
    "assemble",
    "qa",
]


@dataclass(frozen=True)
class UpRef:
    stage: str
    unit: str
    chosen: int | None = None  # pick one candidate of a multi-candidate artifact

    @property
    def id(self) -> str:
        return Manifest.id(self.stage, self.unit)


@dataclass
class Unit:
    stage: str
    unit: str
    fields: dict[str, Any]
    upstream: list[UpRef] = field(default_factory=list)
    capability: str | None = None  # None = deterministic (FFmpeg / pure Python)
    seed: int | None = None
    est_latency_s: float = 0.0
    est_gpu_min: float = 0.0
    unverifiable: set[str] = field(default_factory=set)  # e.g. private photos absent in a clone
    note: str = ""

    @property
    def id(self) -> str:
        return Manifest.id(self.stage, self.unit)


@dataclass
class PlannedProvider:
    name: str
    model: str | None
    tier: str
    chain: list[str]  # every provider id the unit may use under the active profile
    label: str | None = None
    hint: str | None = None
    params: dict = field(default_factory=dict)


# (capability, unit) -> PlannedProvider | None. The router supplies one (feat/providers).
Resolver = Callable[[str, Unit], PlannedProvider | None]


# ---------------------------------------------------------------- unit declarations


def _file_field(project: Project, rel: str | None) -> dict:
    if not rel:
        return {"path": None, "sha256": None}
    p = project.root / rel
    return {"path": rel, "sha256": sha256_file(p) if p.is_file() else None}


def build_units(sb: dict, project: Project) -> list[Unit]:
    """Every plannable unit, in topological order."""
    pipe = load_config(project, "pipeline")
    est = pipe.get("stage_estimates", {})
    gpu = pipe.get("gpu", {})
    assembly = load_config(project, "assembly")
    shots = sb["shots"]
    ids = [s["id"] for s in shots]
    voice = sb["voice"]
    style = sb["style"]
    refs = {r["id"]: r for r in sb["references"]}

    def lat(stage: str, key: str = "latency_s") -> float:
        return float(est.get(stage, {}).get(key, 0))

    units: list[Unit] = []

    # narration: one TTS call per shot
    for s in shots:
        units.append(
            Unit(
                "narration",
                s["id"],
                {
                    "narration.text_am": s["narration"]["text_am"],
                    "meta.narration_language": sb["meta"]["narration_language"],
                    "voice.provider_pref": voice["provider_pref"],
                    "voice.voice_name": voice["voice_name"],
                    "voice.style_instruction": voice["style_instruction"],
                },
                capability="tts",
                est_latency_s=lat("narration"),
            )
        )

    narr_up = [UpRef("narration", i) for i in ids]
    timing_fields: dict[str, Any] = {"shots.order": ids}
    for s in shots:
        timing_fields[f"shots[{s['id']}].duration_s"] = s["duration_s"]
        timing_fields[f"shots[{s['id']}].transition_in"] = s["transition_in"]
    timing_fields["end_card.duration_s"] = sb["end_card"]["duration_s"]
    units.append(Unit("timing", PROJECT, timing_fields, narr_up, est_latency_s=lat("timing")))

    sub_fields: dict[str, Any] = {
        f"shots[{s['id']}].text_en": s["narration"]["text_en"] for s in shots
    }
    sub_fields["end_card.text_en"] = sb["end_card"]["text_en"]
    sub_fields["assembly.subtitles"] = assembly.get("subtitles", {})
    units.append(
        Unit(
            "subtitles",
            PROJECT,
            sub_fields,
            [UpRef("timing", PROJECT)],
            est_latency_s=lat("subtitles"),
        )
    )

    units.append(
        Unit(
            "radio_cut",
            PROJECT,
            {"assembly": assembly},
            [UpRef("timing", PROJECT), UpRef("subtitles", PROJECT), *narr_up],
            est_latency_s=lat("radio_cut"),
        )
    )

    # references: one sheet (N candidates) per reference
    for r in sb["references"]:
        photos = [_file_field(project, p) for p in r.get("photos", [])]
        unverifiable = {"photos"} if any(p["sha256"] is None for p in photos) else set()
        units.append(
            Unit(
                "references",
                r["id"],
                {
                    "kind": r["kind"],
                    "description": r["description"],
                    "photos": photos,
                    "sheet.candidates": r["sheet"]["candidates"],
                    "style.style_block": style["style_block"],
                    "style.character_defaults": style["character_defaults"],
                },
                capability="image",
                seed=r["sheet"]["seed"],
                est_latency_s=lat("references") * r["sheet"]["candidates"],
                unverifiable=unverifiable,
            )
        )

    # keyframes: one per shot, conditioned on chosen golden references
    for s in shots:
        kf = s["keyframe"]
        f: dict[str, Any] = {
            "keyframe.source": kf["source"],
            "keyframe.prompt": kf["prompt"],
            "keyframe.candidates": kf.get("candidates", 1),
            "keyframe.upload": _file_field(project, kf.get("upload_path"))
            if kf["source"] == "upload"
            else None,
            "style.style_block": style["style_block"],
            "style.negative": style["negative"],
        }
        if s.get("characters"):
            f["style.character_defaults"] = style["character_defaults"]
        for c in s.get("characters", []):
            ch = style["characters"].get(c, {})
            f[f"style.characters.{c}"] = {
                "description": ch.get("description"),
                "wardrobe": ch.get("wardrobe"),
            }
        up = [
            UpRef("references", r, refs[r]["sheet"]["chosen"])
            for r in s.get("references", [])
            if r in refs and refs[r]["sheet"].get("chosen") is not None
        ]
        units.append(
            Unit(
                "keyframes",
                s["id"],
                f,
                up,
                capability="image_edit" if kf["source"] == "upload" else "image",
                seed=kf["seed"],
                est_latency_s=lat("keyframes") * kf.get("candidates", 1),
            )
        )

    # shots: fixed-length clip per shot, independent of narration length
    for s in shots:
        m = s["motion"]
        i2v = m["mode"] == "i2v"
        units.append(
            Unit(
                "shots",
                s["id"],
                {
                    "motion.mode": m["mode"],
                    "motion.prompt": m.get("prompt", "") if i2v else None,
                    "motion.kenburns": m.get("kenburns", {}),
                },
                [UpRef("keyframes", s["id"])],
                capability="i2v" if i2v else None,
                seed=m["seed"] if i2v else None,
                est_latency_s=lat("shots", "i2v_latency_s") if i2v else lat("shots"),
                est_gpu_min=float(gpu.get("minutes_per_i2v_shot", 6)) if i2v else 0.0,
                note="" if i2v else m["mode"],
            )
        )

    music = sb["music"]
    units.append(
        Unit(
            "music",
            PROJECT,
            {f"music.{k}": v for k, v in music.items() if k not in ("chosen", "chosen_reason")},
            capability="music",
            seed=music["seed"],
            est_latency_s=lat("music"),
            est_gpu_min=float(est.get("music", {}).get("gpu_minutes", 0)),
        )
    )

    units.append(
        Unit(
            "assemble",
            PROJECT,
            {
                "assembly": assembly,
                "music.chosen": music.get("chosen"),
                "end_card": sb["end_card"],
                "shots.music_cue": {s["id"]: s.get("music_cue") for s in shots},
            },
            [
                UpRef("timing", PROJECT),
                UpRef("subtitles", PROJECT),
                *narr_up,
                *[UpRef("shots", i) for i in ids],
                UpRef("music", PROJECT, music.get("chosen")),
            ],
            est_latency_s=lat("assemble"),
        )
    )
    units.append(Unit("qa", PROJECT, {}, [UpRef("assemble", PROJECT)], est_latency_s=lat("qa")))

    order = {s: i for i, s in enumerate(STAGE_ORDER)}
    return sorted(units, key=lambda u: order[u.stage])


# ---------------------------------------------------------------- dirty detection


@dataclass
class PlanRow:
    stage: str
    unit: str
    status: str  # cached | dirty | missing | fallback-upgradable
    detail: str
    provider: str
    est_latency_s: float
    est_gpu_min: float

    @property
    def needs_work(self) -> bool:
        return self.status in ("dirty", "missing")


def resolve_upstream(unit: Unit, manifest: Manifest, fresh: set[str]) -> tuple[dict, list[str]]:
    """Upstream artifact hashes. An upstream unit that will regenerate makes this unit dirty."""
    shas: dict[str, str] = {}
    stale: list[str] = []
    for ref in unit.upstream:
        entry = manifest.get(ref.stage, ref.unit)
        if entry is None or ref.id not in fresh:
            stale.append(ref.id)
            continue
        try:
            shas[ref.id] = entry.artifact_sha(ref.chosen)
        except (IndexError, KeyError):
            stale.append(ref.id)
    return shas, stale


def unit_key(unit: Unit, upstream_shas: dict[str, str], provider: dict | None) -> str:
    return cache_key(
        unit.stage,
        STAGE_VERSIONS[unit.stage],
        unit.fields,
        upstream_shas,
        provider,
        unit.seed,
    )


def _status(
    unit: Unit,
    entry: ManifestEntry | None,
    project: Project,
    upstream_shas: dict[str, str],
    stale: list[str],
    planned: PlannedProvider | None,
) -> tuple[str, str]:
    if entry is None:
        return "missing", "never generated"
    reasons: list[str] = []
    if entry.stage_version != STAGE_VERSIONS[unit.stage]:
        reasons.append(f"stage_version {entry.stage_version}→{STAGE_VERSIONS[unit.stage]}")
    now = field_hashes(unit.fields)
    changed = sorted(
        k
        for k in set(now) | set(entry.field_hashes)
        if k not in unit.unverifiable and now.get(k) != entry.field_hashes.get(k)
    )
    reasons += changed
    if entry.seed != unit.seed:
        reasons.append("seed")
    reasons += [f"upstream {s}" for s in stale]
    reasons += sorted(
        f"upstream {k}" for k, v in upstream_shas.items() if entry.upstream.get(k) != v
    )
    if set(entry.upstream) - set(upstream_shas) - set(stale):
        reasons.append("upstream set changed")
    used = (entry.provider or {}).get("name")
    if planned is not None and used is not None and used not in planned.chain:
        reasons.append(f"provider {used} not in active chain")
    if not (project.root / entry.path).exists():
        return "missing", "artifact file gone"
    if reasons:
        return "dirty", ", ".join(reasons)
    if (
        entry.is_fallback
        and planned is not None
        and entry.primary_provider == planned.name
        and used != planned.name
    ):
        return "fallback-upgradable", f"made by fallback {used}; {planned.name} available"
    return "cached", ""


def plan(
    sb: dict,
    project: Project,
    manifest: Manifest | None = None,
    resolver: Resolver | None = None,
) -> list[PlanRow]:
    manifest = manifest or Manifest.load(project.manifest)
    rows: list[PlanRow] = []
    fresh: set[str] = set()  # units whose current artifact stays valid this run
    for unit in build_units(sb, project):
        planned = resolver(unit.capability, unit) if (resolver and unit.capability) else None
        shas, stale = resolve_upstream(unit, manifest, fresh)
        entry = manifest.get(unit.stage, unit.unit)
        status, detail = _status(unit, entry, project, shas, stale, planned)
        if status in ("cached", "fallback-upgradable"):
            fresh.add(unit.id)
        if unit.capability is None:
            provider = f"deterministic ({unit.note})" if unit.note else "deterministic"
        elif planned is None:
            provider = f"({unit.capability} chain)"
        else:
            provider = planned.label or planned.name
            if planned.hint:
                detail = f"{detail}; {planned.hint}" if detail else planned.hint
        rows.append(
            PlanRow(
                unit.stage,
                unit.unit,
                status,
                detail,
                provider,
                unit.est_latency_s,
                unit.est_gpu_min,
            )
        )
    return rows


def summarize(rows: list[PlanRow]) -> dict:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    work = [r for r in rows if r.needs_work]
    return {
        "units": len(rows),
        "counts": counts,
        "to_run": len(work),
        "est_latency_s": round(sum(r.est_latency_s for r in work), 1),
        "est_gpu_min": round(sum(r.est_gpu_min for r in work), 1),
    }


def provider_ident_for(planned: PlannedProvider | None) -> dict | None:
    if planned is None:
        return None
    return provider_ident(planned.name, planned.model, planned.params)


def manifest_path_for(project: Project, unit: Unit, key: str, ext: str) -> Path:
    """outputs/<stage>/<unit>/<key>.<ext> (project-level stages drop the unit dir)."""
    base = project.outputs / unit.stage
    if unit.unit != PROJECT:
        base = base / unit.unit
    return base / f"{key}.{ext}"

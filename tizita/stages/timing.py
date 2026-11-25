"""timing: slot per shot from measured narration length (SPEC §10.1). Deterministic, no provider."""

from __future__ import annotations

import wave
from pathlib import Path

from tizita.dag import PROJECT, manifest_path_for
from tizita.stages import Ctx, Outcome
from tizita.storyboard import load_config
from tizita.util import atomic_write_json


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / float(w.getframerate())


def compute_timing(
    shots: list[dict], narr_s: dict[str, float], end_card_s: float, cfg: dict
) -> dict:
    """slot_i = max(duration, narr + lead + tail); slots overlap by the crossfade (0 for `cut`);
    the end card follows the last slot after a fade to black. Pure function."""
    lead, tail, xf = cfg["lead_s"], cfg["tail_s"], cfg["crossfade_s"]
    slots, cursor = [], 0.0
    for i, s in enumerate(shots):
        n = float(narr_s.get(s["id"], 0.0))
        dur = max(float(s["duration_s"]), n + lead + tail)
        overlap = 0.0 if i == 0 or s["transition_in"] == "cut" else xf
        start = round(cursor - overlap, 3)
        slots.append(
            {
                "id": s["id"],
                "start": start,
                "end": round(start + dur, 3),
                "duration": round(dur, 3),
                "planned": float(s["duration_s"]),
                "narration_s": round(n, 3),
                "narration_start": round(start + lead, 3),
                "narration_end": round(start + lead + n, 3),
                "transition_in": s["transition_in"],
            }
        )
        cursor = start + dur
    total = round(cursor + end_card_s, 3)
    return {
        "slots": slots,
        "end_card": {"start": round(cursor, 3), "duration": float(end_card_s)},
        "total_s": total,
        "narration_s": {k: round(float(v), 3) for k, v in narr_s.items()},
    }


def advice(timing: dict, lo: float = 60, hi: float = 90) -> str | None:
    t = timing["total_s"]
    if lo <= t <= hi:
        return None
    if t > hi:
        longest = max(timing["slots"], key=lambda s: s["narration_s"])
        return (
            f"total {t:.1f}s > {hi:.0f}s: trim {longest['id']} narration "
            f"(~{int((t - hi) * 2.3)} words) or shorten shot durations"
        )
    return f"total {t:.1f}s < {lo:.0f}s: lengthen shot durations by ~{(lo - t):.0f}s in total"


def load_timing(project, manifest) -> dict | None:
    import json

    e = manifest.get("timing", PROJECT)
    p = project.root / e.path if e else None
    return json.loads(p.read_text()) if p and p.is_file() else None


def measured_for_lint(project) -> dict | None:
    """`storyboard.lint(measured=...)` input from the timing artifact, if one exists."""
    from tizita.cache import Manifest

    t = load_timing(project, Manifest.load(project.manifest))
    return {"total_s": t["total_s"], "narration_s": t["narration_s"]} if t else None


def run(ctx: Ctx, unit, key: str) -> Outcome:
    narr = {}
    for s in ctx.sb["shots"]:
        e = ctx.manifest.get("narration", s["id"])
        narr[s["id"]] = wav_seconds(ctx.project.root / e.path) if e else 0.0
    t = compute_timing(
        ctx.sb["shots"],
        narr,
        ctx.sb["end_card"]["duration_s"],
        load_config(ctx.project, "assembly")["timing"],
    )
    if msg := advice(t):
        ctx.bus.emit("timing_out_of_range", stage="timing", unit=PROJECT, advice=msg)
    out = manifest_path_for(ctx.project, unit, key, "json")
    atomic_write_json(out, t)
    return Outcome(out)

"""shots: one clip per shot at the master size (1080x1920, 24 fps CFR).

`kenburns` / `still` shots are deterministic FFmpeg zoompan on the approved keyframe. `i2v` shots
use the i2v chain; while no i2v adapter is usable they degrade to Ken Burns (SPEC §10.9), which is
recorded as a fallback with the chain's primary provider so `plan` shows them as upgradable."""

from __future__ import annotations

import subprocess

from tizita.cache import provider_ident
from tizita.dag import manifest_path_for
from tizita.ffmpeg.graphs import kenburns_cmd
from tizita.stages import Ctx, Outcome
from tizita.storyboard import load_config


def kenburns_params(motion: dict, cfg: dict) -> dict:
    """The shot's own kenburns block, unless it is flat (i2v shots carry 1.0 -> 1.0, none)."""
    kb = motion.get("kenburns") or {}
    if motion["mode"] == "still":
        return dict(cfg["kenburns"]["still"])
    flat = kb.get("zoom_from", 1.0) == kb.get("zoom_to", 1.0) and kb.get("pan", "none") == "none"
    return dict(cfg["kenburns"]["fallback"]) if flat else dict(kb)


def render_kenburns(ctx: Ctx, image, kb: dict, duration_s: float, out) -> None:
    root = ctx.project.root
    cfg = load_config(ctx.project, "assembly")
    tmp = out.with_name(f"{out.stem}.tmp.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = kenburns_cmd(
        str(image.relative_to(root)), kb, duration_s, str(tmp.relative_to(root)), cfg
    )
    r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg kenburns failed: {r.stderr[-400:]}")
    tmp.replace(out)


def run(ctx: Ctx, unit, key: str) -> Outcome:
    shot = next(s for s in ctx.sb["shots"] if s["id"] == unit.unit)
    motion = shot["motion"]
    cfg = load_config(ctx.project, "assembly")
    kf = ctx.manifest.get("keyframes", unit.unit)
    image = ctx.project.root / kf.path
    out = manifest_path_for(ctx.project, unit, key, "mp4")
    kb = kenburns_params(motion, cfg)
    render_kenburns(ctx, image, kb, float(shot["duration_s"]), out)
    ident = provider_ident("kenburns", "ffmpeg-zoompan", kb)
    if motion["mode"] != "i2v":
        return Outcome(out, ident)
    chain = ctx.router.chain_ids("i2v")
    primary = chain[0] if chain else "i2v"
    ctx.bus.emit(
        "degraded",
        stage="shots",
        unit=unit.unit,
        reason="no usable i2v provider (Wan on Kaggle not run); Ken Burns of the keyframe",
        primary_provider=primary,
    )
    return Outcome(out, ident, is_fallback=True, primary_provider=primary)

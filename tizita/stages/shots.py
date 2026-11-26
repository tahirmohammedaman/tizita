"""shots: one clip per shot at the master size (1080x1920, 24 fps CFR).

`kenburns` / `still` shots are deterministic FFmpeg zoompan on the approved keyframe. `i2v` shots
use the i2v chain; when no i2v provider succeeds they degrade to Ken Burns (SPEC §10.9), which is
recorded as a fallback with the chain's primary provider so `plan` shows them as upgradable."""

from __future__ import annotations

import subprocess

from tizita.cache import provider_ident
from tizita.dag import manifest_path_for
from tizita.ffmpeg.graphs import i2v_normalise_cmd, kenburns_cmd
from tizita.providers.base import Request
from tizita.providers.errors import ChainExhausted
from tizita.stages import Ctx, Outcome
from tizita.storyboard import load_config
from tizita.util import atomic_write_bytes


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


def clip_seconds(planned_s: float, long_above_s: float) -> int:
    """Wan offers 5 s or 8 s. Assembly slows a short clip and then holds its last frame."""
    return 8 if planned_s > long_above_s else 5


def run_i2v(ctx: Ctx, unit, key: str, shot: dict, image, out, cfg: dict) -> Outcome:
    motion = shot["motion"]
    long_above = load_config(ctx.project, "pipeline")["gpu"]["i2v_long_clip_above_s"]
    seconds = clip_seconds(float(shot["duration_s"]), long_above)
    req = Request(
        capability="i2v",
        stage="shots",
        unit=unit.unit,
        prompt=motion["prompt"],
        params={"duration": seconds},
        seed=motion["seed"],
        inputs={"images": [str(image)]},
        cache_key=key,
    )
    result, prov, is_fb = ctx.router.call(req)
    raw = out.with_name(f"{key}_raw.mp4")
    atomic_write_bytes(raw, result.data)
    root = ctx.project.root
    tmp = out.with_name(f"{out.stem}.tmp.mp4")
    cmd = i2v_normalise_cmd(str(raw.relative_to(root)), str(tmp.relative_to(root)), cfg)
    r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg i2v normalise failed: {r.stderr[-400:]}")
    tmp.replace(out)
    chain = ctx.router.chain_ids("i2v")
    return Outcome(
        out,
        provider_ident(prov.name, result.model, prov.params),
        is_fb,
        chain[0] if chain else prov.name,
        calls=1,
    )


def run(ctx: Ctx, unit, key: str) -> Outcome:
    shot = next(s for s in ctx.sb["shots"] if s["id"] == unit.unit)
    motion = shot["motion"]
    cfg = load_config(ctx.project, "assembly")
    kf = ctx.manifest.get("keyframes", unit.unit)
    image = ctx.project.root / kf.path
    out = manifest_path_for(ctx.project, unit, key, "mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    if motion["mode"] == "i2v":
        try:
            return run_i2v(ctx, unit, key, shot, image, out, cfg)
        except ChainExhausted as e:
            reason = f"no i2v clip ({str(e)[:200]}); Ken Burns of the keyframe"
    kb = kenburns_params(motion, cfg)
    render_kenburns(ctx, image, kb, float(shot["duration_s"]), out)
    ident = provider_ident("kenburns", "ffmpeg-zoompan", kb)
    if motion["mode"] != "i2v":
        return Outcome(out, ident)
    chain = ctx.router.chain_ids("i2v")
    primary = chain[0] if chain else "i2v"
    ctx.bus.emit("degraded", stage="shots", unit=unit.unit, reason=reason, primary_provider=primary)
    return Outcome(out, ident, is_fallback=True, primary_provider=primary)

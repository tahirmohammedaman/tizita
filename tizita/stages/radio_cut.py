"""radio_cut: black 1080x1920 + narration + ducked synth pad + burned 9:16 subtitles
(SPEC §10.8). The pad is a logged `synth_pad` provider call."""

from __future__ import annotations

import subprocess

from tizita.cache import provider_ident
from tizita.dag import manifest_path_for
from tizita.ffmpeg.graphs import radio_cut_cmd
from tizita.providers.base import Request
from tizita.stages import Ctx, Outcome
from tizita.stages.subtitles import ass_path_for
from tizita.stages.timing import load_timing
from tizita.storyboard import load_config


def run(ctx: Ctx, unit, key: str) -> Outcome:
    root = ctx.project.root
    cfg = load_config(ctx.project, "assembly")
    timing = load_timing(ctx.project, ctx.manifest)
    total = timing["total_s"]
    narr = [root / ctx.manifest.get("narration", s["id"]).path for s in timing["slots"]]
    starts = [s["narration_start"] for s in timing["slots"]]
    srt = root / ctx.manifest.get("subtitles", "project").path
    ass = ass_path_for(srt, "9x16")

    pad_path = ctx.project.state / "tmp" / f"pad_{key}.wav"
    result = ctx.router.call_one(
        "synth_pad",
        Request(
            capability="music",
            stage="radio_cut",
            unit=unit.unit,
            params={"duration_s": total},
            cache_key=key,
            output_path=pad_path,
        ),
    )
    out = manifest_path_for(ctx.project, unit, key, "mp4")
    tmp = out.with_name(f"{out.stem}.tmp.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = radio_cut_cmd(
        [str(p.relative_to(root)) for p in narr],
        starts,
        str(pad_path.relative_to(root)),
        str(ass.relative_to(root)),
        cfg["subtitles"]["fonts_dir"],
        total,
        str(tmp.relative_to(root)),
        cfg,
    )
    r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg radio cut failed: {r.stderr[-400:]}")
    tmp.replace(out)
    pad_path.unlink(missing_ok=True)
    return Outcome(out, provider_ident("ffmpeg", None, {}), False, None, calls=1 if result else 0)

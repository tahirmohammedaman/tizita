"""assemble: shots + narration + music + subtitles -> film_9x16.mp4 and film_16x9.mp4
(SPEC §10). Every degradation (missing clip/keyframe/music) is an event and is listed in
`assemble.json`; a rough cut always renders."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from tizita.audio import wav_speech_end_s
from tizita.cache import provider_ident
from tizita.dag import PROJECT
from tizita.ffmpeg import graphs as G
from tizita.stages import Ctx, Outcome
from tizita.stages.endcard import models_used, render_card
from tizita.stages.subtitles import ass_path_for
from tizita.stages.timing import load_timing
from tizita.storyboard import load_config
from tizita.util import atomic_write_json


def _ff(cmd: list[str], root: Path, what: str) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        log = root / "logs" / f"tmp_ffmpeg_{what.replace(' ', '_')}.log"
        log.write_text(" ".join(cmd) + "\n\n" + r.stderr)
        raise RuntimeError(
            f"ffmpeg {what} failed (full log {log.relative_to(root)}): {r.stderr[-300:]}"
        )
    return r


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
    )
    return float(r.stdout.strip() or 0)


def parse_loudnorm_json(stderr: str) -> dict:
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.S)
    if not m:
        raise RuntimeError("loudnorm pass 1 printed no stats")
    return json.loads(m[-1])


def _music(ctx: Ctx, degraded: list[str]) -> Path:
    e = ctx.manifest.get("music", PROJECT)
    if e is None:
        raise RuntimeError("no music artifact (run --stage music; the synth pad always works)")
    chosen = ctx.sb["music"].get("chosen")
    if chosen is None or not e.candidates:
        if e.candidates:
            degraded.append("music: none chosen yet, using candidate 1")
            ctx.bus.emit("degraded", stage="assemble", unit=PROJECT, reason="music not chosen")
        return ctx.project.root / e.path
    return ctx.project.root / e.candidates[chosen]["path"]


def run(ctx: Ctx, unit, key: str) -> Outcome:
    root = ctx.project.root
    cfg = load_config(ctx.project, "assembly")
    timing = load_timing(ctx.project, ctx.manifest)
    slots, card_s, total = timing["slots"], timing["end_card"]["duration"], timing["total_s"]
    shots = {s["id"]: s for s in ctx.sb["shots"]}
    degraded: list[str] = []

    out = ctx.project.outputs / "final" / key / "film_9x16.mp4"
    work = ctx.project.state / "tmp" / f"assemble_{key}"
    work.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)

    # video inputs
    clips, clips_s, stretch = [], [], []
    for s in slots:
        e = ctx.manifest.get("shots", s["id"])
        p = root / e.path
        clips.append(str(p.relative_to(root)))
        clips_s.append(probe_duration(p))
        i2v_clip = bool(e.provider and e.provider.get("name") not in ("kenburns", None))
        stretch.append(1 / cfg["kenburns"]["min_i2v_speed"] if i2v_clip else 1e3)
        if e.is_fallback:
            degraded.append(f"{s['id']}: {shots[s['id']]['motion']['mode']} -> Ken Burns")

    # end cards
    fonts = root / cfg["subtitles"]["fonts_dir"]
    models = models_used(ctx.manifest, cfg.get("credit_names"))
    cards = tuple(
        str(render_card(ctx.sb, models, lay, work / f"card_{lay}.png", fonts).relative_to(root))
        for lay in ("9x16", "16x9")
    )

    # audio: premix -> two-pass loudnorm
    narr = [
        str((root / ctx.manifest.get("narration", s["id"]).path).relative_to(root)) for s in slots
    ]
    starts = [s["narration_start"] for s in slots]
    music = _music(ctx, degraded)
    audio = {**cfg["audio"], "music": cfg["music_mix"]}
    track, pre, mix = work / "narration.wav", work / "premix.wav", work / "mix.wav"
    rel = lambda p: str(p.relative_to(root))  # noqa: E731
    ends = [wav_speech_end_s(root / n) for n in narr]
    if any(ends):
        degraded.append(f"narration: trimmed TTS end-of-take noise on {sum(map(bool, ends))} takes")
    _ff(
        G.narration_track_cmd(narr, starts, total, rel(track), audio, ends), root, "narration track"
    )
    _ff(G.duck_mix_cmd(rel(track), rel(music), total, rel(pre), audio), root, "duck mix")
    final = {**cfg["audio"]["final"], "tp": cfg["master"]["tp"]}
    r = _ff(G.loudnorm_measure_cmd(rel(pre), final), root, "loudnorm pass 1")
    stats = parse_loudnorm_json(r.stderr)
    _ff(G.loudnorm_apply_cmd(rel(pre), rel(mix), final, stats), root, "loudnorm 2")

    # video: body + both exports in one pass
    srt = root / ctx.manifest.get("subtitles", PROJECT).path
    graph = ";".join(
        [
            G.body_graph(slots, clips_s, stretch, cfg),
            G.exports_graph(
                len(clips),
                rel(ass_path_for(srt, "9x16")),
                rel(ass_path_for(srt, "16x9")),
                cfg["subtitles"]["fonts_dir"],
                cfg,
            ),
        ]
    )
    o9, o16 = out, out.with_name("film_16x9.mp4")
    t9, t16 = o9.with_name("film_9x16.tmp.mp4"), o16.with_name("film_16x9.tmp.mp4")
    cmd = G.assemble_cmd(clips, cards, rel(mix), graph, card_s, total, (rel(t9), rel(t16)), cfg)
    try:
        _ff(cmd, root, "assemble")
    except RuntimeError:
        t9.unlink(missing_ok=True)
        t16.unlink(missing_ok=True)
        raise
    t16.replace(o16)
    t9.replace(o9)
    shutil.copyfile(srt, out.with_name("film.srt"))
    atomic_write_json(
        out.with_name("assemble.json"),
        {
            "total_s": total,
            "music": rel(music),
            "music_chosen": ctx.sb["music"].get("chosen"),
            "loudnorm_pass1": stats,
            "degraded": degraded,
            "models": models,
        },
    )
    if not os.environ.get("TIZITA_KEEP_WORK"):
        shutil.rmtree(work, ignore_errors=True)
    return Outcome(o9, provider_ident("ffmpeg", None, {}))

"""subtitles: SRT + 9:16 / 16:9 ASS from `text_en` and the timing slots (SPEC §10.4)."""

from __future__ import annotations

import textwrap

from tizita.dag import PROJECT, manifest_path_for
from tizita.stages import Ctx, Outcome
from tizita.stages.timing import load_timing
from tizita.storyboard import load_config
from tizita.util import atomic_write_text


def wrap_lines(text: str, max_chars: int) -> list[str]:
    return textwrap.wrap(text, width=max_chars, break_long_words=False) or [""]


def build_cues(shots: list[dict], timing: dict, cfg: dict) -> list[tuple[float, float, str]]:
    """Chunk each line into cues of <= max_lines x max_chars; split the narration window by
    character count so long lines become sequential cues timed to the audio."""
    mc, ml, min_cue = cfg["max_chars_per_line"], cfg["max_lines"], float(cfg.get("min_cue_s", 0.8))
    slots = {s["id"]: s for s in timing["slots"]}
    cues: list[tuple[float, float, str]] = []
    for sh in shots:
        text = " ".join(sh["narration"]["text_en"].split())
        slot = slots[sh["id"]]
        if not text:
            continue
        lines = wrap_lines(text, mc)
        chunks = [lines[i : i + ml] for i in range(0, len(lines), ml)]
        start, end = slot["narration_start"], slot["narration_end"]
        if end - start < min_cue:
            end = min(start + min_cue, slot["end"])
        weights = [sum(len(x) for x in c) for c in chunks]
        total_w = sum(weights) or 1
        t = start
        for c, w in zip(chunks, weights, strict=True):
            d = (end - start) * w / total_w
            cues.append((round(t, 3), round(t + d, 3), "\n".join(c)))
            t += d
    return cues


def _srt_time(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def render_srt(cues) -> str:
    return "\n".join(
        f"{i}\n{_srt_time(a)} --> {_srt_time(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(cues, 1)
    )


def _ass_time(t: float) -> str:
    cs = round(t * 100)
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def render_ass(cues, layout: dict, font: str) -> str:
    w, h = layout["play_res"]
    margin_v = round(h * layout["margin_v_pct"] / 100)
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, "
        "Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{layout['font_size']},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,0,0,1,{layout['outline']},{layout['shadow']},2,"
        f"{layout['margin_h']},{layout['margin_h']},{margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    nl = "\\N"
    body = "".join(
        f"Dialogue: 0,{_ass_time(a)},{_ass_time(b)},Default,,0,0,0,,{txt.replace(chr(10), nl)}\n"
        for a, b, txt in cues
    )
    return head + body


def ass_path_for(srt_path, layout: str):
    return srt_path.with_name(f"{srt_path.stem}_{layout}.ass")


def run(ctx: Ctx, unit, key: str) -> Outcome:
    cfg = load_config(ctx.project, "assembly")["subtitles"]
    timing = load_timing(ctx.project, ctx.manifest)
    cues = build_cues(ctx.sb["shots"], timing, cfg)
    srt = manifest_path_for(ctx.project, unit, key, "srt")
    atomic_write_text(srt, render_srt(cues))
    for name, layout in cfg["styles"].items():
        atomic_write_text(ass_path_for(srt, name), render_ass(cues, layout, cfg["font"]))
    return Outcome(srt)


__all__ = ["PROJECT", "build_cues", "render_ass", "render_srt", "run"]

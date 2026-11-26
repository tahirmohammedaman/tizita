"""qa: ffprobe + ebur128 checks on both exports (SPEC §10.10). Writes `qa.json` next to the
films and fails the unit (non-zero `tizita run`) when any check fails."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tizita.dag import PROJECT
from tizita.ffmpeg.graphs import ebur128_cmd
from tizita.stages import Ctx, Outcome
from tizita.storyboard import load_config
from tizita.util import atomic_write_json


def probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(r.stdout)


def parse_ebur128(stderr: str) -> dict:
    """Summary block: 'I: -14.0 LUFS' and, under 'True peak:', 'Peak: -1.3 dBFS'."""
    tail = stderr[stderr.rfind("Summary:") :]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", tail)
    tp = re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS", tail, re.S)
    lra = re.search(r"LRA:\s+(-?[\d.]+) LU", tail)
    f = lambda m: float(m.group(1)) if m else None  # noqa: E731
    return {"lufs": f(i), "true_peak_db": f(tp), "lra": f(lra)}


def check_file(path: Path, layout: str, info: dict, loud: dict, cfg: dict, fps: int) -> dict:
    q = cfg["qa"]
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), {})
    dur = float(info["format"].get("duration", 0))
    num, den = (int(x) for x in v.get("r_frame_rate", "0/1").split("/"))
    rate = num / den if den else 0
    frames = int(v.get("nb_frames", 0) or 0)
    want_frames = round(float(v.get("duration", dur)) * fps)
    lo, hi = q["duration_s"]
    w, h = q["sizes"][layout]
    checks = {
        "duration": lo <= dur <= hi,
        "resolution": (v.get("width"), v.get("height")) == (w, h),
        "fps": abs(rate - fps) < 0.01,
        "video_codec": v.get("codec_name") == "h264" and v.get("pix_fmt") == "yuv420p",
        "audio_codec": a.get("codec_name") == "aac" and int(a.get("sample_rate", 0)) == 48000,
        "frames": frames > 0 and abs(frames - want_frames) <= 2,
        "loudness": loud["lufs"] is not None and abs(loud["lufs"] - q["lufs"]) <= q["lufs_tol"],
        "true_peak": loud["true_peak_db"] is not None and loud["true_peak_db"] <= q["max_tp"],
    }
    return {
        "file": str(path),
        "duration_s": round(dur, 3),
        "size": [v.get("width"), v.get("height")],
        "fps": round(rate, 3),
        "frames": frames,
        "expected_frames": want_frames,
        "video_codec": v.get("codec_name"),
        "profile": v.get("profile"),
        "audio_codec": a.get("codec_name"),
        **loud,
        "checks": checks,
        "pass": all(checks.values()),
    }


def run(ctx: Ctx, unit, key: str) -> Outcome:
    root = ctx.project.root
    cfg = load_config(ctx.project, "assembly")
    fps = cfg["timing"]["fps"]
    film9 = root / ctx.manifest.get("assemble", PROJECT).path
    films = {"9x16": film9, "16x9": film9.with_name("film_16x9.mp4")}
    report = {}
    for layout, p in films.items():
        r = subprocess.run(ebur128_cmd(str(p)), capture_output=True, text=True)
        loud = parse_ebur128(r.stderr)
        report[layout] = check_file(p.relative_to(root), layout, probe(p), loud, cfg, fps)
    report["pass"] = all(r["pass"] for r in report.values() if isinstance(r, dict))
    out = film9.with_name("qa.json")
    atomic_write_json(out, json.loads(json.dumps(report, default=str)))
    ctx.bus.emit("qa_result", stage="qa", unit=PROJECT, passed=report["pass"], path=str(out))
    if not report["pass"]:
        bad = [
            f"{k}:{c}"
            for k, r in report.items()
            if isinstance(r, dict)
            for c, ok in r["checks"].items()
            if not ok
        ]
        raise RuntimeError(f"QA failed: {', '.join(bad)} (see {out.relative_to(root)})")
    return Outcome(out)

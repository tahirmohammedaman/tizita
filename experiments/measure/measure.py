"""Re-runnable measurements behind EXPERIMENTS.md. Local FFmpeg only: no model calls.

    uv run python experiments/measure/measure.py aac|grain|duck|tails|clip|pace

Inputs are the committed artifacts named by outputs/manifest.json. Each subcommand prints JSON
and writes it to experiments/measure/results/<name>.json.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import tempfile
import wave
from array import array
from pathlib import Path

from tizita.audio import frame_db, wav_speech_end_s
from tizita.cache import Manifest
from tizita.ffmpeg import graphs as G
from tizita.runlog import iter_runs
from tizita.stages.assemble import parse_loudnorm_json
from tizita.stages.qa import parse_ebur128
from tizita.stages.timing import load_timing
from tizita.storyboard import load_config
from tizita.util import PACKAGE_ROOT, Project, atomic_write_json

ROOT = PACKAGE_ROOT
PROJECT = Project(ROOT)
MANIFEST = Manifest.load(PROJECT.manifest)
CFG = load_config(PROJECT, "assembly")
SB = json.loads((ROOT / "storyboard.json").read_text())


def sh(cmd: list[str]) -> str:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{cmd[0]} failed: {r.stderr[-600:]}")
    return r.stderr


def loudness(path: Path) -> dict:
    return parse_ebur128(sh(G.ebur128_cmd(str(path))))


def art(stage: str, unit: str) -> Path:
    return ROOT / MANIFEST.get(stage, unit).path


def music_path() -> Path:
    entry = MANIFEST.get("music", "project")
    return ROOT / entry.candidates[SB["music"]["chosen"]]["path"]


def mix_inputs(tmp: Path, trim: bool = True):
    timing = load_timing(PROJECT, MANIFEST)
    slots, total = timing["slots"], timing["total_s"]
    narr = [str(art("narration", s["id"])) for s in slots]
    starts = [s["narration_start"] for s in slots]
    ends = [wav_speech_end_s(Path(n)) if trim else None for n in narr]
    audio = {**CFG["audio"], "music": CFG["music_mix"]}
    track = tmp / "narration.wav"
    sh(G.narration_track_cmd(narr, starts, total, str(track), audio, ends))
    speech = [
        (st, st + (e or s["narration_s"])) for st, e, s in zip(starts, ends, slots, strict=True)
    ]
    return track, total, audio, speech


def aac(tmp: Path) -> dict:
    """Encoder flags x (TTS tail trim on/off) x loudnorm TP target; true peak of WAV and AAC."""
    variants = {
        "192k_default": ["-b:a", "192k"],
        "192k_pns_off": ["-b:a", "192k", "-aac_pns", "0"],
        "192k_is_off": ["-b:a", "192k", "-aac_is", "0"],
        "256k_default": ["-b:a", "256k"],
    }
    rows = []
    for trim in (True, False):
        work = tmp / f"trim_{int(trim)}"
        work.mkdir()
        track, total, audio, _ = mix_inputs(work, trim)
        pre = work / "premix.wav"
        sh(G.duck_mix_cmd(str(track), str(music_path()), total, str(pre), audio))
        for tp in (-1.0, -2.0):
            final = {**CFG["audio"]["final"], "tp": tp}
            stats = parse_loudnorm_json(sh(G.loudnorm_measure_cmd(str(pre), final)))
            mix = work / f"mix{tp}.wav"
            sh(G.loudnorm_apply_cmd(str(pre), str(mix), final, stats))
            row = {
                "tail_trim": trim,
                "tp_target": tp,
                "wav_true_peak_db": loudness(mix)["true_peak_db"],
            }
            for name, flags in variants.items():
                out = work / f"{tp}_{name}.m4a"
                sh(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(mix),
                        "-c:a",
                        "aac",
                        *flags,
                        str(out),
                    ]
                )
                row[name] = loudness(out)["true_peak_db"]
            rows.append(row)
    return {"metric": "ebur128 true peak, dBFS", "rows": rows}


def grain(tmp: Path) -> dict:
    clip = art("shots", "s02")
    if not clip.is_file():
        raise SystemExit("shot clips are not committed: run `uv run tizita run --stage shots`")
    look = CFG["look"]
    sizes = {}
    for g in (0, 2, 3, 4, 6):
        out = tmp / f"g{g}.mp4"
        vf = (
            f"eq=contrast={look['contrast']}:saturation={look['saturation']},"
            f"noise=alls={g}:allf=t,format=yuv420p"
        )
        sh(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(clip),
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                CFG["video"]["preset"],
                "-crf",
                str(CFG["video"]["crf"]),
                str(out),
            ]
        )
        sizes[g] = round(out.stat().st_size / 1e6, 2)
    return {"clip": str(clip.relative_to(ROOT)), "crf": CFG["video"]["crf"], "size_mb": sizes}


def mono_db(path: Path, tmp: Path) -> list[float]:
    mono = tmp / f"mono_{path.stem}.wav"
    sh(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(path),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(mono),
        ]
    )
    with wave.open(str(mono)) as w:
        return frame_db(array("h", w.readframes(w.getnframes())), w.getframerate())


def duck(tmp: Path) -> dict:
    """Level of the ducked-music stem while the narrator speaks vs in the gaps."""
    track, total, audio, speech = mix_inputs(tmp)
    narr_db = mono_db(track, tmp)
    # frames that are clearly speech (inside a take and above -40 dBFS) vs clearly gaps
    inside = [any(a <= i * 0.01 < b for a, b in speech) for i in range(len(narr_db))]
    talking = [i for i, db in enumerate(narr_db) if inside[i] and db > -40]
    fade = max(CFG["music_mix"]["fade_in_s"], CFG["music_mix"]["fade_out_s"])
    gaps = [i for i in range(len(narr_db)) if not inside[i] and fade <= i * 0.01 <= total - fade]
    base = audio["duck"]
    variants = {
        "no_duck (ratio 1)": {**base, "ratio": 1},
        "ratio 3": {**base, "ratio": 3},
        "brief default: 0.02 / 6 / 300 / 1500": base,
        "ratio 12": {**base, "ratio": 12},
        "release 300 ms": {**base, "release_ms": 300},
    }
    rows = {}
    for n, (name, params) in enumerate(variants.items()):
        graph = G.duck_mix_graph(total, {**audio, "duck": params})
        graph = graph.rsplit(";", 1)[0]  # drop the amix: keep only the ducked music stem
        stem = tmp / f"stem{n}.wav"
        sh(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(track),
                "-i",
                str(track),
                "-stream_loop",
                "-1",
                "-i",
                str(music_path()),
                "-filter_complex",
                graph,
                "-map",
                "[ducked]",
                "-t",
                str(total),
                "-c:a",
                "pcm_s16le",
                str(stem),
            ]
        )
        db = mono_db(stem, tmp)

        def med(idx, db=db):
            return round(statistics.median(db[i] for i in idx if i < len(db)), 1)

        voice = round(statistics.median(narr_db[i] for i in talking), 1)
        rows[name] = {
            "music_under_voice_db": med(talking),
            "music_in_gaps_db": med(gaps),
            "voice_db": voice,
            "voice_over_music_db": round(voice - med(talking), 1),
        }
    return {
        "metric": "median 10 ms RMS dBFS",
        "speech_frames": len(talking),
        "gap_frames": len(gaps),
        "rows": rows,
    }


def tails(tmp: Path) -> dict:
    rows = {}
    for s in SB["shots"]:
        p = art("narration", s["id"])
        with wave.open(str(p)) as w:
            rate = w.getframerate()
            pcm = array("h", w.readframes(w.getnframes()))
        db = frame_db(pcm, rate)
        end = wav_speech_end_s(p)
        total = round(len(pcm) / rate, 3)
        rows[s["id"]] = {
            "take_s": total,
            "cut_at_s": end,
            "removed_s": round(total - end, 3) if end else 0,
            "peak_after_cut_dbfs": max(db[int(end / 0.01) :]) if end else None,
        }
    return {"takes": rows, "takes_with_burst": sum(bool(r["cut_at_s"]) for r in rows.values())}


def clip(tmp: Path) -> dict:
    rows = []
    for f in sorted(ROOT.glob("outputs/keyframes*/s*/*.json")):
        d = json.loads(f.read_text())
        for a in d["attempts"]:
            if a.get("score") is None:
                continue
            rows.append(
                {
                    "file": str(f.relative_to(ROOT)),
                    "shot": f.parent.name,
                    "seed": a["seed"],
                    "clip": a["score"],
                    "dino_max": max((a.get("sims") or {}).get("dino") or [0]),
                }
            )
    scores = [r["clip"] for r in rows]
    return {
        "attempts": rows,
        "n": len(rows),
        "min": min(scores),
        "max": max(scores),
        "median": round(statistics.median(scores), 4),
        "would_fail": {str(t): sum(s < t for s in scores) for t in (0.45, 0.5, 0.55, 0.75)},
    }


def pace(tmp: Path) -> dict:
    """Same text rendered by different TTS providers/voices: take length from runs.jsonl."""
    by_text: dict[str, dict[str, list[float]]] = {}
    for r in iter_runs(ROOT / "runs.jsonl"):
        d = (r.get("metrics") or {}).get("duration_s")
        if r["stage"] != "narration" or r["status"] != "ok" or not d:
            continue
        if r["provider"] == "previous_take":
            continue
        who = f"{r['provider']}:{r['params'].get('voice', '-')}"
        by_text.setdefault(r["prompt_sha256"], {}).setdefault(who, []).append(
            {"s": round(d, 2), "run_id": r["run_id"], "unit": r["unit"]}
        )
    return {"texts_with_two_or_more_voices": [v for v in by_text.values() if len(v) > 1]}


if __name__ == "__main__":
    name = sys.argv[1]
    fn = {"aac": aac, "grain": grain, "duck": duck, "tails": tails, "clip": clip, "pace": pace}[
        name
    ]
    with tempfile.TemporaryDirectory() as d:
        result = fn(Path(d))
    atomic_write_json(ROOT / "experiments" / "measure" / "results" / f"{name}.json", result)
    print(json.dumps(result, ensure_ascii=False))

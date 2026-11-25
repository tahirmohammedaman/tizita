"""Pure FFmpeg argument/filtergraph builders (SPEC §10). No I/O: unit-tested on the strings.

All commands start with `-hide_banner -loglevel error`; H.264 exports use the preset/crf from
`config/assembly.yaml` (veryfast / 18).
"""

from __future__ import annotations

from typing import Any

BASE = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]


def _f(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".")


def synth_pad_cmd(duration_s: float, out: str, cfg: dict[str, Any]) -> list[str]:
    """Ambient pad: a few detuned-free sines, slow tremolo, low-pass, fades. 48 kHz stereo WAV."""
    freqs = cfg["freqs"]
    args = list(BASE)
    for f in freqs:
        args += [
            "-f",
            "lavfi",
            "-t",
            _f(duration_s),
            "-i",
            f"sine=frequency={_f(f)}:sample_rate=48000",
        ]
    n = len(freqs)
    ins = "".join(f"[{i}:a]" for i in range(n))
    fade_out = max(0.0, duration_s - cfg["fade_out_s"])
    graph = (
        f"{ins}amix=inputs={n}:normalize=0,volume={_f(0.9 / n)},"
        f"tremolo=f={_f(cfg['tremolo_hz'])}:d=0.35,lowpass=f={_f(cfg['lowpass_hz'])},"
        f"aecho=0.8:0.7:420|610:0.35|0.25,aformat=channel_layouts=stereo,"
        f"afade=t=in:d={_f(cfg['fade_in_s'])},afade=t=out:st={_f(fade_out)}:d={_f(cfg['fade_out_s'])}"
    )
    return [*args, "-filter_complex", graph, "-t", _f(duration_s), "-c:a", "pcm_s16le", out]


def narration_mix_graph(starts_s: list[float], audio: dict[str, Any], first: int = 0) -> str:
    """Narration inputs are [first..first+n-1]; the pad is input first+n. Output label [mix]:
    narration + ducked pad. Each take is normalised, delayed to its slot start, then mixed."""
    n = len(starts_s)
    rate = audio["final"]["rate"]
    parts = []
    for i, s in enumerate(starts_s):
        ms = round(s * 1000)
        parts.append(
            f"[{first + i}:a]aresample={rate},aformat=channel_layouts=stereo,"
            f"loudnorm=I={audio['working_lufs']}:TP=-1.5:LRA=11,adelay={ms}|{ms}[n{i}]"
        )
    ins = "".join(f"[n{i}]" for i in range(n))
    d = audio["duck"]
    parts.append(f"{ins}amix=inputs={n}:normalize=0:dropout_transition=0,asplit=2[narr][sc]")
    parts.append(f"[{first + n}:a]aresample={rate},volume={audio['pad_gain_db']}dB[pad]")
    parts.append(
        f"[pad][sc]sidechaincompress=threshold={_f(d['threshold'])}:ratio={d['ratio']}:"
        f"attack={d['attack_ms']}:release={d['release_ms']}[ducked]"
    )
    f = audio["final"]
    parts.append(
        f"[narr][ducked]amix=inputs=2:normalize=0,"
        f"loudnorm=I={f['lufs']}:TP={f['tp']}:LRA={f['lra']}[mix]"
    )
    return ";".join(parts)


def radio_cut_cmd(
    narration: list[str],
    starts_s: list[float],
    pad: str,
    ass: str,
    fonts_dir: str,
    total_s: float,
    out: str,
    cfg: dict[str, Any],
) -> list[str]:
    """Black 1080x1920 + narration + ducked pad + burned 9:16 subtitles (SPEC §10.8)."""
    fps = cfg["timing"]["fps"]
    args = list(BASE)
    args += ["-f", "lavfi", "-t", _f(total_s), "-i", f"color=c=black:s=1080x1920:r={fps}"]
    for p in narration:
        args += ["-i", p]
    args += ["-i", pad]
    graph_audio = narration_mix_graph(starts_s, cfg["audio"], first=1)  # input 0 = video
    graph = f"[0:v]ass={ass}:fontsdir={fonts_dir},format=yuv420p[v];{graph_audio}"
    v = cfg["video"]
    return [
        *args,
        "-filter_complex",
        graph,
        "-map",
        "[v]",
        "-map",
        "[mix]",
        "-t",
        _f(total_s),
        "-c:v",
        "libx264",
        "-preset",
        v["preset"],
        "-crf",
        str(v["crf"]),
        "-r",
        str(fps),
        "-c:a",
        "aac",
        "-b:a",
        f"{cfg['audio']['final']['aac_kbps']}k",
        "-ar",
        str(cfg["audio"]["final"]["rate"]),
        "-movflags",
        "+faststart",
        out,
    ]

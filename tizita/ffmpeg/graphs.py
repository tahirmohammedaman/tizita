"""Pure FFmpeg argument/filtergraph builders (SPEC §10). No I/O: unit-tested on the strings.

All commands start with `-hide_banner -loglevel error`; H.264 exports use the preset/crf from
`config/assembly.yaml` (veryfast / 18).
"""

from __future__ import annotations

from typing import Any

BASE = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]


def _f(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".")


def synth_pad_cmd(
    duration_s: float, out: str, cfg: dict[str, Any], codec: str = "pcm_s16le"
) -> list[str]:
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
    return [*args, "-filter_complex", graph, "-t", _f(duration_s), "-c:a", codec, out]


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


# ---------------------------------------------------------------- shots (Ken Burns)

_PAN = {  # (x fraction, y fraction) of the free slack at eased time e
    "none": ("0.5", "0.5"),
    "left": ("0.5-0.5*{e}", "0.5"),
    "right": ("0.5+0.5*{e}", "0.5"),
    "up": ("0.5", "0.5-0.5*{e}"),
    "down": ("0.5", "0.5+0.5*{e}"),
}


def kenburns_graph(kb: dict[str, Any], duration_s: float, fps: int, size=(1080, 1920)) -> str:
    """Zoompan on a keyframe pre-scaled 2x (less jitter), smoothstep easing zoom_from -> zoom_to
    and the pan direction (SPEC §10.2). Output label [v]."""
    w, h = size
    n = max(2, round(duration_s * fps))
    t = f"(on/{n - 1})"
    e = f"({t}*{t}*(3-2*{t}))"
    zf, zt = float(kb.get("zoom_from", 1.0)), float(kb.get("zoom_to", 1.0))
    fx, fy = (s.format(e=e) for s in _PAN[kb.get("pan", "none")])
    z = f"{_f(zf)}+{_f(zt - zf)}*{e}"
    return (
        f"[0:v]scale={w * 2}:{h * 2}:flags=lanczos:out_range=tv,setsar=1,"
        f"zoompan=z='{z}':x='(iw-iw/zoom)*({fx})':y='(ih-ih/zoom)*({fy})':"
        f"d={n}:s={w}x{h}:fps={fps},format=yuv420p[v]"
    )


def _h264(cfg: dict[str, Any], fps: int) -> list[str]:
    v = cfg["video"]
    return [
        "-c:v",
        "libx264",
        "-preset",
        v["preset"],
        "-crf",
        str(v["crf"]),
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
    ]


def kenburns_cmd(
    image: str, kb: dict[str, Any], duration_s: float, out: str, cfg: dict[str, Any]
) -> list[str]:
    fps = cfg["timing"]["fps"]
    n = max(2, round(duration_s * fps))
    return [
        *BASE,
        "-i",
        image,
        "-filter_complex",
        kenburns_graph(kb, duration_s, fps),
        "-map",
        "[v]",
        "-frames:v",
        str(n),
        *_h264(cfg, fps),
        "-an",
        out,
    ]


# ---------------------------------------------------------------- assembly


def _fit_clip(i: int, clip_s: float, slot_s: float, fps: int, max_stretch: float) -> str:
    """Normalise clip i to 1080x1920 CFR and exactly slot_s: slow down (<= max_stretch),
    then hold the last frame, then trim."""
    k = min(max(slot_s / clip_s, 1.0), max_stretch) if clip_s > 0 else 1.0
    hold = max(0.0, slot_s - clip_s * k) + 0.1
    return (
        f"[{i}:v]scale=1080:1920:flags=lanczos:out_range=tv,setsar=1,fps={fps},format=yuv420p,"
        f"setpts={_f(k)}*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration={_f(hold)},"
        f"trim=duration={_f(slot_s)},setpts=PTS-STARTPTS,fps={fps},settb=AVTB[c{i}]"
    )


def body_graph(
    slots: list[dict[str, Any]],
    clips_s: list[float],
    max_stretch: list[float],
    cfg: dict[str, Any],
) -> str:
    """Slots joined with cut / crossfade / fade_black (xfade offset = slot start), fade in on
    the first slot, fade to black at the end, unified grade + grain.
    Inputs 0..n-1, output [body]."""
    fps = cfg["timing"]["fps"]
    xf = cfg["timing"]["crossfade_s"]
    look = cfg["look"]
    parts = [
        _fit_clip(i, clips_s[i], s["duration"], fps, max_stretch[i]) for i, s in enumerate(slots)
    ]
    acc = "c0"
    if slots[0]["transition_in"] == "fade_black":
        parts.append(f"[c0]fade=t=in:d={_f(xf)}[f0]")
        acc = "f0"
    for i, s in enumerate(slots[1:], start=1):
        tr = s["transition_in"]
        if tr == "cut":
            parts.append(f"[{acc}][c{i}]concat=n=2:v=1:a=0,fps={fps},settb=AVTB[a{i}]")
        else:
            kind = "fadeblack" if tr == "fade_black" else "fade"
            parts.append(
                f"[{acc}][c{i}]xfade=transition={kind}:duration={_f(xf)}:offset={_f(s['start'])}[a{i}]"
            )
        acc = f"a{i}"
    end = slots[-1]["end"]
    parts.append(
        f"[{acc}]fade=t=out:st={_f(end - look['fade_out_s'])}:d={_f(look['fade_out_s'])},"
        f"eq=contrast={_f(look['contrast'])}:saturation={_f(look['saturation'])},"
        f"noise=alls={look['grain']}:allf=t,format=yuv420p[body]"
    )
    return ";".join(parts)


def exports_graph(n_clips: int, ass9: str, ass16: str, fonts_dir: str, cfg: dict[str, Any]) -> str:
    """[body] -> 9:16 and 16:9 exports. Inputs n (card 9x16) and n+1 (card 16x9) are looped PNGs.
    16:9 = blurred, darkened fill + centred 1080p foreground (SPEC §10.6). Outputs [v9], [v16]."""
    fps = cfg["timing"]["fps"]
    look = cfg["look"]
    c9, c16 = n_clips, n_clips + 1
    card = f"fps={fps},format=yuv420p,fade=t=in:d={_f(look['card_fade_s'])},setsar=1"
    return ";".join(
        [
            "[body]split=2[b9][b16]",
            f"[{c9}:v]scale=1080:1920:out_range=tv,{card}[card9]",
            f"[{c16}:v]scale=1920:1080:out_range=tv,{card}[card16]",
            f"[b9][card9]concat=n=2:v=1:a=0,ass={ass9}:fontsdir={fonts_dir},format=yuv420p[v9]",
            "[b16]split=2[bg0][fg0]",
            f"[bg0]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
            f"gblur=sigma={_f(look['blur_sigma'])},eq=brightness={_f(look['bg_brightness'])}[bg]",
            "[fg0]scale=-2:1080:flags=lanczos[fg]",
            "[bg][fg]overlay=(W-w)/2:0,setsar=1[m16]",
            f"[m16][card16]concat=n=2:v=1:a=0,ass={ass16}:fontsdir={fonts_dir},format=yuv420p[v16]",
        ]
    )


def assemble_cmd(
    clips: list[str],
    cards: tuple[str, str],
    mix: str,
    graph: str,
    card_s: float,
    total_s: float,
    outs: tuple[str, str],
    cfg: dict[str, Any],
) -> list[str]:
    fps = cfg["timing"]["fps"]
    args = list(BASE)
    for c in clips:
        args += ["-i", c]
    for c in cards:
        args += ["-loop", "1", "-framerate", str(fps), "-t", _f(card_s), "-i", c]
    args += ["-i", mix]
    a = len(clips) + 2
    audio = [
        "-c:a",
        "aac",
        "-b:a",
        f"{cfg['audio']['final']['aac_kbps']}k",
        "-aac_pns",
        "0",  # PNS pushed true peak +2 dB on speech at 192k
        "-ar",
        str(cfg["audio"]["final"]["rate"]),
    ]
    args += ["-filter_complex", graph]
    for label, out in zip(("[v9]", "[v16]"), outs, strict=True):
        args += ["-map", label, "-map", f"{a}:a", "-t", _f(total_s), *_h264(cfg, fps), *audio]
        args += ["-movflags", "+faststart", out]
    return args


def narration_track_graph(starts_s: list[float], total_s: float, audio: dict[str, Any]) -> str:
    """Narration inputs 0..n-1: each take pre-normalised and delayed to its slot start, mixed and
    padded to the film length. Output [narr]."""
    rate = audio["final"]["rate"]
    parts = []
    for i, s in enumerate(starts_s):
        ms = round(s * 1000)
        parts.append(
            f"[{i}:a]aresample={rate},aformat=channel_layouts=stereo,"
            f"loudnorm=I={audio['working_lufs']}:TP=-1.5:LRA=11,adelay={ms}|{ms}[n{i}]"
        )
    n = len(starts_s)
    ins = "".join(f"[n{i}]" for i in range(n))
    parts.append(
        f"{ins}amix=inputs={n}:normalize=0:dropout_transition=0,aresample={rate},"
        f"apad,atrim=duration={_f(total_s)}[narr]"
    )
    return ";".join(parts)


def narration_track_cmd(
    narration: list[str], starts_s: list[float], total_s: float, out: str, audio: dict
) -> list[str]:
    args = list(BASE)
    for p in narration:
        args += ["-i", p]
    g = narration_track_graph(starts_s, total_s, audio)
    return [*args, "-filter_complex", g, "-map", "[narr]", "-c:a", "pcm_s16le", out]


def duck_mix_graph(total_s: float, audio: dict[str, Any]) -> str:
    """Input 0 = narration track, 1 = the same file as sidechain (no asplit: a split feeding
    sidechaincompress silenced the other branch), 2 = music (looped by -stream_loop). Music is
    trimmed, pre-normalised, faded and ducked under the narration. Output [pre]; the two-pass
    loudnorm follows."""
    rate = audio["final"]["rate"]
    d = audio["duck"]
    m = audio["music"]
    fo = max(0.0, total_s - m["fade_out_s"])
    return ";".join(
        [
            f"[2:a]aresample={rate},aformat=channel_layouts=stereo,atrim=duration={_f(total_s)},"
            f"loudnorm=I={audio['working_lufs']}:TP=-1.5:LRA=11,aresample={rate},"
            f"volume={m['gain_db']}dB,afade=t=in:d={_f(m['fade_in_s'])},"
            f"afade=t=out:st={_f(fo)}:d={_f(m['fade_out_s'])}[mus]",
            "[1:a]aformat=channel_layouts=stereo[sc]",
            f"[mus][sc]sidechaincompress=threshold={_f(d['threshold'])}:ratio={d['ratio']}:"
            f"attack={d['attack_ms']}:release={d['release_ms']}[ducked]",
            f"[0:a][ducked]amix=inputs=2:normalize=0:duration=first,"
            f"atrim=duration={_f(total_s)}[pre]",
        ]
    )


def duck_mix_cmd(narr_track: str, music: str, total_s: float, out: str, audio: dict) -> list[str]:
    return [
        *BASE,
        "-i",
        narr_track,
        "-i",
        narr_track,
        "-stream_loop",
        "-1",
        "-i",
        music,
        "-filter_complex",
        duck_mix_graph(total_s, audio),
        "-map",
        "[pre]",
        "-c:a",
        "pcm_s16le",
        out,
    ]


def loudnorm_measure_cmd(src: str, final: dict[str, Any]) -> list[str]:
    """Pass 1 of two-pass loudnorm: JSON stats on stderr (needs loglevel info)."""
    ln = f"loudnorm=I={final['lufs']}:TP={final['tp']}:LRA={final['lra']}:print_format=json"
    return ["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", ln, "-f", "null", "-"]


def loudnorm_apply_cmd(src: str, out: str, final: dict[str, Any], m: dict[str, Any]) -> list[str]:
    ln = (
        f"loudnorm=I={final['lufs']}:TP={final['tp']}:LRA={final['lra']}:"
        f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
        f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
    )
    return [*BASE, "-i", src, "-af", f"{ln},aresample={final['rate']}", "-c:a", "pcm_s16le", out]


def ebur128_cmd(src: str) -> list[str]:
    """Integrated loudness + true peak summary on stderr (QA, SPEC §10.10)."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        src,
        "-map",
        "0:a",
        "-af",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]

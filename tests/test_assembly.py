"""Assembly (SPEC §10): golden filtergraphs, Ken Burns params, QA parsing, prune, choose music."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tizita.dag import _prune
from tizita.ffmpeg.graphs import (
    assemble_cmd,
    body_graph,
    duck_mix_graph,
    exports_graph,
    kenburns_cmd,
    kenburns_graph,
    loudnorm_apply_cmd,
    narration_track_graph,
    synth_pad_cmd,
)
from tizita.stages.assemble import parse_loudnorm_json
from tizita.stages.endcard import models_used
from tizita.stages.qa import check_file, parse_ebur128
from tizita.stages.shots import kenburns_params
from tizita.util import Project

REPO = Path(__file__).resolve().parent.parent
ASM = yaml.safe_load((REPO / "config" / "assembly.yaml").read_text())


def slot(i, start, dur, tr):
    return {"id": f"s{i:02d}", "start": start, "end": start + dur, "duration": dur,
            "transition_in": tr}  # fmt: skip


def test_kenburns_graph_golden():
    g = kenburns_graph({"zoom_from": 1.0, "zoom_to": 1.1, "pan": "left"}, 2, 24)
    e = "((on/47)*(on/47)*(3-2*(on/47)))"
    assert g == (
        "[0:v]scale=2160:3840:flags=lanczos:out_range=tv,setsar=1,"
        f"zoompan=z='1+0.1*{e}':x='(iw-iw/zoom)*(0.5-0.5*{e})':y='(ih-ih/zoom)*(0.5)':"
        "d=48:s=1080x1920:fps=24,format=yuv420p[v]"
    )


def test_kenburns_cmd_is_h264_veryfast_crf18_exact_frames():
    cmd = kenburns_cmd("k.jpg", {"zoom_from": 1, "zoom_to": 1.05}, 7, "o.mp4", ASM)
    assert cmd[:5] == ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    assert cmd[cmd.index("-frames:v") + 1] == "168"
    assert cmd[cmd.index("-preset") + 1] == "veryfast" and cmd[cmd.index("-crf") + 1] == "18"
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p" and cmd[-1] == "o.mp4"


def test_kenburns_params_flat_i2v_and_still_use_config_defaults():
    flat = {"mode": "i2v", "kenburns": {"zoom_from": 1.0, "zoom_to": 1.0, "pan": "none"}}
    assert kenburns_params(flat, ASM) == ASM["kenburns"]["fallback"]
    assert kenburns_params({"mode": "still"}, ASM) == ASM["kenburns"]["still"]
    own = {"mode": "kenburns", "kenburns": {"zoom_from": 1.0, "zoom_to": 1.12, "pan": "down"}}
    assert kenburns_params(own, ASM) == own["kenburns"]


def test_body_graph_transitions_offsets_and_look():
    slots = [slot(1, 0, 7, "fade_black"), slot(2, 7, 7, "cut"), slot(3, 13.6, 7, "crossfade"),
             slot(4, 20.2, 7, "fade_black")]  # fmt: skip
    g = body_graph(slots, [7, 7, 5, 7], [1e3, 1e3, 1 / 0.85, 1e3], ASM).split(";")
    assert g[0] == (
        "[0:v]scale=1080:1920:flags=lanczos:out_range=tv,setsar=1,fps=24,format=yuv420p,"
        "setpts=1*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration=0.1,"
        "trim=duration=7,setpts=PTS-STARTPTS,fps=24,settb=AVTB[c0]"
    )
    # a 5 s i2v clip in a 7 s slot: slowed to 0.85x (1.176), then the last frame is held
    assert "setpts=1.176*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration=1.218" in g[2]
    assert "[c0]fade=t=in:d=0.4[f0]" in g
    assert "[f0][c1]concat=n=2:v=1:a=0,fps=24,settb=AVTB[a1]" in g
    assert "[a1][c2]xfade=transition=fade:duration=0.4:offset=13.6[a2]" in g
    assert "[a2][c3]xfade=transition=fadeblack:duration=0.4:offset=20.2[a3]" in g
    assert g[-1] == (
        "[a3]fade=t=out:st=26.6:d=0.6,eq=contrast=1.03:saturation=0.97,"
        f"noise=alls={ASM['look']['grain']}:allf=t,format=yuv420p[body]"
    )


def test_exports_graph_16x9_is_blurred_fill_plus_centred_master():
    g = exports_graph(11, "a9.ass", "a16.ass", "assets/fonts", ASM)
    assert "[11:v]scale=1080:1920:out_range=tv" in g and "[12:v]scale=1920:1080:out_range=tv" in g
    assert "[b9][card9]concat=n=2:v=1:a=0,ass=a9.ass:fontsdir=assets/fonts" in g
    assert "crop=1920:1080,gblur=sigma=30,eq=brightness=-0.12[bg]" in g
    assert "[bg][fg]overlay=(W-w)/2:0" in g and g.endswith("format=yuv420p[v16]")


def test_assemble_cmd_two_outputs_share_the_mix_and_disable_pns():
    cmd = assemble_cmd(["a.mp4", "b.mp4"], ("c9.png", "c16.png"), "mix.wav", "G", 3, 70,
                       ("o9.mp4", "o16.mp4"), ASM)  # fmt: skip
    assert cmd.count("-loop") == 2 and cmd[cmd.index("mix.wav") - 1] == "-i"
    assert cmd.count("4:a") == 2 and cmd.count("+faststart") == 2
    assert cmd.count("-aac_pns") == 2 and cmd[-1] == "o16.mp4"


def test_audio_graphs_golden():
    n = narration_track_graph([0.4, 7.4], 20, ASM["audio"])
    assert n.endswith(
        "[n0][n1]amix=inputs=2:normalize=0:dropout_transition=0,aresample=48000,"
        "apad,atrim=duration=20[narr]"
    )
    d = duck_mix_graph(20, {**ASM["audio"], "music": ASM["music_mix"]}).split(";")
    assert d[0].startswith("[2:a]aresample=48000,aformat=channel_layouts=stereo,atrim=duration=20")
    assert "afade=t=out:st=17:d=3[mus]" in d[0]
    assert (
        d[2] == "[mus][sc]sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500[ducked]"
    )
    assert d[3] == "[0:a][ducked]amix=inputs=2:normalize=0:duration=first,atrim=duration=20[pre]"
    m = {"input_i": "-17", "input_tp": "-1", "input_lra": "5", "input_thresh": "-27",
         "target_offset": "0.2"}  # fmt: skip
    a = loudnorm_apply_cmd("p.wav", "m.wav", {**ASM["audio"]["final"], "tp": -2}, m)
    assert "measured_I=-17:measured_TP=-1" in a[a.index("-af") + 1]
    assert "TP=-2" in a[a.index("-af") + 1] and "linear=true" in a[a.index("-af") + 1]


def test_synth_pad_flac_codec():
    assert synth_pad_cmd(5, "p.flac", ASM["pad"], "flac")[-3:] == ["-c:a", "flac", "p.flac"]


def test_parse_loudnorm_and_ebur128():
    err = 'junk\n[Parsed_loudnorm_0 @ x]\n{\n "input_i" : "-17.5",\n "input_tp" : "-1.2"\n}\n'
    assert parse_loudnorm_json(err)["input_i"] == "-17.5"
    summary = (
        "[Parsed_ebur128_0 @ 0x1] Summary:\n\n  Integrated loudness:\n    I:         -14.6 LUFS\n"
        "    Threshold: -24.7 LUFS\n\n  Loudness range:\n    LRA:         6.8 LU\n\n"
        "  True peak:\n    Peak:       -1.7 dBFS\n"
    )
    assert parse_ebur128(summary) == {"lufs": -14.6, "true_peak_db": -1.7, "lra": 6.8}


def _probe(w, h, dur, frames, codec="h264", pix="yuv420p"):
    return {
        "format": {"duration": str(dur)},
        "streams": [
            {"codec_type": "video", "codec_name": codec, "pix_fmt": pix, "width": w,
             "height": h, "r_frame_rate": "24/1", "nb_frames": str(frames),
             "duration": str(dur)},
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000"},
        ],
    }  # fmt: skip


def test_qa_checks_pass_and_fail():
    loud = {"lufs": -14.6, "true_peak_db": -1.7, "lra": 6.8}
    ok = check_file("f", "9x16", _probe(1080, 1920, 77.2, 1853), loud, ASM, 24)
    assert ok["pass"]
    bad = check_file("f", "16x9", _probe(1920, 1080, 95, 2000, pix="yuvj420p"),
                     {**loud, "true_peak_db": -0.4}, ASM, 24)  # fmt: skip
    failed = {k for k, v in bad["checks"].items() if not v}
    assert failed == {"duration", "video_codec", "frames", "true_peak"}


def test_prune_keeps_new_artifact_with_same_stem(tmp_path):
    p = Project(tmp_path)
    d = p.outputs / "music"
    d.mkdir(parents=True)
    old, new = d / "k_cand1.wav", d / "k_cand1.flac"
    old.write_text("o")
    new.write_text("n")
    _prune(p, "outputs/music/k_cand1.wav", "k", {new})
    assert new.exists() and not old.exists()


def test_prune_removes_a_key_directory(tmp_path):
    p = Project(tmp_path)
    d = p.outputs / "final" / "oldkey"
    d.mkdir(parents=True)
    (d / "film_9x16.mp4").write_text("x")
    (d / "qa.json").write_text("{}")
    _prune(p, "outputs/final/oldkey/film_9x16.mp4", "oldkey", {p.outputs / "final/new/f.mp4"})
    assert not d.exists()


def test_models_used_lists_each_role_once():
    class E:
        def __init__(self, stage, model):
            self.stage, self.provider = stage, {"name": "x", "model": model}

    class M:
        def __init__(self):
            self.entries = {
                "a": E("narration", "models/gemini-tts"),
                "b": E("narration", "models/gemini-tts"),
                "c": E("keyframes", "@cf/black-forest-labs/flux-2-klein-4b"),
            }

    assert models_used(M()) == ["Voice: gemini-tts", "Images: flux-2-klein-4b"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_kenburns_renders_exact_frame_count(tmp_path):
    from PIL import Image

    Image.new("RGB", (72, 128), (90, 60, 30)).save(tmp_path / "k.jpg")
    cfg = {**ASM, "timing": {**ASM["timing"], "fps": 12}}
    cmd = kenburns_cmd("k.jpg", {"zoom_from": 1, "zoom_to": 1.1, "pan": "up"}, 1, "o.mp4", cfg)
    subprocess.run(cmd, cwd=tmp_path, check=True)
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-show_entries",
         "stream=nb_read_frames,width,height,pix_fmt", "-of", "json", "o.mp4"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    s = json.loads(out)["streams"][0]
    assert (s["width"], s["height"], s["nb_read_frames"], s["pix_fmt"]) == (
        1080, 1920, "12", "yuv420p")  # fmt: skip

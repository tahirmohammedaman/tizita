from pathlib import Path

from tizita.ffmpeg.graphs import i2v_normalise_cmd
from tizita.providers.base import Request
from tizita.providers.wavespeed import WaveSpeed
from tizita.stages.shots import clip_seconds


def _provider(capability):
    cfg = {"capability": capability, "tier": "paid", "model": "m"}
    return WaveSpeed("w", cfg, env={}, models_dir=Path("."))


def test_image_payload_sends_all_references_and_size():
    req = Request("image", "keyframes", "s01", prompt="p", params={"width": 576, "height": 1024})
    body = _provider("image").payload(req, ["a", "b"])
    assert body == {"prompt": "p", "images": ["a", "b"], "size": "576*1024"}


def test_i2v_payload_sends_one_image_and_duration():
    req = Request("i2v", "shots", "s01", prompt="p", params={"duration": 8}, seed=7)
    body = _provider("i2v").payload(req, ["a"])
    assert body == {"prompt": "p", "seed": 7, "image": "a", "duration": 8}


def test_clip_seconds():
    assert clip_seconds(7.0, 8) == 5
    assert clip_seconds(8.6, 8) == 8


def test_i2v_normalise_is_silent_portrait_cfr():
    cmd = i2v_normalise_cmd(
        "in.mp4", "out.mp4", {"timing": {"fps": 24}, "video": {"preset": "veryfast", "crf": 18}}
    )
    assert cmd[1:4] == ["-hide_banner", "-loglevel", "error"]
    assert "crop=1080:1920" in cmd[cmd.index("-vf") + 1] and "-an" in cmd
    assert cmd[-1] == "out.mp4"

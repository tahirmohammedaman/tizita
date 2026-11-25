"""`synth_pad`: deterministic FFmpeg ambient pad (placeholder music; end of the music chain)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from tizita.ffmpeg.graphs import synth_pad_cmd
from tizita.providers.base import Availability, Provider, Request, Result, wav_duration_s
from tizita.providers.errors import BadRequest, Unavailable
from tizita.storyboard import load_config
from tizita.util import Project


class SynthPad(Provider):
    executor = "local"

    def available(self) -> Availability:
        import shutil

        if shutil.which("ffmpeg") is None:
            return Availability(False, "ffmpeg not on PATH", "install ffmpeg")
        return super().available()

    def call(self, req: Request) -> Result:
        dur = float(req.params.get("duration_s") or req.inputs.get("duration_s") or 0)
        if dur <= 0:
            raise BadRequest("synth_pad needs params.duration_s")
        cfg = load_config(Project.default(), "assembly")["pad"]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "pad.wav"
            r = subprocess.run(synth_pad_cmd(dur, str(out), cfg), capture_output=True, text=True)
            if r.returncode != 0 or not out.exists():
                raise Unavailable(f"ffmpeg pad failed: {r.stderr[-200:]}")
            data = out.read_bytes()
        return Result(
            model="ffmpeg-sine-pad",
            data=data,
            mime="audio/wav",
            ext="wav",
            metrics={"duration_s": round(wav_duration_s(data), 3)},
        )

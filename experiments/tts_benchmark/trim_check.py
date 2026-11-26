"""One variable: Whisper on the Amharic takes with the TTS end-of-take noise cut off (EXP-02),
against the same takes as generated. 5 Whisper calls through the router; results are saved and
not requested again.   uv run python experiments/tts_benchmark/trim_check.py
"""

import json
import statistics
import tempfile
import wave
from pathlib import Path

from tizita.audio import wav_speech_end_s
from tizita.providers.base import Request
from tizita.providers.session import make_router
from tizita.tts_benchmark import Bench, score
from tizita.util import PACKAGE_ROOT, Project, atomic_write_json

project = Project(PACKAGE_ROOT)
bench = Bench(project)
out_path = bench.dir / "trim_check.json"
done = json.loads(out_path.read_text()) if out_path.is_file() else {}
router = None
for s in bench.cfg["sentences"]:
    sid = s["id"]
    if sid in done:
        continue
    src = project.root / bench.state["audio"][f"am/{sid}"]["path"]
    end = wav_speech_end_s(src)
    router = router or make_router(project)
    with tempfile.TemporaryDirectory() as d:
        cut = Path(d) / f"am_{sid}_trimmed.wav"
        with wave.open(str(src)) as r, wave.open(str(cut), "wb") as w:
            w.setparams(r.getparams())
            w.writeframes(r.readframes(int(end * r.getframerate()) if end else r.getnframes()))
        req = Request(
            capability="asr",
            stage="exp",
            unit=f"asr_trim_am_{sid}",
            params={"language": "am"},
            inputs={"audio": str(cut)},
        )
        text = router.call_one("cf_whisper", req).text or ""
    before = bench.state["transcripts"][f"cf_whisper:am/{sid}"]
    done[sid] = {
        "cut_at_s": end,
        "cer_as_generated": score(s["am"], before["text"], "am")["cer"],
        "cer_trimmed": score(s["am"], text, "am")["cer"],
        "transcript_trimmed": text,
        "run_id": router.runlog.run_id,
    }
    atomic_write_json(out_path, done)
for key in ("cer_as_generated", "cer_trimmed"):
    print(
        key,
        [r[key] for r in done.values()],
        "median",
        statistics.median(r[key] for r in done.values()),
    )
for sid, r in done.items():
    print(sid, r["cut_at_s"], r["run_id"], r["transcript_trimmed"][:120])

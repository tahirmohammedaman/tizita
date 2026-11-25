import io
import shutil
import wave
from pathlib import Path

import pytest
import yaml

from tizita.dag import execute
from tizita.events import EventBus
from tizita.providers.base import Provider, Result
from tizita.providers.profiles import Selection
from tizita.providers.registry import Registry
from tizita.providers.router import Router
from tizita.runlog import RunLog
from tizita.stages.subtitles import build_cues, render_ass, render_srt, wrap_lines
from tizita.stages.timing import advice, compute_timing
from tizita.util import Project

REPO = Path(__file__).resolve().parent.parent
ASM = yaml.safe_load((REPO / "config" / "assembly.yaml").read_text())


def shots(n=3, dur=7.5, tr="crossfade"):
    return [
        {
            "id": f"s{i + 1:02d}",
            "duration_s": dur,
            "transition_in": tr,
            "narration": {"text_en": "x"},
        }
        for i in range(n)
    ]


def test_timing_slot_is_max_of_planned_and_narration_plus_lead_tail():
    t = compute_timing(shots(2), {"s01": 3.0, "s02": 9.0}, 3, ASM["timing"])
    s1, s2 = t["slots"]
    assert s1["duration"] == 7.5  # planned wins
    assert s2["duration"] == 10.0  # 9 + 0.4 + 0.6
    assert s2["start"] == 7.1  # 7.5 - 0.4 crossfade overlap
    assert s2["narration_start"] == 7.5
    assert t["total_s"] == round(7.1 + 10.0 + 3, 3)


def test_timing_cut_has_no_overlap_and_first_shot_never_overlaps():
    t = compute_timing(shots(3, tr="cut"), {}, 3, ASM["timing"])
    assert [s["start"] for s in t["slots"]] == [0.0, 7.5, 15.0]


def test_timing_advice_names_the_longest_narration():
    t = compute_timing(shots(9, dur=12), {"s03": 9.0}, 3, ASM["timing"])
    assert "trim s03" in advice(t)
    assert advice(compute_timing(shots(9), {}, 3, ASM["timing"])) is None


def test_wrap_and_cues_split_long_lines_in_time_order():
    assert all(len(x) <= 40 for x in wrap_lines("word " * 40, 40))
    slot = {"id": "s01", "narration_start": 1.0, "narration_end": 9.0, "end": 10.0}
    text = " ".join(["lorem"] * 40)
    cues = build_cues(
        [{"id": "s01", "narration": {"text_en": text}}], {"slots": [slot]}, ASM["subtitles"]
    )
    assert len(cues) >= 2
    assert cues[0][0] == 1.0 and abs(cues[-1][1] - 9.0) < 0.01
    assert all(len(line) <= 40 for _, _, t in cues for line in t.split("\n"))
    assert all(len(t.split("\n")) <= 2 for _, _, t in cues)


def test_srt_and_ass_golden():
    cues = [(1.0, 3.5, "Hello\nthere")]
    assert render_srt(cues) == "1\n00:00:01,000 --> 00:00:03,500\nHello\nthere\n"
    ass = render_ass(cues, ASM["subtitles"]["styles"]["9x16"], "Noto Sans")
    assert "PlayResX: 1080\nPlayResY: 1920" in ass
    assert ",Default,,0,0,0,,Hello\\Nthere\n" in ass
    assert "Dialogue: 0,0:00:01.00,0:00:03.50" in ass
    assert ",2,80,80,422,1\n" in ass  # alignment 2, margins, MarginV = 22% of 1920


# ------------------------------------------------------------------ runner with a fake TTS


def wav_bytes(seconds: float, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


class FakeTTS(Provider):
    def __init__(self):
        super().__init__(
            "fake_tts",
            {"adapter": "x", "capability": "tts", "tier": "free_hosted", "model": "m"},
            env={},
            models_dir=None,
        )
        self.texts: list[str] = []

    def call(self, req):
        self.texts.append(req.prompt)
        return Result(
            model="m", data=wav_bytes(1.0 + len(req.prompt) / 10), ext="wav", seed_used=req.seed
        )


@pytest.fixture
def live(tmp_path, good_sb):
    import json

    shutil.copytree(REPO / "config", tmp_path / "config")
    (tmp_path / "storyboard.json").write_text(json.dumps(good_sb, ensure_ascii=False))
    (tmp_path / "ethics").mkdir()
    (tmp_path / "ethics" / "consents.yaml").write_text("[]\n")
    project = Project(tmp_path)
    fake = FakeTTS()
    reg = Registry.from_providers([fake], {"tts": ["fake_tts"]})
    sel = Selection(profile="free", tiers=["free_hosted", "deterministic"])
    router = Router(
        reg, sel, project=project, runlog=RunLog(project.runs, profile="free"), bus=EventBus("t")
    )
    return project, router, fake, good_sb


def test_run_skips_cached_and_one_edit_makes_one_tts_call(live):
    project, router, fake, sb = live
    stages = {"narration", "timing", "subtitles"}
    r1 = execute(sb, project, router, stages=stages)
    assert r1.calls == 9 and not r1.failed and len(fake.texts) == 9
    r2 = execute(sb, project, router, stages=stages)
    assert r2.calls == 0 and r2.cache_hits == 11 and len(fake.texts) == 9

    sb["shots"][3]["narration"]["text_am"] = "አዲስ ጽሑፍ።"
    r3 = execute(sb, project, router, stages=stages)
    assert fake.texts[9:] == ["አዲስ ጽሑፍ።"]  # exactly one new TTS call
    assert r3.calls == 1
    assert {"narration/s04", "timing/project", "subtitles/project"} <= set(r3.ran)
    # the superseded take was pruned
    assert len(list((project.outputs / "narration" / "s04").glob("*.wav"))) == 1


def test_seed_is_style_seed_base_plus_shot_index(live):
    project, router, _fake, sb = live
    execute(sb, project, router, stages={"narration"}, unit_id="s03")
    import json

    last = [json.loads(x) for x in project.runs.read_text().splitlines()][-1]
    assert last["unit"] == "s03" and last["seed"] == sb["style"]["seed_base"] + 2


def test_unimplemented_stage_is_reported_not_faked(live):
    project, router, _, sb = live
    r = execute(sb, project, router, stages={"keyframes"})
    assert any("not implemented" in s for s in r.skipped) or any("upstream" in s for s in r.skipped)
    assert r.calls == 0

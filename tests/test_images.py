import json
import shutil
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from tizita.cli import app
from tizita.stages.images import contact_sheet
from tizita.stages.keyframes import keyframe_prompt
from tizita.stages.references import ref_prompt

REPO = Path(__file__).resolve().parent.parent
SB = json.loads((REPO / "storyboard.json").read_text(encoding="utf-8"))


def test_person_ref_prompt_carries_wardrobe_defaults_and_style():
    ref = next(r for r in SB["references"] if r["id"] == "ref_mother")
    p = ref_prompt(SB, ref)
    assert SB["style"]["characters"]["mother"]["wardrobe"] in p
    assert SB["style"]["character_defaults"] in p
    assert SB["style"]["style_block"] in p


def test_keyframe_prompt_has_character_block_and_ref_names():
    shot = next(s for s in SB["shots"] if s["id"] == "s09")
    p = keyframe_prompt(SB, shot, ["car", "child"])
    for c in shot["characters"]:
        assert SB["style"]["characters"][c]["wardrobe"] in p
    assert "car, child" in p and shot["keyframe"]["prompt"] in p


def test_contact_sheet_writes_grid(tmp_path):
    for i in range(3):
        Image.new("RGB", (64, 96), (i * 50, 0, 0)).save(tmp_path / f"{i}.png")
    out = contact_sheet([tmp_path / f"{i}.png" for i in range(3)], tmp_path / "s.jpg", cell=100)
    assert Image.open(out).size == (300, 100)


def test_choose_reference_sets_zero_based_index(tmp_path, monkeypatch):
    shutil.copy(REPO / "storyboard.json", tmp_path / "storyboard.json")
    monkeypatch.setenv("TIZITA_ROOT", str(tmp_path))
    r = CliRunner().invoke(app, ["choose", "reference", "ref_child", "3"])
    assert r.exit_code == 0
    sb = json.loads((tmp_path / "storyboard.json").read_text(encoding="utf-8"))
    assert next(x for x in sb["references"] if x["id"] == "ref_child")["sheet"]["chosen"] == 2
    bad = CliRunner().invoke(app, ["choose", "reference", "ref_child", "9"])
    assert bad.exit_code == 1

import pytest

from tizita.storyboard import count_words, lint, validate_schema
from tizita.util import canonical_hash, canonical_json


def codes(report):
    return {i.code for i in report.issues}


def test_good_fixture_passes(good_sb, project):
    report = lint(good_sb, project)
    assert report.ok, report.issues
    assert not report.warnings
    assert report.stats["shots"] == 9


def test_repo_storyboard_matches_fixture(good_sb):
    import json

    from tizita.util import PACKAGE_ROOT

    assert json.loads((PACKAGE_ROOT / "storyboard.json").read_text()) == good_sb


def test_schema_error(mutate, project):
    sb = mutate(lambda s: s["shots"][0].update(shot_size="huge"))
    assert validate_schema(sb)
    assert codes(lint(sb, project)) == {"schema"}


def _drop_shots(s):
    del s["shots"][7:]


def _dup_shot(s):
    s["shots"][1]["id"] = "s01"


def _short_reason(s):
    s["shots"][2]["reason"] = "because"


def _too_long(s):
    for shot in s["shots"]:
        shot["duration_s"] = 12


def _unknown_char(s):
    s["shots"][0]["characters"] = ["nobody"]


def _unknown_ref(s):
    s["shots"][0]["references"] = ["ref_nope"]


def _unknown_cue(s):
    s["shots"][0]["music_cue"] = "bridge"


def _real_person(s):
    s["references"][0].update(real_person=True, consent_id="C-001")


def _upload(s):
    s["shots"][0]["keyframe"].update(source="upload", upload_path="refs/private/nope.jpg")


@pytest.mark.parametrize(
    ("fn", "code"),
    [
        (_drop_shots, "shot_count"),
        (_dup_shot, "duplicate_id"),
        (_short_reason, "reason_short"),
        (_too_long, "planned_total"),
        (_unknown_char, "unknown_character"),
        (_unknown_ref, "unknown_reference"),
        (_unknown_cue, "unknown_cue"),
        (_real_person, "consent"),
        (_upload, "upload_missing"),
    ],
)
def test_each_error_rule(mutate, project, fn, code):
    report = lint(mutate(fn), project)
    assert not report.ok
    assert code in {i.code for i in report.errors}


def _fast(s):
    s["shots"][0]["narration"]["text_am"] = " ".join(["ቃል"] * 30)


def _long_sub(s):
    s["shots"][0]["narration"]["text_en"] = "word " * 30


def _gpu(s):
    for shot in s["shots"]:
        shot["motion"]["mode"] = "i2v"


@pytest.mark.parametrize(
    ("fn", "code"), [(_fast, "pace"), (_long_sub, "subtitle_fit"), (_gpu, "gpu_budget")]
)
def test_each_warning_rule(mutate, project, fn, code):
    report = lint(mutate(fn), project)
    assert report.ok
    assert code in {i.code for i in report.warnings}


def test_measured_total_out_of_range(good_sb, project):
    report = lint(good_sb, project, measured={"total_s": 95.0})
    assert "measured_total" in codes(report)


def test_measured_narration_replaces_estimate(good_sb, project):
    report = lint(good_sb, project, measured={"narration_s": {"s01": 1.0}})
    assert any(i.code == "pace" and "measured audio" in i.message for i in report.warnings)


def test_consent_passes_with_likeness_scope(mutate, project):
    sb = mutate(_real_person)
    reg = {"C-001": {"id": "C-001", "scope": ["likeness", "story"]}}
    assert lint(sb, project, registry=reg).ok
    reg_no_likeness = {"C-001": {"id": "C-001", "scope": ["story"]}}
    assert "consent" in codes(lint(sb, project, registry=reg_no_likeness))


def test_amharic_word_count():
    assert count_words("ይህ የሙከራ ትረካ ነው።") == 4
    assert count_words("ሰላም፡ዓለም") == 2


def test_canonical_hash_is_order_independent():
    assert canonical_json({"b": 1, "a": "ሰ"}) == '{"a":"ሰ","b":1}'
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})

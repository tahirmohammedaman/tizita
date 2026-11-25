import json

import pytest

from tizita import director
from tizita.events import EventBus
from tizita.providers.base import Provider, Result
from tizita.providers.profiles import Selection
from tizita.providers.registry import Registry
from tizita.providers.router import Router
from tizita.runlog import RunLog


def beats_from(sb: dict) -> dict:
    return {
        "title": "T",
        "logline": "L",
        "audience": "family",
        "intent": "warmth",
        "characters": {"youngest_sibling": {"description": "d", "wardrobe": "w"}},
        "references": [{"id": "ref_youngest", "kind": "person", "description": "d"}],
        "music": {
            "caption": "c",
            "bpm": 70,
            "key": "D minor",
            "cues": [{"id": "intro", "at_s": 0, "intent": "i"}],
        },
        "shots": [
            {
                "id": s["id"],
                "reason": "Shows the story beat for this moment.",
                "shot_size": "wide",
                "duration_s": 7,
                "characters": [],
                "references": [],
                "keyframe_prompt": "a car at dusk",
                "motion": "kenburns",
                "motion_prompt": "slow",
                "pan": "left",
                "zoom_to": 1.1,
                "text_am": s["narration"]["text_am"],
                "text_en": "A short line.",
                "music_cue": "intro",
                "transition_in": "crossfade",
            }
            for s in sb["shots"]
        ],
        "end_card": {"text_am": "ተጠናቀቀ።", "credits": ["ignored"]},
    }


class FakeText(Provider):
    def __init__(self, replies):
        super().__init__(
            "fake_text",
            {"adapter": "x", "capability": "text", "tier": "free_hosted", "model": "m"},
            env={},
            models_dir=None,
        )
        self.replies = list(replies)
        self.prompts = []

    def call(self, req):
        self.prompts.append(req.prompt)
        return Result(model="m", text=self.replies.pop(0))


def router(project, fake):
    reg = Registry.from_providers([fake], {"text": ["fake_text"]})
    sel = Selection(profile="free", tiers=["free_hosted", "deterministic"])
    return Router(
        reg, sel, project=project, runlog=RunLog(project.runs, profile="free"), bus=EventBus("t")
    )


def test_parse_json_strips_fences_and_prose():
    assert director.parse_json('Sure:\n```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ValueError):
        director.parse_json("no json here")


def test_assemble_builds_a_valid_storyboard_with_deterministic_fields(project, good_sb):
    from tizita.storyboard import lint

    sb = director.assemble(beats_from(good_sb))
    assert lint(sb, project, registry={}).ok
    assert sb["shots"][0]["transition_in"] == "fade_black"
    assert sb["shots"][2]["keyframe"]["seed"] == 1003 and sb["shots"][2]["motion"]["seed"] == 2003
    assert sb["references"][0]["real_person"] is False and sb["references"][0]["photos"] == []
    assert sb["style"]["characters"]["youngest_sibling"]["reference_id"] == "ref_youngest"
    assert "TODO(Tahir)" in sb["end_card"]["credits"][0]


def test_draft_repairs_after_an_invalid_reply_and_feeds_errors_back(project, good_sb):
    bad = beats_from(good_sb)
    bad["shots"][0]["shot_size"] = "gigantic"
    fake = FakeText([json.dumps(bad), json.dumps(beats_from(good_sb))])
    _sb, report, _ = director.draft(router(project, fake), project, {"whose_story": "mine"})
    assert report.ok and len(fake.prompts) == 2
    assert "previous attempt failed" in fake.prompts[1]


def test_promote_requires_a_clean_lint_and_backs_up(project, good_sb):
    draft = director.assemble(beats_from(good_sb))
    director.save_draft(project, draft)
    ok, errs = director.promote(project)
    assert ok and not errs
    assert json.loads(project.storyboard.read_text())["meta"]["title"] == "T"
    assert list((project.state / "backup").glob("storyboard_*.json"))
    draft["shots"] = draft["shots"][:3]
    director.save_draft(project, draft)
    ok, errs = director.promote(project)
    assert not ok and errs
    assert json.loads(project.storyboard.read_text())["meta"]["title"] == "T"  # untouched


def test_invented_person_references_are_merged_into_character_references(project, good_sb):
    beats = beats_from(good_sb)
    beats["references"].append({"id": "narrator_ref", "kind": "person", "description": "dup"})
    beats["shots"][0]["references"] = ["narrator_ref"]
    beats["shots"][0]["characters"] = ["youngest_sibling"]
    sb = director.assemble(beats)
    assert [r["id"] for r in sb["references"]] == ["ref_youngest"]
    assert sb["shots"][0]["references"] == ["ref_youngest"]

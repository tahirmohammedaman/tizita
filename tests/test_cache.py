from conftest import materialize

from tizita.cache import Manifest, cache_key
from tizita.dag import PlannedProvider, build_units, plan, summarize, unit_key

PROV = {"name": "fake", "model": "m1", "params": {}}


def _dirty(rows):
    return {f"{r.stage}/{r.unit}" for r in rows if r.needs_work}


def test_empty_manifest_everything_missing(good_sb, project):
    rows = plan(good_sb, project)
    assert {r.status for r in rows} == {"missing"}
    assert summarize(rows)["to_run"] == len(rows)


def test_full_cache_is_clean(good_sb, project):
    materialize(good_sb, project, PROV)
    rows = plan(good_sb, project)
    assert _dirty(rows) == set()


def test_unread_field_leaves_key_unchanged(good_sb, mutate, project):
    sb2 = mutate(lambda s: s["shots"][2]["motion"].update(approved=True, max_attempts=2))
    sb2["meta"]["logline"] = "changed"
    sb2["voice"]["pace_wps_limit"] = 3.0
    k1 = {u.id: u.fields for u in build_units(good_sb, project)}
    k2 = {u.id: u.fields for u in build_units(sb2, project)}
    assert k1 == k2


def test_one_narration_line_dirties_only_its_chain(good_sb, mutate, project):
    materialize(good_sb, project, PROV)
    sb2 = mutate(lambda s: s["shots"][2]["narration"].update(text_am="አዲስ መስመር።"))
    rows = plan(sb2, project)
    assert _dirty(rows) == {
        "narration/s03",
        "timing/project",
        "subtitles/project",
        "radio_cut/project",
        "assemble/project",
        "qa/project",
    }
    s03 = next(r for r in rows if r.stage == "narration" and r.unit == "s03")
    assert "narration.text_am" in s03.detail


def test_keyframe_prompt_dirties_keyframe_shot_and_assembly(good_sb, mutate, project):
    materialize(good_sb, project, PROV)
    sb2 = mutate(lambda s: s["shots"][0]["keyframe"].update(prompt="new composition"))
    assert _dirty(plan(sb2, project)) == {
        "keyframes/s01",
        "shots/s01",
        "assemble/project",
        "qa/project",
    }


def test_choosing_golden_reference_dirties_its_keyframes(good_sb, mutate, project):
    materialize(good_sb, project, PROV)
    sb2 = mutate(lambda s: s["references"][0]["sheet"].update(chosen=2))
    dirty = _dirty(plan(sb2, project))
    assert {"keyframes/s04", "keyframes/s05"} <= dirty
    assert "keyframes/s01" not in dirty


def test_provider_change_changes_key(good_sb, project):
    unit = build_units(good_sb, project)[0]
    assert unit_key(unit, {}, PROV) != unit_key(unit, {}, {**PROV, "name": "other"})
    assert unit_key(unit, {}, PROV) != unit_key(unit, {}, {**PROV, "model": "m2"})
    assert cache_key("a", 1, {}, {}, None, 1) != cache_key("a", 2, {}, {}, None, 1)


def test_provider_outside_active_chain_is_dirty(good_sb, project):
    materialize(good_sb, project, PROV)

    def resolver(cap, unit):
        return PlannedProvider(name="other", model="x", tier="free_hosted", chain=["other"])

    rows = plan(good_sb, project, resolver=resolver)
    narr = [r for r in rows if r.stage == "narration"]
    assert all(r.status == "dirty" and "provider fake" in r.detail for r in narr)


def test_fallback_upgradable(good_sb, project):
    m = materialize(good_sb, project, PROV)
    e = m.get("narration", "s01")
    e.is_fallback, e.primary_provider = True, "primary"
    m.save()

    def resolver(cap, unit):
        return PlannedProvider(
            name="primary", model="p", tier="free_hosted", chain=["primary", "fake"]
        )

    rows = plan(good_sb, project, resolver=resolver)
    row = next(r for r in rows if r.stage == "narration" and r.unit == "s01")
    assert row.status == "fallback-upgradable"
    assert not row.needs_work


def test_deleted_artifact_is_missing(good_sb, project):
    m = materialize(good_sb, project, PROV)
    (project.root / m.get("timing", "project").path).unlink()
    rows = plan(good_sb, project)
    assert next(r for r in rows if r.stage == "timing").status == "missing"
    assert "subtitles/project" in _dirty(rows)


def test_manifest_roundtrip(good_sb, project):
    materialize(good_sb, project, PROV)
    m = Manifest.load(project.manifest)
    assert m.get("narration", "s01").field_hashes
    assert not list(project.manifest.parent.glob(".manifest.json.*"))

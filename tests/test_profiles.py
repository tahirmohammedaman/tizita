import pytest

from tizita.dag import build_units
from tizita.events import EventBus
from tizita.providers.profiles import load_selection, parse_overrides
from tizita.providers.registry import Registry
from tizita.providers.router import Router
from tizita.runlog import RunLog

GPU_LOCAL = {"local_flux", "local_wan", "local_ace"}


def router(project, env=None, profile=None, overrides=None):
    env = {"MODELS_DIR": str(project.root / "no_models"), **(env or {})}
    reg = Registry.load(project, env)
    sel = load_selection(project, env, profile, overrides)
    return Router(reg, sel, project=project, runlog=RunLog(project.runs), bus=EventBus())


def test_free_profile_never_uses_paid_or_local_gpu(project):
    r = router(project)
    assert r.sel.profile == "free"
    for cap in r.registry.chains:
        for pid in r.chain_ids(cap):
            p = r.registry.get(pid)
            assert p.tier != "paid", pid
            assert pid not in GPU_LOCAL, pid


def test_real_config_has_no_lint_errors(project):
    r = router(project)
    assert [i for i in r.registry.lint(r.active_chains()) if i.level == "error"] == []


def test_paid_needs_allow_and_budget(project):
    no_allow = router(project, {"PAID_BUDGET_USD": "5"}, profile="paid")
    assert all(no_allow.registry.get(p).tier != "paid" for p in no_allow.chain_ids("text"))
    no_budget = router(project, {"ALLOW_PAID": "true"}, profile="paid")
    assert all(no_budget.registry.get(p).tier != "paid" for p in no_budget.chain_ids("text"))
    ok = router(project, {"ALLOW_PAID": "true", "PAID_BUDGET_USD": "5"}, profile="paid")
    assert ok.registry.get(ok.chain_ids("text")[0]).tier == "paid"


def test_paid_override_still_needs_the_guard(project):
    r = router(project, overrides=["text=gemini_paid_text"])
    assert "gemini_paid_text" not in r.chain_ids("text")


def test_local_first_and_override_order(project):
    r = router(project, profile="local-first")
    assert r.registry.get(r.chain_ids("tts")[0]).tier == "local"
    o = router(project, overrides=["image=cf_flux1_schnell"])
    assert o.chain_ids("image")[:2] == ["cf_flux1_schnell", "cf_flux2_klein"]
    assert parse_overrides(["text=openrouter_text:meta/x:free"]) == {
        "text": ("openrouter_text", "meta/x:free")
    }
    with pytest.raises(ValueError):
        router(project, overrides=["image=nope"]).chain_ids("image")


def test_custom_profile_chain(project):
    r = router(project, profile="custom")
    assert r.chain_ids("tts")[0] == "mms_tts_local"


def test_missing_weights_unavailable_with_plan_hint(project, good_sb):
    r = router(project)
    ok, reason, hint = r.usable("mms_tts_local")
    assert not ok and reason == "weights missing"
    assert hint == "tizita models download --only mms-tts-amh"
    unit = next(
        u
        for u in build_units(good_sb, project)
        if u.capability == "embed" or u.stage == "narration"
    )
    planned = r.plan_provider("embed", unit)
    assert planned.name == "none" and "tizita models download" in planned.hint


def test_unknown_profile(project):
    with pytest.raises(ValueError):
        router(project, profile="turbo")


def test_privacy_filter_on_real_config(project):
    r = router(project)
    for pid in r.chain_ids("text", private_media=True):
        assert r.registry.get(pid).accepts_private_media
    assert "gemini_flash" not in r.chain_ids("text", private_media=True)


def test_gemini_key_rotation_moves_to_next_key_on_quota():
    from google.genai import errors

    from tizita.providers import gemini_text
    from tizita.providers.gemini_text import GeminiText, call_rotating

    gemini_text._SPENT.clear()
    p = GeminiText(
        "g",
        {"capability": "text", "tier": "free_hosted", "env_any": ["K1", "K2", "K3"]},
        env={"K1": "a", "K2": "b"},
        models_dir=None,
    )
    assert p.api_keys() == ["K1", "K2"] and p.missing_env() == []
    used = []

    def fn(client):
        used.append(client._api_client.api_key)
        if len(used) == 1:
            raise errors.ClientError(
                429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "x"}}
            )
        return "ok"

    assert call_rotating(p, fn) == "ok" and used == ["a", "b"]
    gemini_text._SPENT.clear()
    q = GeminiText(
        "g",
        {"capability": "text", "tier": "free_hosted", "env_any": ["K1"]},
        env={},
        models_dir=None,
    )
    assert q.missing_env() == ["K1"]

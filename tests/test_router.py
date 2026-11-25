import json

import pytest

from tizita.consent import ConsentError
from tizita.events import EventBus, failures_sink, file_sink
from tizita.providers.base import Provider, Request, Result
from tizita.providers.circuit import CircuitStore
from tizita.providers.errors import (
    BadRequest,
    ChainExhausted,
    OutOfMemory,
    QuotaExhausted,
    RateLimited,
    SafetyBlocked,
    Transient,
    classify_http,
)
from tizita.providers.profiles import Selection
from tizita.providers.registry import Registry
from tizita.providers.router import Router
from tizita.runlog import RunLog, iter_runs, runlog_validator


class Fake(Provider):
    def __init__(
        self,
        pid,
        script=(),
        *,
        tier="free_hosted",
        pool=None,
        private=False,
        cap="image",
        usd=None,
        env=None,
    ):
        cfg = {
            "adapter": "fake",
            "capability": cap,
            "tier": tier,
            "quota_pool": pool or f"{pid}:pool",
            "model": f"{pid}-m",
            "accepts_private_media": private,
            "env": env or [],
            "label": pid.upper(),
        }
        super().__init__(pid, cfg, env={}, models_dir=None)
        if usd is not None:
            self.cost_basis = "x"
            self.set_pricing({"usd": usd, "unit": "call"})
        self.script = list(script)
        self.calls = []

    def call(self, req):
        self.calls.append(req)
        step = self.script.pop(0) if self.script else "ok"
        if isinstance(step, Exception):
            raise step
        return Result(model=self.model, data=b"img", ext="png")


SEL = Selection(profile="free", tiers=["free_hosted", "local", "deterministic"])


@pytest.fixture
def mk(project):
    def _mk(*providers, sel=SEL, consents=None, chain=None):
        reg = Registry.from_providers(
            list(providers), {"image": chain or [p.name for p in providers]}
        )
        bus = EventBus("r_test")
        bus.subscribe(file_sink(project.events))
        bus.subscribe(failures_sink(project.failures))
        bus.captured = []
        bus.subscribe(bus.captured.append)
        sleeps = []
        r = Router(
            reg,
            sel,
            project=project,
            runlog=RunLog(project.runs, profile=sel.profile),
            bus=bus,
            consents=consents or {},
            sleep=sleeps.append,
            rng=lambda: 1.0,
        )
        r.sleeps = sleeps
        return r

    return _mk


def req(project, **kw):
    return Request(
        "image",
        "keyframes",
        "s04",
        prompt="a pot",
        seed=1004,
        output_path=project.root / "outputs" / "k.img",
        **kw,
    )


def lines(project):
    return list(iter_runs(project.runs))


def test_quota_falls_back_and_opens_circuit(mk, project):
    a = Fake("a", [QuotaExhausted("429 daily quota", reset_at="2999-01-01T00:00:00.000Z")])
    b = Fake("b")
    r = mk(a, b)
    res, used, is_fb = r.call(req(project))
    assert used.name == "b" and is_fb
    assert res.output_path.suffix == ".png" and res.output_path.exists()
    ls = lines(project)
    assert [(x["provider"], x["status"]) for x in ls] == [("a", "fallback_triggered"), ("b", "ok")]
    assert ls[1]["fallback_from"] == "a"
    assert all(not list(runlog_validator().iter_errors(x)) for x in ls)
    state = json.loads((project.state / "circuits.json").read_text())
    assert state["a"]["open_until"].startswith("2999")
    events = [json.loads(x) for x in project.events.read_text().splitlines()]
    fb = next(e for e in events if e["type"] == "fallback")
    assert fb["from"] == "a" and fb["to"] == "b" and fb["error_class"] == "quota_exhausted"
    cli = next(e for e in r.bus.captured if e["type"] == "fallback")["cli"]
    assert "quota exhausted → falling back to B" in cli
    drafts = [json.loads(x) for x in project.failures.read_text().splitlines()]
    assert [(d["kind"], d["fallback_to"]) for d in drafts] == [("fallback", "b")]

    # the circuit persists: a fresh router skips `a` without calling it
    a2, b2 = Fake("a"), Fake("b")
    r2 = mk(a2, b2)
    r2.circuits = CircuitStore(project.state / "circuits.json")
    r2.call(req(project))
    assert a2.calls == [] and len(b2.calls) == 1


def test_transient_retries_with_backoff_then_falls_back(mk, project):
    a = Fake("a", [Transient("503")] * 3)
    b = Fake("b")
    r = mk(a, b)
    _, used, _ = r.call(req(project))
    assert used.name == "b"
    assert [c.seed for c in a.calls] == [1004, 2004, 3004]  # seed + attempt*1000
    assert r.sleeps == [2.0, 4.0]  # full jitter with rng=1.0 → the cap of each step
    statuses = [x["status"] for x in lines(project) if x["provider"] == "a"]
    assert statuses == ["error", "error", "fallback_triggered"]


def test_transient_then_success_stays_on_provider(mk, project):
    a = Fake("a", [Transient("timeout"), "ok"])
    b = Fake("b")
    _, used, is_fb = mk(a, b).call(req(project))
    assert used.name == "a" and not is_fb and b.calls == []
    assert lines(project)[-1]["attempt"] == 2 and lines(project)[-1]["seed"] == 2004


@pytest.mark.parametrize("exc", [BadRequest("422 bad width"), SafetyBlocked("nsfw")])
def test_bad_request_and_safety_do_not_fall_back(mk, project, exc):
    a, b = Fake("a", [exc]), Fake("b")
    with pytest.raises(type(exc)):
        mk(a, b).call(req(project))
    assert b.calls == []
    assert lines(project)[-1]["status"] == "error"


def test_short_rate_limit_waits_and_retries_once(mk, project):
    a = Fake("a", [RateLimited("429", retry_after=5), "ok"])
    r = mk(a, Fake("b"))
    _, used, _ = r.call(req(project))
    assert used.name == "a" and r.sleeps == [5]


def test_long_rate_limit_is_treated_as_quota(mk, project):
    a = Fake("a", [RateLimited("429", retry_after=600)])
    b = Fake("b")
    r = mk(a, b)
    _, used, _ = r.call(req(project))
    assert used.name == "b" and r.sleeps == []
    assert r.circuits.is_open("a")


def test_oom_retries_degraded_once(mk, project):
    a = Fake("a", [OutOfMemory("CUDA OOM"), "ok"])
    _, used, _ = mk(a).call(req(project, params={"width": 768, "height": 1344}))
    assert used.name == "a"
    assert a.calls[1].degraded and a.calls[1].params["width"] == 384


def test_unavailable_is_skipped_silently(mk, project):
    a = Fake("a", env=["NOT_SET_KEY"])
    b = Fake("b")
    _, used, is_fb = mk(a, b).call(req(project))
    assert used.name == "b" and is_fb and a.calls == []
    assert [x["provider"] for x in lines(project)] == ["b"]
    assert not project.events.exists() or "fallback" not in project.events.read_text()


def test_chain_exhausted(mk, project):
    a = Fake("a", [QuotaExhausted("quota")])
    with pytest.raises(ChainExhausted) as ei:
        mk(a).call(req(project))
    assert ei.value.attempts == [("a", "quota_exhausted")]


def test_private_media_never_goes_to_non_private_provider(mk, project):
    public = Fake("gemini", private=False)
    private_ok = Fake("cf", private=True)
    r = mk(public, private_ok)
    _, used, _ = r.call(req(project, private_media=True))
    assert used.name == "cf" and public.calls == []
    with pytest.raises(ChainExhausted):
        mk(Fake("gemini2", private=False)).call(req(project, private_media=True))


def test_consent_gate_blocks_real_person_without_consent(mk, project):
    a = Fake("a")
    ref = {"id": "ref_g", "real_person": True, "consent_id": "C-001"}
    with pytest.raises(ConsentError):
        mk(a).call(req(project, references=[ref]))
    assert a.calls == []
    ok = mk(a, consents={"C-001": {"id": "C-001", "scope": ["likeness"]}})
    _, used, _ = ok.call(req(project, references=[ref]))
    assert used.name == "a"


def test_budget_cap_falls_back_to_free(mk, project):
    paid = Fake("fal", tier="paid", usd=1.0)
    free = Fake("cf")
    sel = Selection(profile="paid", tiers=["paid", "free_hosted"], allow_paid=True, budget_usd=0.5)
    r = mk(paid, free, sel=sel)
    _, used, _ = r.call(req(project))
    assert used.name == "cf" and paid.calls == []
    ev = [json.loads(x) for x in project.events.read_text().splitlines()]
    assert any(e["type"] == "fallback" and e["error_class"] == "budget_cap" for e in ev)


def test_paid_spend_is_logged_and_capped(mk, project):
    paid = Fake("fal", tier="paid", usd=0.3)
    sel = Selection(profile="paid", tiers=["paid", "free_hosted"], allow_paid=True, budget_usd=0.5)
    r = mk(paid, Fake("cf"), sel=sel)
    assert r.call(req(project))[1].name == "fal"
    assert lines(project)[-1]["cost_actual_usd"] == 0.3
    assert r.call(req(project))[1].name == "cf"  # 0.3 + 0.3 > 0.5


def test_same_pool_warning():
    a, b = Fake("a", pool="cloudflare:neurons"), Fake("b", pool="cloudflare:neurons")
    reg = Registry.from_providers([a, b], {"image": ["a", "b"]})
    issues = reg.lint({"image": ["a", "b"]})
    assert [i.code for i in issues] == ["same_pool_fallback"]


@pytest.mark.parametrize(
    ("status", "body", "ra", "kind"),
    [
        (
            429,
            "you have used up your daily free allocation of 10,000 neurons",
            None,
            "quota_exhausted",
        ),
        (429, "too many requests", "3", "rate_limited"),
        (503, "upstream", None, "transient"),
        (400, "width must be multiple of 16", None, "bad_request"),
        (400, "NSFW content detected", None, "safety_blocked"),
        (404, "no such model", None, "unavailable"),
        (401, "bad token", None, "unavailable"),
    ],
)
def test_classify_http(status, body, ra, kind):
    assert classify_http(status, body, ra).kind == kind

import json

import pytest

from tizita.events import EventBus, FallbackEvent, failures_sink, file_sink
from tizita.runlog import RunLog, iter_runs, prompt_ref, runlog_validator, spent_usd


def test_line_matches_schema(tmp_path):
    log = RunLog(tmp_path / "runs.jsonl", profile="free")
    line = log.record(
        stage="keyframes",
        unit="s04",
        capability="image",
        provider="cloudflare",
        model="@cf/x",
        tier="free_hosted",
        params={"width": 768},
        seed=1004,
        latency_ms=1840,
        **prompt_ref("p" * 500),
    )
    assert list(runlog_validator().iter_errors(line)) == []
    assert len(line["prompt_head"]) == 200
    assert line["call_id"] == "c_0001"
    stored = list(iter_runs(tmp_path / "runs.jsonl"))
    assert stored == [line]


def test_bad_line_rejected(tmp_path):
    log = RunLog(tmp_path / "runs.jsonl")
    with pytest.raises(ValueError):
        log.record(
            stage="x", unit="y", capability="video", provider="p", model="m", tier="free_hosted"
        )
    assert not (tmp_path / "runs.jsonl").exists()


def test_spent_usd(tmp_path):
    log = RunLog(tmp_path / "runs.jsonl")
    for c in (0.5, 0.25):
        log.record(
            stage="s",
            unit="u",
            capability="image",
            provider="fal",
            model="m",
            tier="paid",
            cost_actual_usd=c,
        )
    assert spent_usd(tmp_path / "runs.jsonl") == 0.75


def test_fallback_event_fans_out(tmp_path):
    bus = EventBus("r_x")
    bus.subscribe(file_sink(tmp_path / "events.jsonl"))
    bus.subscribe(failures_sink(tmp_path / "failures.jsonl"))
    fe = FallbackEvent(
        "keyframes",
        "s04",
        "cf_flux2_klein",
        "local_flux",
        "free_hosted",
        "local",
        "quota_exhausted",
        "429 daily",
        from_label="FLUX.2 klein (cloudflare)",
        to_label="FLUX.2 klein (local G14)",
    )
    bus.fallback(fe)
    assert fe.cli_line() == (
        "⚠ keyframes s04: FLUX.2 klein (cloudflare) quota exhausted → falling back to "
        "FLUX.2 klein (local G14) [free_hosted → local]"
    )
    ev = json.loads((tmp_path / "events.jsonl").read_text())
    assert ev["from"] == "cf_flux2_klein" and "cli" not in ev
    draft = json.loads((tmp_path / "failures.jsonl").read_text())
    assert draft["draft"] and draft["fallback_to"] == "local_flux"

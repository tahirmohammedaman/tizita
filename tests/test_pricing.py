import pytest

from tizita import costs
from tizita.pricing import rated_cost

TOKENS = {"unit": "tokens_io", "model": "m", "input_usd_per_m": 1.0, "output_usd_per_m": 4.0}
TTS = {"unit": "tts_audio", "output_usd_per_m": 9.0, "tokens_per_s": 25}
TILES = {"unit": "image_tiles", "tile_usd": 0.001, "step_usd": 0.01, "fixed_px": 1024}


def test_tokens_are_priced_by_direction_and_only_for_the_listed_model():
    used = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}
    assert rated_cost(TOKENS, "m", {}, used) == 3.0
    assert rated_cost(TOKENS, "other", {}, used) is None
    assert rated_cost(TOKENS, "m", {}, {}) is None


def test_audio_seconds_and_image_tiles():
    assert rated_cost(TTS, None, {}, {"duration_s": 10}) == 0.00225
    assert rated_cost(TTS, None, {}, {}) is None
    assert rated_cost(TILES, None, {"width": 512, "height": 512, "steps": 4}, {}) == 0.044
    klein = {"unit": "image_tiles", "tile_usd": 0.001}
    assert rated_cost(klein, None, {"width": 576, "height": 1024}, {}) == pytest.approx(0.00225)
    assert rated_cost(klein, None, {}, {}) is None


def test_report_recomputes_old_lines_that_stored_zero():
    line = {
        "cost_basis": "pricing.yaml#g.tts",
        "status": "ok",
        "tier": "free_hosted",
        "model": "x",
        "params": {},
        "metrics": {"duration_s": 10},
        "cost_list_price_usd": 0.0,
    }
    assert costs.list_price(line, {"g.tts": TTS}) == 0.00225
    assert costs.list_price({**line, "metrics": {}}, {"g.tts": TTS}) is None

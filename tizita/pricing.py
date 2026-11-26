"""List-price arithmetic for `config/pricing.yaml` entries (SPEC §8.3). Pure functions.

"Rated" units carry the provider's published rates and are applied to what a call actually used.
A rated entry never guesses: missing usage or a different model gives None (unknown).
"""

from __future__ import annotations

RATED_UNITS = ("tokens_io", "tts_audio", "audio_minutes", "image_tiles")
TILE_PX = 512 * 512


def _first(metrics: dict, *keys: str):
    return next((metrics[k] for k in keys if metrics.get(k) is not None), None)


def rated_cost(entry: dict, model: str | None, params: dict, metrics: dict) -> float | None:
    if entry.get("model") and model != entry["model"]:
        return None
    unit = entry["unit"]
    if unit == "tokens_io":
        used_in = _first(metrics, "input_tokens", "prompt_tokens")
        used_out = _first(metrics, "output_tokens", "completion_tokens")
        if used_in is None or used_out is None:
            return None
        return (used_in * entry["input_usd_per_m"] + used_out * entry["output_usd_per_m"]) / 1e6
    if unit == "tts_audio":
        # output audio only: the text input tokens are not logged
        seconds = metrics.get("duration_s")
        if seconds is None:
            return None
        return seconds * entry["tokens_per_s"] * entry["output_usd_per_m"] / 1e6
    if unit == "audio_minutes":
        seconds = metrics.get("duration_s")
        return None if seconds is None else seconds / 60 * entry["usd_per_minute"]
    if unit == "image_tiles":
        # output tiles (and steps) only: reference image sizes are not logged
        side = entry.get("fixed_px")
        width, height = (side, side) if side else (params.get("width"), params.get("height"))
        if not width or not height:
            return None
        steps = params.get("steps")
        if entry.get("step_usd") and steps is None:
            return None
        per_step = (entry.get("step_usd") or 0) * (steps or 0)
        return width * height / TILE_PX * entry["tile_usd"] + per_step
    raise ValueError(f"not a rated unit: {unit}")


def estimated_usage(prompt: str | None, params: dict) -> tuple[dict, dict]:
    """(params, metrics) guessed before a call, for the paid guard. Errs high on output."""
    prompt_tokens = len(prompt or "") // 4
    metrics = {
        "input_tokens": prompt_tokens,
        "output_tokens": int(params.get("max_tokens", 512)),
        "duration_s": float(params.get("duration_s", 30)),
    }
    return {"width": 1024, "height": 1024, "steps": 4, **params}, metrics

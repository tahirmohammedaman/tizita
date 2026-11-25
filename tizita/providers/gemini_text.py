"""Gemini text via google-genai (free tier: `accepts_private_media: false`)."""

from __future__ import annotations

import json
import re

from tizita.providers.base import Provider, Request, Result
from tizita.providers.errors import (
    ProviderError,
    QuotaExhausted,
    RateLimited,
    SafetyBlocked,
    Transient,
    classify_http,
)


def gemini_client(env: dict[str, str], key_name: str = "GEMINI_API_KEY"):
    from google import genai

    return genai.Client(api_key=env[key_name])


def classify_gemini(e: Exception) -> ProviderError:
    """google.genai.errors.APIError → taxonomy. Per-minute 429s carry a retryDelay."""
    code = int(getattr(e, "code", 0) or 0)
    body = f"{getattr(e, 'status', '')} {getattr(e, 'message', '') or e}"
    details = json.dumps(getattr(e, "details", None) or {}, default=str)
    if code == 429:
        m = re.search(r'retryDelay["\']?\s*:\s*["\']?(\d+(?:\.\d+)?)s', details)
        delay = float(m.group(1)) if m else None
        if re.search(r"PerDay|per day|daily", body + details, re.IGNORECASE):
            return QuotaExhausted(body[:300], status=code, retry_after=delay)
        return RateLimited(body[:300], status=code, retry_after=delay)
    if code == 0:
        return Transient(body[:300])
    return classify_http(code, body)


def check_blocked(resp) -> None:
    fb = getattr(resp, "prompt_feedback", None)
    if fb is not None and getattr(fb, "block_reason", None):
        raise SafetyBlocked(f"prompt blocked: {fb.block_reason}")
    for c in getattr(resp, "candidates", None) or []:
        reason = str(getattr(c, "finish_reason", "") or "")
        if "SAFETY" in reason or "PROHIBITED" in reason or "BLOCKLIST" in reason:
            raise SafetyBlocked(f"response blocked: {reason}")


class GeminiText(Provider):
    def call(self, req: Request) -> Result:
        from google.genai import errors, types

        client = gemini_client(self.env, self.cfg.get("env", ["GEMINI_API_KEY"])[0])
        params = {**self.params, **req.params}
        cfg = types.GenerateContentConfig(
            system_instruction=req.inputs.get("system"),
            temperature=params.get("temperature"),
            max_output_tokens=params.get("max_tokens"),
            seed=req.seed,
            response_mime_type=params.get("response_mime_type"),
        )
        try:
            resp = client.models.generate_content(model=self.model, contents=req.prompt, config=cfg)
        except errors.APIError as e:
            raise classify_gemini(e) from e
        check_blocked(resp)
        usage = getattr(resp, "usage_metadata", None)
        metrics = {}
        if usage is not None:
            metrics = {
                "input_tokens": getattr(usage, "prompt_token_count", None),
                "output_tokens": getattr(usage, "candidates_token_count", None),
            }
        text = resp.text or ""
        return Result(
            model=self.model,
            text=text,
            data=text.encode(),
            mime="text/plain",
            ext="txt",
            metrics=metrics,
            seed_used=req.seed,
        )

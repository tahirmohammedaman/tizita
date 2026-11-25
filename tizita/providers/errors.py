"""Error taxonomy (SPEC §7.3). Adapters raise these; the router decides retry / fallback / fail."""

from __future__ import annotations

import re


class ProviderError(Exception):
    kind = "provider_error"

    def __init__(
        self,
        message: str,
        *,
        reset_at: str | None = None,
        retry_after: float | None = None,
        status: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.reset_at = reset_at
        self.retry_after = retry_after
        self.status = status


class QuotaExhausted(ProviderError):
    """Daily/weekly limit gone: open the circuit until reset_at, then fall back."""

    kind = "quota_exhausted"


class RateLimited(ProviderError):
    """Short 429: wait if Retry-After <= 30 s and retry once, else treat as quota."""

    kind = "rate_limited"


class Transient(ProviderError):
    """5xx, timeout, connection reset: backoff with full jitter (max 3 tries), then fall back."""

    kind = "transient"


class BadRequest(ProviderError):
    """4xx validation: fail fast, no fallback."""

    kind = "bad_request"


class SafetyBlocked(ProviderError):
    """Provider refused the content: fail the unit with a hint to rephrase; no silent fallback."""

    kind = "safety_blocked"


class Unavailable(ProviderError):
    """Not configured / offline / weights missing / model moved: skip to the next provider."""

    kind = "unavailable"

    def __init__(self, message: str, *, hint: str | None = None, moved: bool = False, **kw):
        super().__init__(message, **kw)
        self.hint = hint
        self.moved = moved


class OutOfMemory(ProviderError):
    """CUDA OOM: retry once degraded (lower resolution / offload), then fall back."""

    kind = "out_of_memory"


class ChainExhausted(ProviderError):
    """Every provider in the chain failed or was unavailable."""

    kind = "chain_exhausted"

    def __init__(self, message: str, *, attempts: list[tuple[str, str]] | None = None):
        super().__init__(message)
        self.attempts = attempts or []


_QUOTA_WORDS = re.compile(
    r"quota|per ?day|daily|exhausted|allocation|neurons|limit exceeded|billing|credits",
    re.IGNORECASE,
)
_SAFETY_WORDS = re.compile(
    r"safety|nsfw|blocked|content policy|moderation|prohibited|flagged", re.IGNORECASE
)


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*s?\s*$", str(value))
    return float(m.group(1)) if m else None


def classify_http(
    status: int, body: str = "", retry_after: str | float | None = None
) -> ProviderError:
    """Map an HTTP failure to the taxonomy. `body` is the (truncated) response text."""
    msg = f"HTTP {status}: {body[:300]}".strip()
    ra = retry_after if isinstance(retry_after, float | int) else parse_retry_after(retry_after)
    if status == 429:
        if _QUOTA_WORDS.search(body) and not (ra is not None and ra <= 30):
            return QuotaExhausted(msg, status=status, retry_after=ra)
        return RateLimited(msg, status=status, retry_after=ra)
    if status in (401, 403):
        if _QUOTA_WORDS.search(body):
            return QuotaExhausted(msg, status=status)
        return Unavailable(f"auth rejected ({msg})", status=status, hint="check the API key/token")
    if status == 404:
        return Unavailable(f"model or endpoint not found ({msg})", status=status, moved=True)
    if status in (408, 409, 425) or status >= 500:
        return Transient(msg, status=status, retry_after=ra)
    if _SAFETY_WORDS.search(body):
        return SafetyBlocked(msg, status=status)
    return BadRequest(msg, status=status)

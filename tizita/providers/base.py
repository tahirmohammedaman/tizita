"""Provider interface (SPEC §7.1). Concrete adapters subclass `Provider` and implement `call`."""

from __future__ import annotations

import io
import os
import wave
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from tizita.providers.errors import ProviderError, Unavailable

CAPABILITIES = ("text", "tts", "image", "image_edit", "i2v", "music", "embed", "asr")
TIERS = ("free_hosted", "local", "paid", "deterministic")


@dataclass
class Request:
    capability: str
    stage: str
    unit: str
    prompt: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None
    inputs: dict[str, Any] = field(default_factory=dict)  # system, images, audio, texts, voice…
    private_media: bool = False  # carries files from refs/private or private uploads
    references: list[dict] = field(default_factory=list)  # storyboard refs (consent gate)
    cache_key: str | None = None
    output_path: Path | None = None
    degraded: bool = False

    def with_seed(self, seed: int | None) -> Request:
        return replace(self, seed=seed)

    def degrade(self) -> Request:
        """After an OOM: halve the resolution and ask for offload."""
        p = dict(self.params)
        for k in ("width", "height"):
            if k in p:
                p[k] = int(p[k]) // 2 // 16 * 16
        p["offload"] = True
        return replace(self, params=p, degraded=True)


@dataclass
class Result:
    model: str
    data: bytes | None = None
    text: str | None = None
    mime: str = "application/octet-stream"
    ext: str = "bin"
    metrics: dict[str, Any] = field(default_factory=dict)
    params_used: dict[str, Any] = field(default_factory=dict)
    seed_used: int | None = None
    gpu_seconds: float | None = None
    queue_ms: int | None = None
    output_path: Path | None = None  # set by the router once written


@dataclass
class Availability:
    ok: bool
    reason: str = "ready"
    hint: str | None = None


class Provider:
    """Configured from one `config/providers.yaml` entry."""

    executor = "api"

    def __init__(self, pid: str, cfg: dict, *, env: dict[str, str], models_dir: Path):
        self.name = pid
        self.cfg = cfg
        self.env = env
        self.models_dir = models_dir
        self.model: str = cfg.get("model") or ""
        self.label: str = cfg.get("label") or pid
        self.capability: str = cfg["capability"]
        self.tier: str = cfg["tier"]
        self.quota_pool: str = cfg.get("quota_pool") or f"{pid}:default"
        self.accepts_private_media: bool = bool(cfg.get("accepts_private_media", False))
        self.licence: str = cfg.get("licence") or ""
        self.params: dict = cfg.get("params") or {}
        self.cost_basis: str | None = cfg.get("cost_basis")
        self._list_price: dict | None = None
        # (key name, error, latency ms) per key given up on mid-call; the router logs and clears it
        self.rotated: list[tuple[str, ProviderError, int]] = []

    # -- configuration -------------------------------------------------
    def missing_env(self) -> list[str]:
        miss = [k for k in self.cfg.get("env", []) if not self.env.get(k)]
        any_of = self.cfg.get("env_any") or []
        if any_of and not any(self.env.get(k) for k in any_of):
            miss.append(" | ".join(any_of))
        return miss

    def api_keys(self) -> list[str]:
        """Names of the configured keys in `env_any` (rotation order)."""
        return [k for k in self.cfg.get("env_any", []) if self.env.get(k)]

    def weights_path(self) -> Path | None:
        w = self.cfg.get("weights")
        return (self.models_dir / w) if w else None

    def available(self) -> Availability:
        if not self.cfg.get("adapter"):
            lands = self.cfg.get("lands_in", "a later milestone")
            return Availability(False, f"planned ({lands})", None)
        if missing := self.missing_env():
            return Availability(False, f"key missing: {', '.join(missing)}", "add it to .env")
        if (w := self.weights_path()) is not None and not w.exists():
            item = self.cfg.get("download_item") or w.name
            return Availability(False, "weights missing", f"tizita models download --only {item}")
        return Availability(True)

    def require_available(self) -> None:
        av = self.available()
        if not av.ok:
            raise Unavailable(av.reason, hint=av.hint)

    # -- cost (SPEC §7.2, §8.3) -----------------------------------------
    def set_pricing(self, entry: dict | None) -> None:
        self._list_price = entry

    def est_cost_usd(self, req: Request) -> float:
        """List-price estimate for one call (0 if unknown). Actual cost is 0 unless tier=paid."""
        e = self._list_price or {}
        usd = e.get("usd")
        if usd is None:
            return 0.0
        unit = e.get("unit", "call")
        if unit == "m_tokens":
            tokens = len(req.prompt or "") / 4 + int(req.params.get("max_tokens", 512))
            return float(usd) * tokens / 1e6
        if unit == "image":
            return float(usd) * int(req.params.get("n", 1))
        if unit == "second":
            return float(usd) * float(req.params.get("duration_s", 5))
        return float(usd)

    # -- the call -----------------------------------------------------
    def call(self, req: Request) -> Result:  # pragma: no cover - interface
        raise NotImplementedError


def pcm16_to_wav(pcm: bytes, rate: int, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_duration_s(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / float(w.getframerate())


def expand(path: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(path)))

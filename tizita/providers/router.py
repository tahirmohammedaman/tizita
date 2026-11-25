"""Provider router (SPEC §7): walks the active chain for a capability, retries, falls back,
opens circuits, enforces the paid guard, privacy routing and the consent gate, and writes one
runs.jsonl line per attempt."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable

import httpx

from tizita.consent import load_registry, require_consent
from tizita.dag import PlannedProvider, Unit
from tizita.events import EventBus, FallbackEvent
from tizita.providers.base import Provider, Request, Result
from tizita.providers.circuit import CircuitStore, next_reset
from tizita.providers.errors import (
    BadRequest,
    ChainExhausted,
    OutOfMemory,
    ProviderError,
    QuotaExhausted,
    RateLimited,
    SafetyBlocked,
    Transient,
    Unavailable,
)
from tizita.providers.profiles import Selection, chain_for
from tizita.providers.registry import Registry
from tizita.runlog import RunLog, prompt_ref, spent_usd
from tizita.util import Project, atomic_write_bytes, canonical_hash, sha256_bytes

log = logging.getLogger("tizita.router")

MAX_ATTEMPTS = 3  # CLAUDE.md: at most 3 attempts per unit and provider before the fallback
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 30.0
RATE_LIMIT_WAIT_MAX_S = 30.0
RETRY_SEED_STEP = 1000  # retries use seed + attempt*1000 (SPEC §6.2)


PRIVATE_MEDIA_NOTICE = (
    "private photo(s) will be sent to a hosted provider that accepts private media (Cloudflare "
    "Workers AI), not to Gemini. Only people who consented may appear; nothing is kept in the repo."
)


class Router:
    def __init__(
        self,
        registry: Registry,
        selection: Selection,
        *,
        project: Project,
        runlog: RunLog,
        bus: EventBus,
        circuits: CircuitStore | None = None,
        consents: dict[str, dict] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ):
        self.registry = registry
        self.sel = selection
        self.project = project
        self.runlog = runlog
        self.bus = bus
        self.circuits = circuits or CircuitStore(project.state / "circuits.json")
        self._consents = consents
        self.sleep = sleep
        self.rng = rng
        self._spent = spent_usd(runlog.path)
        self._notified_private = False

    # ------------------------------------------------------------ chains
    def chain_ids(self, capability: str, *, private_media: bool = False) -> list[str]:
        ids = chain_for(capability, self.registry.catalogue, self.registry.chains, self.sel)
        if private_media:
            ids = [i for i in ids if self.registry.get(i).accepts_private_media]
        return ids

    def active_chains(self) -> dict[str, list[str]]:
        return {cap: self.chain_ids(cap) for cap in self.registry.chains}

    def _model_override(self, p: Provider, capability: str) -> str:
        ov = self.sel.overrides.get(capability)
        return ov[1] if ov and ov[0] == p.name and ov[1] else p.model

    def usable(self, pid: str) -> tuple[bool, str, str | None]:
        p = self.registry.get(pid)
        if self.circuits.is_open(pid):
            return False, f"circuit open until {self.circuits.open_until(pid)}", None
        av = p.available()
        return av.ok, av.reason, av.hint

    def plan_provider(self, capability: str, unit: Unit) -> PlannedProvider | None:
        """Resolver for `tizita plan`: the first usable provider, plus the whole chain."""
        ids = self.chain_ids(capability)
        hints = []
        for pid in ids:
            ok, reason, hint = self.usable(pid)
            if ok:
                p = self.registry.get(pid)
                return PlannedProvider(
                    name=pid,
                    model=self._model_override(p, capability),
                    tier=p.tier,
                    chain=ids,
                    label=f"{p.label} [{p.tier}]",
                    params=p.params,
                )
            if hint:
                hints.append(f"{pid}: {reason} → {hint}")
        msg = "no usable provider" + (f" ({'; '.join(hints[:2])})" if hints else "")
        return PlannedProvider(name="none", model=None, tier="-", chain=ids, label="—", hint=msg)

    # ------------------------------------------------------------ call
    def consents(self) -> dict[str, dict]:
        if self._consents is None:
            self._consents = load_registry(self.project.consents)
        return self._consents

    def call(self, req: Request) -> tuple[Result, Provider, bool]:
        """Returns (result, provider used, is_fallback). Raises BadRequest, SafetyBlocked,
        ConsentError or ChainExhausted."""
        require_consent(req.references, self.consents())
        if req.private_media and not self._notified_private:
            self._notified_private = True
            self.bus.emit(
                "privacy_notice",
                stage=req.stage,
                unit=req.unit,
                message=PRIVATE_MEDIA_NOTICE,
            )
        ids = self.chain_ids(req.capability, private_media=req.private_media)
        primary = ids[0] if ids else None
        failed_from: str | None = None
        attempts: list[tuple[str, str]] = []
        for idx, pid in enumerate(ids):
            ok, reason, hint = self.usable(pid)
            if not ok:
                log.debug("skip %s for %s/%s: %s %s", pid, req.stage, req.unit, reason, hint or "")
                attempts.append((pid, reason))
                continue
            p = self.registry.get(pid)
            if p.tier == "paid" and not self._budget_allows(p, req, ids[idx + 1 :]):
                attempts.append((pid, "budget_cap"))
                failed_from = failed_from or pid
                continue
            try:
                result = self._call_with_retries(p, req, fallback_from=failed_from)
                return result, p, pid != primary
            except (BadRequest, SafetyBlocked):
                raise
            except ProviderError as e:
                attempts.append((pid, e.kind))
                failed_from = failed_from or pid
                self._on_provider_failed(p, req, e, ids[idx + 1 :])
        raise ChainExhausted(
            f"{req.stage} {req.unit}: no provider in the {req.capability} chain succeeded "
            f"({', '.join(f'{a}: {b}' for a, b in attempts) or 'empty chain'})",
            attempts=attempts,
        )

    def call_one(self, pid: str, req: Request) -> Result:
        """Exactly one provider, no fallback (smoke tests). Still logs every attempt."""
        p = self.registry.get(pid)
        p.require_available()
        return self._call_with_retries(p, req, fallback_from=None)

    # ------------------------------------------------------------ internals
    def _budget_allows(self, p: Provider, req: Request, rest: list[str]) -> bool:
        budget = self.sel.budget_usd or 0.0
        est = p.est_cost_usd(req)
        if self._spent + est <= budget:
            return True
        to, to_tier = self._next_usable(rest)
        self.bus.fallback(
            FallbackEvent(
                req.stage,
                req.unit,
                p.name,
                to,
                p.tier,
                to_tier,
                "budget_cap",
                f"spent ${self._spent:.2f} + est ${est:.2f} > budget ${budget:.2f}",
                from_label=p.label,
                to_label=self.registry.get(to).label if to else None,
            )
        )
        return False

    def _next_usable(self, rest: list[str]) -> tuple[str | None, str | None]:
        for pid in rest:
            if self.usable(pid)[0]:
                return pid, self.registry.get(pid).tier
        return None, None

    def _on_provider_failed(
        self, p: Provider, req: Request, e: ProviderError, rest: list[str]
    ) -> None:
        if isinstance(e, QuotaExhausted | RateLimited):
            reset = e.reset_at or next_reset(self.registry.reset_rule(p.name))
            self.circuits.open(p.name, reset_at=reset, error_class=e.kind, reason=e.message)
            self.bus.emit(
                "circuit_open", provider=p.name, reset_at=reset or "end of run", error_class=e.kind
            )
            e.reset_at = reset
        elif isinstance(e, Unavailable):
            self.circuits.open(p.name, reset_at=None, error_class=e.kind, reason=e.message)
            if e.moved:
                self.bus.emit(
                    "provider_moved",
                    provider=p.name,
                    stage=req.stage,
                    unit=req.unit,
                    message=f"{p.label}: {e.message}",
                    error_class=e.kind,
                )
        to, to_tier = self._next_usable(rest)
        self.bus.fallback(
            FallbackEvent(
                req.stage,
                req.unit,
                p.name,
                to,
                p.tier,
                to_tier,
                e.kind,
                e.message[:300],
                reset_at=e.reset_at,
                from_label=p.label,
                to_label=self.registry.get(to).label if to else None,
            )
        )

    def _call_with_retries(self, p: Provider, req: Request, *, fallback_from: str | None) -> Result:
        attempt = 0
        rate_retried = oom_retried = False
        current = req
        while True:
            attempt += 1
            seed = None if req.seed is None else req.seed + (attempt - 1) * RETRY_SEED_STEP
            current = current.with_seed(seed)
            t0 = time.monotonic()
            try:
                result = self._invoke(p, current)
            except ProviderError as e:
                latency = int((time.monotonic() - t0) * 1000)
                retry = False
                if isinstance(e, RateLimited) and not rate_retried:
                    wait = e.retry_after if e.retry_after is not None else BACKOFF_BASE_S
                    if wait <= RATE_LIMIT_WAIT_MAX_S:
                        rate_retried = retry = True
                        self._log(p, current, attempt, latency, e, fallback_from, terminal=False)
                        self.sleep(wait)
                elif isinstance(e, Transient) and attempt < MAX_ATTEMPTS:
                    retry = True
                    self._log(p, current, attempt, latency, e, fallback_from, terminal=False)
                    self.sleep(self.rng() * min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2 ** (attempt - 1)))
                elif isinstance(e, OutOfMemory) and not oom_retried and attempt < MAX_ATTEMPTS:
                    oom_retried = retry = True
                    self._log(p, current, attempt, latency, e, fallback_from, terminal=False)
                    current = current.degrade()
                if retry:
                    continue
                fatal = isinstance(e, BadRequest | SafetyBlocked)
                self._log(p, current, attempt, latency, e, fallback_from, terminal=not fatal)
                if isinstance(e, SafetyBlocked):
                    e.message += " (rephrase the prompt; no silent fallback)"
                raise
            latency = int((time.monotonic() - t0) * 1000)
            self._finish(p, current, attempt, latency, result, fallback_from)
            return result

    def _invoke(self, p: Provider, req: Request) -> Result:
        try:
            return p.call(req)
        except ProviderError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise Transient(f"{type(e).__name__}: {e}") from e

    def _finish(
        self,
        p: Provider,
        req: Request,
        attempt: int,
        latency: int,
        result: Result,
        fallback_from: str | None,
    ) -> None:
        out_path = out_sha = None
        if result.data is not None and req.output_path is not None:
            path = req.output_path
            if result.ext and path.suffix in ("", ".img", ".bin", ".out"):
                path = path.with_suffix(f".{result.ext}")  # the provider decides png vs jpg
            atomic_write_bytes(path, result.data)
            result.output_path = path
            out_path, out_sha = self.project.rel(path), sha256_bytes(result.data)
        list_price = p.est_cost_usd(req)
        actual = list_price if p.tier == "paid" else 0.0
        self._spent += actual
        self.runlog.record(
            **self._base_line(p, req, attempt, result.params_used or None),
            model=result.model or p.model,
            seed=result.seed_used if result.seed_used is not None else req.seed,
            output_path=out_path,
            output_sha256=out_sha,
            status="ok",
            fallback_from=fallback_from,
            latency_ms=latency,
            gpu_seconds=result.gpu_seconds,
            queue_ms=result.queue_ms,
            metrics=result.metrics,
            cost_list_price_usd=round(list_price, 6) if p.cost_basis else None,
            cost_actual_usd=round(actual, 6),
        )

    def _log(
        self,
        p: Provider,
        req: Request,
        attempt: int,
        latency: int,
        e: ProviderError,
        fallback_from: str | None,
        *,
        terminal: bool,
    ) -> None:
        self.runlog.record(
            **self._base_line(p, req, attempt, None),
            model=p.model,
            seed=req.seed,
            status="fallback_triggered" if terminal else "error",
            error_class=e.kind,
            error_message=e.message,
            fallback_from=fallback_from,
            latency_ms=latency,
        )

    def _base_line(self, p: Provider, req: Request, attempt: int, params: dict | None) -> dict:
        merged = {**p.params, **req.params, **(params or {})}
        return {
            "stage": req.stage,
            "unit": req.unit,
            "capability": req.capability,
            "provider": p.name,
            "executor": p.executor,
            "params": merged,
            "attempt": attempt,
            "cache_key": req.cache_key,
            "input_hash": canonical_hash(
                {"prompt": req.prompt, "params": merged, "inputs": _hashable(req.inputs)}
            )[:16],
            "tier": p.tier,
            "cost_basis": f"pricing.yaml#{p.cost_basis}" if p.cost_basis else None,
            **prompt_ref(req.prompt),
        }


def _hashable(value):
    """Paths enter the input hash by name only; private bytes never reach the log."""
    if isinstance(value, dict):
        return {str(k): _hashable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_hashable(v) for v in value]
    if isinstance(value, bytes):
        return sha256_bytes(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)

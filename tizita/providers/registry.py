"""Builds Provider objects from `config/providers.yaml` + `config/pricing.yaml` + the env."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

from tizita.providers.base import CAPABILITIES, TIERS, Provider, expand
from tizita.storyboard import Issue, load_config
from tizita.util import Project

ADAPTERS = {
    "gemini_text": "tizita.providers.gemini_text:GeminiText",
    "gemini_tts": "tizita.providers.gemini_tts:GeminiTTS",
    "cf_workers_ai": "tizita.providers.cf_workers_ai:CloudflareAI",
    "openai_compat": "tizita.providers.openai_compat:OpenAICompat",
    "mms_tts": "tizita.providers.mms_tts:MMSTTS",
    "local_clip": "tizita.providers.local_clip:LocalClip",
    "synth_pad": "tizita.providers.synth_pad:SynthPad",
    "previous_take": "tizita.providers.previous_take:PreviousTake",
}


def load_env(project: Project) -> dict[str, str]:
    """os.environ wins over .env. Values are never printed or logged."""
    env: dict[str, str] = {}
    dotenv = project.root / ".env"
    if dotenv.exists():
        from dotenv import dotenv_values

        env.update({k: v for k, v in dotenv_values(dotenv).items() if v is not None})
    env.update(os.environ)
    return env


def models_dir_from(env: dict[str, str]) -> Path:
    raw = (env.get("MODELS_DIR") or "~/models/tizita").split("#")[0].strip()
    return expand(raw)


def _adapter_class(name: str | None) -> type[Provider]:
    if not name:
        return Provider
    if name not in ADAPTERS:
        raise ValueError(f"unknown adapter {name!r}")
    module, cls = ADAPTERS[name].split(":")
    return getattr(importlib.import_module(module), cls)


class Registry:
    def __init__(
        self,
        catalogue: dict[str, dict],
        chains: dict[str, list[str]],
        providers: dict[str, Provider],
        pools: dict[str, dict] | None = None,
    ):
        self.catalogue = catalogue
        self.chains = chains
        self.providers = providers
        self.pools = pools or {}

    @classmethod
    def load(cls, project: Project, env: dict[str, str] | None = None) -> Registry:
        env = load_env(project) if env is None else env
        cfg = load_config(project, "providers")
        pricing = load_config(project, "pricing").get("prices", {})
        catalogue: dict[str, dict] = cfg.get("providers", {})
        mdir = models_dir_from(env)
        providers: dict[str, Provider] = {}
        for pid, pcfg in catalogue.items():
            p = _adapter_class(pcfg.get("adapter"))(pid, pcfg, env=env, models_dir=mdir)
            p.set_pricing(pricing.get(pcfg.get("cost_basis") or ""))
            providers[pid] = p
        return cls(catalogue, cfg.get("chains", {}), providers, cfg.get("quota_pools", {}))

    @classmethod
    def from_providers(cls, providers: list[Provider], chains: dict[str, list[str]]) -> Registry:
        """For tests: fake providers in memory."""
        catalogue = {
            p.name: {**p.cfg, "tier": p.tier, "capability": p.capability} for p in providers
        }
        return cls(catalogue, chains, {p.name: p for p in providers})

    def get(self, pid: str) -> Provider:
        return self.providers[pid]

    def reset_rule(self, pid: str) -> str | None:
        p = self.providers[pid]
        return p.cfg.get("reset") or self.pools.get(p.quota_pool, {}).get("reset")

    def lint(self, active: dict[str, list[str]] | None = None) -> list[Issue]:
        """Config problems. `active` = the chains under the current profile (for the pool rule)."""
        issues: list[Issue] = []
        for pid, c in self.catalogue.items():
            if c.get("capability") not in CAPABILITIES:
                issues.append(Issue("error", "provider_config", pid, "bad capability"))
            if c.get("tier") not in TIERS:
                issues.append(Issue("error", "provider_config", pid, "bad tier"))
        for cap, ids in self.chains.items():
            for pid in ids:
                if pid not in self.catalogue:
                    issues.append(
                        Issue("error", "provider_config", f"chains.{cap}", f"unknown {pid!r}")
                    )
                elif self.catalogue[pid]["capability"] != cap and not (
                    cap == "image_edit" and self.catalogue[pid]["capability"] == "image"
                ):
                    issues.append(
                        Issue(
                            "error",
                            "provider_config",
                            f"chains.{cap}",
                            f"{pid!r} has capability {self.catalogue[pid]['capability']!r}",
                        )
                    )
        for cap, ids in (active or {}).items():
            usable = [i for i in ids if i in self.providers]
            if len(usable) >= 2:
                a, b = (self.providers[i] for i in usable[:2])
                if a.quota_pool == b.quota_pool:
                    issues.append(
                        Issue(
                            "warning",
                            "same_pool_fallback",
                            f"chains.{cap}",
                            f"first two providers {a.name} and {b.name} share quota pool "
                            f"{a.quota_pool!r}; one exhausted quota takes out both.",
                        )
                    )
        return issues

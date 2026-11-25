"""Profiles, per-capability overrides and the paid guard (SPEC §7.2)."""

from __future__ import annotations

from dataclasses import dataclass, field

from tizita.storyboard import load_config
from tizita.util import Project


def _truthy(v: str | None) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def _float_or_none(v) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    return float(str(v).split("#", 1)[0].strip())


@dataclass
class Selection:
    profile: str
    tiers: list[str]
    local_allow: set[str] | None = None  # None = every local provider allowed
    custom: dict[str, list[str]] = field(default_factory=dict)
    overrides: dict[str, tuple[str, str | None]] = field(default_factory=dict)
    allow_paid: bool = False
    budget_usd: float | None = None

    @property
    def paid_ok(self) -> bool:
        """Paid providers need allow_paid AND a positive budget (and a profile that lists them)."""
        return self.allow_paid and self.budget_usd is not None and self.budget_usd > 0


def parse_overrides(items: list[str] | None) -> dict[str, tuple[str, str | None]]:
    """`image=fal:flux2-klein` → {"image": ("fal", "flux2-klein")}. The model part is optional."""
    out: dict[str, tuple[str, str | None]] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"--provider expects capability=provider[:model], got {item!r}")
        cap, value = item.split("=", 1)
        pid, _, model = value.partition(":")
        out[cap.strip()] = (pid.strip(), model.strip() or None)
    return out


def load_selection(
    project: Project,
    env: dict[str, str],
    profile: str | None = None,
    overrides: list[str] | None = None,
) -> Selection:
    cfg = load_config(project, "profiles")
    profiles = cfg.get("profiles", {})
    name = (
        profile
        or (env.get("TIZITA_PROFILE") or "").split("#")[0].strip()
        or cfg.get("default", "free")
    )
    if name not in profiles:
        raise ValueError(f"unknown profile {name!r}; choose one of {', '.join(profiles)}")
    p = profiles[name]
    allow_env = env.get("ALLOW_PAID")
    budget_env = env.get("PAID_BUDGET_USD")
    allow = _truthy(allow_env) if allow_env is not None else bool(cfg.get("allow_paid", False))
    budget = _float_or_none(budget_env) if budget_env is not None else cfg.get("budget_usd")
    return Selection(
        profile=name,
        tiers=list(p.get("tiers", ["free_hosted", "deterministic"])),
        local_allow=set(p["local_allow"]) if "local_allow" in p else None,
        custom={k: list(v) for k, v in (p.get("chains") or {}).items()},
        overrides=parse_overrides(overrides),
        allow_paid=allow,
        budget_usd=budget,
    )


def chain_for(
    capability: str,
    catalogue: dict[str, dict],
    chains: dict[str, list[str]],
    sel: Selection,
) -> list[str]:
    """Ordered provider ids for one capability under the active selection."""
    base = [pid for pid in chains.get(capability, []) if pid in catalogue]
    if capability in sel.custom:
        ids = [pid for pid in sel.custom[capability] if pid in catalogue]
    else:
        ids = [pid for tier in sel.tiers for pid in base if catalogue[pid]["tier"] == tier]
        if sel.local_allow is not None:
            ids = [p for p in ids if catalogue[p]["tier"] != "local" or p in sel.local_allow]
    if capability in sel.overrides:
        pid = sel.overrides[capability][0]
        if pid not in catalogue:
            raise ValueError(f"--provider {capability}={pid}: unknown provider id")
        ids = [pid, *[i for i in ids if i != pid]]
    if not sel.paid_ok:
        ids = [p for p in ids if catalogue[p]["tier"] != "paid"]
    return ids

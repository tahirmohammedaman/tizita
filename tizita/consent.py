"""Consent gate (SPEC §11.3).

Every `real_person: true` reference needs a `consent_id` that exists in `ethics/consents.yaml`
and whose scope includes `likeness`. The agent never writes consent entries; Tahir does.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ETHICS_HINT = "See ETHICS.md (consent) and add the record to ethics/consents.yaml."


class ConsentError(Exception):
    """A real person would be depicted without a matching consent record."""


def load_registry(path: Path) -> dict[str, dict]:
    if not Path(path).exists():
        return {}
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a YAML list of consent records")
    return {str(e["id"]): e for e in data if isinstance(e, dict) and "id" in e}


def consent_problem(ref: dict, registry: dict[str, dict], scope: str = "likeness") -> str | None:
    """Return a human message if `ref` may not be used, else None."""
    if not ref.get("real_person"):
        return None
    cid = ref.get("consent_id")
    if not cid:
        return f"reference {ref.get('id')!r} is a real person but has no consent_id. {ETHICS_HINT}"
    entry = registry.get(cid)
    if entry is None:
        return (
            f"reference {ref.get('id')!r} points to consent {cid!r}, "
            f"which is not in the registry. {ETHICS_HINT}"
        )
    if scope not in (entry.get("scope") or []):
        return (
            f"consent {cid!r} for reference {ref.get('id')!r} does not include "
            f"the {scope!r} scope. {ETHICS_HINT}"
        )
    return None


def require_consent(refs: list[dict], registry: dict[str, dict], scope: str = "likeness") -> None:
    problems = [p for r in refs if (p := consent_problem(r, registry, scope))]
    if problems:
        raise ConsentError("; ".join(problems))

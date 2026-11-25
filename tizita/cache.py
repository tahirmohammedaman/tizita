"""Content-addressed cache keys and the artifact manifest (SPEC §6.2).

key = sha256(canonical_json({stage, stage_version, fields, upstream, provider, seed}))[:16]

The manifest (`outputs/manifest.json`) maps "<stage>/<unit>" to the current key, the artifact
path + sha256, the provider actually used, whether it was a fallback, and the per-field hashes
that let `tizita plan` explain *which* field changed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tizita.util import atomic_write_json, canonical_hash, iso_ms

KEY_LEN = 16


def cache_key(
    stage: str,
    stage_version: int,
    fields: dict[str, Any],
    upstream: dict[str, str],
    provider: dict[str, Any] | None,
    seed: int | None,
) -> str:
    return canonical_hash(
        {
            "stage": stage,
            "stage_version": stage_version,
            "fields": fields,
            "upstream": upstream,
            "provider": provider,
            "seed": seed,
        }
    )[:KEY_LEN]


def field_hashes(fields: dict[str, Any]) -> dict[str, str]:
    """One short hash per declared field path, so a diff can name the field that changed."""
    return {k: canonical_hash(v)[:KEY_LEN] for k, v in fields.items()}


def provider_ident(name: str | None, model: str | None, params: dict | None = None) -> dict | None:
    if name is None:
        return None
    return {"name": name, "model": model, "params": params or {}}


@dataclass
class Artifact:
    path: str
    sha256: str


@dataclass
class ManifestEntry:
    stage: str
    unit: str
    key: str
    stage_version: int
    path: str
    sha256: str
    provider: dict | None
    is_fallback: bool
    primary_provider: str | None
    created_at: str
    run_id: str | None
    seed: int | None
    field_hashes: dict[str, str]
    upstream: dict[str, str]
    candidates: list[dict] = field(default_factory=list)  # [{path, sha256}] for multi-candidate

    def artifact_sha(self, chosen: int | None = None) -> str:
        if chosen is not None and self.candidates:
            return self.candidates[chosen]["sha256"]
        return self.sha256


class Manifest:
    def __init__(self, path: Path, entries: dict[str, ManifestEntry] | None = None):
        self.path = Path(path)
        self.entries: dict[str, ManifestEntry] = entries or {}

    @staticmethod
    def id(stage: str, unit: str) -> str:
        return f"{stage}/{unit}"

    @classmethod
    def load(cls, path: Path) -> Manifest:
        path = Path(path)
        if not path.exists():
            return cls(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = {k: ManifestEntry(**v) for k, v in raw.get("entries", {}).items()}
        return cls(path, entries)

    def save(self) -> None:
        atomic_write_json(
            self.path,
            {"version": 1, "entries": {k: asdict(v) for k, v in sorted(self.entries.items())}},
        )

    def get(self, stage: str, unit: str) -> ManifestEntry | None:
        return self.entries.get(self.id(stage, unit))

    def record(
        self,
        *,
        stage: str,
        unit: str,
        key: str,
        stage_version: int,
        artifact: Artifact,
        provider: dict | None,
        is_fallback: bool = False,
        primary_provider: str | None = None,
        run_id: str | None = None,
        seed: int | None = None,
        fields: dict[str, Any] | None = None,
        upstream: dict[str, str] | None = None,
        candidates: list[Artifact] | None = None,
    ) -> ManifestEntry:
        entry = ManifestEntry(
            stage=stage,
            unit=unit,
            key=key,
            stage_version=stage_version,
            path=artifact.path,
            sha256=artifact.sha256,
            provider=provider,
            is_fallback=is_fallback,
            primary_provider=primary_provider,
            created_at=iso_ms(),
            run_id=run_id,
            seed=seed,
            field_hashes=field_hashes(fields or {}),
            upstream=dict(upstream or {}),
            candidates=[asdict(c) for c in candidates or []],
        )
        self.entries[self.id(stage, unit)] = entry
        return entry

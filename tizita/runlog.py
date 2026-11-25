"""runs.jsonl writer (SPEC §8.1): one line per model call, including failed attempts."""

from __future__ import annotations

import json
import secrets
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from tizita.util import PACKAGE_ROOT, append_jsonl, iso_ms, sha256_text, utc_now

PROMPT_HEAD = 200


def new_run_id() -> str:
    return utc_now().strftime("r_%Y%m%d_%H%M%S_") + secrets.token_hex(2)


def prompt_ref(text: str | None) -> dict:
    """Prompts are logged by hash plus their first 200 characters."""
    if text is None:
        return {"prompt_sha256": None, "prompt_head": None}
    return {"prompt_sha256": sha256_text(text), "prompt_head": text[:PROMPT_HEAD]}


@cache
def runlog_validator() -> Draft202012Validator:
    schema = json.loads((PACKAGE_ROOT / "schema" / "runlog.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


_DEFAULTS: dict[str, Any] = {
    "executor": "api",
    "params": {},
    "seed": None,
    "attempt": 1,
    "cache_key": None,
    "input_hash": None,
    "output_path": None,
    "output_sha256": None,
    "status": "ok",
    "error_class": None,
    "error_message": None,
    "fallback_from": None,
    "latency_ms": None,
    "gpu_seconds": None,
    "queue_ms": None,
    "metrics": {},
    "cost_list_price_usd": None,
    "cost_actual_usd": 0.0,
    "cost_basis": None,
}


class RunLog:
    def __init__(self, path: Path, run_id: str | None = None, profile: str = "free"):
        self.path = Path(path)
        self.run_id = run_id or new_run_id()
        self.profile = profile
        self._n = 0
        self.last: dict | None = None

    def next_call_id(self) -> str:
        self._n += 1
        return f"c_{self._n:04d}"

    def record(self, **fields: Any) -> dict:
        line = {
            "ts": iso_ms(),
            "run_id": self.run_id,
            "call_id": self.next_call_id(),
            "profile": self.profile,
            **_DEFAULTS,
            **fields,
        }
        if line.get("error_message"):
            line["error_message"] = str(line["error_message"])[:500]
        errors = sorted(runlog_validator().iter_errors(line), key=lambda e: list(e.path))
        if errors:
            raise ValueError(f"runs.jsonl line fails schema: {errors[0].message}")
        append_jsonl(self.path, line)
        self.last = line
        return line


def iter_runs(path: Path):
    path = Path(path)
    if not path.exists():
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                yield json.loads(raw)


def spent_usd(path: Path) -> float:
    """Actual paid spend so far (paid guard, SPEC §7.2)."""
    return round(sum(float(r.get("cost_actual_usd") or 0.0) for r in iter_runs(path)), 6)

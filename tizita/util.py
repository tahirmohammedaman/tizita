"""Small shared helpers: project paths, canonical JSON hashing, atomic writes, time stamps."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8 kept (Ethiopic stays readable)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_hash(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write to a temp file in the same directory, fsync, then rename over the target."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, record: dict) -> None:
    """Append one line. A single O_APPEND write of one line is atomic enough for our logs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def iso_ms(t: dt.datetime | None = None) -> str:
    """2026-11-25T15:02:11.204Z"""
    t = (t or utc_now()).astimezone(dt.UTC)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class Project:
    """Where a project's files live. Tests point this at a tmp dir."""

    root: Path

    @classmethod
    def default(cls) -> Project:
        return cls(Path(os.environ.get("TIZITA_ROOT") or PACKAGE_ROOT).resolve())

    @property
    def storyboard(self) -> Path:
        return self.root / "storyboard.json"

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def schema_dir(self) -> Path:
        # Schemas ship with the package checkout, not with each project.
        return PACKAGE_ROOT / "schema"

    @property
    def outputs(self) -> Path:
        return self.root / "outputs"

    @property
    def manifest(self) -> Path:
        return self.outputs / "manifest.json"

    @property
    def runs(self) -> Path:
        return self.root / "runs.jsonl"

    @property
    def events(self) -> Path:
        return self.root / "logs" / "events.jsonl"

    @property
    def failures(self) -> Path:
        return self.root / "logs" / "failures_auto.jsonl"

    @property
    def state(self) -> Path:
        return self.root / ".state"

    @property
    def consents(self) -> Path:
        return self.root / "ethics" / "consents.yaml"

    def rel(self, path: Path) -> str:
        try:
            return str(Path(path).resolve().relative_to(self.root))
        except ValueError:
            return str(path)

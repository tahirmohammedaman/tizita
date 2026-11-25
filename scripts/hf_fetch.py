"""Helper for scripts/download_models.sh (SPEC §19).

Subcommands:
  record <manifest> <name> <status> [key=value ...]   stdlib only (works before `uv sync`)
  info   <repo_id> [--allow PATTERN ...]              print total size (needs huggingface_hub)
  fetch  <manifest> <name> <repo_id> <dest> [--allow PATTERN ...]

Weights are downloaded, never loaded, here. Run with `python -I`.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def record(manifest: Path, name: str, status: str, **fields: object) -> None:
    """Upsert one entry in MANIFEST.json atomically."""
    manifest.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, dict] = {}
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text())
        except json.JSONDecodeError:
            data = {}
    entry = data.get(name, {})
    entry.update({"name": name, "status": status, "updated_at": _now(), **fields})
    data[name] = entry
    fd, tmp = tempfile.mkstemp(dir=manifest.parent, prefix=".manifest.")
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, manifest)


def _failure_draft(name: str, repo_id: str, err: str) -> None:
    """Append a draft FAILURES entry (CLAUDE.md honesty rules)."""
    path = Path(__file__).resolve().parent.parent / "logs" / "failures_auto.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "ts": _now(),
        "source": "download_models",
        "unit": name,
        "repo_id": repo_id,
        "error": err[:500],
        "draft": f"Download of {repo_id} failed; check whether the repo moved or is gated.",
    }
    with path.open("a") as fh:
        fh.write(json.dumps(line) + "\n")


def _info(repo_id: str, allow: list[str] | None):
    from fnmatch import fnmatch

    from huggingface_hub import HfApi

    info = HfApi().model_info(repo_id, files_metadata=True)
    files = [
        s for s in (info.siblings or []) if not allow or any(fnmatch(s.rfilename, p) for p in allow)
    ]
    size = sum(s.size or 0 for s in files)
    return info, size, len(files)


def _parse_allow(args: list[str]) -> tuple[list[str], list[str]]:
    rest, allow = [], []
    it = iter(args)
    for a in it:
        if a == "--allow":
            allow.append(next(it))
        else:
            rest.append(a)
    return rest, allow


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, *args = argv
    if cmd == "record":
        manifest, name, status, *kv = args
        record(Path(manifest), name, status, **dict(x.split("=", 1) for x in kv))
        return 0
    args, allow = _parse_allow(args)
    if cmd == "info":
        (repo_id,) = args
        info, size, n = _info(repo_id, allow or None)
        gated = getattr(info, "gated", False)
        print(f"{repo_id}  rev={info.sha[:12]}  files={n}  size={size / 1e9:.2f} GB  gated={gated}")
        return 0
    if cmd == "fetch":
        manifest, name, repo_id, dest = args
        mpath = Path(manifest)
        try:
            from huggingface_hub import snapshot_download

            info, size, n = _info(repo_id, allow or None)
            record(mpath, name, "downloading", repo_id=repo_id, revision=info.sha, size_bytes=size)
            print(f"[{name}] {repo_id}@{info.sha[:12]}: {n} files, {size / 1e6:.0f} MB -> {dest}")
            snapshot_download(
                repo_id, revision=info.sha, local_dir=dest, allow_patterns=allow or None
            )
            record(
                mpath, name, "ok", repo_id=repo_id, revision=info.sha, size_bytes=size, path=dest
            )
            print(f"[{name}] ok")
            return 0
        except Exception as exc:  # classified upstream; here we just record it
            err = f"{type(exc).__name__}: {exc}"
            record(mpath, name, "failed", repo_id=repo_id, error=err[:300])
            _failure_draft(name, repo_id, err)
            print(f"[{name}] FAILED {err}", file=sys.stderr)
            return 1
    print(f"unknown command {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env bash
# Clone HEAD to a temp dir and `make film` with no .env, no API keys and no local weights.
# Pass = 0 new runs.jsonl lines (no model call), both films rendered, QA passed.
# The films are gitignored, so assemble and qa re-render here (deterministic FFmpeg).
set -euo pipefail

repo="$(git rev-parse --show-toplevel)"
work="$(mktemp -d "${TMPDIR:-/tmp}/tizita-clean-XXXXXX")"
trap '[ -n "${KEEP:-}" ] || rm -rf "$work"' EXIT
mkdir -p "$work/empty-models" "$repo/logs"
log="$repo/logs/tmp_clean_clone.log"

git clone --quiet "$repo" "$work/repo"
cd "$work/repo"
[ ! -e .env ] || { echo "FAIL: .env exists in the clone"; exit 1; }
before="$(wc -l < runs.jsonl)"

# A whitelisted environment: no key from this shell can leak into the clone.
run() {
  env -i HOME="$HOME" PATH="$PATH" LANG="${LANG:-C.UTF-8}" TERM=dumb COLUMNS=160 \
    MODELS_DIR="$work/empty-models" "$@"
}

echo "clone: $(git rev-parse --short HEAD) in $work/repo (full log: $log)"
if ! run make film > "$log" 2>&1; then
  tail -n 30 "$log"
  echo "FAIL: make film exited non-zero"
  exit 1
fi
grep -E "^Run r_|QA" "$log" || true

# qa stays cached when the re-rendered film is byte-identical to the committed run's, so force it
# to measure the files this clone actually rendered.
if ! run uv run tizita run --stage qa --force >> "$log" 2>&1; then
  tail -n 30 "$log"
  echo "FAIL: QA failed on the freshly rendered films"
  exit 1
fi
grep -E "^Run r_" "$log" | tail -n 1

after="$(wc -l < runs.jsonl)"
calls=$((after - before))
echo "model calls (new runs.jsonl lines): $calls"
[ "$calls" -eq 0 ] || { tail -n "$calls" runs.jsonl | cut -c1-300; echo "FAIL: expected 0"; exit 1; }

run uv run --quiet python - <<'PY'
import json, pathlib, sys

manifest = json.loads(pathlib.Path("outputs/manifest.json").read_text())
text = json.dumps(manifest)
qa_files = sorted(pathlib.Path("outputs/final").glob("*/qa.json"))
if len(qa_files) != 1:
    sys.exit(f"FAIL: expected one qa.json, found {len(qa_files)}")
qa = json.loads(qa_files[0].read_text())
films = sorted(qa_files[0].parent.glob("film_*.mp4"))
print("films:", ", ".join(f"{f.name} {f.stat().st_size / 1e6:.0f} MB" for f in films))
print("qa pass:", qa.get("pass"), "|", " ".join(
    f"{k}: {qa[k]['duration_s']} s, {qa[k]['lufs']} LUFS, {qa[k]['true_peak_db']} dBTP"
    for k in ("9x16", "16x9")
))
sys.exit(0 if qa.get("pass") is True and len(films) == 2 else "FAIL: QA or films missing")
PY
echo "PASS"

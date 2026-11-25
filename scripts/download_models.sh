#!/usr/bin/env bash
# Tizita Studio downloader (SPEC §19). Idempotent; safe to re-run.
#
#   scripts/download_models.sh                 default set (python env, fonts, small CPU models,
#                                              frontend deps, docker images); logs to logs/downloads.log
#   scripts/download_models.sh --only <name>   one item; optional items print size and ask first
#   scripts/download_models.sh --only wan --yes
#
# Default names : env fonts mms-tts-amh clip-vit-b32 dinov2-small frontend docker
# Optional names: ace flux wan ltx musicgen whisper gpu   (never downloaded by default)
#
# Weights go to $MODELS_DIR (default ~/models/tizita), never into the repo.
# Status per item is written to $MODELS_DIR/MANIFEST.json.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
mkdir -p logs
LOG="logs/downloads.log"

ONLY=""
YES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --only) ONLY="${2:-}"; shift 2 ;;
    --yes|-y) YES=1; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$ONLY" ]]; then
  exec >>"$LOG" 2>&1          # background mode: everything to the log
else
  exec > >(tee -a "$LOG") 2>&1  # interactive mode: show and log
fi

# MODELS_DIR: env > .env > default
if [[ -z "${MODELS_DIR:-}" && -f .env ]]; then
  MODELS_DIR="$(grep -E '^MODELS_DIR=' .env | tail -n1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//' | tr -d '"' || true)"
fi
MODELS_DIR="${MODELS_DIR:-$HOME/models/tizita}"
MODELS_DIR="${MODELS_DIR/#\~/$HOME}"
MANIFEST="$MODELS_DIR/MANIFEST.json"
mkdir -p "$MODELS_DIR"

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
record() { python3 -I scripts/hf_fetch.py record "$MANIFEST" "$@"; }
pyenv() { uv run --no-sync python -I scripts/hf_fetch.py "$@"; }

confirm() {  # confirm "<question>"
  [[ $YES -eq 1 ]] && return 0
  local ans
  read -r -p "$1 [y/N] " ans </dev/tty || return 1
  [[ "$ans" =~ ^[Yy]$ ]]
}

check_disk() {
  log "disk: $(df -h ~ | tail -n1)"
  local avail_kb
  avail_kb=$(df -Pk ~ | tail -n1 | awk '{print $4}')
  if (( avail_kb < 10 * 1024 * 1024 )); then
    log "ERROR: under 10 GB free in ~; aborting"; exit 1
  fi
}

# ---------- default set ----------
do_env() {
  log "uv sync --extra ml (CPU torch)"
  record env downloading kind=python
  if uv sync --extra ml; then
    record env ok kind=python torch="$(uv run --no-sync python -c 'import torch;print(torch.__version__)' 2>/dev/null)"
  else
    record env failed kind=python; return 1
  fi
}

FONT_BASE="https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts"
do_fonts() {
  log "fonts -> assets/fonts (Noto, OFL)"
  mkdir -p assets/fonts
  local ok=1 f
  for f in NotoSans/hinted/ttf/NotoSans-Regular.ttf NotoSans/hinted/ttf/NotoSans-Bold.ttf \
           NotoSansEthiopic/hinted/ttf/NotoSansEthiopic-Regular.ttf \
           NotoSansEthiopic/hinted/ttf/NotoSansEthiopic-Bold.ttf; do
    local out="assets/fonts/${f##*/}"
    [[ -s "$out" ]] && continue
    curl -fsSL --retry 3 -o "$out.tmp" "$FONT_BASE/$f" && mv "$out.tmp" "$out" || { ok=0; rm -f "$out.tmp"; }
  done
  [[ -s assets/fonts/OFL-NotoSans.txt ]] || curl -fsSL -o assets/fonts/OFL-NotoSans.txt \
    https://raw.githubusercontent.com/notofonts/latin-greek-cyrillic/main/OFL.txt || ok=0
  [[ -s assets/fonts/OFL-NotoSansEthiopic.txt ]] || curl -fsSL -o assets/fonts/OFL-NotoSansEthiopic.txt \
    https://raw.githubusercontent.com/notofonts/ethiopic/main/OFL.txt || ok=0
  if (( ok )); then record fonts ok path=assets/fonts licence=OFL-1.1; else record fonts failed; return 1; fi
}

hf() {  # hf <name> <repo_id> [--allow pattern ...]
  local name="$1" repo="$2"; shift 2
  if [[ "$(python3 -I -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get(sys.argv[2],{}).get('status',''))" "$MANIFEST" "$name" 2>/dev/null)" == "ok" ]]; then
    log "$name already ok"; return 0
  fi
  pyenv fetch "$MANIFEST" "$name" "$repo" "$MODELS_DIR/$name" "$@"
}

do_frontend() {
  log "npm install (frontend)"
  if (cd frontend && npm install --no-audit --no-fund); then record frontend ok kind=npm
  else record frontend failed kind=npm; return 1; fi
}

do_docker() {
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    log "docker daemon unavailable; skipping (enable Docker Desktop WSL integration, then --only docker)"
    record docker skipped reason=daemon_unavailable; return 0
  fi
  local ok=1 img
  for img in python:3.11-slim cloudflare/cloudflared:latest; do
    docker pull -q "$img" || ok=0
  done
  if (( ok )); then record docker ok images="python:3.11-slim,cloudflare/cloudflared:latest"
  else record docker failed; return 1; fi
}

# ---------- optional set (on demand only) ----------
optional() {  # optional <name> <repo_id> [--allow ...]
  local name="$1" repo="$2"; shift 2
  log "optional item '$name': looking up $repo"
  pyenv info "$repo" "$@" || { log "lookup failed for $repo (moved or gated?)"; return 1; }
  [[ "$name" == flux ]] && log "FLUX.2 klein may need the licence accepted on huggingface.co and HF_TOKEN set."
  confirm "Download $name into $MODELS_DIR/$name?" || { log "skipped $name"; return 0; }
  pyenv fetch "$MANIFEST" "$name" "$repo" "$MODELS_DIR/$name" "$@"
}

run_one() {
  case "$1" in
    env) do_env ;;
    fonts) do_fonts ;;
    mms-tts-amh) hf mms-tts-amh facebook/mms-tts-amh --allow '*.json' --allow '*.safetensors' --allow '*.md' ;;
    clip-vit-b32) hf clip-vit-b32 timm/vit_base_patch32_clip_224.openai --allow 'open_clip_model.safetensors' --allow 'open_clip_config.json' --allow '*.md' ;;
    dinov2-small) hf dinov2-small facebook/dinov2-small --allow '*.json' --allow 'model.safetensors' --allow '*.md' ;;
    frontend) do_frontend ;;
    docker) do_docker ;;
    ace) optional ace ACE-Step/Ace-Step1.5 ;;
    flux) optional flux black-forest-labs/FLUX.2-klein-4B ;;
    wan) optional wan Wan-AI/Wan2.2-TI2V-5B-Diffusers ;;
    ltx) optional ltx Lightricks/LTX-Video --allow 'ltxv-2b-0.9.8-distilled.safetensors' --allow '*.json' --allow '*.md' ;;
    musicgen) optional musicgen facebook/musicgen-small ;;
    whisper) optional whisper Systran/faster-whisper-small ;;
    gpu)
      log "gpu extra: CUDA torch + diffusers wheels (several GB); replaces the CPU torch in .venv"
      confirm "Run 'uv sync --extra gpu'?" || { log "skipped gpu"; return 0; }
      if uv sync --extra gpu; then record gpu ok kind=python; else record gpu failed kind=python; return 1; fi ;;
    *) log "unknown item: $1"; return 2 ;;
  esac
}

log "==== download_models start (only=${ONLY:-default}) MODELS_DIR=$MODELS_DIR ===="
check_disk
if [[ -n "$ONLY" ]]; then
  run_one "$ONLY"; rc=$?
else
  rc=0
  do_env || rc=1
  do_fonts || rc=1
  if [[ -x .venv/bin/python ]]; then
    for n in mms-tts-amh clip-vit-b32 dinov2-small; do run_one "$n" || rc=1; done
  else
    log "no .venv; skipping HF models"; rc=1
  fi
  do_frontend || rc=1
  do_docker || rc=1
fi
log "disk after: $(df -h ~ | tail -n1)"
log "==== download_models done rc=$rc ===="
exit $rc

# Tizita Studio

> *Tizita* (ትዝታ): Amharic for memory and longing, and one of the classic Ethiopian musical modes.

A storyboard-driven AI short-film pipeline. One file, `storyboard.json`, is the contract between every stage. `make film` validates it, regenerates only what's missing or changed, and exports a 60–90 s Amharic-narrated film with English subtitles, a ducked original score and an AI end card, in 9:16 and 16:9.

> **Status:** M0 scaffold. The commands below are wired up, but most of them land in later milestones (see `docs/PROGRESS.md`).

## One command

```bash
cp .env.example .env    # add your keys (see below)
make models             # one-time: python env (CPU), fonts, small CPU models (~2–4 GB)
make film               # validate → run all stages → QA → outputs/final/<key>/film_{9x16,16x9}.mp4
```

<!-- TODO(agent, M5/M9): document clean-clone behaviour (committed cache → 0 model calls), how to regenerate one shot, and what a run costs (from COSTS.md). -->

## Prerequisites

Linux or WSL2. You need Python 3.11 (via `uv`), Node 20+, FFmpeg **with libx264 and libass**, and optionally Docker (showcase only).

### Fedora (dnf)

```bash
# FFmpeg: the stock ffmpeg-free has no libx264. Enable RPM Fusion and swap it:
sudo dnf install -y https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
                    https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
sudo dnf swap -y ffmpeg-free ffmpeg --allowerasing
sudo dnf install -y nodejs git jq
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Debian / Ubuntu (apt)

```bash
sudo apt update && sudo apt install -y ffmpeg nodejs npm git jq   # Ubuntu's ffmpeg includes libx264 + libass
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Check FFmpeg

```bash
ffmpeg -hide_banner -encoders | grep libx264
ffmpeg -hide_banner -filters | grep -E "subtitles|loudnorm|sidechaincompress|zoompan|xfade"
```

## Keys (`.env`)

| Variable | Needed for | Free? |
|---|---|---|
| `GEMINI_API_KEY_1`..`_3` (rotated on quota; one is enough) | director, narration (TTS), ASR | free tier (may train on inputs) |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | keyframes (FLUX on Workers AI) | daily free allowance |
| `KAGGLE_USERNAME`, `KAGGLE_KEY` | moving shots (Wan 2.2) + music (ACE-Step) | ~30 GPU h/week |
| `HF_TOKEN`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` | optional free fallbacks | free |
| `FAL_KEY`, `REPLICATE_API_TOKEN` | optional paid providers (need `ALLOW_PAID=true` and a budget) | paid |

Secrets live only in `.env` (gitignored). gitleaks runs in pre-commit and CI.

## Provider profiles

`TIZITA_PROFILE=free` (default), `free+local`, `local-first`, `paid` or `custom`. Large local GPU weights are optional: `tizita models download --only wan|flux|ace|ltx|musicgen|whisper|gpu`.

## Development

```bash
uv sync --extra ml
uv run pre-commit install
make test lint
```

## Docs

[ARCHITECTURE](ARCHITECTURE.md) · [DESIGN](DESIGN.md) · [EXPERIMENTS](EXPERIMENTS.md) · [FAILURES](FAILURES.md) · [COSTS](COSTS.md) · [ETHICS](ETHICS.md) · [SPEC](SPEC.md)

Showcase: `tizita.tahiraman.me` <!-- TODO(agent, M8): link once live -->

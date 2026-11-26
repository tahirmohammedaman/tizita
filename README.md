# Tizita Studio

> *Tizita* (ትዝታ): Amharic for memory and longing, and one of the classic Ethiopian musical modes.

A storyboard-driven AI short-film pipeline. One file, `storyboard.json`, is the contract between every stage. `make film` validates it, regenerates only what's missing or changed, and exports a 60–90 s Amharic-narrated film with English subtitles, a ducked original score and an AI end card, in 9:16 and 16:9.

**The film:** *The Seat in the Front*, 11 shots, 77.2 s, in 9:16 and 16:9: a youngest sibling who
watched from the back seat becomes the one who drives everyone home.

**State (26 Nov 2026):** the pipeline runs end to end. Two parts are not built: the Wan image-to-video
GPU path (the four `i2v` shots are Ken Burns moves, recorded as fallbacks) and the web showcase
(API, worker, frontend, deploy). See [what works and what doesn't](docs/AUDIT.md).

## One command

```bash
git clone https://github.com/tahirmohammedaman/tizita.git && cd tizita
make film     # validate → run what is missing or changed → QA
```

It needs `uv`, `make` and FFmpeg (below). **No `.env`, no API keys, no GPU, no model downloads** for a
clean clone: every model output is committed, so the run makes **0 model calls**. Only the final
assembly and QA run again, because the MP4s are not stored in git.

Output, in `outputs/final/<key>/`:

| File | What it is |
|---|---|
| `film_9x16.mp4` | 1080×1920 master (about 63 MB), English subtitles burned in |
| `film_16x9.mp4` | 1920×1080 version (about 26 MB) |
| `film.srt` | the English subtitles |
| `assemble.json` | music used, loudness stats, models credited, every degradation |
| `qa.json` | duration, resolution, frame rate, codecs, loudness, true peak; `make film` fails if a check fails |

`make clean-clone-test` proves the claim: it clones `HEAD` to a temp directory, strips the
environment, runs `make film` with an empty model directory, and fails on any new `runs.jsonl` line
or a QA failure.

## Changing the film

`storyboard.json` is the only thing you edit. Generating anything new needs keys (below).

```bash
uv run tizita validate        # schema + lint (and consent for real people)
uv run tizita plan            # dry run: what is dirty, why, with which provider, how long
make film                     # regenerates only that
```

- **One narration line:** edit `shots[N].narration.text_am` / `text_en`. The plan shows 1 TTS call,
  then deterministic timing, subtitles, radio cut, assembly and QA.
- **One picture:** edit `shots[N].keyframe.prompt` (or `seed`). Only that keyframe, its clip,
  assembly and QA rebuild.
- **Force one unit** without an edit: `uv run tizita run --stage keyframes --unit s04 --force`.
- **Replace Ken Burns fallbacks** once an i2v provider exists: `uv run tizita run --upgrade-fallbacks`.

### Choosing a reference or the music

Models propose, a person picks. The pick is written into `storyboard.json`, so it is versioned and
invalidates exactly what depends on it.

```bash
uv run tizita run --stage references       # 4 candidates per reference + a contact sheet
#   look at outputs/references/<ref>/*_sheet.jpg, then (N starts at 1):
uv run tizita choose reference <ref> <N>

uv run tizita run --stage music            # the score candidates
#   listen to outputs/music/*_cand{1,2,3}.flac, then:
uv run tizita choose music <N> --reason "why this one"
uv run tizita run --stage assemble --stage qa
```

### Starting a new story

`uv run tizita new --answers interview/answers.yaml` drafts `storyboard.draft.json`; review it, then
`uv run tizita new --write` promotes it (the old storyboard is backed up).

## What a run costs

| Run | Model calls | Money |
|---|---|---|
| Clean clone, `make film` | 0 | $0 |
| Edit one narration line | 1 (TTS) | $0 on the free tier |
| Everything logged while building (251 lines, retries and experiments included) | 251 attempts, 211 ok | $0 actual |

List prices are only partly published, so the paid-tier equivalent is incomplete. See
[COSTS](COSTS.md) (`make costs` regenerates it from `runs.jsonl`).

## Prerequisites

Linux or WSL2 (tested on Fedora under WSL2 only). You need `uv` (it provides Python 3.11), `make`, `git` and
FFmpeg **with libx264 and libass** (FFmpeg 7.1 was used). Node 20+ is needed only for the unfinished
frontend scaffold.

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

## Keys (`.env`), only for generating new material

```bash
cp .env.example .env
uv run tizita providers     # what is configured and what is missing
uv run tizita smoke         # one call per configured provider, logged to runs.jsonl
```

| Variable | Used for | Free? |
|---|---|---|
| `GEMINI_API_KEY_1`..`_6` (one is enough; rotated on quota) | director, Amharic narration (TTS) | free tier (**Google may train on inputs**, see ETHICS) |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | references and keyframes (FLUX.2 klein), text fallback, Whisper | daily free allowance |
| `HF_TOKEN` | music (ACE-Step on a Hugging Face Space) | free |
| `GROQ_API_KEY`, `OPENROUTER_API_KEY` | optional text fallbacks | free |

`.env.example` also lists names reserved for paid providers, Kaggle and the showcase; those paths are
not built. Secrets live only in `.env` (gitignored); gitleaks runs in pre-commit and CI.

Local CPU models (MMS-TTS fallback, CLIP/DINOv2 consistency check) are optional for a clean clone:
`uv sync --extra ml && make models` (about 2–4 GB).

## Provider profiles

`TIZITA_PROFILE=free` (default), `free+local`, `local-first`, `paid` or `custom`;
`--provider tts=<id>` puts one provider first. Paid providers need `ALLOW_PAID=true` **and** a budget. No paid provider was ever called: only the paid Gemini text entry has an adapter, and it is untested.

## Development

```bash
uv sync --extra ml
uv run pre-commit install
make test lint
```

## Docs

[ARCHITECTURE](ARCHITECTURE.md) · [DESIGN](DESIGN.md) · [EXPERIMENTS](EXPERIMENTS.md) ·
[Four-language TTS benchmark](experiments/tts_benchmark/REPORT.md) ·
[FAILURES](FAILURES.md) · [COSTS](COSTS.md) · [ETHICS](ETHICS.md) · [Requirements audit](docs/AUDIT.md) ·
[SPEC](SPEC.md) (the plan; where it differs from the code, ARCHITECTURE describes the code)

The brief's `pipeline/` folder is the `tizita/stages/` package here; the mapping and the reason are in
[ARCHITECTURE → Repository layout vs. the brief](ARCHITECTURE.md#repository-layout-vs-the-brief).

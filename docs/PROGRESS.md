# Progress log (agent-maintained)

## Status: M0 done (Wed 25 Nov 2026, ~17:00 EAT)

### Done in M0
- Environment checked: 949 GB free; RTX 4060 Laptop 8 GB (driver 617.42, WSL); FFmpeg 7.1.5 from RPM Fusion with libx264 + subtitles/loudnorm/sidechaincompress/zoompan/xfade (no fix needed); uv 0.13.7; Node 22; Docker 28.3.3 (WSL integration enabled by Tahir during M0).
- `scripts/download_models.sh` + `scripts/hf_fetch.py`: idempotent, logs to `logs/downloads.log`, writes `$MODELS_DIR/MANIFEST.json`. The default set is all `ok`: env (`uv sync --extra ml`, torch `2.15.0+cpu`), fonts, `mms-tts-amh` (291 MB), `clip-vit-b32` (605 MB), `dinov2-small` (88 MB), frontend npm, docker images. About 1 GB of weights in `~/models/tizita`.
- `tizita models download [--only X] [--yes]` and `tizita models status` are implemented. Optional items (`ace flux wan ltx musicgen whisper gpu`) look up their size live from the HF API and ask before downloading. **None were downloaded.**
- uv project: base, `ml` (CPU torch from the pytorch-cpu index) and `gpu` (cu128 torch + diffusers), declared as conflicting extras. The lock resolves both forks.
- Typer CLI with every SPEC §13 command. The ones not built yet exit 2 with "lands in M<n>".
- Also done: repo layout (§4), Makefile, `.env.example`, `.gitignore`, pre-commit (ruff, hygiene, gitleaks), the frontend shell (Vite + React 19 + TS + Tailwind 4 + TanStack Query + React Router 7, typecheck + build green), and doc skeletons with TODO(Tahir) markers.
- Git: bootstrap commit on `main`; scaffold on `chore/m0-scaffold` → PR → merged.

### Model ids / tools discovered (verify again when used)
| Item | Found | Note |
|---|---|---|
| MMS-TTS Amharic | `facebook/mms-tts-amh` @ e366aee5e22a | CC-BY-NC-4.0 |
| CLIP ViT-B/32 | `timm/vit_base_patch32_clip_224.openai` @ a6f597a30f7b | open_clip format; only `open_clip_model.safetensors` + config fetched |
| DINOv2-small | `facebook/dinov2-small` | |
| ACE-Step 1.5 | `ACE-Step/Ace-Step1.5` | MIT, not gated. Many 1.5 variants exist (turbo, xl, sft, diffusers); M4 picks one |
| FLUX.2 klein 4B | `black-forest-labs/FLUX.2-klein-4B` | apache-2.0, **not gated** (spec expected it might be) |
| Wan 2.2 TI2V-5B | `Wan-AI/Wan2.2-TI2V-5B-Diffusers` (also a non-diffusers repo) | |
| LTX-Video | **moved:** Lightricks' current line is LTX-2.x (22B, too big for 8 GB) | `ltx` points at `Lightricks/LTX-Video` file `ltxv-2b-0.9.8-distilled.safetensors` |
| MusicGen small / faster-whisper | `facebook/musicgen-small`, `Systran/faster-whisper-small` | |

### Gotchas
- **`jq` is not installed** (CLAUDE.md relies on it): `sudo dnf install -y jq`. Until then, use `python3 -c` for JSON filters.
- System Python is 3.14; `uv python install 3.11` was needed (uv's Python downloads are set to manual).
- Never edit `scripts/download_models.sh` in place while it's running (bash reads by offset). Edit with `sed -i`, which renames, or stop it first. Python `write_text` truncates in place.
- The `kaggle` CLI comes from the base deps (`uv run kaggle`); there's no global install.
- Pre-commit excludes `assets/fonts/` from the whitespace fixers, so the OFL texts stay verbatim.
- No CI yet, so the M0 PR had no checks. M1 adds the minimal CI and `main` branch protection.

### Open TODO(Tahir)
- The GitHub repo is **private**. Make it public before submission (graders clone it).
- `sudo dnf install -y jq`.
- Fill in `.env`: GEMINI_API_KEY, CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN, KAGGLE_USERNAME + KAGGLE_KEY, and HF_TOKEN (recommended: higher HF rate limits, Spaces). Groq/OpenRouter are optional.
- §18.1 "before M3": story-owner interview; consent in `ethics/consents.yaml`; DESIGN.md audience + intent written and timestamped **before** any image generation.

### Next
M1 Core (see the prompt below).

## Next session prompt

```
Model: Opus · Effort: high
Read CLAUDE.md, docs/PROGRESS.md, then SPEC §5–8, §11.3–11.4, §16, §15 (CI bullet only), §20.

Goal: Milestone M1 Core. Branches: feat/core (schema, lint, cache, DAG, plan, runlog), feat/providers
(router, profiles, adapters, smoke), ci/minimal (CI + branch protection). One PR each, merged in order.

Scope:
- schema/storyboard.schema.json + schema/runlog.schema.json; tizita/storyboard.py (load, validate,
  §5.2 lint, canonical hashing); `tizita validate`, `tizita lint [--json]`.
- A 9-shot PLACEHOLDER fixture (tests/fixtures/ + storyboard.json); not the real story.
- cache.py (§6.2 keys, manifest with field hashes), dag.py (stage graph, dirty detection, plan),
  runlog.py + events.py (§8). `tizita plan [--check]` with the table from §6.3.
- providers/: base, errors (§7.3), router, circuit (.state/circuits.json), FallbackEvent + yellow
  rich line + logs/failures_auto.jsonl; config/providers.yaml, profiles.yaml, pricing.yaml (sourced,
  dated); profiles + per-capability overrides + paid guard (§7.2); privacy routing; consent gate.
- Adapters: Gemini text + TTS (google-genai, already a base dep), Cloudflare Workers AI image,
  Groq/OpenRouter text fallback; mms_tts + local_clip (weights already in ~/models/tizita:
  mms-tts-amh, clip-vit-b32 open_clip safetensors, dinov2-small; heavy imports lazy).
- `tizita providers`, `tizita smoke` (one call per configured provider → runs.jsonl). Record the real
  model ids found via models.list / the CF catalogue in providers.yaml and PROGRESS.md; anything moved →
  logs/failures_auto.jsonl.
- §16 core tests (schema/lint, cache, router, consent, profiles, privacy, runlog schema).
- .github/workflows/ci.yml: uv sync (base), ruff check + format --check, pytest, tizita validate,
  gitleaks, frontend npm ci + typecheck + build. Then protect main via gh api (require the `ci` check,
  PR required, 0 reviews, no force-push).
- Reuse: tizita/cli.py stubs (replace them), scripts/hf_fetch.py patterns, the Makefile targets.

Pre-conditions (Tahir): .env has GEMINI_API_KEY, CLOUDFLARE_ACCOUNT_ID/API_TOKEN (HF_TOKEN, GROQ,
OPENROUTER optional); `sudo dnf install -y jq`.

Acceptance:
- `make test lint` green; CI green on every M1 PR.
- `uv run tizita validate && uv run tizita plan` on the fixture prints the per-stage table.
- `uv run tizita smoke` → one runs.jsonl line per configured provider, real model ids;
  `tail -n 5 runs.jsonl | jq -c '{provider,model,status,latency_ms}'`.
- Write the §20 quota-budget table in PROGRESS.md (observed limits vs plan needs).

Stop and ask Tahir if a provider needs a paid key or a model id in the brief doesn't exist.
Remind him of the §18.1 "before M3" checkpoint (interview, consent, DESIGN audience/intent).
```

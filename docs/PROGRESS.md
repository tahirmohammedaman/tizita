# Progress log (agent-maintained)

## Status: M1 done (Wed 25 Nov 2026, ~18:00 EAT, ~30 min behind the §18 window)

### Done in M1
- **feat/core (PR #2):** `schema/storyboard.schema.json`, `schema/runlog.schema.json`; `tizita/storyboard.py` (load, schema, every §5.2 lint rule, Ethiopic-aware word count); `tizita/consent.py`; `tizita/cache.py` (§6.2 keys, manifest with per-field hashes); `tizita/dag.py` (per-stage `fields`/`upstream` declarations in `build_units`, dirty/missing/fallback-upgradable detection, `plan`); `tizita/runlog.py` (schema-checked writer, prompt hash + 200-char head, `spent_usd`); `tizita/events.py` (bus, `FallbackEvent`, sinks: events.jsonl, failures_auto.jsonl, yellow CLI line); `tizita validate | lint [--json] | plan [--check]`; 9-shot **PLACEHOLDER** fixture (`storyboard.json` == `tests/fixtures/storyboard_good.json`).
- **ci/minimal (PR #3):** `.github/workflows/ci.yml`, a single job `ci` (uv sync base, ruff check/format, pytest, `tizita validate`, gitleaks 8.24.3 binary over full history, frontend npm ci + typecheck + build). **Merged before feat/providers** (order changed so the providers PR gets real checks; the core PR had none).
- **feat/providers (PR #4):** `tizita/providers/` = errors (§7.3 + `classify_http`), base (`Request`/`Result`/`Provider`), circuit (`.state/circuits.json`, reset rules `daily_utc|daily_pacific|hours:N`), profiles (§7.2 profiles, `--provider cap=id[:model]`, paid guard), registry (yaml → providers, config lint incl. same-pool warning), router (retry/backoff/fallback, budget cap, privacy filter, consent gate, one runs.jsonl line per attempt), session, smoke (+ catalogue discovery). Adapters: `gemini_text`, `gemini_tts`, `cf_workers_ai` (text, image multipart/json, ASR), `openai_compat` (Groq/OpenRouter), `mms_tts`, `local_clip` (CLIP + DINOv2). `tizita providers`, `tizita smoke`, `plan --profile/--provider`.
- New config: `config/providers.yaml`, `profiles.yaml`, `pricing.yaml` (sourced, dated), `pipeline.yaml` (lint thresholds, GPU budget, plan estimates), `assembly.yaml` (subtitle limits only so far).
- Tests: 73 passing (schema/lint rules, cache/dirty propagation, router, profiles, privacy, consent, runlog schema, CLI).

### Smoke results (run `r_20261125_144821_ad0f`, plus `r_20261125_145107_31a9` re-checking klein)
| provider | model | status | latency |
|---|---|---|---|
| cf_text | `@cf/openai/gpt-oss-120b` | ok | 1.9 s |
| mms_tts_local | `facebook/mms-tts-amh@e366aee5e22a` | ok (3.0 s of audio) | 8.4 s incl. load |
| cf_flux2_klein | `@cf/black-forest-labs/flux-2-klein-4b` | ok, 512×512 4 steps | 7.2–10.0 s |
| cf_flux1_schnell | `@cf/black-forest-labs/flux-1-schnell` | ok (always 1024², no seed) | 2.5 s |
| local_clip | CLIP ViT-B/32 + DINOv2-small | ok | 3.7 s incl. load |
| cf_whisper | `@cf/openai/whisper-large-v3-turbo` | ok | 3.6 s |
| gemini_flash / _lite / gemini_tts | — | **skipped: GEMINI_API_KEY missing** | |
| groq_text / openrouter_text | — | skipped: keys not set (optional) | |

### Model ids / tools discovered (verify again when used)
| Item | Found | Note |
|---|---|---|
| Workers AI FLUX.2 klein 4B | `@cf/black-forest-labs/flux-2-klein-4b` | **multipart** input (schema: `{multipart: {body, contentType}}`): prompt, width, height, steps, seed, `input_image_0..3` for refs (ref path not exercised yet, M3). Returns base64 **JPEG** |
| Workers AI FLUX.1 schnell | `@cf/black-forest-labs/flux-1-schnell` | JSON `{prompt, steps≤8}` only, `additionalProperties: false`: **no seed, no size** (1024² out) |
| Workers AI text | `@cf/openai/gpt-oss-120b` (also llama-3.3-70b-fp8-fast, llama-4-scout, gemma-4-26b, qwen3.8-27b) | messages format works with gpt-oss-120b |
| Workers AI ASR | `@cf/openai/whisper-large-v3-turbo` | without `language` it wrote Amharic audio in Arabic script; pass `language: am` |
| Workers AI FLUX.2 klein **9B** / FLUX.2 dev | present in catalogue | **not used** (klein 9B non-commercial, SPEC §7.2) |
| Gemini 3.8 Flash / Flash-Lite / Flash TTS | ids in providers.yaml are **UNVERIFIED** guesses | `tizita smoke` checks them via `models.list` once the key exists and prints candidates if moved |
| MMS-TTS Amharic | needs **uroman** romanisation (`is_uroman: true`, Latin-only vocab) | added `uroman>=1.3` to the `ml` extra; 16 kHz output |
| CLIP | open_clip arch `ViT-B-32-quickgelu` loads the local safetensors directly | |
| M0 items (ACE-Step 1.5, FLUX.2 klein 4B HF, Wan 2.2 TI2V-5B, LTX moved to 2.x, MusicGen, faster-whisper) | unchanged | see git history of this file |

### Quota budget (SPEC §20): observed vs what the plan needs
| Free tier | Observed in M1 | Documented / assumed (not observed) | Plan needs | Risk |
|---|---|---|---|---|
| Cloudflare Workers AI (`cloudflare:neurons`, shared by text, image and ASR) | 7 small calls, no limit hit; the API does not report neurons per call | 10,000 neurons/day, resets 00:00 UTC | ~4 ref candidates + 12 keyframes × ≤3 attempts ≈ 40 images, plus text fallback | **Unknown neurons per klein image.** Read it from the CF dashboard (Workers AI → usage) for today's ~3 images before M3 |
| Gemini free (flash, flash-lite, tts: separate pools) | **not observed (no key)** | per-model RPM/RPD; preview TTS models have historically had small daily caps | TTS ≈ 9–12 lines × ~3 takes + benchmark ≈ 50–70 calls; text: director ≈ 10–20 calls | **TTS at risk** if the RPD is small. MMS-TTS local is the fallback and already works |
| Kaggle GPU (`kaggle:gpu`) | not exercised in M1 | weekly GPU quota (check the Kaggle settings page) | ≈ 3–6 i2v shots × ~6 min + ACE-Step 3 candidates ≈ 0.5–1 h | low, if the weekly quota is ≥ 20 h |
| HF (Spaces / ZeroGPU / Inference credits) | not exercised (adapters land M2–M4) | small ZeroGPU daily quota; monthly inference credits | a few fallback units only | low (fallback only) |
| Groq / OpenRouter | no keys | — | text fallback only | none |

### Gotchas
- **GitHub branch protection is unavailable while the repo is private** (Free plan, 403). `scripts/protect_main.sh` applies it (require `ci`, PR, 0 reviews, no force-push, enforce admins). Run it right after making the repo public.
- `gitleaks/gitleaks-action@v2` got a 403 listing PR commits even with `pull-requests: read`. CI runs the pinned binary instead.
- `.env` uses `ALLOW_PAID` / `PAID_BUDGET_USD`; `.env.example` says `TIZITA_ALLOW_PAID` / `TIZITA_BUDGET_USD`. **Both are accepted**; the TIZITA_ names win.

- Narration seeds: the storyboard has none, so the router logs `seed: null` for Gemini TTS and the MMS run uses whatever the stage passes. M2's narration stage should pass `style.seed_base + shot index` to MMS for reproducibility.
- Retry seeds: attempt 1 uses the storyboard seed; retry n uses `seed + (n-1)*1000`.
- Rich tables wrap at 80 columns when piped. Provider ids are `no_wrap`.
- `jq` is still not installed (`sudo dnf install -y jq`). Use `python3 -c` filters until then.

### Open TODO(Tahir)
- **Add `GEMINI_API_KEY` to `.env`**, then run `uv run tizita smoke --only gemini_flash --only gemini_flash_lite --only gemini_tts`. If the catalogue check says `moved`, put the right ids from the printed candidates into `config/providers.yaml` (or ask the next session to).
- Make the GitHub repo **public**, then `bash scripts/protect_main.sh`.
- `sudo dnf install -y jq`.
- Read today's Workers AI neuron usage in the Cloudflare dashboard and note it here (sizes the image budget).
- ETHICS.md data-flow table: Workers AI is marked `accepts_private_media: true` (Cloudflare states Workers AI inputs are not used for training). Confirm you accept that for photo mode, or set it to false (photo mode would then need the local FLUX path).
- §18.1 **before M3**: story-owner interview; consent in `ethics/consents.yaml`; DESIGN.md audience + intent written and timestamped **before** any image generation; `tizita new` for the real storyboard (M2 builds it).

### Next
M2 Narration + radio cut + director (prompt below).

## Next session prompt

```
Model: Sonnet · Effort: medium
Read CLAUDE.md, docs/PROGRESS.md, then SPEC §6.1, §10 items 1/4/8, §11.1, §13 (radio-cut/new rows).

Goal: M2 Narration + radio cut + director. Branches: feat/narration (narration, timing, subtitles
stages + `tizita run`), feat/radio-cut (synth pad + radio cut + `make radio-cut`), feat/director
(`tizita new`). One PR each, CI must be green (job `ci`), merge with --merge.

Reuse (don't rebuild): tizita/dag.py build_units/plan/resolve_upstream/unit_key/manifest_path_for
(stage field declarations already exist; keep STAGE_VERSIONS); tizita/cache.py Manifest.record;
tizita/providers/session.make_router + Router.call (returns result, provider, is_fallback; it writes
the artifact atomically and the runs.jsonl line); events.default_bus; storyboard.lint(measured=...).

Scope:
- tizita/stages/{narration,timing,subtitles,radio_cut}.py + a small runner in dag.py (`tizita run
  [--stage X] [--profile] [--provider]`): skip cached units, record manifest with is_fallback /
  primary_provider, end-of-run summary line (§7.4).
- narration: Request(capability="tts", prompt=text_am, inputs={voice, style_instruction}); MMS seed
  = style.seed_base + shot index. Measured duration → timing; feed lint(measured=...).
- deterministic providers `synth_pad` (FFmpeg ambient pad) and `previous_take`: give them adapters so
  the chains end somewhere. FFmpeg filtergraphs as pure functions in tizita/ffmpeg/ with golden-string
  tests (CLAUDE.md); `-hide_banner -loglevel error`; H.264 `-preset veryfast -crf 18`.
- subtitles: SRT + 9x16/16x9 ASS using config/assembly.yaml + Noto Sans Ethiopic (assets/fonts).
- radio cut: black 1080x1920 + narration + pad + burned subs → outputs/radio_cut/<key>.mp4.
- director (`tizita new`): Gemini text via the router (falls back to cf_text) → storyboard.draft.json;
  `--write` promotes after lint. Never overwrite storyboard.json without --write.
- Once outputs are committed, add `tizita plan --check` to CI (it must report 0 dirty).

Pre-conditions (Tahir): GEMINI_API_KEY in .env + re-smoke the 3 Gemini providers (fix ids if moved);
jq installed. Without the key, narration falls back to MMS-TTS (fine for M2, say so in the PR).

Acceptance:
- `make radio-cut` → an MP4 (ffprobe: 1080x1920, duration within 60–90 s).
- Edit one text_am, `uv run tizita run` → exactly 1 new tts line:
  `tail -n 20 runs.jsonl | jq -c 'select(.capability=="tts") | {unit,provider,status}'`.
- `make test lint` green; tag `radio-cut-v1` on main after the merge.
Stop for Tahir: after the radio cut exists (test 1 with 3+ people, §18.1), and before `tizita new
--write` replaces the placeholder storyboard.
Remind him of §18.1 "before M3": interview, consent, DESIGN.md audience/intent timestamped.
```

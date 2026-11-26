# Progress log (agent-maintained)

## Status: M2 done + storyboard v2 + male-voice radio cut v4 merged; M3 (references, keyframes) next (Thu 26 Nov 2026, DEADLINE 23:59 EAT)

### Done in M2
- **feat/narration (PR #5):** `tizita run [--stage] [--unit] [--force] [--upgrade-fallbacks]` (`dag.execute`: skips cached units, prunes superseded artifacts, manifest with `is_fallback`/`primary_provider`, §7.4 summary line); stages `narration` (seed = `seed_base` + shot index), `timing` (§10.1 slots, advice when outside 60–90 s), `subtitles` (SRT + 9x16/16x9 ASS). `.env.example` now uses exactly the `.env` names (no aliases). **Gemini key rotation**: `GEMINI_API_KEY_1..3` via `env_any`, next key on 429/quota before the router's circuit sees an error.
- **feat/radio-cut (PR #6, tag `radio-cut-v1`):** `tizita/ffmpeg/graphs.py` (pure builders + golden tests), `synth_pad` and `previous_take` adapters, `radio_cut` stage, `make radio-cut`, `plan --stage`, CI step `plan --check` over narration/timing/subtitles/radio_cut (0 dirty). Radio cut of the **placeholder**: 1080×1920 h264, 67.3 s.
- **feat/director (this PR):** `tizita new [--answers FILE] [--write]` (`tizita/director.py`): the model writes a compact beat sheet, code assembles the schema-shaped storyboard (seeds, flags, house style, one person reference per character), lint + up to 2 repair rounds → `storyboard.draft.json`. `--write` alone promotes an existing draft after lint (old storyboard backed up to `.state/backup/`). `interview/answers.yaml` holds Tahir's story brief; lines marked AGENT-ASSUMED need his confirmation. Privacy notice event when private photos go to a hosted provider.
- Tests: 100+ passing.

### Findings in M2 (real runs)
- **Gemini TTS reads a style prefix aloud**: with `"<style>: <text>"` a 2.7 s Amharic line came out at 9–10 s. `style_mode: none` is the default (plain text, voice name only). Draft in `logs/failures_auto.jsonl`. Voice `Kore` speaks Amharic acceptably to a non-native ear; **Tahir must rate it**.
- Gemini text: `gemini-3.8-flash` and `3.7-flash` returned 503 "high demand" for hours; `gemini-3.5-flash` and `3.6-flash` answered (slow, 20 s+). Added `gemini_flash_35` to the text chain. There is no `3.8-flash-lite`; the lite id is `gemini-3.5-flash-lite`.
- `gpt-oss-120b` (Workers AI) drafts a fine English beat sheet but writes poor, ungrammatical Amharic; prefer a Gemini draft for narration (`--provider text=gemini_flash_35`).
- gitleaks flagged 16-hex cache keys in generated logs as API keys; `.gitleaks.toml` allowlists exactly `"cache_key"|"key": "<16 hex>"`.

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
- Branch protection on `main` applied with `scripts/protect_main.sh` after the repo went public (25 Nov).
- `gitleaks/gitleaks-action@v2` got a 403 listing PR commits even with `pull-requests: read`. CI runs the pinned binary instead.
- Env names are identical in `.env` and `.env.example` (no aliases): `ALLOW_PAID`, `PAID_BUDGET_USD`, `GEMINI_API_KEY_1..3`.

- Narration seeds: the storyboard has none, so the router logs `seed: null` for Gemini TTS and the MMS run uses whatever the stage passes. M2's narration stage should pass `style.seed_base + shot index` to MMS for reproducibility.
- Retry seeds: attempt 1 uses the storyboard seed; retry n uses `seed + (n-1)*1000`.
- Rich tables wrap at 80 columns when piped. Provider ids are `no_wrap`.
- The provider cache check does not look at provider *params* (only the provider name): after changing params (e.g. `style_mode`) use `tizita run --force --stage narration`.
- `plan --check` in CI is limited to the four stages with committed outputs; extend `--stage` as M3–M5 commit theirs.

### Open TODO(Tahir)
- **Review `storyboard.draft.json`** (10 shots, 73 s planned, Gemini 3.5 Flash). Edit it if you like, then `uv run tizita new --write` promotes it. It replaces the placeholder storyboard, so the cached outputs go dirty by design.
- Confirm or replace the **AGENT-ASSUMED** lines in `interview/answers.yaml` (audience, final feeling) and write them into **DESIGN.md** (audience + intent, timestamped) **before any image is generated**. Replace the credits placeholder (`TODO(Tahir) your name`) in the storyboard.
- A native speaker must check the Amharic narration (grammar and tone) before M3 spends GPU/quota on it; the text is Gemini-written.
- Consent: you said you and your family consent. Record it in `ethics/consents.yaml` (the agent never writes consent records). The draft uses fictional, text-only references (`real_person: false`); photos/likeness of real people need those records first.
- **Photos (decided 25 Nov):** uploading to Cloudflare Workers AI is accepted; every upload path must warn first (CLI event `privacy_notice` exists; **the frontend upload page must show the warning**, M7). A repo clone uses the local FLUX path for private photos.
- Test 1 (3+ people) with the real radio cut, then `git tag test1-radio-cut`.
- Read today's Workers AI neuron usage in the Cloudflare dashboard (sizes the image budget for M3).
- §18.1 **before M3**: story-owner interview, consent, DESIGN.md timestamped.

### Next
M3 References + keyframes (prompt below). Needs the real storyboard promoted first.

### Done Thu 26 Nov (after M2)
- Storyboard v2 merged (PR #9): 11 shots (sisters at night, parents by day, nephew on lap), refs `ref_father`, `ref_child` added (6 refs total, 4 sheet candidates each), Amharic rewritten (Gemini 3.5 Flash draft, Flash-Lite critique, hand edits; Tahir approved: "nothing to correct"). Credits: "Story: Tahir Mohammedaman", "Narration voice, images and music: AI-generated".
- Male voice `Achird` (PR #10). TTS chain: gemini_tts, gemini_tts_paid, previous_take, then local MMS (never reached in free profile, so no mid-film voice change). Gemini keys 1-6 rotate on 429; a stale open circuit (`.state/circuits.json`) blocks keys until its `open_until`: delete the entry after adding keys.
- Radio cut v4 (`outputs/radio_cut/968f9abb6b180d97.mp4`, 77.2 s, 11/11 Gemini TTS, run r_20261126_072953_685c).
- Test 1 (family group chat, 4 siblings + 2 parents) and consent method recorded from Tahir's report; consent dates/evidence/words_approved still TODO(Tahir).

## Next session prompt

```
Model: Sonnet · Effort: medium (image calls are mostly plumbing; effort high only if the klein ref path misbehaves)
Read CLAUDE.md, docs/PROGRESS.md, then SPEC §6, §7.2 (image rows), §11.2.

Goal: M3 References + keyframes. Branches: feat/references (stage, 4 candidates per ref -> golden pick,
`tizita choose reference <ref> <N>`), then feat/keyframes (stage, CLIP gate, upload repaint, HF/local adapters).
One PR each, CI job `ci` green, merge with --merge (do NOT delete the branch yourself while a merge is pending: it closed PR #8).
DEADLINE is Thu 26 Nov 23:59 EAT: keep it lean; Ken Burns on all keyframes is the fallback if i2v time runs out.

State: storyboard.json = real story, 11 shots, 6 refs (family_car_ref object + 5 fictional text-only people).
Tag test1-radio-cut is on main (test 1 done by family). Consents are method-only; no photos are used, no real_person refs.

Reuse (don't rebuild): dag.build_units (references/keyframes fields + UpRef chosen declared), dag.execute +
stages/__init__.handlers (add `references`, `keyframes`), Router.call capability image/image_edit (chains in
config/providers.yaml), cf_workers_ai adapter (FLUX.2 klein is multipart; refs go in input_image_0..3; returns JPEG),
local_clip adapter for the CLIP gate, Request.private_media + consent gate.

Facts: klein 4B ok (~7-10 s, 512x512, 4 steps); schnell has no seed/size (1024^2). Neurons per image UNKNOWN: read the
CF dashboard and note it in PROGRESS. Max 3 attempts/unit, retry seed = seed + (n-1)*1000. ~24 ref candidates + 11 keyframes.
The ref path (input_image_0..3) has never been exercised: test it on one unit first.
Keyframe prompts for people must carry style.character_defaults + the ref's wardrobe from style.characters.

Acceptance: `uv run tizita plan --stage references --stage keyframes` lists units; candidates exist in outputs/references/<ref>/.
STOP: send Tahir each ref's candidate sheet with SendUserFile (he has no file access), wait for picks like
"car 2, brother 1, mother 3, youngest 2, father 1, child 4", apply `tizita choose reference`. Then generate all keyframes,
print the CLIP score table, send the keyframes to Tahir for the faces/hands check (SPEC §18.1).
make test lint green; extend `plan --check` in CI only for stages with committed outputs.
Also pending from Tahir: consent dates/evidence/words_approved; per-person quotes for test 1 (optional); DESIGN.md logline is final.
Stop and ask before spending quota if CF neurons look exhausted.
```

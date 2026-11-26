# Progress log (agent-maintained)

## Status: Ken Burns rough cut done, both films pass QA (feat/assemble). Waiting for Tahir: phone/headphones watch + `tizita choose music N`. Thu 26 Nov 2026, DEADLINE 23:59 EAT

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

### Done Thu 26 Nov (M3, PR feat/references: references + keyframes in one PR, two commits)
- `references` stage (4 candidates/ref at 512x512, contact sheet `<key>_sheet.jpg`, resumes without re-spending), `tizita choose reference <ref> <N>` (N 1-based, stored 0-based), `keyframes` stage (golden refs via `input_image_0..3`, character + wardrobe blocks in the prompt, CLIP/DINO gate with up to 3 re-seeds `seed+(n-1)*1000`, sidecar json), `Outcome.candidates` recorded in the manifest. `tizita/stages/images.py` holds the shared helpers. CI `plan --check` now covers references + keyframes.
- Tahir's picks: car 4, youngest 2, older 3, mother 4, father 3, child 2 (after one regeneration round with his notes: hijab mother, 1990 boxy dark blue-black sedan, no green, style_block "deep greens" -> "deep indigo blues"). Keyframes s01/s03/s04/s07/s09 redone once (prompts rewritten), others approved by Tahir.
- Found: the klein ref path (`input_image_0..3`) works. CF filter rejected a prompt naming "Mercedes-Benz" (HTTP 400, code 3030). Neurons: dashboard showed klein 2.71k for ~28 images at 512x512 (about 100 each, read 26 Nov 11:12); total today then 2.5k of 10k. CLIP scene-vs-portrait ~0.55 so threshold set to 0.5 (was 0.75); s01 scores: 0.5575/0.5448/0.563 across 3 seeds.
- Not done: HF image fallback adapter and local FLUX adapter (no adapter yet, chain falls to schnell which has no ref conditioning); upload repaint path is coded in the keyframes stage but untested (no upload shot). Do these only if CF quota fails.

### Done Thu 26 Nov (after M2)
- Storyboard v2 merged (PR #9): 11 shots (sisters at night, parents by day, nephew on lap), refs `ref_father`, `ref_child` added (6 refs total, 4 sheet candidates each), Amharic rewritten (Gemini 3.5 Flash draft, Flash-Lite critique, hand edits; Tahir approved: "nothing to correct"). Credits: "Story: Tahir Mohammedaman", "Narration voice, images and music: AI-generated".
- Male voice `Achird` (PR #10). TTS chain: gemini_tts, gemini_tts_paid, previous_take, then local MMS (never reached in free profile, so no mid-film voice change). Gemini keys 1-6 rotate on 429; a stale open circuit (`.state/circuits.json`) blocks keys until its `open_until`: delete the entry after adding keys.
- Radio cut v4 (`outputs/radio_cut/968f9abb6b180d97.mp4`, 77.2 s, 11/11 Gemini TTS, run r_20261126_072953_685c).
- Test 1 (family group chat, 4 siblings + 2 parents) and consent method recorded from Tahir's report; consent dates/evidence/words_approved still TODO(Tahir).

### Done Thu 26 Nov ~12:15 EAT (compressed M4/M5, part A: guaranteed final cut; PR feat/assemble)
- Stages `shots` (Ken Burns per keyframe, 1080x1920 24 fps, `shot.duration_s` long, zoompan on a 2x pre-scale with smoothstep easing), `music` (`music.candidates` through the music chain; with no Kaggle adapter it lands on `synth_pad`, one chord per candidate from `assembly.yaml: pad_variants`, FLAC), `assemble` (body with cut/crossfade/fade_black via xfade at slot starts, grade + grain, Pillow end card per ratio listing the models actually used, 9:16 + 16:9 in one ffmpeg pass, narration track -> ducked music -> two-pass loudnorm), `qa` (ffprobe + ebur128 -> `outputs/final/<key>/qa.json`, unit fails on any failed check). `tizita choose music N --reason`.
- The 4 i2v shots (s01 s03 s06 s10) are recorded as **fallbacks** (Ken Burns, primary `kaggle_wan22`) with `zoom 1.0->1.07` from `kenburns.fallback` because their own kenburns block is flat.
- Result (run `r_20261126_090820_6906`): both films 77.208 s, 1853/1853 frames, h264 High yuv420p, AAC 48 kHz, **-14.6 LUFS, -1.7 dBTP, LRA 6.8**. 9:16 = 61 MB, 16:9 = 26 MB. QA pass.
- `.gitignore` now excludes `outputs/final/**/*.mp4` (one render ~90 MB of history); `qa.json`, `assemble.json`, `film.srt` are committed. CI `plan --check` now covers shots + music too.
- `dag._prune` bug fixed: a new artifact with the old stem (same key, `.wav` -> `.flac`) was deleted as a "sibling". New artifacts/candidates are now kept; key-named dirs (`outputs/final/<key>/`) are removed whole.

### Findings (real measurements, 26 Nov; EXPERIMENTS material)
- **AAC PNS raises true peak**: master WAV at -3.0 dBTP became -0.9 dBTP after the native AAC encoder at 192k. `-aac_pns 0`: -2.5; `-aac_is 0`: -1.4; twoloop: -0.9; 256k: -2.9. Fix: `-aac_pns 0` + loudnorm TP target -2 (`assembly.yaml: master.tp`) -> -1.7 dBTP in the MP4.
- **Grain vs file size** (7 s Ken Burns clip, CRF 18 veryfast): grain 0: 2.3 MB, 2: 2.3 MB (x264 erases it), 3: 4.6 MB, 4: 10.4 MB, 6 (SPEC default): film 295 MB. Chose 3.
- ffmpeg quirks: concat/setpts output has no frame rate, so xfade fails ("1/0 is invalid"); end every clip chain and concat with `fps=24,settb=AVTB`. JPEG/PNG inputs come out full range (`yuvj420p`); scale with `out_range=tv`. A single graph with `asplit` feeding `sidechaincompress` produced a silent narration branch (-70 LUFS); the mix is now two commands and the sidechain is the narration file read twice.

### Done Thu 26 Nov ~12:40 EAT: real music (PR feat/ace-music)
- Tahir: "I want better music, not the continuous machine humming" and "no lyrics at all, just instrumental".
- `hf_ace_space` adapter (gradio_client, HF_TOKEN). Spaces tried 26 Nov: **ACE-Step/Ace-Step-v1.5** is RUNNING but answers "Model not fully initialized. Missing components: model, vae, text_tokenizer, text_encoder" for both `acestep-v15-xl-turbo` and `acestep-v15-turbo`; **ACE-Step/ACE-Step** (v1) fails server-side with `RepositoryNotFoundError`; **victor/ace-step-jam** `/generate` works (ACE-Step v1 3.5B, 8 steps, returns a base64 data URI WAV). 20 s took 26 s; 83 s ~35 s each.
- Caption changed to acoustic-only (no "synth pads"). Tags add "<bpm> BPM, <key>, instrumental, no vocals"; lyrics `[instrumental]`. 3 candidates (seeds 3000-3002, run `r_20261126_093124_ab46`), FLAC in `outputs/music/`. Whisper check on each (cf_whisper, en) returned only no-speech hallucinations ("Thank you." x3, "We'll be right back." x3): no words detected; wordless humming not ruled out, Tahir listens.
- Film re-assembled with candidate 1 (none chosen yet): QA pass, -14.6 LUFS, -1.7 dBTP.

- **Gemini TTS end-of-take noise** (Tahir heard a "ssshhh" between lines): every take ends with a ~0.16 s burst at -3..-7 dBFS (with a 30 ms digital-zero gap, identical pattern in all 11 takes) after the speech has decayed. Our adapter only wraps Gemini's PCM in a WAV header, so the noise is in Gemini's output. Fix: `tizita/audio.py: speech_end_s` + `narration_track_graph(ends_s=...)` cut each take in the quiet run before the burst (0.26-0.36 s removed, 30 ms fade). Takes unchanged (no new TTS calls). The radio cut v4 still has the burst (not re-rendered).
- Music previews (narration + ducked music, burst fixed) for listening: `previews/music_preview_{1,2,3}.m4a` (gitignored).

### Re-plan (time left ~11.5 h; SPEC §1 order: pipeline -> evidence/docs -> ceiling -> API/worker -> frontend -> deploy)
1. **Now (Tahir, ~20 min):** watch both films (phone + headphones), `uv run tizita choose music N --reason "..."`, then `uv run tizita run --stage assemble --stage qa`.
2. **GPU (optional, needs Tahir's OK):** no Kaggle runner/executor exists yet (adapters `kaggle_wan22`/`kaggle_ace` are `null`). Building runner + executor + kernel is ~2-3 h with real risk. Recommendation: **skip Wan**; try ACE-Step only if Tahir wants real music, time-boxed to 90 min, else the pad stays (documented as degradation).
3. **13:00-15:00 M6 evidence:** `tizita costs`, `make clean-clone-test` (0 model calls), EXPERIMENTS from real run_ids (AAC/PNS, grain, CLIP threshold, TTS style prefix, voice), FAILURES draft from `logs/failures_auto.jsonl`. TTS benchmark only if cheap.
4. **15:00-18:00 M9 docs + audit** (moved before M7: graded work reads docs only).
5. **18:00-21:00 M7** API + frontend pages 1-4 if time remains; **M8 deploy is cut** unless everything above is done.
6. Tahir: test 2 (3+ people) with the cut that has his chosen music -> DESIGN.md -> `git tag test2-near-final`; report, walkthrough, submit.

### Open TODO(Tahir) (new)
- Watch the cut; `tizita choose music N --reason`. Music is now 3 ACE-Step instrumental candidates (HF Space).
- Wan i2v recommended cut (no Kaggle runner).
- Publishing the films: they are not in git. Upload `outputs/final/<key>/film_*.mp4` where you post them (or say if you want a GitHub release made).

## Next session prompt

```
Model: Sonnet · Effort: medium (evidence + docs from existing runs; no new ML plumbing)
Read CLAUDE.md, docs/PROGRESS.md (Re-plan + Findings of 26 Nov), then SPEC §8.3, §12.1, §16, §17.

DEADLINE Thu 26 Nov 23:59 EAT. Goal: M6 evidence, then M9 docs (moved before M7, SPEC §1 order).
First, if `jq .music.chosen storyboard.json` is null, ask Tahir for `tizita choose music N` and stop.
Then `uv run tizita run --stage assemble --stage qa` (re-renders with the chosen music; ~1 min) and
commit the qa.json/assemble.json (films are gitignored).
Scope:
 1. `tizita costs` (SPEC §8.3, stub in tizita/cli.py) from runs.jsonl -> docs/COSTS.md.
 2. `make clean-clone-test`: clone, `make film` with no keys -> 0 model calls, QA pass. Fix what breaks.
 3. EXPERIMENTS.md: >= 8 entries from REAL measurements only, each with run_ids or the measuring
    command: AAC PNS vs true peak, grain vs size, CLIP threshold (s01 0.5575/0.5448/0.563), TTS style
    prefix (2.7 s -> 9-10 s), voice Kore vs Achird, ducking defaults (measure music under voice with
    ebur128 on stems), klein ref conditioning, Gemini model availability. Untested ones = `planned`.
 4. FAILURES.md draft from logs/failures_auto.jsonl (Tahir curates).
 5. Then M9: README (one-command run), ARCHITECTURE (Mermaid; say honestly which adapters are null:
    kaggle_wan22, kaggle_ace, hf_*), ETHICS licence table, audit vs the brief's criteria.
Reuse: tizita/stages/{shots,music,assemble,qa,endcard}.py, ffmpeg/graphs.py builders, dag.execute.
Acceptance: `make test lint` green; clean-clone test 0 calls + QA pass; COSTS.md generated;
EXPERIMENTS.md entries cite run_ids; PR merged with CI green.
STOP for Tahir: if he OKs Kaggle ACE-Step (time-box 90 min, needs runner/executor that don't exist);
test 2 with 3+ people on the cut with chosen music (SPEC 18.1), then `git tag test2-near-final`.
Quirks: AAC needs `-aac_pns 0`; grain 3 max; ffmpeg chains end with fps=24,settb=AVTB; never commit
films (~90 MB); i2v shots are Ken Burns fallbacks (primary kaggle_wan22) and show as upgradable.
```

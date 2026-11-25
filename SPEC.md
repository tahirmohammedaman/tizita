# Tizita — Project Specification

> *Tizita* (ትዝታ): Amharic for memory and longing. It is also the name of one of the classic Ethiopian musical modes (qenet). Repo: `tizita` · Python package and CLI: `tizita` · display name: **Tizita Studio** · showcase: `tizita.tahiraman.me`.

> Source of truth for the build. Original brief: `docs/challenge/Challenge_Document.pdf` (read it once in M0; afterwards read only the sections this spec points to).
> Owner: Tahir A. Mohammedaman. Deadline: **Thu 26 Nov 2026, 23:59 EAT** (target submit 21:00).

---

## 1. What we are building

Two things from one repo:

1. **The graded pipeline (local, one command).** `make film` on a clean clone (plus API keys in `.env`) validates `storyboard.json`, regenerates only what is missing or changed, and outputs a 60–90 s Amharic-narrated film with English subtitles, ducked original score, AI end card, in **9:16 and 16:9**. Runs entirely in-process on one machine. **Must never depend on the VPS, the Cloudflare Worker, or the frontend.**
2. **The showcase deployment (separate).** Same codebase, reusing the pipeline modules: React frontend on a Cloudflare Worker → FastAPI on a VPS via Cloudflare Tunnel → GPU work dispatched to Kaggle and to a GPU worker on the G14. Exists to show deployment and CI/CD. Nothing graded depends on it being up.

**Grading reality** (brief, "How your work is assessed"): Assignment 1 reads **code, text, logs and docs only**. It never opens media. So all evidence must be in writing: `runs.jsonl`, `logs/`, and the `.md` files. Build the pipeline and evidence first. Frontend and deployment come after.

**Priority order when time is short:** pipeline CLI → evidence/docs → ceiling experiments → API/worker → frontend → deployment.

---

## 2. Non-negotiables

- `storyboard.json` is the only contract between stages. Prompts, seeds, durations, references and voice settings live there, not in code.
- JSON Schema validation **plus** semantic lint runs before every run. Failure means no model is called.
- **Every model call appends one line to `runs.jsonl`** (schema §8). Cache hits and plan output go to `logs/events.jsonl`, not `runs.jsonl`.
- Content-addressed caching per shot per stage. A re-run regenerates only what changed (§6).
- Retries + classified errors + fallback chains + circuit breaker. The user is always told when a fallback happens (§7).
- **Every major stage offers free-hosted, local and paid options; the user chooses** via a profile or per-capability override (§7.2). The default profile is **free hosted**. Local GPU weights are optional and downloaded only on request. **Paid providers are never called without explicit opt-in and a budget cap.**
- No secrets in git: `.env` is gitignored, `.env.example` is committed, gitleaks runs in pre-commit and CI.
- **Consent gate in code:** a reference tagged `real_person: true` without a valid consent record fails validation (§11).
- **Privacy routing:** private photos are never sent to Gemini (free tier may train on inputs). Only image providers flagged `accepts_private_media` may receive them (§11).
- **Agents must not fabricate human evidence.** User-test notes, consent records, native-speaker ratings, A/B votes and "what I learned" text come from Tahir. Leave `<!-- TODO(Tahir): ... -->` markers. Experiment *results* must come from real runs and cite `run_id`s.
- Visual style is always the **warm painterly** house style, with or without uploaded photos.
- Characters default to **Ethiopian people with warm brown skin tones in everyday contemporary clothing**. Traditional dress (habesha kemis, netela, gabi) only when a shot or character block says so.
- Frontend text inputs and textareas: `spellCheck={false}` (owner preference: no red squiggles).

---

## 3. Environment

- Machine: ASUS ROG Zephyrus G14, RTX 4060 Laptop (8 GB VRAM), **WSL2 with Fedora 43**. Repo lives in the WSL filesystem (`~/tizita`), never `/mnt/c`. Package manager: `dnf`.
- **FFmpeg on Fedora:** the stock `ffmpeg-free` package has no H.264 encoder (libx264). Enable RPM Fusion (free + nonfree) and swap it: `sudo dnf swap ffmpeg-free ffmpeg --allowerasing`. Then verify that `ffmpeg -encoders | grep libx264`, `ffmpeg -filters | grep -E "subtitles|loudnorm|sidechaincompress|zoompan|xfade"` all succeed. `tizita smoke` must check this and fail with the fix if anything's missing.
- GPU: the NVIDIA driver is on the Windows side; check `nvidia-smi` inside WSL (it comes from `/usr/lib/wsl/lib`). The CUDA toolkit is only needed for the optional `gpu` extra.
- Python 3.11+ via `uv`. Node 20+ (`dnf install nodejs`). Docker Desktop with WSL integration enabled for the Fedora distro (or Podman with `podman compose` if Docker Desktop doesn't integrate; document whichever works).
- The README prerequisites must cover both Fedora (`dnf` + RPM Fusion) and Debian/Ubuntu (`apt`), because graders may use either.
- Model weights live outside the repo in `$MODELS_DIR` (default `~/models/tizita`), gitignored and never committed. **Large local weights are optional** (§19): the default install downloads only small CPU models (~1 GB), and every local GPU option is skipped as `Unavailable` until its weights are fetched with `tizita models download --only …`.
- Dependency groups in `pyproject.toml`:
  - base: CPU-only, CI-safe. Pipeline core, providers via HTTP, FFmpeg wrappers, FastAPI.
  - extra `ml`: CPU ML with the **CPU torch wheel** (open_clip/transformers for CLIP, MMS-TTS, jiwer). Installed by default.
  - extra `gpu`: torch CUDA, diffusers, ACE-Step, LTX-Video deps. **Not installed by default.** Use uv per-extra indexes/`conflicts` for CPU vs CUDA torch; if that's fiddly, keep CPU torch and document `uv sync --extra gpu` as the opt-in.
  - **All heavy imports are lazy**, so base install + `tizita validate/plan` work in CI with no GPU.

---

## 4. Repository layout

```
README.md            one command, prerequisites, keys, what it costs
SPEC.md  CLAUDE.md   this spec, agent rules
storyboard.json      THE contract
schema/storyboard.schema.json
config/
  providers.yaml     fallback chains per capability, model ids, quota pools
  pricing.yaml       list-price assumptions (sourced + dated) for COSTS.md
  assembly.yaml      ducking, loudness, subtitle styles, grade, transitions
tizita/              python package (CLI = `tizita`)
  cli.py             Typer app
  storyboard.py      load, validate, lint, canonical hashing
  dag.py             stage graph, dirty detection, plan, run
  cache.py           content-addressed keys, manifest
  runlog.py          runs.jsonl + events.jsonl writers
  events.py          event bus (CLI printer, SSE, files)
  providers/         base.py, errors.py, router.py, circuit.py,
                     gemini_text.py, gemini_tts.py, cf_workers_ai.py,
                     local_flux.py, mms_tts.py, local_clip.py, whisper_cf.py,
                     musicgen.py, synth_pad.py
  executors/         base.py, local.py, kaggle.py, worker.py   (GPU jobs)
  stages/            director.py, narration.py, timing.py, radio_cut.py,
                     references.py, keyframes.py, shots.py, music.py,
                     subtitles.py, assemble.py, qa.py
  gpu_jobs/          runner.py (same code on Kaggle, G14 and worker),
                     wan_i2v.py, ltx_i2v.py, ace_step.py, flux_local.py
  ffmpeg/            filtergraph builders (pure functions, unit-tested)
  api/               FastAPI app (showcase), db models, storage (local/R2)
  worker/            GPU worker client (showcase)
kaggle/wan_runner/   kernel-metadata.json template + entry script
experiments/
  tts_benchmark/     ceiling A
  motion_ab/         ceiling B
frontend/            Vite + React + TS + Tailwind + TanStack Query; worker.ts (CF Worker)
deploy/              Dockerfile, docker-compose.yml, cloudflared config, README
scripts/             download_models.sh, smoke.sh, clean_clone_test.sh
ethics/consents.yaml consent registry (evidence files private, hashes committed)
refs/                public/ (committed painterly sheets), private/ (gitignored photos)
outputs/             generated artifacts by stage/shot/key + manifest.json (committed, small)
logs/                events.jsonl, failures_auto.jsonl
runs.jsonl
docs/challenge/Challenge_Document.pdf
docs/PROGRESS.md     agent-maintained handoff log between sessions
DESIGN.md ARCHITECTURE.md EXPERIMENTS.md FAILURES.md COSTS.md ETHICS.md
.github/workflows/ci.yml  cd.yml
Makefile  .env.example  .gitignore  .gitleaks.toml  .pre-commit-config.yaml
```

Size budget for committed `outputs/`: keep it under ~300 MB total, with no single file over 90 MB. Draft clips at 480p. Final exports can be committed if under 90 MB each; otherwise link them in the README and keep them out of git. No Git LFS (graders' clones would hit LFS bandwidth limits).

---

## 5. The storyboard contract

### 5.1 Shape (abbreviated; the schema in `schema/` is authoritative)

```jsonc
{
  "version": 1,
  "meta": {
    "title": "…", "logline": "…",
    "narration_language": "am", "subtitle_language": "en",
    "target_duration_s": 75,                 // 60..90 incl. end card
    "audience": "…", "intent": "…"           // mirrored from DESIGN.md
  },
  "style": {
    "style_block": "warm painterly illustration, visible gouache and oil brush texture, soft golden-hour light, gentle film grain, muted earthy palette with warm ochres and deep greens, cinematic composition, subject centred for vertical framing",
    "character_defaults": "Ethiopian, warm brown skin tones, natural features, everyday contemporary clothing",
    "characters": {
      "grandmother": { "description": "…", "wardrobe": null, "reference_id": "ref_grandmother" }
    },
    "negative": "text, letters, watermark, logo, extra fingers, deformed hands, pale skin, western stock-photo look",
    "seed_base": 1000
  },
  "references": [
    { "id": "ref_grandmother", "kind": "person",       // person | place | object
      "real_person": true, "consent_id": "C-001",
      "photos": ["refs/private/grandmother_01.jpg"],   // optional; empty = text-only mode
      "description": "…",
      "sheet": { "candidates": 4, "chosen": null, "seed": 1100 } }
  ],
  "voice": {
    "provider_pref": "gemini_tts", "voice_name": "…",
    "style_instruction": "warm, slow, unhurried, like an elder telling a story",
    "pace_wps_limit": 2.3                               // lint threshold (measured values replace this later)
  },
  "music": {
    "caption": "gentle instrumental, soft strings and warm pads, sparse krar-like plucks, no lead melody, calm, nostalgic",
    "bpm": 70, "key": "D minor", "duration_s": 80, "instrumental": true,
    "candidates": 3, "seed": 3000, "chosen": null, "chosen_reason": null,
    "cues": [ { "id": "intro", "at_s": 0, "intent": "…" } ]
  },
  "shots": [
    {
      "id": "s01",
      "reason": "Establish the village at dawn so the viewer knows where and when we are.",
      "shot_size": "extreme_wide",       // extreme_wide|wide|medium|medium_close|close|extreme_close|insert
      "duration_s": 7.0,                 // planned; timing stage may extend to fit narration
      "characters": ["grandmother"],
      "references": ["ref_grandmother"],
      "keyframe": {
        "source": "generate",            // generate | upload
        "upload_path": null,             // if upload: repainted in house style (still generated, cached by file hash)
        "prompt": "…",                   // subject + composition only; style/character blocks auto-appended
        "seed": 1001, "candidates": 1, "approved": false
      },
      "motion": {
        "mode": "i2v",                   // i2v | kenburns | still
        "prompt": "camera pushes in slowly, morning mist drifts",  // motion + camera only
        "seed": 2001, "max_attempts": 3,
        "kenburns": { "zoom_from": 1.0, "zoom_to": 1.12, "pan": "none" }, // also used as fallback
        "approved": false
      },
      "narration": { "text_am": "…", "text_en": "…" },
      "music_cue": "intro",
      "transition_in": "crossfade"       // cut | crossfade | fade_black
    }
  ],
  "end_card": { "text_en": "Made with AI", "text_am": "…", "credits": ["…"], "duration_s": 3 }
}
```

### 5.2 Semantic lint (beyond JSON Schema)

- 8–12 shots, unique ids, `reason` ≥ 10 chars on every shot.
- Planned total (shots + end card) within 60–90 s. After the timing stage, the **measured** total must also fall in range.
- Narration words-per-second ≤ `voice.pace_wps_limit` per shot. Warning, not error. Once narration exists, the measured audio length replaces the estimate.
- Every referenced character, reference and cue id exists.
- `real_person` references need a consent (§11).
- `keyframe.source == upload` requires an existing `upload_path`.
- Subtitle lines (`text_en`) fit 2 lines × ~40 chars at the configured font (warning).
- `mode: i2v` count ≤ configured GPU budget (warning, with the estimated GPU minutes).
- The lint prints a short report and exits non-zero on errors. `tizita lint --json` gives the API/frontend a machine-readable version.

---

## 6. Stage graph and caching

### 6.1 Stages

| Stage | Granularity | Reads (fields → cache key) | Output |
|---|---|---|---|
| `director` | project | interview answers | draft `storyboard.json` (never overwrites without `--write`) |
| `narration` | shot | `narration.text_am`, `voice.*`, provider id | `outputs/narration/<shot>/<key>.wav` |
| `timing` | project | narration artifact hashes + measured durations, `shots[].duration_s`, `transition_in`, end_card duration | `outputs/timing/<key>.json` (slot start/end per shot) |
| `radio_cut` | project | timing, narration artifacts, placeholder pad | `outputs/radio_cut/<key>.mp4` (black 1080×1920 + narration + pad + burned subs) |
| `references` | reference | photo file hashes, description, `style_block`, `character_defaults`, sheet seed, provider | `outputs/references/<ref>/<key>_cand<N>.png`; chosen → golden |
| `keyframes` | shot | `keyframe.*`, style block, relevant character blocks, **golden reference hash(es)**, upload file hash, provider | `outputs/keyframes/<shot>/<key>.png` + CLIP score |
| `shots` | shot | keyframe artifact hash, `motion.*`, model + resolution + steps | `outputs/shots/<shot>/<key>.mp4` (fixed ~5 s; **independent of narration length**) |
| `music` | project | `music.*` except `chosen*`, provider | `outputs/music/<key>_cand<N>.wav` |
| `subtitles` | project | timing, `text_en`, subtitle styles | `outputs/subtitles/<key>.srt` + `_9x16.ass` + `_16x9.ass` |
| `assemble` | project | all upstream artifact hashes, `assembly.yaml`, chosen music | `outputs/final/<key>/film_9x16.mp4`, `film_16x9.mp4`, `film.srt` |
| `qa` | project | final artifacts | `outputs/final/<key>/qa.json` (ffprobe + ebur128 checks) |

Dependency order: narration → timing → (radio_cut) ; references → keyframes → shots ; music ; timing+text → subtitles ; everything → assemble → qa.

**Shot clips do not depend on narration length.** Assembly conforms each clip to its slot (trim, gentle slow-down down to 0.85×, then a Ken Burns tail on the last frame). Changing a narration line therefore regenerates **one TTS call** plus deterministic timing, subtitles and assembly. That is the walkthrough demo.

### 6.2 Cache keys

```
key = sha256(canonical_json({
  "stage": name, "stage_version": STAGE_VERSION,   // bump when stage code semantics change
  "fields": <exact storyboard fields this stage reads, canonicalised>,
  "upstream": {<artifact_name>: <sha256 of upstream artifact bytes>},
  "provider": {"name":…, "model":…, "params":…}, "seed": …
}))[:16]
```

- Each stage declares a `fields_for(shot|project)` function. Only those fields enter the key.
- `outputs/manifest.json` maps `(stage, unit_id)` → current key, path, sha256, provider actually used, `is_fallback`, created_at, run_id.
- **Provider in the key:** a fallback output is cached under the fallback provider's key. `tizita plan --upgrade-fallbacks` lists the units whose manifest `is_fallback=true` and whose primary provider is now available again. `tizita run --upgrade-fallbacks` re-renders them.
- Retries use `seed + attempt*1000`, and the seed actually used is logged.
- Writes are atomic (write to tmp, then rename). An interrupted run never leaves a half-written artifact registered as cached.

### 6.3 `tizita plan`

Dry run. It prints a table per stage with `unit | status (cached / dirty: <which field changed> / missing / fallback-upgradable) | provider | est. latency | est. GPU min`. To explain *which field changed*, it compares the current field hashes with the field hashes stored alongside each manifest entry. It also writes the plan to `logs/events.jsonl`. Exit code 0 always; `--check` exits 1 if anything is dirty (used in CI).

### 6.4 Approvals

`approved` flags in the storyboard gate expensive stages in `--interactive` mode. `tizita approve keyframes s03` sets the flag. Plain `make film` runs straight through, using whatever is committed, so a clean clone needs no human input.

---

## 7. Providers, retries, fallbacks

### 7.1 Interface

```python
class Provider(Protocol):
    name: str; model: str; capability: str        # text | tts | image | image_edit | i2v | music | embed | asr
    tier: str                                     # free_hosted | local | paid | deterministic
    quota_pool: str                               # e.g. "gemini-free:flash", "cloudflare:neurons", "hf:zerogpu", "local:g14", "kaggle:gpu", "fal:paid"
    accepts_private_media: bool
    est_cost_usd(req) -> float                    # 0 for free/local; real price for paid (from pricing.yaml)
    def available(self) -> Availability           # configured? circuit closed? worker online?
    def call(self, req) -> Result                 # raises classified errors
```

`router.py` walks the chain from `config/providers.yaml` for each capability. **Adjacent fallbacks must use different `quota_pool`s** wherever possible. The lint warns if a chain's first two entries share a pool.

### 7.2 Provider catalogue, profiles and user choice (verify every id at M1 smoke; record changes in FAILURES.md)

Each capability has options in four tiers. **Default chain = the free-hosted column, left to right, then the deterministic last resort.** Local and paid options are adapters the user can switch on.

| Capability | Free hosted (default chain, in order) | Local (optional; weights on demand) | Paid hosted (opt-in) | Deterministic last resort |
|---|---|---|---|---|
| text (director, translation) | Gemini 3.8 Flash → Gemini 3.8 Flash-Lite (separate quota) → Workers AI text model (Llama / gpt-oss family) → Groq free tier or an OpenRouter `:free` model | — | Gemini paid tier; Anthropic / OpenAI API | hand-edited storyboard |
| tts (Amharic) | Gemini 3.8 Flash TTS → MMS-TTS Amharic via a Hugging Face Space (`gradio_client`) | **MMS-TTS `facebook/mms-tts-amh`, CPU, ~150 MB, downloaded by default** (CC-BY-NC) | Gemini TTS paid tier; Azure Speech `am-ET` voices; ElevenLabs (verify Amharic) | previous cached take |
| image (+ ref conditioning) | FLUX.2 klein **4B** on Workers AI → FLUX via Hugging Face Inference Providers (free monthly credits) → FLUX.1 schnell on Workers AI (same CF pool, so last; no ref conditioning, logged as degraded consistency) | FLUX.2 klein 4B on the 4060 (quantised/offloaded) | fal.ai or Replicate FLUX.2; Nano Banana (Gemini paid / org lane) | previous approved keyframe |
| i2v | Wan 2.2 TI2V-5B on **Kaggle** (2×T4; weights download on Kaggle's side) → Wan 2.2 via a Hugging Face ZeroGPU Space (`gradio_client`, HF token; small daily quota, a few shots only) | Wan 2.2 5B or LTX-Video on the 4060 | fal.ai or Replicate Wan 2.2; Gemini Omni Flash (org lane) | **Ken Burns** (FFmpeg) |
| music | ACE-Step 1.5 on **Kaggle** (same batch as Wan) → ACE-Step via a Hugging Face Space | ACE-Step 1.5 on the 4060 (<4 GB VRAM) | fal.ai or Replicate (ACE-Step / Stable Audio); Lyria 3.5 (org lane) | FFmpeg-synthesised ambient pad |
| embed (consistency) | — | **CLIP ViT-B/32 + DINOv2-small, CPU, ~0.5 GB, downloaded by default** | — | skip + warning |
| asr (benchmark only) | Gemini 3.8 Flash (audio in) → Whisper on Workers AI → Groq Whisper | faster-whisper (optional) | — | skip |

Do **not** use FLUX.2 klein 9B (non-commercial licence).

**Free hosted Spaces are flaky** (queues, cold starts, tiny ZeroGPU quotas). Pin Space id + API endpoint name in `config/providers.yaml`, authenticate with the HF token, use timeouts, and treat them as "a few units" fallbacks, not throughput. If a Space has moved or its API changed, log it and skip it.

**Implementation scope (time-boxed):** free-hosted adapters and the two tiny local CPU adapters are built and smoke-tested. **One generic paid adapter** (fal.ai *or* Replicate, whichever is reachable; one class covering image, i2v and music by model id) plus Gemini paid-model entries through the existing Gemini SDK. Local GPU adapters are written against `runner.py` but marked `untested` in docs unless their weights were actually downloaded and run. Be honest about this in ARCHITECTURE.md.

#### Profiles (`config/profiles.yaml`)

| Profile | Chain order per capability |
|---|---|
| `free` (**default**) | free hosted → deterministic. Local only for the default tiny CPU models (MMS-TTS, CLIP) |
| `free+local` | free hosted → local (if weights present) → deterministic |
| `local-first` | local → free hosted → deterministic |
| `paid` | paid → free hosted → local → deterministic; requires `allow_paid: true` and `budget_usd` |
| `custom` | per-capability ordered lists |

How the user chooses:
- CLI: `tizita run --profile free+local`, the env var `TIZITA_PROFILE`, or per-capability overrides: `--provider image=fal:flux2-klein --provider i2v=kaggle:wan22`.
- Frontend: a **Settings → Providers** page per project: pick a profile, reorder or toggle providers per capability, see each one's status (configured / key missing / weights missing / circuit open / budget left).
- `tizita providers` lists every provider with tier, status, quota pool and licence.
- Missing local weights → `Unavailable`. `tizita plan` says so with the fix (`tizita models download --only wan`).

#### Paid guard
- Paid providers enter a chain only if the active profile allows them **and** `allow_paid: true` **and** a `budget_usd` is set.
- `tizita plan` shows the estimated paid spend. `tizita run` asks for confirmation (the UI shows a dialog) unless `--yes`.
- Spend is tracked from `runs.jsonl` (`cost_actual_usd`). When the budget is hit → a `FallbackEvent` with reason `budget_cap`, and the chain continues with the free tiers.
- A fallback **never escalates into paid** unless the profile explicitly lists paid after the failing provider.

### 7.3 Error taxonomy (`errors.py`)

| Class | Trigger | Action |
|---|---|---|
| `QuotaExhausted` | 429 with a quota message, daily/weekly limit, Kaggle GPU quota gone | open the circuit until `reset_at` (parsed or configured) → **fallback** |
| `RateLimited` | 429 with a short Retry-After | wait if ≤ 30 s, retry once; else treat as quota |
| `Transient` | 5xx, timeouts, connection reset | exponential backoff with full jitter (base 2 s, max 3 tries) → then fallback |
| `BadRequest` | 4xx validation | fail fast, no fallback, clear message |
| `SafetyBlocked` | provider refused the content | fail that unit with the provider message and a hint to rephrase; no silent fallback |
| `Unavailable` | not configured / worker offline / weights missing | skip to the next in the chain silently, but log at debug |
| `OutOfMemory` | CUDA OOM | retry once with lower resolution/offload; then fallback |

Circuit state is persisted in `.state/circuits.json` (gitignored). A dead provider is skipped for the remaining units in the run.

### 7.4 Telling the user

Every fallback emits a `FallbackEvent {stage, unit, from, to, from_tier, to_tier, error_class, message, reset_at}` (tier changes like free → local or paid → free are shown explicitly) that goes to:
- CLI: a yellow `rich` line: `⚠ keyframes s04: FLUX.2 klein (cloudflare) quota exhausted → falling back to FLUX.2 klein (local G14)`.
- `logs/events.jsonl`, plus the `fallback_from` field on the `runs.jsonl` line.
- `logs/failures_auto.jsonl` as a draft FAILURES entry (Tahir curates it into FAILURES.md).
- API SSE stream (frontend toast + "fallback" badge on the unit).
- End-of-run summary: `Run r_… done: 14 calls, 9 cache hits, 3 fallbacks (see logs/failures_auto.jsonl)`.

---

## 8. Logging

### 8.1 `runs.jsonl`: one line per model call (including failed attempts)

```json
{"ts":"2026-11-25T15:02:11.204Z","run_id":"r_20261125_150201_ab12","call_id":"c_0007",
 "stage":"keyframes","unit":"s04","capability":"image","provider":"cloudflare","model":"<id>",
 "executor":"api","params":{"width":768,"height":1344,"steps":4},"seed":1004,"attempt":1,
 "cache_key":"9f1c…","input_hash":"…","output_path":"outputs/keyframes/s04/9f1c….png","output_sha256":"…",
 "status":"ok","error_class":null,"error_message":null,"fallback_from":null,
 "latency_ms":1840,"gpu_seconds":null,"queue_ms":null,
 "metrics":{"clip_sim_to_golden":0.83},
 "tier":"free_hosted","profile":"free","cost_list_price_usd":0.0011,"cost_actual_usd":0.0,"cost_basis":"pricing.yaml#cloudflare.flux2_klein"}
```

`status` is one of `ok | error | fallback_triggered`. Prompts are stored by hash plus the first 200 characters (prompts live in storyboard.json anyway). Never log secrets or private photo bytes.

### 8.2 `logs/events.jsonl`

Run start/end, plan results, cache hits, fallbacks, circuit open/close, approvals, QA results.

### 8.3 `tizita costs`

Aggregates `runs.jsonl` and writes the **generated section** of COSTS.md (between `<!-- BEGIN GENERATED -->` markers):
- per-stage calls, p50/p95 latency, GPU minutes, cache-hit rate, list-price equivalent
- per-provider breakdown
- T4 vs 4060 latency for the same job type
- the free-tier limits Tahir actually observed

`config/pricing.yaml` lists list-price assumptions **with source URL and date**. Mark them as estimates.

---

## 9. GPU execution

### 9.1 Job model

`GpuJob {job_id, kind: wan_i2v|ltx_i2v|ace_step|flux_local, inputs: {name: path}, params, seed, cache_key, priority}`. A stage collects its dirty jobs into a batch, the executor runs them, results are imported into the cache, and `runs.jsonl` lines are written from each job's `result.json`: model, params, seed, latency, gpu_seconds, device name.

`gpu_jobs/runner.py` is the **same code everywhere**:
- input: `jobs.json` + an inputs dir
- output: per-job outputs + `results.jsonl`
- it processes jobs by priority
- it writes each result as soon as that job finishes
- it skips jobs whose output already exists (resumable)
- it stops starting new jobs when its time budget (`--budget-min`) runs out

### 9.2 Executors

- **LocalExecutor** (only for local-tier providers, and only when their weights are present): runs `runner.py` in a subprocess on the G14 GPU. One job at a time (8 GB VRAM). Catches OOM.
- **KaggleExecutor** (default for `wan_i2v` **and** `ace_step`; both run in the same batch so one session covers video and music), fully automated through the `kaggle` CLI/API:
  1. Build the bundle at `build/kaggle/<batch_id>/` (jobs.json + keyframes) and `kaggle datasets version` (create the first time).
  2. Render `kaggle/wan_runner/kernel-metadata.json` with `enable_gpu: true`, `enable_internet: true`, the dataset source, and the accelerator (T4×2 if the API exposes it; **verify and record**). Then `kaggle kernels push`.
  3. The kernel installs deps, downloads the Wan 2.2 TI2V-5B and ACE-Step weights from HF onto Kaggle's disk (Kaggle's bandwidth, not ours), and runs **two runner processes, one per GPU** (`CUDA_VISIBLE_DEVICES=0` and `1`) splitting the jobs. Budget: stop starting new jobs at about 10.5 h of the 12 h session.
  4. Poll `kaggle kernels status` every 60 s, emitting progress events. On completion, `kaggle kernels output` → import.
  5. Fallback mode (documented): `tizita gpu export --kind wan_i2v` builds a zip to run manually; `tizita gpu import <dir>`.
- **Choosing local vs Kaggle for Wan (measured, not guessed).** In M4, render the same 480p job once on a T4 and once on the 4060 (EXP-07); this needs the optional `wan` weights. Rule: **the overnight batch always goes to Kaggle** (2 GPUs in parallel, unattended, no laptop thermals). Single-shot re-renders on Thursday go to `local` **if** the 4060 fits in memory without swapping **and** it's at least 1.5× faster than a T4, counting Kaggle's ~10–15 min boot + weight download per session. Otherwise they go to Kaggle too. Record the numbers and the decision in EXPERIMENTS.md and COSTS.md.
- **WorkerExecutor** (showcase only): jobs are queued in the API DB. `tizita worker` on the G14 claims jobs over HTTPS (outbound only), sends a heartbeat every 15 s, and uploads results through presigned R2 URLs. If the heartbeat is missing for more than 60 s, the job is requeued and the router treats the worker as `Unavailable`.

### 9.3 Wan settings (starting points; tune via experiments)

- Image-to-video from the approved keyframe. Prompt = **motion + camera only**.
- Draft 480p, vertical (e.g. 480×832; check the model card for supported sizes), 24 fps. Frame count per the model card (~5 s).
- T4 has no fast bf16, so use fp16 with model CPU offload and VAE tiling. Steps: try 30 vs 40 (an experiment).
- Clips get upscaled in assembly (lanczos + grain). Re-render hero shots at 720p only if quota remains.

### 9.4 ACE-Step

- Runs on Kaggle by default (in the Wan batch; it's small and fast, so put the music jobs **first** in the batch so candidates arrive early). The HF Space is the free fallback; local on the 4060 is optional.
- Caption from `music.caption`. Tempo and key go in metadata fields, not the caption. Instrumental flag on.
- Duration: `music.duration_s` (if unstable past ~60 s, generate two sections and crossfade; log this).
- `candidates` seeds: `seed + i`.

---

## 10. Assembly (FFmpeg, deterministic)

All filtergraphs are built by pure functions in `tizita/ffmpeg/` (unit-tested on the graph string). Parameters come from `config/assembly.yaml`. Video exports use `-preset veryfast -crf 18`.

1. **Timing.** `slot_i = max(shot.duration_s, narration_len_i + lead 0.4 s + tail 0.6 s)`. Crossfades of 0.4 s overlap the slots. The end card is 3 s. Assert the measured total is within 60–90 s; otherwise fail with advice ("trim s07 narration by ~6 words").
2. **Video per slot (vertical master 1080×1920, 24 fps CFR):**
   - `i2v`: trim 0.25 s head and tail; if the clip is shorter than the slot, slow it down (min 0.85×), then hold the last frame with a Ken Burns tail.
   - `kenburns` and fallback: zoompan on a keyframe pre-scaled 2× (to avoid jitter), easing `zoom_from → zoom_to` and the pan direction.
   - `still`: a very slow 1.00 → 1.03 push.
   - Unified look: lanczos scale, a light grade (`eq` or a generated LUT), gentle grain (`noise=alls=6:allf=t`).
   - Transitions via `xfade` (crossfade / fade to black). Fade to black before the end card.
3. **Audio (48 kHz stereo):**
   - Place each narration take with `adelay` at its slot start.
   - Pre-normalise each source to a common working loudness before the mix (so balance decisions are creative, not repairs).
   - Music: chosen candidate, trimmed or looped to length, 2 s fade in, 3 s fade out.
   - **Ducking:** `sidechaincompress` with the narration as sidechain. Start at threshold 0.02, ratio 6, attack 300 ms, release 1500 ms (brief, Appendix B), then tune by ear and log as an experiment.
   - Optional very quiet ambience bed: skip unless time allows.
   - Final: **two-pass `loudnorm`**, I = −14 LUFS, TP = −1 dBTP, LRA 11. AAC 192 kbps.
4. **Subtitles:** SRT from `text_en` with slot-timed cues. Chunk at ≤ 2 lines × ~40 characters, splitting long lines into sequential cues by word count proportional to the audio.
   - Two ASS styles: **9:16** (Noto Sans, bottom margin about 22% of height to clear platform UI, outline + shadow) and **16:9** (bottom margin about 8%).
   - Burned per export (not into the master) so each layout is correct.
   - `film.srt` is also exported.
5. **End card:** Pillow renders a 3 s card per ratio. "Made with AI" (EN) plus an Amharic line in Noto Sans Ethiopic, a short credits list (models used), and the title. It's part of the film, not a platform overlay.
6. **16:9 export:** the background is the same master scaled to fill 1920×1080, `gblur` (sigma ~30) and darkened. The foreground is the master scaled to 1080 px high and centred. Then burn the 16:9 subtitles and append the 16:9 end card.
7. **Outputs:** `film_9x16.mp4` (1080×1920), `film_16x9.mp4` (1920×1080), H.264 High, yuv420p, `+faststart`, CFR 24.
8. **Radio cut:** black 1080×1920 + narration + an FFmpeg-synthesised placeholder pad + burned subtitles. Uses the same timing and subtitle code.
9. **Graceful degradation:** missing clip → Ken Burns of the keyframe. Missing keyframe → a dark placeholder card with the shot id and reason. Missing chosen music → first candidate → synth pad. Every degradation is logged as an event and listed in the run summary. A rough cut always renders.
10. **QA (`qa` stage):** ffprobe checks duration within 60–90 s for both files, resolution, fps, codecs. An `ebur128` measure checks integrated loudness within −14 ± 1 LUFS and true peak ≤ −1 dBTP. Results go to `qa.json` and `events.jsonl`. `make film` exits non-zero if QA fails.

---

## 11. Director, references, consent, privacy

### 11.1 Director interview (`tizita new`, also the API/frontend)

- Gemini text with **structured output against the storyboard JSON Schema**.
- It asks 6–8 questions, one at a time: whose story; who watches and where; the one feeling at the end; setting and era; key moments (3–5 beats); narration voice mood; music mood; photos available? (and whether the person is real, which triggers the consent prompt).
- It then drafts a storyboard (8–12 shots, each with a reason, prompts, motion, Amharic narration plus English, cues), which goes through lint and is saved as `storyboard.draft.json`. `--write` promotes it.
- Before the first question it warns the user not to share private family details (the free tier may train on inputs).
- Character blocks always start from `style.character_defaults` (Ethiopian, warm brown skin, contemporary clothes) unless the user specifies otherwise.

### 11.2 References (both modes)

- **Text-only:** generate `sheet.candidates` character/place sheets from description + style block + character defaults. The user picks one, which becomes the golden reference.
- **Photo mode:** photos → image-edit provider (klein reference conditioning) with the style block: "repaint as warm painterly illustration, keep identity and proportions". Same candidate and pick flow. Photos are used only to steer identity and composition. The output is always painterly.
- **Per-shot upload** (`keyframe.source: upload`): the uploaded image is repainted in the house style by the same edit path, conditioned on the golden reference if characters appear. Cached by file hash.
- **Consistency gate:** after each keyframe, compute the CLIP (fallback DINOv2) cosine similarity to the golden reference(s) for shots with characters. If below `consistency.threshold` (calibrate in an experiment; start at 0.75), re-seed, up to 3 attempts. Keep the best and log all scores. Flag it in the plan/QA if still below the threshold.

### 11.3 Consent gate

`ethics/consents.yaml`:
```yaml
- id: C-001
  person: "…"            # name or relation
  relation: grandmother
  scope: [likeness, story]   # likeness | voice | story
  recorded_on: 2026-11-25
  method: "voice note"       # voice note | video | written
  evidence_sha256: "…"       # evidence file kept private, NOT committed
  words_approved: true       # they agreed to the narration text
```
Validation: every `real_person: true` reference needs a `consent_id` whose scope includes `likeness`. Voice replication would need `voice` (not used: we use a prebuilt Gemini voice). Failure is a hard error with a message pointing to ETHICS.md. **The agent never creates consent entries.** It creates the template and a `TODO(Tahir)`.

### 11.4 Privacy routing

- `refs/private/` is gitignored, and so are uploads in the deployed instance's private R2 prefix.
- Providers with `accepts_private_media: false` (all Gemini free tier) are excluded by the router for any request carrying private media. Narration text sent to Gemini TTS is the approved script only.
- ETHICS.md has a data-flow table: which data → which provider → that provider's data terms.

---

## 12. Experiments and ceiling work

### 12.1 EXPERIMENTS.md format

Each entry: `EXP-NN | Hypothesis | Change (one variable, fixed seed) | Result (numbers + run_ids) | Decision`. Target ≥ 10 real entries. Candidates (pick by usefulness):
1. Gemini TTS voice A/B/C for Amharic (native ratings).
2. TTS style instruction vs none (prosody, measured length).
3. Keyframes: klein with reference conditioning vs prompt-only (CLIP similarity).
4. Calibrating the CLIP threshold against Tahir's same/not-same judgements.
5. Fixed seed vs varied seed for identity hold.
6. Wan steps 30 vs 40 (latency, visible artifacts).
7. Wan T4 vs local 4060 latency for the same job.
8. Motion prompt "motion + camera only" vs full description (tests a suggested practice).
9. ACE-Step caption short vs detailed (3 candidates each).
10. Ducking: brief's default parameters vs tuned (music level under voice measured via `ebur128` on stems).
11. Ceiling A: multilingual TTS benchmark.
12. Ceiling B: blind motion A/B.

### 12.2 Ceiling A: multilingual narration benchmark (`experiments/tts_benchmark/`)

- The same 5 short sentences from the film's story domain in **Amharic, Afaan Oromo, Tigrinya, Somali**. Translations drafted by Gemini; flag them for native-speaker correction.
- Gemini TTS per language: **1 voice first** (5 sentences × 4 languages = 20 calls), and a 2nd voice only if the TTS daily quota measured in M1 leaves room after the film's narration and retakes. The film always gets quota priority.
- **ASR round trip:** transcribe with Gemini (fallback: Whisper on Workers AI), then compute **CER** against the source with `jiwer`, with Unicode NFC normalisation and punctuation stripped. Ge'ez script for am/ti, Latin (Qubee) for om, Latin for so.
- Native-speaker ratings (1–5 intelligibility, 1–5 naturalness, notes on mispronounced words), collected via the tester pages or a CSV template.
- Output: `results.csv`, `REPORT.md` (table + failure modes + where each model breaks). **It is not in the film.**

### 12.3 Ceiling B: "Is motion worth the GPU?" (`experiments/motion_ab/`)

- For 4–6 shots that have a Wan clip, render a slot-identical Ken Burns version.
- Build blind pairs with randomised left/right (seeded and logged).
- Collect ≥ 5 people's preferences via the tester A/B page (or a static HTML fallback that exports a CSV).
- Analysis: preference % per shot and overall, a binomial 95% CI, plotted against GPU minutes per shot from `runs.jsonl`. Output: `REPORT.md`.

### 12.4 Optional ceiling D: MCP server

Only if Thursday is on schedule. `tizita mcp` exposes `validate`, `plan`, `run_unit`, `status` over stdio.

---

## 13. CLI

```
tizita smoke                     # one call per configured provider; logs latency to runs.jsonl
tizita models download [--only …]   # wraps scripts/download_models.sh; reports status
tizita new [--write]             # director interview
tizita validate | lint [--json]
tizita plan [--stage S] [--unit U] [--upgrade-fallbacks] [--check]
tizita run [--stage S] [--unit U] [--force] [--executor auto|local|kaggle] [--interactive] [--upgrade-fallbacks]
tizita radio-cut
tizita approve <stage> <unit> | tizita choose music <N> --reason "…"
tizita gpu export|import|status
tizita costs                     # regenerate COSTS.md generated section
tizita exp tts-benchmark | motion-ab build|analyze
tizita serve                     # showcase API
tizita worker --api-url … --token …   # showcase GPU worker
```

Makefile: `film` (validate → run all → qa), `radio-cut`, `plan`, `test`, `lint`, `costs`, `smoke`, `models`, `clean-clone-test` (clones to /tmp and runs `make film` with the cache, expecting 0 model calls), `serve`, `frontend`, `deploy`.

---

## 14. Showcase: API, worker, frontend

### 14.1 API (FastAPI, SQLite via SQLModel; storage interface `LocalStorage` | `R2Storage` via S3 API)

- Projects: `POST /api/projects`, `GET /api/projects/{id}`.
- Storyboard: `GET|PUT /api/projects/{id}/storyboard` (PUT validates and returns the lint).
- `POST /api/projects/{id}/plan`.
- Runs: `POST /api/projects/{id}/runs` → `run_id` (async; never a long request). `GET /api/runs/{id}`. `GET /api/runs/{id}/events` (SSE, **heartbeat comment every 20 s**, because Cloudflare cuts idle connections at about 100 s).
- Units: `POST /api/projects/{id}/units/{stage}/{unit}/regenerate` (optional new seed), `/approve`. `POST /api/projects/{id}/music/choose`.
- Uploads: `POST /api/projects/{id}/uploads/presign` → R2 presigned PUT (bypasses the 100 MB proxy limit), with a consent checkbox plus consent record required for `real_person`.
- Director: `POST /api/director/sessions`, `POST /api/director/sessions/{id}/messages`.
- Testers (public, tester-token scoped): `GET /api/t/{token}`, `POST /api/t/{token}/feedback`, `GET /api/t/{token}/ab`, `POST /api/t/{token}/ab/votes`.
- Worker: `POST /api/worker/claim|heartbeat|jobs/{id}/complete`.
- Read-only: `GET /api/projects/{id}/runs.jsonl?tail=200`, `/costs`.
- Export helpers: `GET /api/projects/{id}/feedback.md` (formatted for DESIGN.md), `/ab.csv`.
- Auth: an admin invite token (cookie) for studio pages; tester tokens scoped to (project, kind, expiry); a worker token; plus a shared `X-Edge-Auth` secret header added by the Cloudflare Worker. The API rejects anything without it, so the tunnel hostname can't be hit directly.

### 14.2 Frontend (Vite + React + TS + Tailwind + TanStack Query + React Router; EventSource for SSE)

Build order (cut line after page 4 if the Thu-noon checkpoint is missed):
1. **Tester pages** (public via token): watch a cut and answer 3 questions (What did you feel at the end? Where were you confused or bored? One thing to change?) with a timestamped "react here" button; **blind A/B** voting.
2. **Run monitor + shot grid:** per-shot cards (keyframe, clip, narration audio, status, cache/fallback badges, CLIP score), live progress, fallback toasts, log tail, cost panel.
3. **Storyboard editor:** shots as timeline cards; inline lint errors; duration meter; WPS warnings; **Plan** button showing dirty units; **Regenerate** / **Approve** per unit.
4. **Music chooser + export:** 3 players, a reason field, download both ratios + SRT.
5. **Director chat** → draft storyboard → open in the editor.
6. **References and uploads:** photo upload with the consent gate, character sheet candidates → pick golden.

Every text input/textarea has `spellCheck={false}`. Mobile-friendly tester pages (testers open them from Telegram).

### 14.3 Cloudflare Worker (`frontend/worker.ts`, `wrangler.toml`)

Serves the static SPA build (Workers static assets). Proxies `/api/*` to the tunnel hostname, adding `X-Edge-Auth`. It checks the admin cookie for studio routes and lets token-scoped tester routes through. Media is served from R2 via signed URLs (never video through the proxy from the VPS).

---

## 15. Deployment and CI/CD

- `deploy/Dockerfile`: python slim + ffmpeg + base & `ml` extras (no GPU).
- `deploy/docker-compose.yml`: `api` (+ SQLite volume) and `cloudflared` (tunnel token from env). The VPS runs no GPU stages. Kaggle is dispatched from the API, and local-GPU jobs go to the worker queue.
- `deploy/README.md`: tunnel setup, DNS (`tizita.tahiraman.me` → Worker; tunnel hostname for the API), R2 bucket + CORS for presigned PUTs, secrets list.
- **Branch workflow:** feature branches → PR → merge to `main` via `gh` (CLAUDE.md, "Git workflow"). A **minimal CI lands in M1** (ruff, pytest, `tizita validate`, gitleaks) so every PR from M1 onward has checks. M8 extends it. Once CI exists, protect `main` via `gh api` (require the `ci` status check and a PR before merging; 0 required reviews, because this is a solo repo; no force-push).
- **CI** (`.github/workflows/ci.yml`, every push/PR):
  - `uv sync` base, then `ruff check`, `ruff format --check`, `pytest`
  - `tizita validate`, then `tizita plan --check` (proves a clean clone with committed cache needs **0** regenerations)
  - gitleaks
  - frontend `npm ci && npm run typecheck && npm run build`
- **CD** (`.github/workflows/cd.yml`, on `main` after CI passes):
  - build & push the API image to GHCR
  - SSH to the VPS: `docker compose pull && docker compose up -d`
  - `wrangler deploy` for the frontend Worker
  - Secrets live in GitHub Actions secrets only.

---

## 16. Tests (pytest, CPU-only, fast)

- Schema + lint: good fixture passes; each lint rule has a failing fixture.
- Cache: changing a field a stage doesn't read leaves its key unchanged; changing one shot's narration dirties only `narration/sX` + timing + subtitles + assemble; provider change changes the key.
- Router: fake providers covering quota → fallback, transient → retry then fallback, bad request → no fallback, circuit opens and persists, adjacent same-pool warning.
- Consent gate: a real person without consent fails; with consent passes.
- Profiles: the default `free` profile never calls paid or local-GPU providers; paid without `allow_paid` + budget is excluded; the budget cap triggers a fallback to free; missing local weights → `Unavailable` with the plan hint.
- Privacy routing: private media is never routed to `accepts_private_media=false`.
- FFmpeg builders: golden-string tests for ducking, loudnorm two-pass args, xfade chain, pillarbox, subtitle styles.
- Timing: slot math, measured total within range, overflow error message.
- runlog: the line matches the JSON schema in `schema/runlog.schema.json`.

---

## 17. Documentation deliverables

| File | Who writes | Content |
|---|---|---|
| README.md | agent | what it is, one command, prerequisites (Linux or WSL; Fedora and Ubuntu install commands; FFmpeg with libx264/libass; uv; keys), `.env` setup, what a run costs (from COSTS), clean-clone behaviour (cache → 0 calls), how to regenerate one shot, showcase links |
| ARCHITECTURE.md | agent, reviewed | Mermaid stage diagram, the contract, cache-key design + example of a dirty plan, fallback chains & error taxonomy, executors, failure handling, local vs showcase split |
| DESIGN.md | **Tahir** (agent makes the skeleton) | audience, intent, logline (written **before** generation, with timestamp); test 1 (radio cut) and test 2 (near-final) with ≥ 3 people each: what they said → what changed, linked to storyboard git diffs (tag `test1-radio-cut`, `test2-near-final`); the reason per shot |
| EXPERIMENTS.md | agent drafts from runs, Tahir confirms | ≥ 10 entries (§12.1) citing run_ids |
| FAILURES.md | Tahir curates from `failures_auto.jsonl` | blocker → tried → fix/workaround; include tools that moved since the brief |
| COSTS.md | generated + Tahir notes | §8.3 |
| ETHICS.md | agent template, **Tahir fills consent** | consent records summary, licence table (every model + output, verified), labelling plan (end card, platform AI label, keep SynthID/C2PA metadata intact, no metadata stripping in FFmpeg: use `-map_metadata 0` where applicable), privacy data-flow table |
| docs/PROGRESS.md | agent, every milestone | done / next / gotchas / open TODO(Tahir) |
| docs/report_outline.md | agent | evidence pointers for each report section (audience learning, hardest problem, practice that helped/didn't, ceiling, next) |

Licence table starting points, **all to be verified**: Wan 2.2 Apache-2.0; ACE-Step 1.5 MIT (outputs commercial OK); FLUX.2 klein 4B Apache-2.0; FLUX.1 schnell Apache-2.0; Gemini API terms (free-tier data use); MMS-TTS CC-BY-NC-4.0; MusicGen weights CC-BY-NC-4.0; LTX-Video (own licence, check); open_clip/CLIP MIT; DINOv2 Apache-2.0; Whisper MIT; Noto fonts OFL.

---

## 18. Milestones

The plan, not a script. Times are targets (EAT). **Each milestone ends with the agent writing the prompt for the next one**, updated with what was learned (CLAUDE.md, "End of every milestone"). If reality diverges (a model moved, Kaggle is slow, we're behind), the agent re-plans the remaining milestones in `docs/PROGRESS.md`, keeping the priority order from §1 and the cut lines below.

Switch models with `/model`. "High" effort means the highest effort setting your Claude Code version offers, or "think hard" in the prompt. Run `/clear` between milestones.

| M | Window | Model / effort | Read | Scope | Acceptance |
|---|---|---|---|---|---|
| **M0 Init + downloads** | Wed 14:30–15:30 | **Opus / high**, plan mode | all of SPEC; brief sections listed in the M0 prompt | Plan; **start the default downloads in the background first** (§19 default set only, about 2–4 GB); scaffold the repo (§4); `uv` project with extras; Makefile stubs; `.env.example`; gitignore; pre-commit + gitleaks; doc skeletons with TODO(Tahir) markers; PROGRESS.md; **bootstrap commit on `main`, then the scaffold on `chore/m0-scaffold` → PR → merge** | `uv sync --extra ml` works; downloads running under `nohup` with logs; repo pushed; `.env.example` includes the optional keys (HF, Groq, OpenRouter, fal/Replicate) |
| **M1 Core** | Wed 15:30–17:30 | **Opus / high** | §5–8, §11.3–11.4, §16 | Schema + lint; canonical hashing; cache + manifest; DAG + plan; runlog/events; provider base, router, errors, circuit breaker, fallback events + CLI warnings; provider registry with tiers + **profiles + per-capability overrides + paid guard** (§7.2); Gemini text + TTS + Cloudflare image providers + Groq/OpenRouter text fallback; `tizita providers`; `tizita smoke`; consent gate; privacy routing; core tests; a 9-shot **placeholder** fixture (not the real story); **minimal CI workflow + `main` branch protection** | `tizita smoke` logs one line per provider with the real model ids recorded in `config/providers.yaml`; `tizita plan` works on the fixture; tests pass |
| **M2 Narration + radio cut + director** | Wed 17:30–19:00 | Sonnet / medium | §6.1, §10 items 1/4/8, §11.1 | Director interview; narration with the MMS-TTS fallback; timing; subtitles; radio cut with a synth pad | `make radio-cut` produces an MP4; editing one line → exactly 1 new TTS line in runs.jsonl (shown with jq); tag `radio-cut-v1` |
| **M3 References + keyframes** | Wed 19:00–21:00 | Sonnet / medium | §6, §7.2 image rows, §11.2 | References (text + photo modes, painterly repaint); candidates → golden pick; keyframes with reference conditioning + style/character blocks; CLIP gate; upload repaint path; HF Inference Providers image fallback; local FLUX adapter (weights optional) | Stops for Tahir to choose the golden, then all keyframes generated; CLIP score table reported |
| **M4 GPU: shots + music** | Wed 21:00–23:30 | **Opus / high** | §9, §7.2 i2v/music rows, §12.1 items 6–7 | Shared resumable `runner.py`; Wan/LTX/ACE-Step jobs; Local + Kaggle executors; `tizita gpu export/import/status`; HF Space fallbacks for i2v/music; one generic paid adapter (fal or Replicate) + Gemini paid entries; Ken Burns fallback; a Kaggle smoke batch (1 Wan job + 3 ACE-Step candidates); **then wait for Tahir's OK** to launch the overnight batch | Batch running; ACE-Step candidates exist; T4 latency recorded (4060 comparison only if Tahir downloaded the local weights) |
| **M5 Assembly + QA** | Thu 07:00–09:30 | **Opus / medium** | §10, §13, §16 ffmpeg/timing tests | Import Kaggle outputs; full assembly; both exports; QA; `make clean-clone-test` | Both MP4s pass QA (numbers reported); clean clone = 0 model calls |
| **M6 Ceiling + evidence** | Thu 09:30–11:00 | Sonnet / medium | §12, §8.3 | TTS benchmark (CER; rating columns left for natives); motion A/B pairs; `tizita costs`; EXPERIMENTS drafted from real runs only | Benchmark CSV + REPORT; pairs ready; COSTS generated |
| **M7 API + worker + frontend** | Thu 11:00–15:00 | Sonnet / medium (Opus only if the worker protocol gets stuck) | §14 | API → worker → frontend pages in §14.2 order; check with Tahir after page 4. **Cut line at 12:00:** if M5 isn't done, pages 1–4 only | Tester pages work on a phone; run monitor streams events; regenerate works end to end |
| **M8 Deploy + CI/CD** | Thu 15:00–16:30 | Sonnet / medium | §14.3, §15 | Docker/compose/cloudflared; CF Worker + wrangler; CI + CD workflows; list the secrets Tahir must add, then wait | CI green; Worker live at `tizita.tahiraman.me`; tunnel up; tester links work on a phone |
| **M9 Docs + audit** | Thu 16:30–19:00 | **Opus / high**, **fresh session** | §1–2, §17, brief's "How your work is assessed" | Finish README, ARCHITECTURE (Mermaid), the ETHICS licence table (verified), `docs/report_outline.md`; audit every Assignment 1 criterion as criterion → evidence → ✅/⚠ → fix; gitleaks on history; runs.jsonl schema check; clean-clone test | Audit all ✅ or explicitly accepted gaps; remaining TODO(Tahir) listed |
| Overflow | any | OpenCode / Antigravity (free models) | — | Boilerplate and docs polish when Claude limits hit; log which agent did what (report material) | — |

### 18.1 Tahir's checkpoints (the agent reminds him in each handoff prompt)

- **Before M3 (Wed afternoon):** story-owner interview; consent recorded in `ethics/consents.yaml`; DESIGN.md audience + intent written and timestamped **before** any image generation; run `tizita new` to create the real storyboard.
- **After M2 (Wed evening):** test 1 with the radio cut, 3+ people → DESIGN.md → storyboard changes → `git tag test1-radio-cut`.
- **During M3:** choose the golden reference; check faces and hands on every keyframe.
- **During M4 (~23:00):** OK the overnight Kaggle batch.
- **After M5 (Thu morning):** watch the rough cut on a phone and on headphones; `tizita choose music N --reason "…"`.
- **After M6 (~11:00):** test 2 with the near-final cut, 3+ people → DESIGN.md → changes → `git tag test2-near-final`; send native speakers the benchmark clips; collect 5+ blind A/B votes.
- **Thu 19:00–21:00:** curate FAILURES.md from `logs/failures_auto.jsonl`; confirm EXPERIMENTS.md; write the report; record the walkthrough (≤ 5 min, regenerate one narration line live); public post with the AI label on; **submit both assignments by 21:00**.

---

## 19. Downloads (start in M0, in the background)

`scripts/download_models.sh` is idempotent, logs to `logs/downloads.log`, writes `$MODELS_DIR/MANIFEST.json` (repo id, revision, size, status), runs under `nohup`, and checks `df -h ~` first.

**Default (M0, about 2–4 GB in total):**
1. Python env: `uv sync --extra ml` (base + CPU torch). Node deps for the frontend scaffold. `docker pull python:3.11-slim cloudflare/cloudflared`.
2. Fonts: Noto Sans + Noto Sans Ethiopic into `assets/fonts/` (OFL, committed).
3. Small CPU models: `facebook/mms-tts-amh`, open_clip ViT-B/32 weights, `facebook/dinov2-small`.

**Optional, on demand only** (`tizita models download --only <name>`; prints the size and asks before downloading; not run in M0):
`ace` (ACE-Step 1.5), `flux` (FLUX.2 klein 4B; may be gated, so tell Tahir to accept the licence on HF), `wan` (Wan 2.2 TI2V-5B), `ltx` (LTX-Video light variant), `musicgen` (MusicGen small), `whisper` (faster-whisper), plus `gpu` (the `uv sync --extra gpu` CUDA wheels).

Kaggle downloads its own weights inside the kernel, so they cost none of Tahir's bandwidth. Resolve exact repo ids from the model cards at download time, and record any changes in FAILURES.md.

---

## 20. Things to verify early (the brief warns tools move)

- Exact Gemini model ids for 3.8 Flash, Flash-Lite and Flash TTS via `models.list`; the Amharic voice list; the free-tier limits actually observed.
- The Workers AI catalogue: the FLUX.2 klein id and its reference-image input format, the FLUX.1 schnell id, the text model ids, the Whisper id, the daily neuron allowance.
- The Kaggle API: dataset version flow, the kernel accelerator selection field, output retrieval after a timeout.
- Wan 2.2 TI2V-5B: supported resolutions/frame counts, diffusers support, T4 fp16 behaviour; whether it fits the 4060 with offload.
- ACE-Step 1.5 install path and max stable duration.
- Free hosted fallbacks: current Hugging Face Space ids/API names for Wan 2.2, ACE-Step and MMS-TTS; HF Inference Providers free credit and the FLUX models available; Groq / OpenRouter free models and limits.
- Paid: whether fal.ai or Replicate is reachable/payable from Ethiopia (it may not be; the adapter still ships as an option for other users and the org lane).

- **Quota budget:** after M1's smoke test, write a small table in PROGRESS.md of each free tier's observed daily limit vs what the plan needs (TTS: about 12 lines + retakes + benchmark; images: about 4 reference candidates + 12 keyframes × up to 3 attempts; Kaggle: GPU hours for the batch). Flag any stage at risk *before* it runs.

Write each finding into `docs/PROGRESS.md`, and into FAILURES.md if something moved or broke.

# Failures

Blockers hit while building the pipeline: **blocker → what was tried → fix or workaround → evidence.**
Automatic drafts come from `logs/failures_auto.jsonl` (every fallback appends one); `run_id`s point
into `runs.jsonl`. This draft was assembled by the coding agent from those logs and
`docs/PROGRESS.md` on 26 Nov 2026.

## The hardest problems (Tahir)

1. **The Gemini TTS quota running out mid-run** (F-02): the narration voice changed halfway
   through the film.
2. **Working out what to build:** deciding the specification and writing the first versions of
   `SPEC.md` and `CLAUDE.md`, which the whole project started from.
3. **The local pipeline I first aimed for did not work out.** Running the models on my own machine
   meant downloading around 120 GB of weights, and most of the models needed about 32 GB of RAM plus
   CPU offloading. So I dropped the local-model option and moved to hosted providers (free tiers
   first, then WaveSpeed for images and motion).

Tahir reviewed the list below on 26 Nov 2026 and kept every entry.

## Quota, availability and limits

### F-01 · Gemini text models returned 503 for the whole drafting window
- **Blocker:** `gemini-3.8-flash` answered 0 of 24 attempts, director and smoke runs together
  ("experiencing high demand").
- **Tried:** retries with backoff, then Flash-Lite, then Workers AI `gpt-oss-120b`. The last
  answered, but its Amharic read as ungrammatical to the (non-native) agent.
- **Fix:** added `gemini-3.5-flash` to the text chain; it answered, slowly (p50 31 s). Narration was
  drafted with Gemini and then hand-edited and approved by Tahir.
- **Evidence:** `r_20261125_151751_c7d8` … `r_20261125_152435_ea1d`; EXP-10.

### F-02 · Gemini TTS free quota ran out in the middle of a narration run
- **Blocker:** `RESOURCE_EXHAUSTED` at s04. The router fell back to local MMS-TTS, so 8 of 11 lines
  came out in a different voice.
- **Tried:** the fallback worked as designed, but a voice change mid-film is not acceptable, and MMS
  ran 30% longer on the same lines (EXP-09).
- **Fix:** rotate across up to six keys (`GEMINI_API_KEY_1..6`) on a 429; put `previous_take` ahead
  of MMS in the TTS chain; delete the stale open circuit in `.state/circuits.json` after adding
  keys. The final narration is 11/11 Gemini.
- **Evidence:** `r_20261126_070255_0908` (failure), `r_20261126_072953_685c` (fixed).

### F-03 · No working GPU path for moving shots before the deadline
- **Blocker:** the Wan 2.2 image-to-video adapter needs a Kaggle runner and executor that were never
  built.
- **Decision:** cut Wan. A late, untested GPU path risked the whole film.
- **Workaround:** the four `i2v` shots (s01, s03, s06, s10) render as eased Ken Burns moves and are
  recorded in the manifest as **fallbacks**, so `tizita plan` can upgrade them later.
- **Evidence:** `outputs/final/*/assemble.json` (`degraded`).
- **Later (26 Nov afternoon):** after family feedback, all 11 shots were animated with Wan 2.2
  i2v on the paid WaveSpeed API instead (`tizita/providers/wavespeed.py`; F-17, EXP-16). Ken Burns
  stays as the fallback.

## Tools that moved since the brief

### F-04 · ACE-Step hosted Spaces
- **Blocker:** the official 1.5 Space answered "Model not fully initialized"; the official v1 Space
  failed with `RepositoryNotFoundError`. The first adapter calls also sent arguments the API
  rejected. Each failure fell back to the synth pad, so the run succeeded but the score was still a
  hum.
- **Tried:** both 1.5 model variants, then the v1 Space.
- **Fix:** a community Space, `victor/ace-step-jam` (ACE-Step v1 3.5B).
- **Evidence:** `r_20261126_092802_0914` … `r_20261126_093124_ab46`; EXP-11.

### F-05 · Model ids and APIs that differ from the plan
- There is no `gemini-3.8-flash-lite`; the lite id is `gemini-3.5-flash-lite`.
- FLUX.2 klein on Workers AI takes **multipart** input (references as `input_image_0..3`) and returns
  JPEG; FLUX.1 schnell accepts only prompt and steps (no seed, no size).
- MMS-TTS Amharic needs romanised input (`uroman`).
- **Evidence:** `config/providers.yaml` comments; `docs/PROGRESS.md` "Model ids / tools discovered".

## Language

### F-06 · The TTS model read the style instruction aloud
- **Blocker:** a 2.7 s Amharic line came out at 9–10 s; radio-cut slots were 11 s for six words.
- **Tried:** long instruction, "Say warmly:", plain text.
- **Fix:** plain text and a voice name (`style_mode: none`).
- **Evidence:** `r_20261125_150850_3486`, `r_20261125_150908_b5f0`; EXP-01.

### F-07 · Whisper wrote Amharic in Arabic script
- **Blocker:** without a language hint, Workers AI Whisper transcribed Amharic audio in the wrong
  script.
- **Fix:** pass `language: am` in any ASR round trip. It is not sufficient on its own: see F-15.
- **Evidence:** `logs/failures_auto.jsonl`, 2026-11-25T14:51.

### F-15 · Whisper cannot score our Amharic speech
- **Blocker:** median CER 1.333 on five lines that Gemini transcribed at 0.191, with repetition
  loops, and one line written in Latin letters despite `language=am`.
- **Tried:** the language hint (set from the start); trimming the TTS noise burst off the takes.
- **Outcome:** neither helped (median 1.375 trimmed). Whisper is not used as a judge of this
  Amharic. It stays only as the check for words in the score (EXP-12).
- **Evidence:** `r_20261126_112822_3429`, `r_20261126_113245_64ab`; EXP-14.

## Consistency and content filters

### F-08 · The similarity gate could never pass
- **Blocker:** the planned CLIP threshold (0.75) failed every attempt, because a scene and a portrait
  reference score about 0.55.
- **Fix:** threshold 0.5, used only as a tripwire; humans judge identity.
- **Evidence:** EXP-06.

### F-09 · The image safety filter rejected a car brand
- **Blocker:** HTTP 400 (code 3030) on a prompt that named "Mercedes-Benz". A safety block does not
  fall back silently, so the unit failed.
- **Fix:** describe the car instead (a boxy 1990 dark blue-black sedan).
- **Evidence:** `r_20261126_081945_b206` ("Your output has been flagged"); the cause (the brand
  name) is from `docs/PROGRESS.md`.

## Audio and FFmpeg

### F-10 · A hiss and click at both ends of every Gemini TTS take
- **Blocker:** Tahir heard a "ssshhh" between lines. 11 of 11 takes carried a near-full-scale burst
  after the speech, and a click at the start.
- **First fix (wrong cause):** trim at the quiet gap before the burst at assembly (EXP-02). That hid
  the tail but treated a symptom.
- **Root cause (found 26 Nov afternoon):** the Gemini TTS API answered with a **whole WAV file**
  (header, PCM, then a C2PA provenance chunk), and our adapter wrapped it in a second WAV header as
  if it were raw PCM. The player then read the inner header as samples (the click) and the C2PA
  manifest as samples (the burst at the end).
- **Fix:** `tizita/providers/gemini_tts.py: as_wav` keeps a WAV answer byte for byte and wraps only
  raw PCM; `tests/test_gemini_tts_wav.py`. The 10 committed takes were unwrapped back to Gemini's
  original bytes, so their sha256 no longer matches `output_sha256` in the older `runs.jsonl`
  lines (that log is append-only and was not rewritten). The tail trim stays as a guard.
- **Evidence:** `r_20261126_095219_805f` in `failures_auto.jsonl`; takes from
  `r_20261126_072953_685c`; commit `e7775c6`; EXP-02 and EXP-03 (corrected).

### F-11 · QA failed on true peak
- **Blocker:** both exports failed `true_peak` (`r_20261126_090216_2873`).
- **Tried:** AAC encoder flags and bitrates.
- **Fix:** `-aac_pns 0` and a −2 dBTP loudnorm target. A later grid (EXP-03) showed that the large
  PNS overshoot came from the F-10 noise bursts, i.e. from the C2PA bytes played as audio; with
  clean takes the −2 target is what matters.

### F-12 · Silent narration and broken crossfades
- **Blocker 1:** one filtergraph with `asplit` feeding `sidechaincompress` produced a silent
  narration branch (−70 LUFS). **Fix:** mix in two commands and read the narration file twice.
- **Blocker 2:** `concat` output has no frame rate, so `xfade` failed ("1/0 is invalid"). **Fix:** end
  every chain in `fps=24,settb=AVTB`.
- **Evidence:** `docs/PROGRESS.md` findings; golden tests in `tests/test_assembly.py`.

### F-13 · The end card credited the wrong string
- **Blocker:** the film's end card read "Music: ace-step-jam)", and the provider label said
  ACE-Step 1.5 although v1 3.5B ran. It passed QA, which does not read text.
- **Fix:** strip the host note before splitting the model id; corrected the label; added a test
  (PR #22). Found while writing the docs.

## Paid fallback for images and motion (26 Nov afternoon)

### F-16 · Cloudflare neurons and Hugging Face ZeroGPU ran out during the redraw
- **Blocker:** redrawing frames after family feedback used up the daily 10,000 Workers AI neurons
  (HTTP 429 for both FLUX.2 klein and FLUX.1 schnell). A new `hf_flux` adapter (FLUX through a
  ZeroGPU Space) failed on its first call: "You have exceeded your ZeroGPU runs limit".
- **Tried:** the free FLUX.1 schnell path (same neuron pool), then the Hugging Face Space.
- **Fix:** a paid adapter, `wavespeed` (FLUX.2 klein 4B edit with reference images, and Wan 2.2
  i2v), behind the paid guard (`ALLOW_PAID`, `PAID_BUDGET_USD`, profile `paid`). Three frames
  (s07, s09, s10) are still the free Workers AI ones.
- **Evidence:** `r_20261126_130951_92a3`, `r_20261126_132846_1b3a`; COSTS.md "Free-tier limits".

### F-17 · A price quoted before a paid run was wrong by 5×
- **Blocker:** before the s03 720p test, the coding assistant quoted the clip at about $0.03, reading
  WaveSpeed's `base_price` as per clip. It is per second of output; the 8 s 720p clip cost $0.16 by
  the account balance. The router logged the wrong estimate ($0.032).
- **Fix:** `config/pricing.yaml` prices Wan per second; the remaining clips used 480p
  ($0.01/s). The logged line stays as written; COSTS.md "Notes" carries the correction.
- **Lesson:** check a paid price against the balance after one call before batching.
- **Evidence:** `r_20261126_134523_f6fd`; COSTS.md.

### F-18 · Slowed i2v clips cut the film to 15.5 s, and QA passed it
- **Blocker:** the assembly slows i2v clips to fill their slot. The 5 s Wan clips ended before their
  slots did, the concatenated video stopped at 15.5 s while the audio ran on, and QA still passed:
  it counted the expected frames from the video stream, which agreed with itself.
- **Fix:** a slowed clip holds its last frame to the end of its slot (`tizita/ffmpeg/graphs.py`,
  assemble v3), and QA takes the expected length from the timing plan (`tizita/stages/qa.py`).
- **Evidence:** commit `e7775c6`; tests in `tests/test_assembly.py`.

### F-19 · A budget-capped retry replaced approved clips with Ken Burns
- **Blocker:** a paid retry of s05 and s08 ran with `PAID_BUDGET_USD=0.12`. The guard compares the
  **cumulative** logged spend ($0.73) plus the estimate against the budget, so both calls were
  blocked, the stage fell back to Ken Burns, and pruning removed the approved Wan clips.
- **Fix:** no money was spent; the clips and manifest were restored from git and the retry re-run
  with budget = logged spend + $0.12. The free profile no longer marks paid artifacts dirty
  ("provider not in active chain"), so `make film` keeps them.
- **Open:** a budget block should fail the unit, not fall back over an approved take.
- **Evidence:** `r_20261126_142935_5f40` (blocked), `r_20261126_143111_6c85` (2 calls, $0.10).

## Repository and CI

### F-14 · CI secret scan and branch protection
- `gitleaks-action` got HTTP 403 listing PR commits: replaced with a pinned gitleaks binary over the
  full history. It then flagged 16-hex cache keys as API keys: `.gitleaks.toml` allowlists exactly
  that pattern.
- Branch protection needed a public repository: applied with `scripts/protect_main.sh` afterwards.
- **Evidence:** `logs/failures_auto.jsonl`, 2026-11-25T14:51.

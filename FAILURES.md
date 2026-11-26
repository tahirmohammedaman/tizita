# Failures

Blockers hit while building the pipeline: **blocker → what was tried → fix or workaround → evidence.**
Automatic drafts come from `logs/failures_auto.jsonl` (every fallback appends one); `run_id`s point
into `runs.jsonl`. This draft was assembled by the coding agent from those logs and
`docs/PROGRESS.md` on 26 Nov 2026.

<!-- TODO(Tahir): curate. Cut, reorder, and add what you hit yourself. Name the hardest one for the
report and say in your own words what you learned. -->

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
- **Fix:** pass `language: am`. This matters for any ASR round trip.
- **Evidence:** `logs/failures_auto.jsonl`, 2026-11-25T14:51.

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

### F-10 · A burst of noise at the end of every Gemini TTS take
- **Blocker:** Tahir heard a "ssshhh" between lines. 11 of 11 takes carried a near-full-scale burst
  after the speech.
- **Fix:** detect the quiet gap before the burst and trim there at assembly.
- **Evidence:** `r_20261126_095219_805f` in `failures_auto.jsonl`; EXP-02.

### F-11 · QA failed on true peak
- **Blocker:** both exports failed `true_peak` (`r_20261126_090216_2873`).
- **Tried:** AAC encoder flags and bitrates.
- **Fix:** `-aac_pns 0` and a −2 dBTP loudnorm target. A later grid (EXP-03) showed that the large
  PNS overshoot came from the F-10 noise bursts; with clean takes the −2 target is what matters.

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

## Repository and CI

### F-14 · CI secret scan and branch protection
- `gitleaks-action` got HTTP 403 listing PR commits: replaced with a pinned gitleaks binary over the
  full history. It then flagged 16-hex cache keys as API keys: `.gitleaks.toml` allowlists exactly
  that pattern.
- Branch protection needed a public repository: applied with `scripts/protect_main.sh` afterwards.
- **Evidence:** `logs/failures_auto.jsonl`, 2026-11-25T14:51.

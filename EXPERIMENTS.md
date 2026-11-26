# Experiments

Format (SPEC §12.1): **Hypothesis → Change → Result (numbers + evidence) → Decision.**

- Results come only from real runs. Model calls cite `run_id`s in `runs.jsonl`. FFmpeg measurements
  name a command you can re-run: `uv run python experiments/measure/measure.py <name>` (no model
  calls; JSON saved in `experiments/measure/results/`).
- Several entries are single comparisons on one input (n is stated). Where more than one thing
  differs, the entry says so. Anything not run is listed under **Planned** with no result.
- Drafted by the coding agent from the logs on 26 Nov 2026.
  <!-- TODO(Tahir): confirm each Decision, or correct it. -->

| ID | Question | Outcome |
|---|---|---|
| 01 | Does a style instruction improve Gemini TTS? | No: the take was 3.1–3.4× longer. Removed |
| 02 | Is the "shhh" between lines in our mix or in the TTS takes? | In all 11 takes. Trimmed in assembly |
| 03 | Which AAC / loudnorm settings keep true peak ≤ −1 dBTP? | My first explanation was incomplete |
| 04 | How much film grain can we afford? | 3. The spec's 6 is 7× larger than 3 |
| 05 | Is the brief's ducking starting point right for this mix? | Kept: 23 dB voice over music |
| 06 | Does a CLIP threshold of 0.75 gate keyframes usefully? | No: it fails all 19 attempts. Lowered to 0.5 |
| 07 | Does re-seeding raise a low similarity score? | Not reliably |
| 08 | Does the male voice change the pacing? (Kore vs Achird) | No meaningful change |
| 09 | Can local MMS-TTS stand in for Gemini TTS mid-film? | No: 30% slower on the same lines |
| 10 | Which Gemini text model can the director rely on? | `3.8-flash` answered 0 of 24 attempts |
| 11 | Which hosted ACE-Step actually works? | One community Space, v1 model |
| 12 | Synth pad or generated score? | ACE-Step, candidate 1 |
| 13 | What does editing one narration line cost? | 1 model call, 0 GPU minutes |
| 14 | Can an ASR round trip judge TTS in four languages? | Not with one transcriber |

---

## EXP-01: TTS style instruction vs plain text

- **Hypothesis:** a style instruction ("warm, slow, like an elder telling a story") improves the
  Amharic delivery.
- **Change:** only the text sent to `gemini_tts` (voice Kore, same test sentence): style prefix,
  short "Say warmly:" prefix, or no prefix. Two rounds.
- **Result (take length, s):**

  | Variant | `r_20261125_150850_3486` | `r_20261125_150908_b5f0` |
  |---|---|---|
  | long style instruction | 9.12 | 10.43 |
  | "Say warmly:" | 6.17 | 4.63 |
  | no prefix | 2.65 | 3.39 |

  The long takes were longer because the model **read part of the instruction aloud**
  (`logs/failures_auto.jsonl`, 2026-11-25T15:10). The same input also varied between rounds
  (2.65 vs 3.39 s with no prefix), so TTS length is not deterministic.
- **Decision:** `style_mode: none` is the default: plain text, voice chosen by name.

## EXP-02: where the noise between narration lines comes from

- **Hypothesis:** the "shhh" heard between lines is in the TTS takes, not added by our FFmpeg mix.
- **Change:** none to the takes. Measured the 10 ms RMS of each committed WAV
  (`measure.py tails`), then cut each take in the quiet run before the burst.
- **Result:** **11 of 11** takes end in the same burst (peak about −2.6 dBFS) after the speech has
  decayed. The cut removes 0.26–0.36 s per take. The takes come from `r_20261126_072953_685c`.
- **Correction (26 Nov afternoon):** the hypothesis was right but the explanation was not. The
  sentence here used to say "the adapter only wraps Gemini's PCM in a WAV header". In fact Gemini
  returned a complete WAV with a C2PA chunk after the samples, and the adapter wrapped that whole
  file again, so the inner header played as a click and the C2PA manifest as the burst. The noise
  was ours, not Gemini's. Fixed at the source (FAILURES F-10); the takes were restored to the
  original bytes.
- **Decision:** keep the takes as generated (no re-spend) and trim at assembly
  (`tizita/audio.py: speech_end_s`, 30 ms fade). The older radio cut still has the noise.

## EXP-03: AAC encoder flags × tail trim × loudnorm true-peak target

- **Hypothesis (first version):** FFmpeg's AAC encoder raises true peak by about 2 dB on our speech,
  and the cause is perceptual noise substitution (PNS). On 26 Nov this led to `-aac_pns 0`.
- **Change:** re-ran as a grid (`measure.py aac`, FFmpeg 7.1.5): four encoder settings, with the
  EXP-02 trim on or off, with loudnorm TP target −1 or −2. QA limit: ≤ −1 dBTP.
- **Result (true peak, dBFS):**

  | tail trim | TP target | WAV master | AAC 192k | 192k, PNS off | 192k, IS off | AAC 256k |
  |---|---|---|---|---|---|---|
  | on | −1 | −1.0 | −0.8 | −0.8 | −0.8 | −0.8 |
  | on | −2 | −2.0 | −1.7 | −1.7 | −1.7 | −1.8 |
  | off | −1 | −1.0 | **+0.4** | −0.2 | +1.0 | −0.4 |
  | off | −2 | −2.0 | **+0.4** | **−1.7** | +1.5 | −1.5 |

- **What changed my mind:** the large overshoot, and the PNS effect, happen **only with the
  untrimmed noise bursts** (PNS acts on noise-like content). With clean takes the four encoder
  settings agree within 0.1 dB. What keeps QA green now is the −2 dBTP target: a −1 target still
  fails at −0.8.
- **Decision:** keep `master.tp: -2.0`. `-aac_pns 0` stays as a harmless guard for an untrimmed
  take, not as the fix.
- **Correction (26 Nov afternoon):** the "noise bursts" in this grid were the C2PA bytes of a
  double-wrapped WAV played as audio (F-10), so the "trim off" rows measure our own bug, not a
  property of the TTS. The "trim on" rows are the relevant ones.

## EXP-04: grain strength vs file size

- **Hypothesis:** the spec's grain (6) costs little at CRF 18.
- **Change:** only `noise=alls=N` on one Ken Burns clip (shot s02), CRF 18, preset veryfast
  (`measure.py grain`).
- **Result (MB):** 0 → 2.35 · 2 → 2.30 · 3 → 4.05 · 4 → 8.93 · 6 → 28.26. On the full film,
  grain 6 gave a 295 MB 9:16 export (measured 26 Nov, first assembly). At 2 the size equals no
  grain, which suggests x264 discards it; I did not compare the frames.
- **Decision:** grain 3 (`assembly.yaml: look.grain`).

## EXP-05: ducking parameters, measured on the music stem

- **Hypothesis:** the brief's starting point (threshold 0.02, ratio 6, attack 300 ms, release
  1500 ms) keeps the voice clear without removing the score in the gaps.
- **Change:** one parameter at a time, same narration track and chosen score. The ducked-music stem
  is rendered alone and its median 10 ms RMS taken during speech and in gaps (`measure.py duck`;
  2517 speech frames, 4292 gap frames; voice median −19.8 dBFS). Values are before final loudnorm.
- **Result (dBFS):**

  | Setting | music under voice | music in gaps | voice above music |
  |---|---|---|---|
  | no ducking (ratio 1) | −27.6 | −27.3 | 7.8 dB |
  | ratio 3 | −39.8 | −28.1 | 20.0 dB |
  | **brief default (ratio 6)** | **−42.9** | **−28.2** | **23.1 dB** |
  | ratio 12 | −44.4 | −28.2 | 24.6 dB |
  | release 300 ms | −39.8 | −27.3 | 20.0 dB |

- **Reading:** ducking adds 12–17 dB of separation. Going from ratio 6 to 12 adds only 1.5 dB. The
  short release lets the music back up sooner, including between words.
- **Decision:** keep the brief's values. RMS is not a listening test.
  <!-- TODO(Tahir): by ear on a phone speaker and headphones, is the music too quiet under speech? -->

## EXP-06: CLIP similarity threshold for keyframes

- **Hypothesis:** CLIP similarity ≥ 0.75 between a keyframe and its golden reference (SPEC default)
  separates acceptable keyframes from bad ones.
- **Change:** threshold only, applied after the fact to every recorded attempt (`measure.py clip`,
  from the keyframe sidecar JSONs, current and superseded; runs `r_20261126_082710_439e`,
  `r_20261126_084128_94c5`). The 19 attempts with a score cover scenes compared with portrait
  references.
- **Result:** min 0.445, median 0.550, max 0.744. Attempts that would fail: **0.75 → 19/19**,
  0.55 → 9, 0.50 → 4, 0.45 → 1. DINOv2 on the same attempts ranged from −0.07 to 0.37.
- **Reading:** a full scene against a head-and-shoulders portrait scores about 0.55 even for
  keyframes that were approved by eye. At 0.5 the gate is only a coarse tripwire. It was **not**
  calibrated against human same/not-same labels, so it does not prove identity is held.
- **Decision:** threshold 0.5; identity is judged by a human looking at the keyframes.

## EXP-07: does a new seed fix a low score?

- **Hypothesis:** re-seeding a keyframe that fails the gate raises its similarity score.
- **Change:** seed only (`+1000` per retry); same prompt and references.
- **Result:** s02: 0.482 → **0.625**. s07: 0.498 → 0.506. s08: 0.486 → 0.445 → 0.550
  (`outputs/keyframes/{s02,s07,s08}/*.json`). Three shots only.
- **Reading:** the score moved by −0.04 to +0.14 on the seed alone, about as much as the gap between
  passing and failing. When a picture was wrong in a way Tahir could name, editing the prompt (done
  for s01, s03, s04, s07, s09) was the tool used, not more seeds.
- **Decision:** keep at most 3 attempts, then keep the best.

## EXP-08: Kore vs Achird on the same Amharic lines

- **Hypothesis:** switching to a male voice (the story is told by a man) changes pacing enough to
  affect timing.
- **Change:** voice name only, 3 identical lines (`r_20261126_070255_0908` Kore,
  `r_20261126_072953_685c` Achird; `measure.py pace`).
- **Result (s):** s01 3.96 vs 3.92 · s02 3.19 vs 3.35 · s03 4.12 vs 4.20. All within 0.17 s.
- **Decision:** Achird, chosen for who is telling the story. Pacing was not a factor. No blind or
  native-speaker voice rating was run.
  <!-- TODO(Tahir): your own judgement of the two voices, if you compared them by ear. -->

## EXP-09: local MMS-TTS vs Gemini TTS on the same lines

- **Hypothesis:** the local fallback (`facebook/mms-tts-amh`) can replace single lines when the
  Gemini quota runs out.
- **Change:** provider (this also changes the voice), 8 identical lines (s04–s11). MMS ran after
  `gemini_tts` hit `quota_exhausted` in `r_20261126_070255_0908`; Gemini (Achird) ran later in
  `r_20261126_072953_685c`.
- **Result:** total 29.56 s (MMS) vs 22.75 s (Gemini): MMS is **30% longer**, even though the
  Gemini lengths include the EXP-02 tail. Per line the ratio ran from 1.01 (s06) to 1.66 (s09).
- **Reading:** mixing the two would change both the speaker and the rhythm in mid-film.
- **Decision:** the TTS chain tries `previous_take` (last cached take of that shot) before MMS. The
  shipped film uses Gemini for 11/11 lines.

## EXP-10: Gemini text model availability for the director

- **Hypothesis:** the newest Flash model is the right default for drafting the storyboard.
- **Change:** model id (director drafts, plus short smoke-test calls).
- **Result (`runs.jsonl`):** `gemini-3.8-flash`: **0 ok out of 24 attempts** across 6 runs
  (25 Nov 15:03–15:27 UTC), all `transient` (HTTP 503 "high demand"). `gemini-3.5-flash` answered
  5 of 6 attempts (25–26 Nov), slowly (p50 31 s, max 179 s; see COSTS.md).
  `r_20261125_152206_f1c9` shows the fall from one to the other.
- **Reading:** a window of under half an hour, and not run side by side; not a general reliability figure. The Workers AI
  fallback (`gpt-oss-120b`) also answered, but its Amharic looked ungrammatical (the agent's
  non-native reading, not a rating).
- **Decision:** add `gemini_flash_35` to the text chain and use a Gemini draft for narration.

## EXP-11: which hosted ACE-Step works

- **Hypothesis:** the official ACE-Step 1.5 Space can produce the score (no Kaggle runner exists).
- **Change:** the Space and model; same caption and `[instrumental]` lyrics.
- **Result:**

  | Target | Outcome | run_id |
  |---|---|---|
  | 1.5 Space, first calls | wrong arguments for its API | `r_20261126_092802_0914`, `r_20261126_092829_1c04` |
  | 1.5 `xl-turbo`, `turbo` | "Model not fully initialized" | `r_20261126_092850_1875`, `r_20261126_092907_6d80` |
  | official v1 Space | `RepositoryNotFoundError` | `r_20261126_092951_ef61` |
  | `victor/ace-step-jam` (v1 3.5B) | ok: 20 s clip in 26 s | `r_20261126_093039_edf9` |
  | same, 3 × 83 s candidates | ok: 50.1, 29.9, 28.7 s | `r_20261126_093124_ab46` |

- **Decision:** use `victor/ace-step-jam` and record the real model (v1 3.5B) in the log and on
  the end card. It is a community Space and may disappear; the committed FLAC files keep the film
  reproducible.

## EXP-12: synth pad vs ACE-Step score

- **Hypothesis:** a deterministic FFmpeg chord pad is good enough as the score.
- **Change:** score only. First `synth_pad` (`r_20261126_090820_6906`), then three ACE-Step
  candidates (`r_20261126_093124_ab46`) with an acoustic-only caption (the words "synth pads" were
  removed from it).
- **Result:** on the pad, Tahir: "I want better music, not the continuous machine humming", and
  asked for no lyrics at all. Whisper on the three candidates (`r_20261126_093444_954b`) returned
  only stock no-speech phrases, so no words were detected; wordless humming is not ruled out by
  that check. Tahir chose **candidate 1**: "More human-like, and goes well with the intent"
  (`storyboard.json: music.chosen_reason`). One listener, not blind.
- **Decision:** ship candidate 1. The pad stays as the last-resort fallback.

## EXP-13: cost of changing one narration line

- **Hypothesis:** because shot clips do not depend on narration length, editing one line needs one
  model call and no new pictures.
- **Change:** `shots[3].narration.text_am` (s04) in a scratch copy of the storyboard, then
  `tizita plan --storyboard <copy>`.
- **Result:** `45 units: 39 cached, 6 dirty` (≈ 2.2 min estimated wall time, **0 GPU min**): one
  TTS unit, then the deterministic timing, subtitles, radio_cut, assemble and qa. References,
  keyframes, shots and music stay cached. With no edit, a clean clone makes **0 model calls**
  (`make clean-clone-test`). This is a plan; the edited line was not re-rendered here.
- **Decision:** keep clips independent of narration; assembly fits clips to slots.

---

## EXP-14: judging TTS in four languages by ASR round trip (Ceiling A)

- **Hypothesis:** transcribing Gemini TTS output and scoring the CER shows which of Amharic, Oromo,
  Tigrinya and Somali the voice handles.
- **Change:** language (5 lines each, voice Achird); then the transcriber on identical audio; then,
  for Whisper on Amharic only, the noise burst trimmed or not.
- **Result (median CER, Gemini ASR / Whisper):** Amharic 0.191 / 1.333 · Somali 0.167 / 0.391 ·
  Oromo 0.309 / unsupported · Tigrinya 0.385 / unsupported. Trimming the burst: Whisper 1.333 →
  1.375. Runs: TTS `r_20261126_111807_9624` (Amharic reuses `r_20261126_072953_685c`), ASR
  `r_20261126_112822_3429`, trim `r_20261126_113245_64ab`.
- **What changed my mind:** on one Amharic file Gemini scored 0.000 and Whisper 1.333, writing the
  right sounds in Latin letters. The score measured the judge as much as the voice. My noise-burst
  explanation for Whisper's loops did not hold.
- **Decision:** report CER with its transcriber, never alone; treat Oromo and Tigrinya as unverified
  until a native speaker rates them. Full account:
  [REPORT](experiments/tts_benchmark/REPORT.md).

---

## EXP-15: FLUX.2 klein 4B edit prompts, v1 vs v2 (family-feedback frames)

- **Hypothesis:** a revised prompt fixes what the family pointed out in the redrawn frames.
- **Change:** prompt text only; same model (`wavespeed-ai/flux-2-klein-4b/edit`), same seeds
  (1001–1004, 1008), same reference images. v1: `r_20261126_133047_c3f0`; v2:
  `r_20261126_133254_a95a` (all five `prompt_sha256` differ; the logged heads are identical, so the
  change is in the later part of each prompt). s08 then got a third version with a new father
  description and seed 3108 (`r_20261126_133457_11d4`).
- **Result:** 14 images, $0.012 each, p50 17 s. The final film uses frames from this set for s01–s06,
  s08 and s11; s07, s09 and s10 are earlier free Workers AI frames.
- <!-- TODO(Tahir): what was wrong in v1, what v2 changed, and why you picked v2 (your judgement). -->

## EXP-16: Wan 2.2 i2v on WaveSpeed, 720p vs 480p

- **Hypothesis:** 720p is worth its price for a film delivered at 1080×1920.
- **Change:** resolution tier. s03 at 720p, 8 s (`r_20261126_134523_f6fd`); the other ten shots at
  480p, 5 s (s04 8 s) (`r_20261126_135159_20a5`, `r_20261126_135242_0610`).
- **Result:**

  | tier | raw clip | cost | inference time |
  |---|---|---|---|
  | 720p, 8 s | 720×1280, 241 frames @ 30 fps | $0.16 (by balance) | 119 s |
  | 480p, 5 s | 464×832, 161 frames @ 30 fps | $0.05 | 20–41 s (10 clips) |

  Per second of output, 720p costs 2× ($0.02 vs $0.01) and took about 3× as long to infer per second.
  This is one 720p clip against ten 480p ones, on different shots, so it is not a quality comparison.
- **Decision:** 480p for the rest of the film, to fit the prepaid credit; s03 keeps its 720p clip.
  Two 480p retries (s05, s08) with new seeds and tighter motion prompts went in after Tahir compared
  old and new side by side (`r_20261126_143111_6c85`).
- <!-- TODO(Tahir): did 720p look better than 480p once upscaled? Your judgement only. -->

## Planned (not run, no results)

| Question | Why not run |
|---|---|
| klein with reference images vs prompt-only (identity) | no prompt-only control run was made |
| CLIP threshold against human same / not-same labels | no labels collected |
| Gemini TTS voices rated by a native speaker | no ratings collected |
| Wan 30 vs 40 steps; motion-only prompts; T4 vs RTX 4060 | Wan was cut: no GPU runner was built |
| ACE-Step short vs detailed captions | one caption used |
| Native-speaker ratings for the four-language benchmark (EXP-14) | not collected yet |
| Ceiling B: blind motion A/B (Wan vs Ken Burns) | needs Wan clips |

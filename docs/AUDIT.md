# Requirements audit: Assignment 1

Each criterion from the brief ("How your work is assessed"), the evidence, and an honest status.
**ok** = evidence is in the repository · **partial** = real evidence with a stated hole ·
**gap** = missing. Written by the coding agent on 26 Nov 2026. It is a self-check, not a score.

## Software engineering and reproducibility (20)

| Asked | Evidence | Status |
|---|---|---|
| Clear stage boundaries around a validated `storyboard.json` | `schema/`, `tizita/storyboard.py`, `dag.build_units` (declared fields per stage); ARCHITECTURE | ok |
| Caching: only what changed is re-run | `tizita/cache.py`, `outputs/manifest.json`, tests; EXP-13; `tizita plan` | ok |
| Retries | `providers/router.py`, error taxonomy, `tests/test_router.py` | ok |
| No secrets committed | `.env` gitignored; gitleaks in pre-commit and CI over full history | ok |
| `runs.jsonl` complete | one schema-checked line per router attempt, and since the afternoon of 26 Nov one per rotated Gemini key (`metrics.rotated_key`, the key's name only). **Hole:** rotations before that fix have no line and cannot be reconstructed | partial |
| One documented command, from a clean clone | `make film`; `make clean-clone-test`: 0 model calls, QA pass | ok (tested on one machine only) |
| Same command generating from nothing | needs keys; the film was built stage by stage over two days and never regenerated from an empty cache in one run | partial |

## Documentation (10)

| Asked | Evidence | Status |
|---|---|---|
| README a stranger can follow | README: one command, outputs, picking music and references, keys | ok (not yet tried by a stranger; apt/dnf lines untested on a fresh machine) |
| ARCHITECTURE: contracts, caching, failures | ARCHITECTURE with stage and router diagrams, adapter status | ok |

## Design thinking and audience (10)

| Asked | Evidence | Status |
|---|---|---|
| Audience and intent before generating | DESIGN, timestamped 25 Nov 18:42, before the first film image (26 Nov), with the logline. Smoke-test images with unrelated prompts ran earlier. The wording started as agent-assumed defaults in `interview/answers.yaml`; the report states the same audience and intent | ok |
| Test 1 (radio cut), 3+ people | DESIGN: 6 family members; paraphrased, no verbatim quotes; one combined row | partial |
| Test 2 (near-final), 3+ people | DESIGN: two sisters, both parents and a friend, paraphrased; tag `test2-near-final`; seven requested changes with decisions | ok |
| Storyboard visibly changed by feedback | test 1: `git diff d483076 004855b -- storyboard.json`; test 2: `git diff test2-near-final main -- storyboard.json` (s01–s06, s08, s11 frames, s04 line, references, animation) | ok |
| A reason for every shot | `storyboard.json`, table in DESIGN; lint-enforced | ok |

## Experimentation and iteration (10)

| Asked | Evidence | Status |
|---|---|---|
| 10+ logged experiments with hypotheses | EXPERIMENTS EXP-01 to 16 | ok (several are small single comparisons, and say so) |
| Comparisons backed by evidence | run_ids; `experiments/measure/` with saved results | ok |
| Reasons for each choice | "Decision" in each entry, confirmed by Tahir on 26 Nov | ok |

## Troubleshooting and persistence (10)

| Asked | Evidence | Status |
|---|---|---|
| FAILURES.md: quota, consistency, language; tried; resolved | FAILURES F-01 to F-19 (reviewed by Tahir, all kept), `logs/failures_auto.jsonl` | ok |

## Measurement (5)

| Asked | Evidence | Status |
|---|---|---|
| Latency per stage | COSTS (generated) | ok |
| GPU minutes per stage | no own GPU job ran, and the hosted Space reports no GPU time | **gap** (stated in COSTS) |
| List-price cost equivalent | COSTS; published rates (read 26 Nov) applied to logged usage, lower bounds where usage is missing. Still unknown: gemini-3.5-flash (not on the pricing page), both ASR paths (usage not logged), the hosted music Space | partial |
| Frontier comparison "where you had access" | none run | not done |

## Consent, labelling and licences (5)

| Asked | Evidence | Status |
|---|---|---|
| Consent for every real person shown or voiced | no real person is shown or voiced; story consent from 6 family members in `ethics/consents.yaml`; the children's parents agreed to the mention (ETHICS) | ok |
| Licences checked | ETHICS table, read 26 Nov | ok |
| Labelling plan | ETHICS (YouTube with its AI label); end card | ok; label on the published video to be confirmed after posting; C2PA is in the narration WAVs, not in the MP4 (stated, not claimed) |

## Report (30, written by Tahir)

| Criterion | Evidence ready | Status |
|---|---|---|
| Reflection and learning from the audience (10) | REPORT sections 1–2; test 1 + diff; test 2 changes in DESIGN | written |
| Suggested practices tested honestly (10) | REPORT sections 4–5 | written |
| Curiosity beyond the floor (10) | REPORT section 6; `experiments/tts_benchmark/REPORT.md` (4 languages, 2 transcribers, EXP-14). Native comments: Amharic only, three named listeners (EXP-08); no motion A/B | written |

## Not built (from SPEC, not from the brief's criteria)

A free GPU executor (Kaggle/local; Wan runs on WaveSpeed's paid API instead); local image/music providers; FastAPI, worker, web
frontend pages and deployment (`tizita serve` and `worker` are stubs).

## Biggest risks, in order of points at stake

1. The motion depends on a paid API whose key must be revoked after submission; a clean clone
   rebuilds from committed clips and makes no paid call.
2. Ceiling A has native comments for Amharic only (three named listeners, no numeric scores), and
   Oromo and Tigrinya rest on one same-vendor transcriber.

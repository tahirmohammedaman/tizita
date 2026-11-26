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
| `runs.jsonl` complete | one schema-checked line per router attempt. **Hole:** when a Gemini key returns 429 and the next key is tried, that rotated attempt gets no line of its own (`gemini_text.call_rotating`) | partial |
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
| Audience and intent before generating | DESIGN, timestamped 25 Nov 18:42, before the first film image (26 Nov). Smoke-test images with unrelated prompts ran earlier. The wording started as agent-assumed defaults in `interview/answers.yaml`; the logline is empty | partial: TODO(Tahir) |
| Test 1 (radio cut), 3+ people | DESIGN: 6 family members; paraphrased, no verbatim quotes; one combined row | partial |
| Test 2 (near-final), 3+ people | DESIGN: two sisters and a friend, paraphrased; tag `test2-near-final`. How each watched, and the decisions on their requests, are still TODO | partial |
| Storyboard visibly changed by feedback | `git diff d483076 004855b -- storyboard.json` | ok for test 1 |
| A reason for every shot | `storyboard.json`, table in DESIGN; lint-enforced | ok |

## Experimentation and iteration (10)

| Asked | Evidence | Status |
|---|---|---|
| 10+ logged experiments with hypotheses | EXPERIMENTS EXP-01 to 13 | ok (several are small single comparisons, and say so) |
| Comparisons backed by evidence | run_ids; `experiments/measure/` with saved results | ok |
| Reasons for each choice | "Decision" in each entry | partial: Tahir has not confirmed them |

## Troubleshooting and persistence (10)

| Asked | Evidence | Status |
|---|---|---|
| FAILURES.md: quota, consistency, language; tried; resolved | FAILURES F-01 to F-14, `logs/failures_auto.jsonl` | partial until Tahir curates it |

## Measurement (5)

| Asked | Evidence | Status |
|---|---|---|
| Latency per stage | COSTS (generated) | ok |
| GPU minutes per stage | no own GPU job ran, and the hosted Space reports no GPU time | **gap** (stated in COSTS) |
| List-price cost equivalent | COSTS; most calls have no price in `config/pricing.yaml` | partial |
| Frontier comparison "where you had access" | none run | not done |

## Consent, labelling and licences (5)

| Asked | Evidence | Status |
|---|---|---|
| Consent for every real person shown or voiced | no real person is shown or voiced; story consent from 6 family members in `ethics/consents.yaml` | ok; one TODO about the children mentioned |
| Licences checked | ETHICS table, read 26 Nov | ok |
| Labelling plan | ETHICS; end card | ok; platform TODO; provenance survival unverified |

## Report (30, written by Tahir)

| Criterion | Evidence ready | Status |
|---|---|---|
| Reflection and learning from the audience (10) | test 1 + diff; test 2 pending | **gap** until written |
| Suggested practices tested honestly (10) | candidates in report_outline | **gap** until written |
| Curiosity beyond the floor (10) | no ceiling work run: no TTS benchmark, no motion A/B. `experiments/measure/` and EXP-03 (a corrected explanation) are the closest things | **gap** |

## Not built (from SPEC, not from the brief's criteria)

Wan 2.2 image-to-video and any GPU executor; local image/music providers; FastAPI, worker, web
frontend pages and deployment (`tizita serve` and `worker` are stubs).

## Biggest risks, in order of points at stake

1. Report not yet written (30).
2. No storyboard or film change in response to test 2 so far (test 1 did change the storyboard).
3. No ceiling work (10). The cheapest real option is Ceiling A, the TTS + ASR round-trip benchmark
   (SPEC §12.2: about 20 TTS and 20 ASR calls, plus the code, which does not exist yet).

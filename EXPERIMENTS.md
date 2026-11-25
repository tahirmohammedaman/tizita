# Experiments

Format (SPEC §12.1): **EXP-NN | Hypothesis | Change (one variable, fixed seed) | Result (numbers + run_ids) | Decision**.
Results come only from real runs and cite `run_id`s in `runs.jsonl`. Anything not yet run is `planned`.

| ID | Hypothesis | Change | Result | Decision | Status |
|---|---|---|---|---|---|
| EXP-01 | Gemini TTS voices differ in Amharic naturalness | voice A / B / C, same lines | — | — | planned |
| EXP-02 | A style instruction improves prosody | instruction vs none | — | — | planned |
| EXP-03 | klein reference conditioning holds identity better | ref-conditioned vs prompt-only (CLIP sim) | — | — | planned |
| EXP-04 | CLIP threshold 0.75 matches human same/not-same | threshold sweep vs Tahir's labels | — | — | planned |
| EXP-05 | A fixed seed helps identity hold | fixed vs varied seed | — | — | planned |
| EXP-06 | Wan 30 steps is close enough to 40 | steps 30 vs 40 | — | — | planned |
| EXP-07 | The local 4060 beats a Kaggle T4 for single re-renders | same 480p job on both | — | — | planned |
| EXP-08 | "Motion + camera only" prompts beat full descriptions | prompt style | — | — | planned |
| EXP-09 | Detailed ACE-Step captions beat short ones | short vs detailed, 3 candidates each | — | — | planned |
| EXP-10 | Tuned ducking beats the brief's defaults | sidechaincompress params (ebur128 on stems) | — | — | planned |
| EXP-11 | Ceiling A: multilingual TTS benchmark | am / om / ti / so, CER | — | — | planned |
| EXP-12 | Ceiling B: motion is worth the GPU | blind A/B, Wan vs Ken Burns | — | — | planned |

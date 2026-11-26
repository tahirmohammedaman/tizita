# Report outline (evidence pointers)

Agent-maintained pointers only. **The report is Tahir's to write.**

| Report section | Evidence in the repository |
|---|---|
| What I set out to make, and for whom | DESIGN.md "Audience and intent"; `storyboard.json` (`meta`, every shot's `reason`) |
| What my audience said and what changed | DESIGN.md test 1 and test 2; `git diff d483076 004855b -- storyboard.json` |
| The hardest problem and how I solved it | Candidates in FAILURES.md: F-02 (TTS quota changed the voice mid-film), F-10 → F-11 → EXP-03 (noise burst behind the true-peak failure), F-04 (score), F-03 (cutting Wan) |
| A suggested practice that helped | Candidates: ducking starting point (EXP-05, measured); two-pass loudnorm + QA gate (F-11, EXP-03); one storyboard contract + caching (EXP-13) |
| A suggested practice that did not, or needed changing | Candidates: style instructions for TTS (EXP-01, this was our own assumption: check what the brief suggests before claiming it); planned CLIP threshold (EXP-06, from our spec, not the brief) |
| Ceiling work | `experiments/tts_benchmark/REPORT.md`, EXP-14: four languages; Whisper vs Gemini disagreed on identical Amharic audio; a refuted explanation |
| What I'd build next | Candidates: Wan runner for the 4 fallback shots; human-labelled identity check; native ratings for the benchmark; showcase |

<!-- TODO(Tahir): choose and write in your own words. "A practice that beat my instinct" must be a
practice the brief suggested and an instinct you really had; only you know that. -->

# Ceiling A: how far can Gemini TTS go in four languages, and who can check it?

Run on 26 Nov 2026. **Not part of the film.** Voice `Achird`, model `gemini-3.8-flash-tts`, five short
story lines per language (the film's shots s01, s03, s06, s07, s09). Each take is transcribed by an
ASR model that never sees the text, and the transcript is compared with it (character error rate,
CER: 0 is identical; above 1 means more edits than the reference has characters).

## What a CER here does and does not mean

A round-trip CER mixes **three** sources of error: the translation, the voice, and the transcriber.
It is not a quality score for the voice, and with n = 5 it cannot rank languages.

- **Amharic** text is the film's own narration, approved by Tahir. Its five takes are the film's
  takes (`r_20261126_072953_685c`), so no new TTS quota was spent on them.
- **Oromo, Tigrinya, Somali** text was drafted by `gemini-3.5-flash-lite`
  (`r_20261126_111807_9624`) and **no native speaker has checked it**. The 15 new takes are from the
  same run.
- Transcripts: `r_20261126_112822_3429` (`gemini-3.5-flash-lite` and Whisper large-v3-turbo).
- **No native-speaker ratings have been collected.** `ratings_template.csv` is blank.

## Results

| Language | ASR | n | median CER | mean CER | best | worst | median CER, homophones folded |
|---|---|---|---|---|---|---|---|
| Amharic | gemini_asr | 5 | 0.191 | 0.160 | 0.000 | 0.300 | 0.191 |
| Amharic | cf_whisper | 5 | 1.333 | 1.422 | 0.769 | 2.733 | 1.333 |
| Afaan Oromo | gemini_asr | 5 | 0.309 | 0.319 | 0.200 | 0.437 | n/a |
| Afaan Oromo | cf_whisper | 0 | no Whisper language support | | | | |
| Tigrinya | gemini_asr | 5 | 0.385 | 0.377 | 0.222 | 0.576 | n/a |
| Tigrinya | cf_whisper | 0 | no Whisper language support | | | | |
| Somali | gemini_asr | 5 | 0.167 | 0.221 | 0.048 | 0.388 | n/a |
| Somali | cf_whisper | 5 | 0.391 | 0.327 | 0.175 | 0.485 | n/a |

Per-line scores, references and transcripts: [`results.csv`](results.csv).
Gemini TTS answered **15 of 15** new requests; no quota error. The takes are 2.2–4.5 s long, and all
20 end in the same noise burst found in the film (EXP-02).

## Findings

### 1. One transcriber would have given the wrong answer for Amharic
Whisper's median CER on Amharic was **1.333**; Gemini's on the **same files** was **0.191**. For s07,
Gemini's transcript is exact (0.000). Whisper's is `Matā matā hë tōčin wude bīt adr-sallu.`: close
to the right sounds, **written in Latin letters** although `language=am` was set (score 1.333). On
other lines it falls into repetition loops (`እን እን እን`, `ፍፍፍፍ`). So the audio on s07 is
intelligible and the failure is Whisper's. Had Whisper been the only judge, the conclusion would
have been "Gemini cannot speak Amharic".

### 2. The obvious explanation was wrong
Every take ends in a loud noise burst, which could plausibly start Whisper's loops. One variable
changed: the burst trimmed off (`trim_check.py`, `r_20261126_113245_64ab`).

| line | s01 | s03 | s06 | s07 | s09 | median |
|---|---|---|---|---|---|---|
| as generated | 2.733 | 0.769 | 1.381 | 1.333 | 0.893 | 1.333 |
| trimmed | 2.667 | 0.949 | 4.191 | 1.375 | 1.143 | 1.375 |

No improvement. The burst does not explain the failure. (F-07 introduced the `language=am` hint
after Arabic-script output on another clip. Here the hint was set, and s07 still came out in Latin.)

### 3. Where it breaks, by language
- **Amharic (Gemini ASR 0.19):** one line exact, one nearly exact (0.026), the rest 0.19–0.30. The
  errors are changed vowels and dropped consonants (s06 `ይጮኻል` "rings" → `ይዞሃል`, a different phrase).
  Folding same-sounding Amharic letters (ሀ/ሐ/ኀ, ሰ/ሠ, አ/ዐ, ጸ/ፀ) changed **nothing**, so these are
  not spelling variants.
- **Somali (Gemini 0.17, Whisper 0.39 median):** the one language where two unrelated transcribers
  both return readable text. They agree that s03 and s07 are the easiest lines (≤ 0.18).
- **Afaan Oromo (0.31):** word boundaries and long or doubled letters drift. s07 loses most of the
  sentence (`obboleettota koo gara manaatti` → `Obbo Luba Taakkoo Garmanaatiin`, which reads like a
  personal name).
- **Tigrinya (0.39):** the worst median. Part of this is the **translation**: the s01 draft begins
  with a word in **Arabic script** (`كتريا`), and s03 carries a bracketed gloss `(መንዳቢ)` that the
  voice reads out. These were left as drafted and not removed after seeing the scores.
  Correction (26 Nov, afternoon): a character scan also found a stray **Hebrew** letter inside a word
  in s03 (U+05DC) and a **Syriac** letter in s07 (U+072C). So 3 of the 5 Tigrinya lines (s01, s03,
  s07) contain non-Ethiopic letters. Do not use these lines for native ratings without saying so.
  How much each fault adds to the CER was not measured.

### 4. Availability was a result too
`gemini-3.5-flash` returned HTTP 503 on every audio request tried (11 items, three attempts each,
`r_20261126_111807_9624`) and on all 12 translation attempts (`r_20261126_111750_1ca2` and the same
run).
`gemini-3.5-flash-lite` then did all of it. See `runs.jsonl`, stage `exp`.

## What I would not claim

- That Somali is "better" than Amharic: five lines, an unchecked translation, and no listener.
- That the Gemini ASR score is independent evidence about Gemini TTS. Both are Google models; a
  shared habit could make the pair look better than a human would find it. Only Amharic and Somali
  have a second transcriber, and for Amharic that one failed. **Oromo and Tigrinya rest on a single,
  same-vendor judge.**

## Next
Native ratings (1–5 intelligibility and naturalness) in `ratings_template.csv`; checked
translations; an ASR model built for these languages as a third judge.

## Reproduce
```bash
uv sync --extra ml                       # jiwer
uv run tizita exp tts-benchmark --report # re-score the saved transcripts, no model calls
uv run tizita exp tts-benchmark          # calls only what is missing from state.json
```

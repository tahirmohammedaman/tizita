# Ethics: consent, licences, labelling, privacy

## Consent

Every real person shown or voiced needs an entry in `ethics/consents.yaml` **before** anything of them is generated. Validation enforces this: a `real_person: true` reference without a consent whose scope includes `likeness` is a hard error. Evidence files stay private; only their SHA-256 is committed.

| ID | Person / relation | Scope | Recorded on | Method | Words approved |
|---|---|---|---|---|---|
| <!-- TODO(Tahir): summarise each consent; the agent never creates consent entries --> | | | | | |

## Licences (every model and output)

**All rows are unverified starting points (SPEC §17). Verify each against the model card in M9.**

| Component | Use | Licence | Outputs usable? | Verified |
|---|---|---|---|---|
| Wan 2.2 TI2V-5B | i2v | Apache-2.0 | | ☐ |
| ACE-Step 1.5 | music | MIT | commercial OK (per brief) | ☐ |
| FLUX.2 klein 4B | keyframes | Apache-2.0 | | ☐ |
| FLUX.1 schnell | keyframes (fallback) | Apache-2.0 | | ☐ |
| Gemini API (text, TTS) | director, narration | Gemini API terms (free tier may use inputs) | | ☐ |
| MMS-TTS `facebook/mms-tts-amh` | TTS fallback | CC-BY-NC-4.0 | non-commercial | ☐ |
| MusicGen | music (optional) | CC-BY-NC-4.0 (weights) | non-commercial | ☐ |
| LTX-Video | i2v (optional) | own licence | check | ☐ |
| OpenAI CLIP ViT-B/32 (open_clip) | consistency | MIT | n/a | ☐ |
| DINOv2-small | consistency | Apache-2.0 | n/a | ☐ |
| Whisper | ASR (benchmark) | MIT | n/a | ☐ |
| Noto Sans / Noto Sans Ethiopic | subtitles, end card | OFL-1.1 | yes | ☐ |

## Labelling plan

- An end card inside the film: "Made with AI" (EN) plus an Amharic line, with credits for the models used.
- The platform's AI label switched on when posting.
- Provenance metadata (SynthID / C2PA) is never stripped; FFmpeg uses `-map_metadata 0` where applicable.
<!-- TODO(Tahir): platform(s) and how you'll label there. -->

## Privacy data flow

| Data | Goes to | Provider terms | Notes |
|---|---|---|---|
| Approved narration script | Gemini TTS | free tier may train on inputs | only the approved text |
| Storyboard prompts (no private details) | Gemini text, Workers AI | | the director warns first |
| Private photos (`refs/private/`) | only providers with `accepts_private_media: true`: Cloudflare Workers AI (hosted), local FLUX (a repo clone runs local) | Cloudflare states Workers AI inputs are not used for training | never Gemini free tier; never committed. **Decision (Tahir, 2026-11-25):** uploading photos to Cloudflare is accepted. Every upload path (frontend and CLI) must show a warning before the first private photo is sent: the photo goes to Cloudflare, only people who consented may appear, and it is not stored in the repo. |
| Generated keyframes | Kaggle (dataset), HF Spaces (fallback) | | |
<!-- TODO(agent, M1/M3): complete once providers are wired. -->

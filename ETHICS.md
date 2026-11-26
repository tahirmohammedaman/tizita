# Ethics: consent, licences, labelling, privacy

## Consent

Every real person shown or voiced needs an entry in `ethics/consents.yaml` **before** anything of them is generated. Validation enforces this: a `real_person: true` reference without a consent whose scope includes `likeness` is a hard error. Evidence files stay private; only their SHA-256 is committed.

Summary of `ethics/consents.yaml`. The entries were recorded from Tahir's report; the evidence (one
screenshot of the family group chat covering all six) is private and only its SHA-256 is committed.

| ID | Person / relation | Scope | Recorded on | Method | Words approved |
|---|---|---|---|---|---|
| C-001 | older brother 1 | story, likeness | 2026-11-26 | written (family group chat) | yes |
| C-002 | older brother 2 | story, likeness | 2026-11-26 | written (family group chat) | yes |
| C-003 | older sister 1 | story, likeness | 2026-11-26 | written (family group chat) | yes |
| C-004 | older sister 2 | story, likeness | 2026-11-26 | written (family group chat) | yes |
| C-005 | mother | story, likeness | 2026-11-26 | written (family group chat) | yes |
| C-006 | father | story, likeness | 2026-11-26 | written (family group chat) | yes |

- The narrator is the author.
- **No real person is shown or voiced.** All six references are fictional, text-only painterly
  characters or objects (`real_person: false`), no photo was used, and the narration is a stock
  synthetic voice, not a clone.
- The story mentions young nephews and nieces. The child on screen is a fictional character.
  <!-- TODO(Tahir): say whether the children's parents agreed to the story mentioning them. -->

## Licences (every model and output)

"Checked" means the licence field of the model card (Hugging Face API) or the provider's terms page
was read on **26 Nov 2026**. It is a reading of the declared licence, not legal advice. Hosted
services also apply their own terms of use.

### Used in the shipped film

| Component | Output in the film | Licence (as declared) | How checked |
|---|---|---|---|
| FLUX.2 klein 4B (on Workers AI) | references, keyframes | Apache-2.0 | card `black-forest-labs/FLUX.2-klein-4B` |
| ACE-Step v1 3.5B (via the `victor/ace-step-jam` Space) | score | model Apache-2.0; Space code MIT | card `ACE-Step/ACE-Step-v1-3.5B`; Space card |
| Gemini TTS (`gemini-3.8-flash-tts`, unpaid tier) | narration | Gemini API Additional Terms (effective 23 Mar 2026): Google does not claim ownership of generated content; the user is responsible for its use | [terms](https://ai.google.dev/gemini-api/terms) |
| Gemini text (3.5 Flash, Flash-Lite) | draft script and Amharic | same terms | same |
| Noto Sans, Noto Sans Ethiopic | subtitles, end card | OFL-1.1 | licence files in `assets/fonts/` |
| FFmpeg (libx264, libass) | all assembly | GPL/LGPL tool; applies to the software, not to the films | not re-checked |

### Used in development or as fallbacks (nothing of theirs is in the final film)

| Component | Use | Licence (as declared) |
|---|---|---|
| MMS-TTS `facebook/mms-tts-amh` | TTS fallback; spoke 8 lines in one superseded run | **CC-BY-NC-4.0: non-commercial.** Check `assemble.json` credits before any commercial use |
| FLUX.1 schnell | one smoke-test image | Apache-2.0 |
| `gpt-oss-120b` (Workers AI) | text fallback during drafting | Apache-2.0 |
| CLIP ViT-B/32 (`timm` mirror of OpenAI weights) | keyframe similarity | Apache-2.0 on the `timm` card |
| DINOv2-small | keyframe similarity | Apache-2.0 |
| Whisper large-v3-turbo | vocals check on the score | MIT |

Not used, listed because the plan named them: Wan 2.2 TI2V-5B (card: Apache-2.0), ACE-Step 1.5
(card: MIT), MusicGen and LTX-Video (not checked).

## Labelling plan

- **In the film:** an end card with "Made with AI", an Amharic line, "Narration voice, images and
  music: AI-generated", and the models actually used (read from the manifest).
- **When posting:** switch on the platform's AI-content label and say in the post that voice,
  pictures and music are AI-generated.
  <!-- TODO(Tahir): which platform(s), and confirm the label was switched on. -->
- **Provenance marks:** no step is designed to remove watermarks or provenance metadata, and
  generated takes, images and score files are kept as received. Assembly does re-encode audio and
  video, and the FFmpeg commands do not set any metadata options. **Whether SynthID or C2PA marks
  survive into the MP4 was not verified.**

## Privacy data flow

What actually left the machine for this film:

| Data | Went to | Provider terms (read 26 Nov 2026) |
|---|---|---|
| Story brief (`interview/answers.yaml`: first-person family story, family roles, no names or photos) and storyboard drafts | Gemini API unpaid tier; Workers AI as fallback | Gemini unpaid: Google **uses submitted content and responses to improve its products and ML, human reviewers may read them**, and its terms say not to submit sensitive or personal information |
| Amharic narration lines | Gemini TTS, unpaid tier | same |
| Image prompts and the fictional reference images | Cloudflare Workers AI | [Data usage](https://developers.cloudflare.com/workers-ai/platform/data-usage/): no training on customer content; zero data retention for standard inference, with listed exceptions |
| Score caption and tags (no family details by design) | a community Hugging Face Space (`victor/ace-step-jam`) | the Space owner's code receives the request; its handling was not audited |
| Generated score audio | Cloudflare Whisper | as Cloudflare above |

**An honest caveat:** the story brief is personal, even without names, and it went to a tier that may
train on it. The family consented to the story being told; <!-- TODO(Tahir): were they told that the
text would go to a free AI service that may train on it? -->

**Private photos:** none were used. The design for them: `refs/private/` is gitignored, and the router
never sends those files to a provider with `accepts_private_media: false` (every Gemini free-tier
entry). Cloudflare Workers AI is allowed (Tahir's decision, 2026-11-25), with a `privacy_notice`
warning before the first upload. The photo upload path has not been exercised, and the web upload
page that should show the same warning is not built. A fully local image provider is not built
either, so today any photo-based keyframe would go to Cloudflare.

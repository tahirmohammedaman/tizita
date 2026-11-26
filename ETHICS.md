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
  The children's parents agreed to the story mentioning them. We talked about it while I was
  brainstorming the idea, and again with the whole family; they then saw the radio cut and the
  near-final cut, gave their consent and commented on them.

## Licences (every model and output)

"Checked" means the licence field of the model card (Hugging Face API) or the provider's terms page
was read on **26 Nov 2026**. It is a reading of the declared licence, not legal advice. Hosted
services also apply their own terms of use.

### Used in the shipped film

| Component | Output in the film | Licence (as declared) | How checked |
|---|---|---|---|
| FLUX.2 klein 4B (on Workers AI) | references; keyframes s07, s09, s10 | Apache-2.0 | card `black-forest-labs/FLUX.2-klein-4B` |
| FLUX.2 klein 4B edit (on WaveSpeed, paid) | keyframes s01–s06, s08, s11 | model Apache-2.0 (upstream card); WaveSpeed's model page names no licence and says commercial rights "depend on the model's license" | [model page](https://wavespeed.ai/models/wavespeed-ai/flux-2-klein-4b/edit); ToS below |
| Wan 2.2 i2v 480p/720p ultra-fast (on WaveSpeed, paid) | motion for all 11 shots | not stated by WaveSpeed (same wording as above), and which upstream Wan 2.2 checkpoint it runs is not stated; the Wan 2.2 TI2V-5B card we checked is Apache-2.0 | [model page](https://wavespeed.ai/models/wavespeed-ai/wan-2.2/i2v-480p-ultra-fast); ToS below |
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

**WaveSpeed terms** ([ToS](https://wavespeed.ai/terms-of-service), last updated 1 Nov 2026;
[acceptable use](https://wavespeed.ai/static/acceptable-use), 28 Sep 2026): the customer owns
inputs and outputs (11.1); WaveSpeed takes a licence only "to the extent necessary to provide the
Output and associated Services" (11.2); it does not warrant that outputs are copyrightable or
unique (13.5). The customer warrants consent from "every identifiable person whose image, likeness,
or voice appears in its Inputs" (12.2); deepfakes of real people without consent are prohibited
(8.3), as is misleading people into believing outputs are human-made (8.3). No general AI-label
requirement. Our inputs were the generated, fictional reference sheets and keyframes, not photos of
real people. The ToS sections after 14 were not read in full.

Not used, listed because the plan named them: Wan 2.2 TI2V-5B (card: Apache-2.0), ACE-Step 1.5
(card: MIT), MusicGen and LTX-Video (not checked).

## Labelling plan

- **In the film:** an end card with "Made with AI", an Amharic line, "Narration voice, images and
  music: AI-generated", and the models actually used (read from the manifest).
- **When posting:** switch on the platform's AI-content label and say in the post that voice,
  pictures and music are AI-generated.
  Platform: **YouTube**, with its AI-generated (altered or synthetic) content label switched on.
  Posted 26 Nov 2026 (vertical cut): <https://www.youtube.com/shorts/NuHwauQU1EY>. The label was
  switched on after publishing; Tahir confirmed that it shows on the published video.
- **Provenance marks:** no step is designed to remove watermarks or provenance metadata, and
  generated takes, images and score files are kept as received. **The 11 Gemini narration WAVs
  carry a C2PA chunk** (checked 26 Nov; the adapter now keeps Gemini's WAV byte for byte, FAILURES
  F-10). The WaveSpeed frames and clips carry no C2PA marker. Assembly re-encodes audio and video
  and does not copy the C2PA chunk, so **the final MP4s carry no C2PA manifest, and we do not claim
  one**; whether an inaudible SynthID watermark survives the mix was not tested. The AI label is the
  end card and the post.

## Privacy data flow

What actually left the machine for this film:

| Data | Went to | Provider terms (read 26 Nov 2026) |
|---|---|---|
| Story brief (`interview/answers.yaml`: first-person family story, family roles, no names or photos) and storyboard drafts | Gemini API unpaid tier; Workers AI as fallback | Gemini unpaid: Google **uses submitted content and responses to improve its products and ML, human reviewers may read them**, and its terms say not to submit sensitive or personal information |
| Amharic narration lines | Gemini TTS, unpaid tier | same |
| Image prompts and the fictional reference images | Cloudflare Workers AI | [Data usage](https://developers.cloudflare.com/workers-ai/platform/data-usage/): no training on customer content; zero data retention for standard inference, with listed exceptions |
| Score caption and tags (no family details by design) | a community Hugging Face Space (`victor/ace-step-jam`) | the Space owner's code receives the request; its handling was not audited |
| Generated score audio | Cloudflare Whisper | as Cloudflare above |
| Benchmark audio and five story lines in four languages (EXP-14) | Gemini (unpaid tier); Whisper on Cloudflare | as above |
| Image and motion prompts, the generated reference sheets and keyframes (no photos) | WaveSpeed (paid, 26 Nov) | [Privacy](https://wavespeed.ai/privacy-policy) (25 Sep 2026): kept "as long as necessary to provide our Services", no set period for uploads; no explicit promise either way on training with inputs or outputs; the ToS licence covers providing the service only. Third-party model hosts are involved and their retention is not stated |
| Image prompt for one frame | a Hugging Face ZeroGPU Space (`hf_flux`) | the call failed on quota (F-16); the Space owner's code would have received it |

**An honest caveat:** the story brief is personal, even without names, and it went to a tier that may
train on it. The family consented to the story being told, and I told them the text and pictures would go
through online AI services. That is why we used no photos: only the storyboard and our characters'
descriptions went to the providers, and no photo was used as a reference.

**Private photos:** none were used. The design for them: `refs/private/` is gitignored, and the router
never sends those files to a provider with `accepts_private_media: false` (every Gemini free-tier
entry). Cloudflare Workers AI is allowed (Tahir's decision, 2026-11-25), with a `privacy_notice`
warning before the first upload. The photo upload path has not been exercised, and the web upload
page that should show the same warning is not built. A fully local image provider is not built
either, so today any photo-based keyframe would go to Cloudflare.

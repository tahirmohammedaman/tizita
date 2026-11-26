# Tizita: The Seat in the Front

Tahir Mohammedaman · 10 Academy / Tenacious TRP2, Week 0 · 26 Nov 2026

Film: 78.8 s, Amharic narration with English subtitles, 9:16 and 16:9.
Repository: https://github.com/tahirmohammedaman/tizita

## 1. What I set out to make, and for whom

I wanted to tell a small, true story from my own life: growing up as the youngest of five, always
sitting in the back seat watching the others drive, then nervously learning to drive myself, and
now being the one everyone calls when they need a ride. I chose it because it is simple and it
feels like me.

The audience is my family and friends first, then the course reviewers. They watch on phones, so
the master is vertical (9:16). At the end they should feel quiet pride and warmth: the kid in the
back seat became the one everyone can count on. I narrated in Amharic, my native language, with
English subtitles, so the film speaks to my family in their language and still reads for reviewers.

The film is built by Tizita, a pipeline I designed around one storyboard file. Every shot, line,
seed and prompt lives in `storyboard.json`; a cache works out what an edit changes, so editing
one narration line costs one TTS call and a local rebuild, and a clean clone rebuilds the whole film
with no model calls.

## 2. What my audience said, and what changed

**Test 1, the radio cut (25–26 Nov).** I shared the storyboard and a voice-and-music-only cut in our
family group chat: my two older brothers, two older sisters and both parents. Everyone agreed to the
story being told, liked the idea and wanted to see the film. They asked for more of the story and for
more natural Amharic. Because of that I added three beats (driving my sisters home at night, taking
my parents on errands by day, the little ones on my lap holding the wheel), dropped a weaker line,
and rewrote the Amharic with Gemini plus my own edits. The change is visible in
`git diff d483076 004855b -- storyboard.json` (10 shots to 11).

**Test 2, the near-final cut (26 Nov, ~14:00).** My sisters, my parents and a friend watched the
full film on their phones. They liked the warmth and nostalgia, especially the last scene with my
little nephew, and asked for seven concrete fixes (DESIGN.md, Test 2):

- s04's line "My hands gripped the wheel so tight" became my real memory: "The first time Dad let me
  drive, I was so nervous. The car kept stalling."
- In the errands shot Dad was in the driver's seat. Now I drive, Dad sits beside me, Mum in the back.
- Dad looked too Asian. I made a new father reference with explicitly Ethiopian features.
- Shot 1 did not show me in the back seat, although the line says so; shots 1 and 2 had to show me
  at the same age; shot 2 should show me curious while my brother drives; shot 3 should be my first
  day driving with Dad beside me. All were redrawn.

One sister wished the voice sounded more like me. I kept the AI voice, mainly for time and cost,
and because voice-cloning tools are not very good with Amharic. My friend asked for real motion instead of still pictures with camera
moves, so I animated all 11 shots with Wan 2.2. Three native Amharic listeners later said the Achird
voice was really good; one found it a bit machine-like but fine, especially the later takes, and one
again said it would be nicer in my own voice (EXPERIMENTS EXP-08).

**What I learned.** First, pictures unlock feedback. The radio cut drew general comments (more
story, more natural Amharic); the near-final film drew seven concrete fixes. Next
time I would show rough frames much earlier instead of waiting for a polished cut. Second, my
family sees what the model misses. The image model's defaults did not know my family: Dad came out
looking Asian, and seats and ages were wrong. Only people who know the real story caught that, so
the prompts now spell out ethnicity, who sits where and how old everyone is. Third, a voice is
personal. A good synthetic voice was accepted, but two listeners still wished it sounded like me;
a personal story wants the teller's own voice.

## 3. The hardest problem, and how I solved it

Three things were hardest.

**The TTS quota ran out mid-run.** Gemini's free TTS quota ended at shot s04
(`r_20261126_070255_0908`). The router did what it was built to do and fell back to a local voice,
so 8 of 11 lines came out in a different voice, about 30% slower (EXP-09). A voice change mid-film
was unacceptable. The fix: rotate across several API keys on a quota error, and put a
`previous_take` provider (the last approved take of that line) ahead of the local voice, so the voice
never changes mid-film. The final narration is 11 of 11 Gemini (`r_20261126_072953_685c`;
FAILURES F-02).

**Working out what to build.** Before any code I had to decide what the pipeline was: one
storyboard file as the contract, cached stages, a provider router with free-tier fallbacks, logging,
and the rules the coding agent works by. Writing the first `SPEC.md` and `CLAUDE.md` took the most
thought, and everything after was built from them.

**The local pipeline did not work out.** My first plan ran the models on my own machine. That
meant around 120 GB of weights, and most models needed about 32 GB of RAM plus CPU offloading. I
dropped it and moved to hosted providers: free tiers first (Gemini, Cloudflare Workers AI, a Hugging
Face Space for music), then, when the free image allowance and ZeroGPU runs ran out on the last day
(F-16), a paid API (WaveSpeed) for the redrawn frames and the Wan animation, about $0.96 in total
(COSTS.md).

A smaller problem taught me the most about checking causes: a hiss and click on every narration take.
We first trimmed it at assembly; the real cause was our own adapter wrapping Gemini's WAV file in a
second WAV header, so the player read the header and the C2PA provenance block as sound (F-10).

## 4. A suggested practice that beat my instinct

**A JSON contract between stages.** My instinct was separate scripts for each step, with outputs
edited by hand. Everything the film needs lives in `storyboard.json`,
and each stage's cache key hashes only the fields it reads. Editing one narration line rebuilds
exactly that line's chain: in the walkthrough rehearsal one changed Amharic line cost one TTS call
and `make film` took 60 s (`r_20261126_120740_b6ca`). A clean clone rebuilds the whole film with
0 model calls (`make clean-clone-test`). The same contract let me add the family's seven changes
as storyboard edits and rebuild only what they touched.

## 5. A suggested practice that did not work for me

**A reference sheet before keyframes.** I still think it is a good practice in general, but it did
not work in my implementation. I generated a reference sheet for every character before any
keyframe and fed it to FLUX.2 klein as a reference image. Two things went wrong:

- The family still said Dad looked too Asian. The sheet gave the model one father to copy, but
  not the features that mattered to the people who know him. I had to remake the father reference with
  explicitly Ethiopian features, and the scene prompts also needed exact head counts and who sits
  where (EXP-15), which a reference sheet does not give you.
- The automatic check built on the sheet never worked. The planned CLIP similarity gate (0.75
  between keyframe and reference) failed 19 of 19 attempts, including frames I had approved by eye,
  because a full scene scores about 0.55 against a head-and-shoulders portrait (F-08, EXP-06). I
  lowered it to 0.5 as a coarse tripwire and judged identity by eye.

In the end, identity was held by people looking at the frames, not by the sheet.

## 6. Ceiling work

**More languages: how far does Gemini TTS go in Amharic, Afaan Oromo, Tigrinya and Somali, and who
can check it?** I generated five story lines per language with the same voice and scored each take by
transcribing it and comparing with the text (character error rate), using two transcribers
(experiments/tts_benchmark/REPORT.md, EXP-14).

- The judge mattered as much as the voice. On identical Amharic audio, Gemini's transcriber scored a
  median CER of 0.19 and Whisper 1.33; on one file Gemini scored 0.00 and Whisper 1.33 by writing the
  right sounds in Latin letters. With one transcriber I would have concluded the opposite.
- My first explanation for Whisper's failures (the noise burst at the end of each take) was wrong:
  trimming it changed nothing (1.333 → 1.375).
- Whisper does not support Oromo or Tigrinya at all, and 3 of 5 Tigrinya lines contained
  non-Ethiopic letters from the translation step, so those languages remain unverified.
- Three native Amharic listeners rated the Amharic narration (section 2); nobody has rated the other
  three languages yet.

The lesson: an automatic score in a low-resource language measures the scorer as well as the
thing scored, so report it with its transcriber and get a native listener.

**A tool for others.** The pipeline is a CLI (`tizita new | plan | run`, `make film`): someone can
answer a short story brief, get a draft storyboard, and build their own film on free tiers.

## 7. What I would build next

- **A free GPU runner for Wan** (Kaggle or local), so the motion does not depend on a paid API. The
  adapter and fallback slots already exist in the provider chain.
- **My own Amharic voice:** voice cloning or fine-tuning that works for Amharic, so the film sounds
  like me, the request that came up in both tests.
- **A web app for my family,** so a relative who does not code can tell their own story and get a
  film back. The `tizita new` interview and the storyboard contract are the backend for it.
- **Native ratings in Oromo, Tigrinya and Somali,** and a blind test of Wan motion against Ken Burns
  with at least five people, to turn the ceiling work into real evidence.

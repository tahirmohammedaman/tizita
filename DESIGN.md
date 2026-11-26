# Design

## Audience and intent (written **before** any generation)

- **Written at:** 2026-11-25 18:42 EAT, before any image call (filled in by the agent at Tahir's instruction; values from interview/answers.yaml)
- **Who will watch:** family and friends, then the course reviewers
- **Where they'll watch:** phones, vertical (9x16)
- **What they should feel or understand at the end:** quiet pride and warmth: the kid in the back seat became the one everyone can count on
- **Logline:** <!-- TODO(Tahir) -->

## Story source

Tahir's own story, told in first person as the youngest of five siblings (two older brothers, two older sisters). Details in Tahir's words (2026-11-26): he now drives his sisters home at night, drives his older parents and runs errands, and lets his small nephews and nieces sit on his lap and hold the wheel. All characters are fictional painterly stand-ins; no photos are used.
<!-- TODO(Tahir): how you spoke with your family about the film, and what they asked you to keep or leave out. -->

## Test 1: radio cut (tag `test1-radio-cut`)

| # | Who (relation to the audience) | When / how | What they said | What I'll change |
|---|---|---|---|---|
| 1 | Whole family: 4 older siblings + both parents (6 people) | Family group chat. Shared the storyboard and the v1 radio cut on the evening of 2026-11-25; everyone replied yes around 09:00 EAT on 2026-11-26, then saw the rewritten Amharic text and liked it | Reported by Tahir: everyone liked the idea and is excited to see the final video. Their comments asked for more parts in the story and for more natural Amharic. (Paraphrase by Tahir; no verbatim quotes recorded.) | Added the sisters/parents/nephews shots (now 11 shots); rewrote the Amharic with Gemini and hand edits (Tahir approved) |
| 2 | <!-- TODO(Tahir) --> | | | |
| 3 | <!-- TODO(Tahir) --> | | | |

**Storyboard changes:** `git diff d483076 004855b -- storyboard.json`

`d483076` (25 Nov 18:42) is the first real storyboard (10 shots); `004855b` (26 Nov 09:57) is the
revision after the family's replies (11 shots). Visible in the diff: the line "Listening to my family
laugh and talk." is gone; three beats are added ("I drive my sisters home at night.", "By day, I take
my parents on their errands.", "The little ones sit on my lap and hold the wheel."); references for
the father and a child are added; the Amharic is rewritten. (The tag `radio-cut-v1` marks the earlier
pipeline build with a placeholder storyboard, so a diff from that tag does not show feedback changes.)
<!-- TODO(Tahir): confirm that d483076 is the version your family saw. -->

## Test 2: near-final cut (tag `test2-near-final`)

Viewers on 26 Nov 2026: two sisters, both parents and a friend. The family watched the final cut of
that time (with the AI end card) on their own phones through the family group chat, around 14:00 EAT.
Feedback is paraphrased; no verbatim quotes were recorded. The first notes (14:15) covered only part
of it. The picture and line requests below were made at the same time, but I left them out of those
first notes and added them later.

| # | Who | What they said (paraphrased) |
|---|---|---|
| 1 | Sister 1 | Really liked the warm nostalgia and family feeling, especially the last scene with the little nephew. Asked for changes 1, 2, 3, 4 and 6 below. |
| 2 | Sister 2 | Liked the nostalgia and the generated pictures. The voice-over could be a little more realistic, for example closer to my own voice. Asked for changes 3, 4, 5, 6 and 7. |
| 3 | Mum | Asked for changes 1, 2, 3 and 7. |
| 4 | Dad | Asked for changes 1, 2 and 7. |
| 5 | A friend (more technical) | It would be nice if some or all frames were animated like real video, not only Ken Burns stills. Found the pipeline idea really interesting. I told him animation is planned if there is time. |

| Change | Request | Asked by (and my own view) | What is changing |
|---|---|---|---|
| 1 | Replace "My hands gripped the wheel so tight" with a line that shows how nervous I was learning to drive | Sister 1, mum, dad, me | s04: new Amharic and English from my memory of Dad first letting me drive and the car stalling; new frame |
| 2 | In the errands shot, Dad is in the driver's seat; he shouldn't be | Sister 1, mum, dad, me | s08: I drive, Dad in the front passenger seat, Mum in the back |
| 3 | Dad looks too Asian | Both sisters, mum | New father reference with explicitly Ethiopian features |
| 4 | Shot 1 doesn't show me sitting in the back seat, although the line says so | Both sisters, me | s01: new frame inside the car, in the back seat |
| 5 | In shot 2, show child me excited, attentive and curious while someone else drives | Sister 2 | s02: child me leaning forward, watching my older brother drive in daytime |
| 6 | Shots 1 and 2 should show me as a child of the same age | Both sisters | One reference of me at about 7, used in s01 and s02 |
| 7 | Shot 3 should show my first day driving | Mum, dad, sister 2 | s03 and s04: me at about 15 with Dad beside me, a quiet cobblestone neighbourhood road |

**Status:** nothing had changed when the tag was made. Changes 1 to 7 were then rendered on 26 Nov
(afternoon): new father, child and teenage references; new frames for s01–s06, s08 and s11
(FLUX.2 klein 4B edit on WaveSpeed, because the free image allowance had run out, FAILURES F-16);
a new s04 line in Amharic and English (Gemini TTS). The final film is
`outputs/final/f1eb451f1815c80d/` (78.8 s, QA pass).
**The two other requests:**
- **Voice closer to mine:** I kept the AI voice, mainly because of time and cost. There are AI tools
  that clone voices well, but they are not very good with Amharic, so my choice of narrating in my
  native language also limits this.
- **Animation:** I decided to do Wan animation for this submission. All 11 shots are now animated
  with Wan 2.2 image-to-video (WaveSpeed, 480p; s03 at 720p). After watching the result I had s05
  and s08 redone with new seeds and compared old and new side by side; I kept both new ones.

## Shot reasons

Copied from `storyboard.json` (lint enforces a reason on every shot).

| Shot | Subtitle | Reason |
|---|---|---|
| s01 | I always sat in the back seat growing up. | Establishes the narrator's early life perspective always watching from the back seat. |
| s02 | Watching my older siblings take the wheel. | Focuses on the art of driving as seen through an observant younger child's eyes. |
| s03 | Then came the day I sat in the driver's seat. | The turning point: the first day in the driver's seat, with Dad beside him. |
| s04 | The first time Dad let me drive, I was so nervous. The car kept stalling. | The first drive with Dad: nerves and a car that keeps stalling, with Dad patiently beside him. |
| s05 | Checking the mirror over and over. | Still on the first drive: the nervous teenager checks the mirror again and again, learning to be careful. |
| s06 | Now my phone lights up, day or night. | The present day: even resting in bed, the narrator's phone lights up because the family relies on him. |
| s07 | I drive my sisters home at night. | Night pickups: the sisters' ride home, shown as headlights and dark road (no faces needed). |
| s08 | By day, I take my parents on their errands. | Daytime counterpart to the night rides: the narrator now drives his ageing parents on errands. |
| s09 | The little ones sit on my lap and hold the wheel. | The warmest beat: a small nephew or niece on the narrator's lap holding the wheel, the new generation in the seat he once watched from. |
| s10 | The little kid from the back seat... | Depicts the emotional payoff of helping loved ones and earning their trust. |
| s11 | ...is the one who brings everyone home. | Closing image: everyone has been brought home safely, and the narrator watches them go in. |

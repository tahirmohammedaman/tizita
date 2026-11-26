# Design

> Written by Tahir. The agent created this skeleton only; it never fills in test notes or quotes.

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

| # | Who | When / how | What they said | What changed |
|---|---|---|---|---|
| 1 | <!-- TODO(Tahir) --> | | | |
| 2 | <!-- TODO(Tahir) --> | | | |
| 3 | <!-- TODO(Tahir) --> | | | |

**Storyboard changes:** <!-- TODO(Tahir) -->

## Shot reasons

Copied from `storyboard.json` (lint enforces a reason on every shot).

| Shot | Subtitle | Reason |
|---|---|---|
| s01 | I always sat in the back seat growing up. | Establishes the narrator's early life perspective always watching from the back seat. |
| s02 | Watching my older siblings take the wheel. | Focuses on the art of driving as seen through an observant younger child's eyes. |
| s03 | Then came the day I sat in the driver's seat. | Marks the narrative turning point where narrator steps into the driver's seat. |
| s04 | My hands gripped the wheel so tight. | Highlights the vulnerability and physical tension of learning to drive. |
| s05 | Checking the mirror over and over. | Shows growing self-awareness and careful responsibility behind the wheel. |
| s06 | Now my phone lights up, day or night. | Signals the present day transition where the family relies on the narrator. |
| s07 | I drive my sisters home at night. | Night pickups: the sisters' ride home, shown as headlights and dark road (no faces needed). |
| s08 | By day, I take my parents on their errands. | Daytime counterpart to the night rides: the narrator now drives his ageing parents on errands. |
| s09 | The little ones sit on my lap and hold the wheel. | The warmest beat: a small nephew or niece on the narrator's lap holding the wheel, the new generation in the seat he once watched from. |
| s10 | The quiet kid from the back seat... | Depicts the emotional payoff of helping loved ones and earning their trust. |
| s11 | ...is the one who brings everyone home. | Concludes on full resolution of personal transformation and familial pride. |

# CLAUDE.md — rules for the coding agent

Project: **Tizita**. A storyboard-driven AI short-film pipeline for the 10 Academy / Tenacious TRP2 Week 0 challenge. Deadline Thu 26 Nov 2026 23:59 EAT.

## Start of every session
1. Read this file, then `docs/PROGRESS.md`.
2. Read **only the SPEC.md sections for the current milestone** (the "Read" column of the §18 table, or what the handoff prompt lists). Don't reread the whole spec or the challenge PDF unless asked. M0 is the exception: it reads all of SPEC once.
3. If the prompt names a model or effort that doesn't match the current session, mention it in one line and continue.
4. Say in one or two lines what you'll do, then do it.

## The owner is on Claude Pro, so save tokens
- **Never** `cat`, `Read` or print media files, `runs.jsonl`, `logs/*.jsonl`, `outputs/manifest.json`, lockfiles, or model weights. Use `tail -n 20`, `wc -l`, `jq` filters, or `head -c 2000`.
- Pipe long command output to a log file and show only the tail: `cmd > logs/tmp_x.log 2>&1; tail -n 30 logs/tmp_x.log`. FFmpeg always runs with `-hide_banner -loglevel error` (or `-stats` to a log file).
- `pip`, `uv`, `npm` and download output goes to log files, with progress checked by `tail`.
- Don't explore the repo with broad `find` or `ls -R`. You know the layout from SPEC §4.
- Prefer targeted edits over rewriting whole files.
- Batch related changes. Run tests once per meaningful change set, not after every line.
- Ask Tahir only when a decision is irreversible or costs GPU quota beyond the plan. Otherwise pick the spec's default and note it in PROGRESS.md.

## Engineering rules
- Python 3.11, `uv`, Typer, `rich`, `pydantic` v2, `jsonschema`, `httpx`. Ruff for lint/format. Pytest.
- Heavy ML imports are lazy (inside functions) so the base install, CI and `tizita validate/plan` work without a GPU.
- All prompts, seeds and parameters come from `storyboard.json` / `config/*.yaml`, never hard-coded.
- Every model call goes through the provider router and writes one `runs.jsonl` line (SPEC §8). No direct SDK calls from stages.
- Atomic writes for artifacts (write to tmp, then rename).
- Secrets only come from `.env` / the environment. Never print them, log them or commit them. Keep `.env.example` current.
- FFmpeg filtergraphs are built by pure functions in `tizita/ffmpeg/` with unit tests. H.264 exports use `-preset veryfast -crf 18`.
- Frontend: every input/textarea has `spellCheck={false}`.
- Commit small and often with clear messages. End commit messages (and PR descriptions) with the attribution trailer your environment specifies, if any.

## Git workflow (branch → PR → merge with `gh`)
- **Never commit to `main` directly.** The only exception is the single bootstrap commit in M0 (README stub + .gitignore + SPEC.md + CLAUDE.md + the challenge PDF), so that `main` exists.
- **One branch per main feature**, cut from an up-to-date `main` (`git switch main && git pull && git switch -c <branch>`). A milestone can have several features (M7 = `feat/api`, `feat/worker`, `feat/frontend-tester-pages`, …). Naming: `feat/…`, `fix/…`, `chore/…`, `docs/…`, `exp/…` (experiments), `ci/…`.
- Small commits on the branch. Push with `git push -u origin <branch>`.
- Open the PR with `gh pr create --base main --title "<type>: <summary>" --body-file <tmpfile>`. The body has: **What** (3–6 bullets), **Why** (the SPEC § it implements), **Evidence** (the commands run and their key output, e.g. test counts, `tizita plan` excerpt, run_ids), **Follow-ups / TODO(Tahir)**.
- Wait for CI with `gh pr checks --watch`. If it's red, fix it on the same branch. Never merge red.
- Merge with `gh pr merge --merge --delete-branch`. Use merge commits, **not squash**, so the granular commit history stays visible to graders. Then `git switch main && git pull`.
- Tags (`radio-cut-v1`, `test1-radio-cut`, `test2-near-final`) go on `main` after the relevant merge: `git tag <name> && git push origin <name>`.
- Generated artifacts (`outputs/`, `runs.jsonl`, `logs/events.jsonl`) are committed on the branch whose work produced them. Branches are sequential (merge before starting the next one) so `runs.jsonl` never conflicts; if it does, resolve by keeping all lines from both sides in timestamp order.
- Tahir may commit his human-written docs (DESIGN notes, consents summary) on a `docs/…` branch the same way, or ask you to open the PR for him.

## Honesty rules (graded and checked in an interview)
- **Never fabricate** user-test notes, consent records, native-speaker ratings, A/B votes, observed free-tier limits, or the owner's reflections. Leave `<!-- TODO(Tahir): … -->` markers.
- EXPERIMENTS.md results must come from real runs and cite `run_id`s. If an experiment hasn't run, mark it `planned`.
- When a tool or model named in the brief has moved, been renamed or fails, record what you found in `docs/PROGRESS.md` and append a draft to `logs/failures_auto.jsonl`.
- Don't strip AI provenance metadata (SynthID/C2PA) from generated files.
- Private photos (`refs/private/`) never go to Gemini or any provider with `accepts_private_media: false`.

## GPU and quota discipline
- Before launching any Kaggle batch or long local GPU job: run `tizita plan`, show the dirty units and the estimated GPU minutes, and confirm with Tahir unless it's the planned M4 overnight batch.
- Never download optional local weights (SPEC §19) or install the `gpu` extra unless Tahir asks.
- Never call a paid provider unless the active profile allows it, `allow_paid` is set and a budget exists (SPEC §7.2).
- Draft at 480p. Use a maximum of 3 attempts per unit before the fallback.
- Long jobs run under `nohup` or `tmux` with logs, so they survive the session.

## End of every milestone
1. `make test` green (and `make lint`).
2. Commit, push the branch, open the PR, wait for CI, merge (Git workflow above). If the milestone produced several features, each has its own PR.
3. Update `docs/PROGRESS.md`: done / next / gotchas / open `TODO(Tahir)` items / any model ids discovered. If reality has diverged from SPEC §18 (behind schedule, a model moved, a quota is smaller than expected), re-plan the remaining milestones there, keeping the SPEC §1 priority order and the cut lines.
4. Tell Tahir in 3–5 lines what to check manually, including any SPEC §18.1 checkpoint that is now due.
5. **Write the handoff prompt for the next milestone** and output it as the last thing in your reply, in a single fenced code block he can paste after `/clear`. Also save it under `## Next session prompt` in `docs/PROGRESS.md` (replace the previous one). The prompt must be self-contained for a fresh session and include:
   - The first line: `Model: <Opus|Sonnet> · Effort: <high|medium|low>` (from SPEC §18, adjusted if this session showed the next one is harder or easier than planned, with a one-clause reason).
   - "Read CLAUDE.md, docs/PROGRESS.md, then SPEC §…" (only the sections needed).
   - The milestone goal and concrete scope, updated with what you learned: real model ids, provider quirks, failed approaches to avoid, files and functions that already exist and should be reused, and decisions Tahir made this session.
   - Pre-conditions Tahir must finish first (a choice, an approval, keys, a test), if any.
   - Acceptance checks, as commands to run and what output proves success.
   - Where the session must stop and wait for Tahir (GPU spend, golden pick, secrets).
   - Keep it under ~40 lines. Point to files instead of pasting their contents.

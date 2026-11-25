# Architecture

<!-- Skeleton (M0). Filled in M1–M5, finished and reviewed in M9. Source of truth: SPEC.md §4–§10. -->

## Stage graph

<!-- TODO(agent, M1): Mermaid diagram of narration → timing → radio_cut; references → keyframes → shots; music; subtitles; assemble → qa. -->

## The contract: `storyboard.json`

<!-- TODO(agent, M1): schema location, semantic lint rules, what each stage reads. -->

## Caching

<!-- TODO(agent, M1): cache-key design (stage, stage_version, fields, upstream hashes, provider, seed), manifest, and a real `tizita plan` excerpt showing one dirty unit. -->

## Providers, fallback chains and errors

<!-- TODO(agent, M1): profiles, tiers, chains per capability, error taxonomy, circuit breaker, paid guard, privacy routing. Mark untested adapters honestly. -->

## GPU executors

<!-- TODO(agent, M4): runner.py job model, Local / Kaggle / Worker executors, measured T4 vs 4060 decision. -->

## Assembly

<!-- TODO(agent, M5): timing slots, conform rules, ducking, loudnorm, subtitles, 16:9 pillarbox, graceful degradation. -->

## Failure handling

<!-- TODO(agent, M5): what happens when each stage fails, and how a rough cut always renders. -->

## Local pipeline vs showcase

<!-- TODO(agent, M8): the graded pipeline never depends on the VPS, Worker or frontend. -->

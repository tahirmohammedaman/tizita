"""music: `music.candidates` candidates through the music chain (SPEC §9.4). The human pick is
`tizita choose music N --reason ...`. With the free chain and no Kaggle run this lands on the
deterministic synth pad; each candidate then uses a different chord from `pad_variants`."""

from __future__ import annotations

from tizita.cache import provider_ident
from tizita.dag import manifest_path_for
from tizita.providers.base import Request
from tizita.stages import Ctx, Outcome
from tizita.stages.images import generate
from tizita.storyboard import load_config

HEADROOM_S = 10.0  # longer than the film so the pad's own fade-out is never reached


def run(ctx: Ctx, unit, key: str) -> Outcome:
    music = ctx.sb["music"]
    variants = load_config(ctx.project, "assembly").get("pad_variants") or [{}]
    base = manifest_path_for(ctx.project, unit, key, "x").with_suffix("")
    paths, ident, any_fb, primary, calls = [], None, False, None, 0
    for i in range(int(music["candidates"])):
        existing = sorted(base.parent.glob(f"{key}_cand{i + 1}.*"))
        if existing:
            paths.append(existing[0])
            continue
        v = variants[i % len(variants)]
        req = Request(
            capability="music",
            stage="music",
            unit=unit.unit,
            prompt=music["caption"],
            params={
                "duration_s": float(music["duration_s"]) + HEADROOM_S,
                "bpm": music["bpm"],
                "key": music["key"],
                "instrumental": music["instrumental"],
                "freqs": v.get("freqs"),
                "variant": v.get("name"),
                "format": "flac",
            },
            seed=int(music["seed"]) + i,
            cache_key=key,
        )
        path, (prov, result), fb, primary = generate(ctx, req, base.with_name(f"{key}_cand{i + 1}"))
        ident = provider_ident(prov.name, result.model, prov.params)
        any_fb = any_fb or fb
        paths.append(path)
        calls += 1
    if ident is None:
        prev = ctx.manifest.get("music", unit.unit)
        ident = prev.provider if prev else None
    return Outcome(paths[0], ident, any_fb, primary, calls=calls, candidates=paths)

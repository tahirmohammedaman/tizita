"""narration: one TTS call per shot (SPEC §6.1). Seed = style.seed_base + shot index (MMS)."""

from __future__ import annotations

from tizita.cache import provider_ident
from tizita.dag import manifest_path_for
from tizita.providers.base import Request
from tizita.stages import Ctx, Outcome


def run(ctx: Ctx, unit, key: str) -> Outcome:
    shot = next(s for s in ctx.sb["shots"] if s["id"] == unit.unit)
    voice = ctx.sb["voice"]
    prev = ctx.manifest.get("narration", unit.unit)
    req = Request(
        capability="tts",
        stage="narration",
        unit=unit.unit,
        prompt=shot["narration"]["text_am"],
        seed=unit.seed,
        inputs={
            "voice": voice["voice_name"],
            "style_instruction": voice["style_instruction"],
            "previous_path": str(ctx.project.root / prev.path) if prev else None,
        },
        cache_key=key,
        output_path=manifest_path_for(ctx.project, unit, key, "wav"),
    )
    result, prov, is_fb = ctx.router.call(req)
    primary = (ctx.router.chain_ids("tts") or [prov.name])[0]
    return Outcome(
        result.output_path,
        provider_ident(prov.name, result.model, prov.params),
        is_fb,
        primary,
        calls=1,
    )

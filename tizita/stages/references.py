"""references: N candidate sheets per reference (SPEC §11.2). The human pick is
`tizita choose reference <ref> <N>`; candidate paths are all recorded in the manifest."""

from __future__ import annotations

from tizita.cache import provider_ident
from tizita.dag import manifest_path_for
from tizita.providers.base import Request
from tizita.stages import Ctx, Outcome
from tizita.stages.images import character_for_ref, contact_sheet, generate, is_private

SIZE = {"width": 512, "height": 512}  # klein draft size verified in M1; refs need no 9:16


def ref_prompt(sb: dict, ref: dict) -> str:
    st = sb["style"]
    ch = character_for_ref(sb, ref["id"])
    if ref["kind"] == "person":
        who = f"{ref['description']} {ch.get('wardrobe', '')}".strip()
        return (
            f"Character reference portrait, waist-up, facing the camera, plain neutral "
            f"background, even soft light. {who} {st['character_defaults']}. {st['style_block']}"
        )
    return (
        f"Reference image, no people, no text: {ref['description']} "
        f"Plain composition showing the details clearly. {st['style_block']}"
    )


def run(ctx: Ctx, unit, key: str) -> Outcome:
    ref = next(r for r in ctx.sb["references"] if r["id"] == unit.unit)
    n = ref["sheet"]["candidates"]
    photos = [str(ctx.project.root / p) for p in ref.get("photos", [])]
    private = any(is_private(ctx.project.root, p) for p in ref.get("photos", []))
    base = manifest_path_for(ctx.project, unit, key, "x").with_suffix("")
    paths, prov_info, any_fb, primary, calls = [], None, False, None, 0
    for i in range(n):
        existing = sorted(base.parent.glob(f"{key}_cand{i + 1}.*"))
        if existing:  # resume an interrupted run without re-spending quota
            paths.append(existing[0])
            continue
        req = Request(
            capability="image_edit" if photos else "image",
            stage="references",
            unit=unit.unit,
            prompt=ref_prompt(ctx.sb, ref),
            params=dict(SIZE),
            seed=unit.seed + i,
            inputs={"images": photos},
            private_media=private,
            references=[ref],
            cache_key=key,
        )
        path, prov_info, fb, primary = generate(ctx, req, base.with_name(f"{key}_cand{i + 1}"))
        any_fb = any_fb or fb
        paths.append(path)
        calls += 1
    contact_sheet(
        paths, base.with_name(f"{key}_sheet.jpg"), [f"{ref['id']} #{i + 1}" for i in range(n)]
    )
    if prov_info is None:  # all candidates were already on disk
        prev = ctx.manifest.get("references", unit.unit)
        ident = prev.provider if prev else None
    else:
        prov, result = prov_info
        ident = provider_ident(prov.name, result.model, prov.params)
    return Outcome(paths[0], ident, any_fb, primary, calls=calls, candidates=paths)

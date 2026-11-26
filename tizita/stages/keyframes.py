"""keyframes: one image per shot (SPEC §11.2). Conditioned on the golden reference(s) via
klein's input_image_0..3; CLIP/DINO gate vs the golden person refs, up to 3 re-seeds, keep best.
Upload shots are repainted in the house style by the same path (image_edit)."""

from __future__ import annotations

from tizita.cache import provider_ident
from tizita.dag import manifest_path_for
from tizita.providers.base import Request
from tizita.stages import Ctx, Outcome
from tizita.stages.images import generate, is_private
from tizita.storyboard import load_config
from tizita.util import atomic_write_json

MAX_ATTEMPTS = 3
RESEED_STEP = 1000  # retry seed = seed + (n-1)*1000
DEFAULT_THRESHOLD = 0.75


def keyframe_prompt(sb: dict, shot: dict, ref_names: list[str]) -> str:
    st = sb["style"]
    kf = shot["keyframe"]
    parts = []
    people = []
    for c in shot.get("characters", []):
        ch = st["characters"].get(c, {})
        people.append(f"{ch.get('description', '')} Wearing: {ch.get('wardrobe', '')}".strip())
    if people:
        parts.append(" ".join(people) + f" {st['character_defaults']}.")
    if ref_names:
        parts.append(
            "Keep the people, vehicle and place identical to the provided reference images "
            f"({', '.join(ref_names)})."
        )
    if kf["source"] == "upload":
        parts.append("Repaint the first image in this painterly style, keeping its composition.")
    parts.append(kf["prompt"])
    parts.append(st["style_block"])
    return " ".join(p for p in parts if p)


def run(ctx: Ctx, unit, key: str) -> Outcome:
    sb, root = ctx.sb, ctx.project.root
    shot = next(s for s in sb["shots"] if s["id"] == unit.unit)
    kf = shot["keyframe"]
    refs = {r["id"]: r for r in sb["references"]}
    ref_paths, ref_names, person_refs = [], [], []
    for rid in shot.get("references", []):
        r = refs.get(rid)
        ent = ctx.manifest.get("references", rid)
        ch = r["sheet"].get("chosen") if r else None
        if ent is None or ch is None:
            continue
        p = root / ent.candidates[ch]["path"]
        ref_paths.append(str(p))
        ref_names.append(rid.removeprefix("ref_").replace("_", " "))
        if r["kind"] == "person":
            person_refs.append(p)
    images = list(ref_paths)
    private = False
    if kf["source"] == "upload":
        images.insert(0, str(root / kf["upload_path"]))
        private = is_private(root, kf["upload_path"])
    prompt = keyframe_prompt(sb, shot, ref_names)
    params = {"width": 576, "height": 1024}
    thr = float(
        load_config(ctx.project, "pipeline")
        .get("consistency", {})
        .get("threshold", DEFAULT_THRESHOLD)
    )
    base = manifest_path_for(ctx.project, unit, key, "x").with_suffix("")
    best = None
    attempts = []
    calls = 0
    for n in range(1, MAX_ATTEMPTS + 1):
        seed = unit.seed + (n - 1) * RESEED_STEP
        req = Request(
            capability="image_edit" if kf["source"] == "upload" else "image",
            stage="keyframes",
            unit=unit.unit,
            prompt=prompt,
            params=dict(params),
            seed=seed,
            inputs={"images": images[:4]},
            private_media=private,
            references=[refs[r] for r in shot.get("references", []) if r in refs],
            cache_key=key,
        )
        path, (prov, result), fb, primary = generate(ctx, req, base.with_name(f"{key}_try{n}"))
        calls += 1
        sims = None
        if person_refs:
            from tizita.stages.images import embed_sims

            sims = embed_sims(ctx, unit.unit, path, person_refs)
        score = None
        if sims:
            score = round(min([*sims.get("clip", [1]), 1]), 4)  # worst person ref, CLIP
        attempts.append(
            {"attempt": n, "seed": seed, "path": path.name, "sims": sims, "score": score}
        )
        cand = (score if score is not None else 1.0, n, path, prov, result, fb, primary)
        if best is None or cand[0] > best[0]:
            best = cand
        if score is None or score >= thr or fb:
            break
    _, n_best, path, prov, result, fb, primary = best
    final = base.with_suffix(path.suffix)
    path.replace(final)
    for a in attempts:  # drop the losing tries
        (final.parent / a["path"]).unlink(missing_ok=True)
    flagged = best[0] < thr if person_refs and attempts[0]["score"] is not None else False
    atomic_write_json(
        final.with_suffix(".json"),
        {
            "threshold": thr,
            "chosen_attempt": n_best,
            "below_threshold": flagged,
            "attempts": attempts,
        },
    )
    return Outcome(
        final,
        provider_ident(prov.name, result.model, prov.params),
        fb,
        primary,
        calls=calls,
    )

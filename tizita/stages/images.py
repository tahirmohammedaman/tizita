"""Shared helpers for the image stages: prompt assembly, contact sheets, embeddings."""

from __future__ import annotations

import json
from pathlib import Path

from tizita.providers.base import Request
from tizita.util import atomic_write_bytes


def character_for_ref(sb: dict, ref_id: str) -> dict:
    for ch in sb["style"].get("characters", {}).values():
        if ch.get("reference_id") == ref_id:
            return ch
    return {}


def is_private(project_root: Path, rel: str) -> bool:
    return "private" in Path(rel).parts


def generate(ctx, req: Request, base: Path) -> tuple[Path, object, bool, str]:
    """One router call; write `<base>.<ext>`; returns (path, (prov, result), fallback?, primary)."""
    result, prov, is_fb = ctx.router.call(req)
    primary = (
        ctx.router.chain_ids(req.capability, private_media=req.private_media) or [prov.name]
    )[0]
    path = base.with_suffix("." + result.ext)
    atomic_write_bytes(path, result.data)
    return path, (prov, result), is_fb, primary


def embed_sims(ctx, unit: str, query: Path, refs: list[Path]) -> dict | None:
    """CLIP + DINO cosine of `query` against each ref (None if the embed provider is unusable)."""
    if not refs:
        return None
    req = Request(
        capability="embed",
        stage="keyframes",
        unit=unit,
        inputs={"images": [str(query), *map(str, refs)]},
    )
    try:
        result, _prov, _ = ctx.router.call(req)
    except Exception as e:
        ctx.bus.emit("embed_failed", stage="keyframes", unit=unit, message=str(e)[:200])
        return None
    data = json.loads(result.data)
    out: dict = {}
    for name in ("clip_image", "dino_image"):
        v = data.get(name)
        if v:
            out[name.split("_")[0]] = [
                round(sum(a * b for a, b in zip(v[0], row, strict=True)), 4) for row in v[1:]
            ]
    return out


def contact_sheet(paths: list[Path], out: Path, labels: list[str] | None = None, cell=384) -> Path:
    """Numbered grid of images for the human pick (Tahir has no file access: sent as one file)."""
    from PIL import Image, ImageDraw

    cols = min(len(paths), 4) or 1
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB")
        im.thumbnail((cell, cell))
        x, y = (i % cols) * cell, (i // cols) * cell
        sheet.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
        d.rectangle((x, y, x + 150, y + 34), fill=(0, 0, 0))
        d.text((x + 8, y + 8), (labels[i] if labels else str(i + 1)), fill=(255, 255, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.jpg")
    sheet.save(tmp, quality=88)
    tmp.replace(out)
    return out

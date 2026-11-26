"""End card (SPEC §10.5): a Pillow PNG per ratio. Title, "Made with AI", the Amharic line in
Noto Sans Ethiopic, credits and the models actually used (read from the manifest)."""

from __future__ import annotations

from pathlib import Path

SIZES = {"9x16": (1080, 1920), "16x9": (1920, 1080)}
BG = (12, 12, 18)
FG = (238, 232, 220)
DIM = (170, 164, 152)


def short_model(model: str) -> str:
    """'org/name@rev' or 'name (space/owner)' -> 'name'. The host note goes first: it can hold
    a '/' of its own."""
    return model.split(" (")[0].split("/")[-1].split("@")[0]


def credit_name(model: str, names: dict[str, str] | None = None) -> str:
    """Display name for a recorded model id: the first `credit_names` substring that matches
    (case-insensitive), else the short id."""
    low = model.lower()
    for key, label in (names or {}).items():
        if key.lower() in low:
            return label
    return short_model(model)


def models_used(manifest, credit_names: dict[str, str] | None = None) -> list[str]:
    """Short 'Role: model' lines from the provider idents recorded in the manifest."""
    roles = [
        ("narration", "Voice"),
        ("keyframes", "Images"),
        ("shots", "Motion"),
        ("music", "Music"),
    ]
    out = []
    for stage, label in roles:
        names = []
        for e in manifest.entries.values():
            if e.stage == stage and e.provider:
                m = e.provider.get("model") or e.provider.get("name")
                m = credit_name(str(m), credit_names)
                if m not in names:
                    names.append(m)
        if names:
            out.append(f"{label}: {', '.join(names[:2])}")
    return out


def render_card(sb: dict, models: list[str], layout: str, out: Path, fonts_dir: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    w, h = SIZES[layout]
    s = 1.0 if layout == "9x16" else 0.8
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    def font(name: str, px: float):
        return ImageFont.truetype(str(fonts_dir / name), round(px * s))

    ec = sb["end_card"]
    rows = [
        (sb["meta"]["title"], font("NotoSans-Bold.ttf", 76), FG, 40),
        (ec["text_am"], font("NotoSansEthiopic-Regular.ttf", 54), FG, 70),
        (ec["text_en"], font("NotoSans-Bold.ttf", 60), FG, 60),
        *[(c, font("NotoSans-Regular.ttf", 34), DIM, 16) for c in ec.get("credits", [])],
        ("", font("NotoSans-Regular.ttf", 20), DIM, 20),
        *[(m, font("NotoSans-Regular.ttf", 28), DIM, 12) for m in models],
    ]
    heights = [d.textbbox((0, 0), t or " ", font=f)[3] + gap * s for t, f, _, gap in rows]
    y = (h - sum(heights)) / 2
    for (text, f, color, _gap), rh in zip(rows, heights, strict=True):
        if text:
            tw = d.textlength(text, font=f)
            d.text(((w - tw) / 2, y), text, font=f, fill=color)
        y += rh
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".tmp.png")
    img.save(tmp)
    tmp.replace(out)
    return out

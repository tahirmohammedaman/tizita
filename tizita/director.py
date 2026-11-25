"""Director (SPEC §11.1): interview answers -> beat sheet from a text model -> full storyboard.

The model writes only the creative parts (a compact beat sheet). Everything mechanical (seeds,
approval flags, voice, house style, schema shape) is assembled here, then validated against the
storyboard JSON Schema and the semantic lint, with up to 2 repair rounds that feed the errors back.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tizita.providers.base import Request
from tizita.storyboard import lint
from tizita.util import Project, atomic_write_text, iso_ms

PRIVACY_WARNING = (
    "Do not share private family details: the free Gemini tier may use inputs to improve Google "
    "products. Use first names or relations at most, no addresses, no health or money details."
)

QUESTIONS = [
    ("whose_story", "Whose story is this (and does that person consent)?"),
    ("audience_and_where", "Who watches it, and where (phone, class, family)?"),
    ("final_feeling", "The one feeling they should have at the end?"),
    ("setting_era", "Setting and era?"),
    ("key_moments", "3-5 key moments, separated by ';'"),
    ("narration_voice", "Narration voice mood?"),
    ("music_mood", "Music mood?"),
    ("photos", "Photos available? If a real person appears, say so (consent is checked later)."),
]

HOUSE_STYLE = {
    "style_block": (
        "warm painterly illustration, visible gouache and oil brush texture, soft golden-hour "
        "light, gentle film grain, muted earthy palette with warm ochres and deep greens, "
        "cinematic composition, subject centred for vertical framing"
    ),
    "character_defaults": (
        "Ethiopian, warm brown skin tones, natural features, everyday contemporary clothing"
    ),
    "negative": (
        "text, letters, watermark, logo, extra fingers, deformed hands, pale skin, "
        "western stock-photo look"
    ),
    "seed_base": 1000,
}

SYSTEM = """You are the director of a 60-90 second vertical AI short film told in Amharic.
Reply with ONE JSON object, no prose, no code fences. Rules:
- Write EVERYTHING in English (title, logline, audience, intent, reason, descriptions, prompts)
  except narration.text_am and end_card.text_am, which are Amharic (Ge'ez script).
- Tell the story the answers give, in order: back seat -> learning to drive -> everyone calls me.
- 10 shots (8-12). Each shot duration_s 6-8 (the sum plus a 3 s end card must land in 62-85 s).
- narration.text_am: first-person Amharic, MAX 11 words per shot, simple spoken Amharic, ends with
  the Ethiopic full stop. narration.text_en: faithful English subtitle, MAX 70 characters.
- keyframe_prompt: ONLY subject + composition + light (the house style is appended automatically).
  Mostly interiors of a car: back seat, rear-view mirror, side mirror, dashboard, headlights, quiet
  roads, a phone lighting up. No text, no signs, no readable writing in the image.
- motion: "i2v" for at most 4 hero shots (motion_prompt = camera/motion only, slow), else
  "kenburns" (pan: none|left|right|up|down, zoom 1.0 -> 1.08..1.15).
- shot_size one of extreme_wide|wide|medium|medium_close|close|extreme_close|insert.
- transition_in one of cut|crossfade|fade_black (first shot: fade_black).
- characters: fictional painterly people (never real_person). Give each a short visual description
  and wardrobe. A character id is lowercase snake_case; the narrator is the youngest sibling.
- references: one per recurring character (kind person) and at most one place/object.
- Every shot has a `reason` (>= 12 chars) saying what it does for the story.
- music_cues: 2-3 cues {id, at_s, intent}; each shot names one cue id in music_cue.
JSON shape:
{"title","logline","audience","intent",
 "characters":{"id":{"description","wardrobe"}},
 "references":[{"id","kind","description"}],
 "music":{"caption","bpm","key","cues":[{"id","at_s","intent"}]},
 "shots":[{"id","reason","shot_size","duration_s","characters":[ids],"references":[ids],
   "keyframe_prompt","motion":"i2v|kenburns","motion_prompt","pan","zoom_to",
   "text_am","text_en","music_cue","transition_in"}],
 "end_card":{"text_am","credits":[...]}}"""


def load_answers(path: Path) -> dict[str, Any]:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def ask_interactively(prompt_fn) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, q in QUESTIONS:
        ans = prompt_fn(q)
        out[key] = [a.strip() for a in ans.split(";") if a.strip()] if key == "key_moments" else ans
    return out


def build_prompt(answers: dict[str, Any], feedback: list[str] | None = None) -> str:
    lines = ["Interview answers:"]
    for key, _ in QUESTIONS:
        v = answers.get(key)
        if isinstance(v, list):
            v = "; ".join(f"({i}) {x}" for i, x in enumerate(v, 1))
        lines.append(f"- {key}: {str(v).strip()}")
    if feedback:
        lines.append(
            "\nYour previous attempt failed validation. Fix exactly these and resend the JSON:"
        )
        lines += [f"- {m}" for m in feedback]
    return "\n".join(lines)


def parse_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a:
        raise ValueError("no JSON object in the model reply")
    return json.loads(t[a : b + 1])


def _ref_for(cid: str, refs: list[dict]) -> str | None:
    """`youngest_sibling` -> `ref_youngest`: a reference whose stem is inside the character id."""
    for r in refs:
        stem = r["id"].removeprefix("ref_")
        if r["kind"] == "person" and (stem == cid or stem in cid or cid in stem):
            return r["id"]
    return None


def ensure_character_refs(sb: dict) -> dict:
    """Every character gets a person reference (text-only, fictional) so keyframes can condition
    on one golden sheet per character; shots that use the character list that reference too."""
    base = sb["style"]["seed_base"]
    refs = sb["references"]
    ids = {r["id"] for r in refs}
    for cid, ch in sb["style"]["characters"].items():
        rid = ch.get("reference_id") or f"ref_{cid}"
        if rid not in ids:
            refs.append(
                {
                    "id": rid,
                    "kind": "person",
                    "real_person": False,
                    "consent_id": None,
                    "photos": [],
                    "description": ch["description"],
                    "sheet": {
                        "candidates": 4,
                        "chosen": None,
                        "seed": base + 100 * (len(refs) + 1),
                    },
                }
            )
            ids.add(rid)
        ch["reference_id"] = rid
    mine = {c["reference_id"] for c in sb["style"]["characters"].values()}
    # person references the model invented on top of the character ones are duplicates: drop them
    sb["references"] = [r for r in refs if r["kind"] != "person" or r["id"] in mine]
    keep = {r["id"] for r in sb["references"]}
    for shot in sb["shots"]:
        shot["references"] = [r for r in shot["references"] if r in keep]
        for cid in shot["characters"]:
            rid = sb["style"]["characters"][cid]["reference_id"]
            if rid not in shot["references"]:
                shot["references"].append(rid)
    return sb


def assemble(beats: dict, sb_defaults: dict | None = None) -> dict:
    """Beat sheet -> a schema-shaped storyboard. Seeds follow the fixture convention."""
    base = HOUSE_STYLE["seed_base"]
    shots = beats["shots"]
    refs = []
    for i, r in enumerate(beats.get("references", [])):
        refs.append(
            {
                "id": r["id"],
                "kind": r.get("kind", "person"),
                "real_person": False,
                "consent_id": None,
                "photos": [],
                "description": r["description"],
                "sheet": {"candidates": 4, "chosen": None, "seed": base + 100 + i * 100},
            }
        )
    out_shots = []
    for i, s in enumerate(shots, 1):
        i2v = s.get("motion") == "i2v"
        out_shots.append(
            {
                "id": f"s{i:02d}",
                "reason": s["reason"],
                "shot_size": s["shot_size"],
                "duration_s": float(s["duration_s"]),
                "characters": list(s.get("characters", [])),
                "references": list(s.get("references", [])),
                "keyframe": {
                    "source": "generate",
                    "upload_path": None,
                    "prompt": s["keyframe_prompt"],
                    "seed": base + i,
                    "candidates": 1,
                    "approved": False,
                },
                "motion": {
                    "mode": "i2v" if i2v else "kenburns",
                    "prompt": s.get("motion_prompt") or "slow push in, soft light drifts",
                    "seed": base + 1000 + i,
                    "max_attempts": 3,
                    "kenburns": {
                        "zoom_from": 1.0,
                        "zoom_to": float(s.get("zoom_to") or 1.1),
                        "pan": s.get("pan")
                        if s.get("pan") in ("none", "left", "right", "up", "down")
                        else "none",
                    },
                    "approved": False,
                },
                "narration": {"text_am": s["text_am"], "text_en": s["text_en"]},
                "music_cue": s["music_cue"],
                "transition_in": s["transition_in"] if i > 1 else "fade_black",
            }
        )
    total = sum(s["duration_s"] for s in out_shots) + 3
    music = beats["music"]
    chars = {
        cid: {
            "description": c["description"],
            "wardrobe": c.get("wardrobe"),
            "reference_id": _ref_for(cid, refs),
        }
        for cid, c in beats.get("characters", {}).items()
    }
    em = beats["end_card"]
    return ensure_character_refs(
        {
            "version": 1,
            "meta": {
                "title": beats["title"],
                "logline": beats["logline"],
                "narration_language": "am",
                "subtitle_language": "en",
                "target_duration_s": round(total),
                "audience": beats["audience"],
                "intent": beats["intent"],
            },
            "style": {**HOUSE_STYLE, "characters": chars},
            "references": refs,
            "voice": {
                "provider_pref": "gemini_tts",
                "voice_name": "Kore",
                "style_instruction": "warm, quiet, a little shy, like telling a story to a friend",
                "pace_wps_limit": 2.3,
            },
            "music": {
                "caption": music["caption"],
                "bpm": int(music["bpm"]),
                "key": music["key"],
                "duration_s": round(total),
                "instrumental": True,
                "candidates": 3,
                "seed": base + 2000,
                "chosen": None,
                "chosen_reason": None,
                "cues": music["cues"],
            },
            "shots": out_shots,
            "end_card": {
                "text_en": "Made with AI",
                "text_am": em["text_am"],
                "credits": ["Story and narration: TODO(Tahir) your name"],
                "duration_s": 3,
            },
        }
    )


def draft(router, project: Project, answers: dict[str, Any], rounds: int = 3):
    """Returns (storyboard, lint report, provider used). Raises ValueError if it never validates."""
    feedback: list[str] | None = None
    last = None
    for attempt in range(rounds):
        req = Request(
            capability="text",
            stage="director",
            unit="project",
            prompt=build_prompt(answers, feedback),
            inputs={"system": SYSTEM},
            params={
                "response_mime_type": "application/json",
                "max_tokens": 12000,
                "temperature": 0.8,
            },
            seed=HOUSE_STYLE["seed_base"] + attempt * 1000,
        )
        result, prov, _ = router.call(req)
        try:
            sb = assemble(parse_json(result.text or ""))
        except (ValueError, KeyError, TypeError) as e:
            feedback = [f"could not assemble: {type(e).__name__}: {e}"]
            continue
        report = lint(sb, project, registry={})
        last = (sb, report, prov)
        if report.ok:
            return last
        feedback = [f"{i.path}: {i.message}" for i in report.errors][:12]
    if last is None:
        raise ValueError(f"director failed: {feedback}")
    return last


def save_draft(project: Project, sb: dict) -> Path:
    path = project.root / "storyboard.draft.json"
    atomic_write_text(path, json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
    return path


def promote(project: Project) -> tuple[bool, list[str]]:
    """storyboard.draft.json -> storyboard.json if it lints clean. Backs the old one up."""
    draft_path = project.root / "storyboard.draft.json"
    sb = json.loads(draft_path.read_text(encoding="utf-8"))
    report = lint(sb, project)
    if not report.ok:
        return False, [f"{i.path}: {i.message}" for i in report.errors]
    if project.storyboard.exists():
        backup = project.state / "backup" / f"storyboard_{iso_ms().replace(':', '')}.json"
        atomic_write_text(backup, project.storyboard.read_text(encoding="utf-8"))
    atomic_write_text(project.storyboard, draft_path.read_text(encoding="utf-8"))
    return True, []

"""`tizita smoke`: one real call per configured provider (SPEC §20), plus model-id discovery.

Every call goes through the router (`call_one`), so each writes a runs.jsonl line. Outputs land in
.state/smoke/ (gitignored); nothing here is a film artifact.
"""

from __future__ import annotations

from dataclasses import dataclass

from tizita.providers.base import Request
from tizita.providers.errors import ProviderError
from tizita.providers.router import Router

ORDER = ["text", "tts", "image", "embed", "asr"]
SMOKE_TEXT_AM = "ሰላም፣ ይህ የሙከራ ድምፅ ነው።"
SMOKE_IMAGE_PROMPT = (
    "smoke test: a small clay jebena coffee pot on a low wooden stool, warm painterly "
    "illustration, soft golden light"
)


@dataclass
class SmokeRow:
    provider: str
    capability: str
    model: str
    status: str  # ok | error:<kind> | skipped
    latency_ms: int | None = None
    detail: str = ""


def _request(cap: str, pid: str, router: Router, made: dict) -> Request | None:
    out = router.project.state / "smoke"
    base = {"stage": "smoke", "unit": pid}
    if cap == "text":
        return Request(
            "text",
            prompt="Reply with exactly the word OK.",
            params={"max_tokens": 256, "temperature": 0},
            seed=1,
            output_path=out / f"{pid}.txt",
            **base,
        )
    if cap == "tts":
        return Request(
            "tts",
            prompt=SMOKE_TEXT_AM,
            seed=1,
            inputs={"voice": "Kore", "style_instruction": "Say warmly and slowly"},
            output_path=out / f"{pid}.wav",
            **base,
        )
    if cap == "image":
        return Request(
            "image",
            prompt=SMOKE_IMAGE_PROMPT,
            seed=1,
            params={"width": 512, "height": 512, "steps": 4},
            output_path=out / f"{pid}.img",
            **base,
        )
    if cap == "embed":
        img = made.get("image")
        if img is None:
            from PIL import Image

            img = out / "solid.png"
            img.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (224, 224), (180, 120, 60)).save(img)
        return Request(
            "embed",
            inputs={"images": [img, img], "texts": ["a clay coffee pot", "a city skyline"]},
            output_path=out / f"{pid}.json",
            **base,
        )
    if cap == "asr":
        audio = made.get("tts")
        if audio is None:
            return None
        return Request("asr", inputs={"audio": audio}, output_path=out / f"{pid}.txt", **base)
    return None


def run_smoke(router: Router, only: set[str] | None = None) -> list[SmokeRow]:
    rows: list[SmokeRow] = []
    made: dict = {}
    reg = router.registry
    for cap in ORDER:
        for pid in reg.chains.get(cap, []):
            p = reg.get(pid)
            if only and pid not in only:
                continue
            if not p.cfg.get("adapter"):
                continue  # not built yet: listed by `tizita providers`
            ok, reason, hint = router.usable(pid)
            if not ok:
                rows.append(
                    SmokeRow(
                        pid, cap, p.model, "skipped", None, reason + (f" → {hint}" if hint else "")
                    )
                )
                continue
            req = _request(cap, pid, router, made)
            if req is None:
                rows.append(SmokeRow(pid, cap, p.model, "skipped", None, "no input available"))
                continue
            try:
                res = router.call_one(pid, req)
            except ProviderError as e:
                rows.append(SmokeRow(pid, cap, p.model, f"error:{e.kind}", None, e.message[:160]))
                continue
            path = res.output_path
            made.setdefault(cap, path)
            detail = (res.text or "").strip()[:60] if res.text else str(res.metrics)[:120]
            last_latency = (router.runlog.last or {}).get("latency_ms")
            rows.append(SmokeRow(pid, cap, res.model, "ok", last_latency, detail))
    return rows


# ---------------------------------------------------------------- discovery


def discover(router: Router) -> list[dict]:
    """Check configured model ids against the providers' own catalogues."""
    findings: list[dict] = []
    reg = router.registry
    env = next(iter(reg.providers.values())).env if reg.providers else {}
    gem = [
        p
        for p in reg.providers.values()
        if (p.cfg.get("adapter") or "").startswith("gemini") and env.get(p.cfg["env"][0])
    ]
    if gem:
        try:
            from tizita.providers.gemini_text import gemini_client

            names = sorted(
                m.name.removeprefix("models/")
                for m in gemini_client(env, gem[0].cfg["env"][0]).models.list()
            )
        except Exception as e:  # discovery must never break the smoke run
            findings.append({"provider": "gemini", "status": "error", "message": str(e)[:200]})
        else:
            for p in gem:
                found = p.model in names
                findings.append(
                    {
                        "provider": p.name,
                        "model": p.model,
                        "status": "ok" if found else "moved",
                        "candidates": [n for n in names if _related(n, p.capability)][:12],
                    }
                )
    cf = [p for p in reg.providers.values() if p.cfg.get("adapter") == "cf_workers_ai"]
    if cf and env.get("CLOUDFLARE_API_TOKEN") and env.get("CLOUDFLARE_ACCOUNT_ID"):
        import httpx

        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{env['CLOUDFLARE_ACCOUNT_ID']}"
            "/ai/models/search"
        )
        names: set[str] = set()
        try:
            for page in range(1, 6):
                r = httpx.get(
                    url,
                    params={"per_page": 100, "page": page},
                    timeout=30,
                    headers={"Authorization": f"Bearer {env['CLOUDFLARE_API_TOKEN']}"},
                )
                res = r.json().get("result") or []
                names |= {m["name"] for m in res}
                if len(res) < 100:
                    break
        except Exception as e:
            findings.append({"provider": "cloudflare", "status": "error", "message": str(e)[:200]})
        else:
            for p in cf:
                findings.append(
                    {
                        "provider": p.name,
                        "model": p.model,
                        "status": "ok" if p.model in names else "moved",
                    }
                )
    for f in findings:
        if f["status"] == "moved":
            router.bus.emit(
                "provider_moved",
                provider=f["provider"],
                stage="smoke",
                unit=f["provider"],
                error_class="model_moved",
                message=f"{f['provider']}: model {f['model']!r} not in the provider catalogue; "
                f"candidates: {', '.join(f.get('candidates', [])[:6]) or 'see catalogue'}",
            )
    return findings


def _related(name: str, capability: str) -> bool:
    n = name.lower()
    if capability == "tts":
        return "tts" in n
    return "flash" in n and "tts" not in n and "image" not in n

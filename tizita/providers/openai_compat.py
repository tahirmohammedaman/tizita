"""OpenAI-compatible chat completions (Groq free tier, OpenRouter `:free` models)."""

from __future__ import annotations

import httpx

from tizita.providers.base import Provider, Request, Result
from tizita.providers.errors import Transient, classify_http


class OpenAICompat(Provider):
    def call(self, req: Request) -> Result:
        params = {**self.params, **req.params}
        key = self.env[self.cfg["env"][0]]
        messages = []
        if req.inputs.get("system"):
            messages.append({"role": "system", "content": req.inputs["system"]})
        messages.append({"role": "user", "content": req.prompt or ""})
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": int(params.get("max_tokens", 512)),
        }
        if params.get("temperature") is not None:
            payload["temperature"] = params["temperature"]
        if req.seed is not None:
            payload["seed"] = req.seed
        r = httpx.post(
            f"{self.cfg['base_url'].rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=90.0,
        )
        if r.status_code >= 400:
            raise classify_http(r.status_code, r.text[:600], r.headers.get("retry-after"))
        body = r.json()
        try:
            text = body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise Transient(f"unexpected response: {str(body)[:200]}") from e
        usage = body.get("usage") or {}
        return Result(
            model=body.get("model") or self.model,
            text=text,
            data=text.encode(),
            mime="text/plain",
            ext="txt",
            seed_used=req.seed,
            metrics={k: usage.get(k) for k in ("prompt_tokens", "completion_tokens")},
        )

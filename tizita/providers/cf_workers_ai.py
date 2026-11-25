"""Cloudflare Workers AI (REST `ai/run`): text, image (FLUX.2 klein via multipart, FLUX.1 schnell
via JSON) and ASR (Whisper). Free allowance is a daily neuron pool shared by every model."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from tizita.providers.base import Provider, Request, Result
from tizita.providers.errors import BadRequest, Transient, classify_http

API = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"


class CloudflareAI(Provider):
    timeout_s = 120.0

    def _url(self, model: str) -> str:
        return API.format(account=self.env["CLOUDFLARE_ACCOUNT_ID"], model=model)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.env['CLOUDFLARE_API_TOKEN']}"}

    def _post(self, model: str, **kw) -> dict:
        r = httpx.post(self._url(model), headers=self._headers(), timeout=self.timeout_s, **kw)
        if r.status_code >= 400:
            raise classify_http(r.status_code, r.text[:600], r.headers.get("retry-after"))
        try:
            body = r.json()
        except ValueError as e:
            raise Transient(f"non-JSON response ({r.headers.get('content-type')})") from e
        if body.get("success") is False:
            raise classify_http(400, str(body.get("errors"))[:600])
        return body.get("result") or {}

    def call(self, req: Request) -> Result:
        cap = "image" if req.capability == "image_edit" else req.capability
        if cap == "text":
            return self._text(req)
        if cap == "image":
            return self._image(req)
        if cap == "asr":
            return self._asr(req)
        raise BadRequest(f"cloudflare adapter does not do {req.capability}")

    # -- text --------------------------------------------------------
    def _text(self, req: Request) -> Result:
        params = {**self.params, **req.params}
        messages = []
        if req.inputs.get("system"):
            messages.append({"role": "system", "content": req.inputs["system"]})
        messages.append({"role": "user", "content": req.prompt or ""})
        payload = {"messages": messages, "max_tokens": int(params.get("max_tokens", 512))}
        if params.get("temperature") is not None:
            payload["temperature"] = params["temperature"]
        if req.seed is not None and self.cfg.get("supports_seed", True):
            payload["seed"] = req.seed
        res = self._post(self.model, json=payload)
        text = res.get("response")
        if text is None and res.get("choices"):
            text = res["choices"][0].get("message", {}).get("content")
        if not isinstance(text, str):
            raise Transient(f"unexpected text result keys: {sorted(res)[:8]}")
        usage = res.get("usage") or {}
        return Result(
            model=self.model,
            text=text,
            data=text.encode(),
            mime="text/plain",
            ext="txt",
            metrics={k: usage.get(k) for k in ("prompt_tokens", "completion_tokens") if k in usage},
            seed_used=payload.get("seed"),
        )

    # -- image -------------------------------------------------------
    def _image(self, req: Request) -> Result:
        params = {**self.params, **req.params}
        seed = req.seed if self.cfg.get("supports_seed", True) else None
        if self.cfg.get("input_format") == "multipart":
            fields: list[tuple[str, tuple]] = [("prompt", (None, req.prompt or ""))]
            for k in ("width", "height", "steps", "guidance"):
                if params.get(k) is not None:
                    fields.append((k, (None, str(params[k]))))
            if seed is not None:
                fields.append(("seed", (None, str(seed))))
            for i, img in enumerate(req.inputs.get("images", [])[:4]):
                p = Path(img)
                fields.append((f"input_image_{i}", (p.name, p.read_bytes(), "image/png")))
            res = self._post(self.model, files=fields)
        else:
            payload = {"prompt": req.prompt or ""}
            if params.get("steps") is not None:
                payload["steps"] = int(params["steps"])
            if seed is not None:
                payload["seed"] = seed
            res = self._post(self.model, json=payload)
        b64 = res.get("image")
        if not b64:
            raise Transient(f"no image in result (keys: {sorted(res)[:8]})")
        data = base64.b64decode(b64)
        ext = "jpg" if data[:3] == b"\xff\xd8\xff" else "png"
        used = {k: params[k] for k in ("width", "height", "steps") if k in params}
        if self.cfg.get("input_format") != "multipart":
            for k in ("width", "height"):
                used.pop(k, None)  # this model's schema takes no size
        return Result(
            model=self.model,
            data=data,
            mime=f"image/{'jpeg' if ext == 'jpg' else 'png'}",
            ext=ext,
            params_used=used,
            seed_used=seed,
            metrics={"bytes": len(data), "ref_images": len(req.inputs.get("images", []))},
        )

    # -- asr ---------------------------------------------------------
    def _asr(self, req: Request) -> Result:
        audio = Path(req.inputs["audio"]).read_bytes()
        payload = {"audio": base64.b64encode(audio).decode()}
        if req.params.get("language"):
            payload["language"] = req.params["language"]
        res = self._post(self.model, json=payload)
        text = res.get("text") or ""
        return Result(model=self.model, text=text, data=text.encode(), mime="text/plain", ext="txt")

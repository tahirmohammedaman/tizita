"""`wavespeed`: WaveSpeedAI REST (paid, prepaid credit). One adapter for FLUX.2 klein reference
editing (`image`) and Wan 2.2 image-to-video (`i2v`). Local files are uploaded first, then the
job is submitted and polled until it finishes."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from tizita.providers.base import Provider, Request, Result
from tizita.providers.errors import BadRequest, Transient, Unavailable, classify_http

API = "https://api.wavespeed.ai/api/v3"
POLL_S = 3.0


class WaveSpeed(Provider):
    timeout_s = 600.0

    def _json(self, r: httpx.Response) -> dict:
        if r.status_code >= 400:
            raise classify_http(r.status_code, r.text[:600], r.headers.get("retry-after"))
        return r.json().get("data") or {}

    def _upload(self, client: httpx.Client, path: str) -> str:
        p = Path(path)
        data = self._json(
            client.post(f"{API}/media/upload/binary", files={"file": (p.name, p.read_bytes())})
        )
        if not data.get("download_url"):
            raise Transient("wavespeed upload returned no url")
        return data["download_url"]

    def payload(self, req: Request, urls: list[str]) -> dict:
        p = {**self.params, **{k: v for k, v in req.params.items() if v is not None}}
        body: dict = {"prompt": req.prompt or ""}
        if req.seed is not None:
            body["seed"] = int(req.seed)
        if self.capability == "i2v":
            body["image"] = urls[0]
            body["duration"] = int(p.get("duration", 5))
            if p.get("negative_prompt"):
                body["negative_prompt"] = p["negative_prompt"]
        else:
            body["images"] = urls
            body["size"] = f"{int(p.get('width', 576))}*{int(p.get('height', 1024))}"
        return body

    def call(self, req: Request) -> Result:
        files = [str(i) for i in req.inputs.get("images", [])]
        limit = int(self.cfg.get("max_images", 1))
        if not req.prompt or not files:
            raise BadRequest("wavespeed needs a prompt and at least one input image")
        if len(files) > limit:
            raise BadRequest(f"wavespeed {self.model} takes at most {limit} images")
        headers = {"Authorization": f"Bearer {self.env['WAVESPEED_API_KEY']}"}
        t0 = time.time()
        with httpx.Client(headers=headers, timeout=60.0) as client:
            body = self.payload(req, [self._upload(client, f) for f in files])
            job = self._json(client.post(f"{API}/{self.model}", json=body))
            while job.get("status") != "completed":
                if job.get("status") == "failed":
                    raise Unavailable(f"wavespeed job failed: {str(job.get('error'))[:300]}")
                if time.time() - t0 > self.timeout_s or not job.get("id"):
                    # not Transient: a retry would submit (and bill) the job again
                    raise Unavailable(f"wavespeed job {job.get('id')} did not finish")
                time.sleep(POLL_S)
                try:
                    r = client.get(f"{API}/predictions/{job['id']}/result")
                except httpx.HTTPError:
                    continue
                if r.status_code >= 500:
                    continue
                job = self._json(r)
        out = (job.get("outputs") or [None])[0]
        if not out:
            raise Unavailable("wavespeed returned no output")
        data = httpx.get(out, timeout=120.0, follow_redirects=True).raise_for_status().content
        if self.capability == "i2v":
            ext, mime = "mp4", "video/mp4"
        elif data[:3] == b"\xff\xd8\xff":
            ext, mime = "jpg", "image/jpeg"
        else:
            ext, mime = "png", "image/png"
        return Result(
            model=self.model,
            data=data,
            mime=mime,
            ext=ext,
            params_used={k: v for k, v in body.items() if k not in ("prompt", "image", "images")},
            seed_used=body.get("seed"),
            metrics={
                "job_id": job.get("id"),
                "inference_ms": (job.get("timings") or {}).get("inference"),
                "latency_s": round(time.time() - t0, 1),
            },
        )

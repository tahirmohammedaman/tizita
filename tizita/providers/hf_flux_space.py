"""`hf_flux`: FLUX.2 klein on the official Hugging Face Space through `gradio_client` (free
ZeroGPU quota, authenticated with HF_TOKEN). Reference images condition the result. One call = one
image. Space id and endpoint come from `config/providers.yaml`."""

from __future__ import annotations

import io
import time
from pathlib import Path

from tizita.providers.base import Provider, Request, Result
from tizita.providers.errors import BadRequest, Unavailable
from tizita.providers.hf_ace_space import _classify

MAX_REFS = 4


class HFFluxSpace(Provider):
    def call(self, req: Request) -> Result:
        if not req.prompt:
            raise BadRequest("hf_flux needs a prompt")
        from gradio_client import Client, handle_file

        p = {**self.params, **{k: v for k, v in req.params.items() if v is not None}}
        seed = int(req.seed or 0)
        refs = [str(i) for i in req.inputs.get("images", [])[:MAX_REFS]]
        args = {
            "prompt": req.prompt,
            "input_images": [{"image": handle_file(r), "caption": None} for r in refs],
            "mode_choice": self.cfg.get("mode_choice", "Distilled (4 steps)"),
            "seed": seed,
            "randomize_seed": False,
            "width": int(p.get("width", 576)),
            "height": int(p.get("height", 1024)),
            "num_inference_steps": int(p.get("steps", 4)),
            "guidance_scale": float(p.get("guidance", 1.0)),
            "prompt_upsampling": False,
        }
        t0 = time.time()
        try:
            client = Client(self.cfg["space"], token=self.env.get("HF_TOKEN"), verbose=False)
            out = client.predict(**args, api_name=self.cfg.get("api_name", "/infer"))
        except Exception as e:  # gradio_client raises AppError / httpx errors / ValueError
            raise _classify(e) from e
        image = out[0] if isinstance(out, list | tuple) else out
        if isinstance(image, dict):
            image = image.get("path")
        if not image or not Path(image).is_file():
            raise Unavailable("hf space returned no image")
        from PIL import Image

        buf = io.BytesIO()
        with Image.open(image) as im:
            im.convert("RGB").save(buf, "PNG")
            size = im.size
        return Result(
            model=self.model,
            data=buf.getvalue(),
            mime="image/png",
            ext="png",
            params_used={"width": size[0], "height": size[1], "steps": args["num_inference_steps"]},
            seed_used=seed,
            metrics={"ref_images": len(refs), "space_latency_s": round(time.time() - t0, 1)},
        )

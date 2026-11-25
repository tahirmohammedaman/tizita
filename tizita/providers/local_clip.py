"""Consistency embeddings on CPU: CLIP ViT-B/32 (open_clip safetensors) + DINOv2-small.

`call` takes `inputs={"images": [paths], "texts": [str]}` and returns L2-normalised vectors as
JSON; `metrics` carries the pairwise CLIP image↔text and DINO image↔image cosine similarities.
"""

from __future__ import annotations

import json
from pathlib import Path

from tizita.providers.base import Availability, Provider, Request, Result
from tizita.providers.errors import BadRequest


class LocalClip(Provider):
    executor = "local"
    _clip = None
    _dino = None

    def available(self) -> Availability:
        av = super().available()
        if not av.ok:
            return av
        dino = self.models_dir / self.cfg.get("dino_weights", "dinov2-small")
        if not dino.exists():
            return Availability(
                False, "weights missing", "tizita models download --only dinov2-small"
            )
        import importlib.util as u

        missing = [m for m in ("torch", "open_clip", "transformers") if u.find_spec(m) is None]
        if missing:
            return Availability(
                False, f"python deps missing: {', '.join(missing)}", "uv sync --extra ml"
            )
        return av

    def _load_clip(self):
        if self._clip is None:
            import open_clip

            ckpt = self.weights_path() / "open_clip_model.safetensors"
            model, _, preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32-quickgelu", pretrained=str(ckpt)
            )
            type(self)._clip = (model.eval(), preprocess, open_clip.get_tokenizer("ViT-B-32"))
        return self._clip

    def _load_dino(self):
        if self._dino is None:
            from transformers import AutoImageProcessor, AutoModel
            from transformers.utils import logging as hf_logging

            hf_logging.disable_progress_bar()

            path = str(self.models_dir / self.cfg.get("dino_weights", "dinov2-small"))
            type(self)._dino = (
                AutoModel.from_pretrained(path).eval(),
                AutoImageProcessor.from_pretrained(path),
            )
        return self._dino

    def call(self, req: Request) -> Result:
        import torch
        from PIL import Image

        images = [Path(p) for p in req.inputs.get("images", [])]
        texts = list(req.inputs.get("texts", []))
        if not images and not texts:
            raise BadRequest("embed needs images and/or texts")
        out: dict = {}
        metrics: dict = {}
        with torch.no_grad():
            if images or texts:
                model, preprocess, tokenizer = self._load_clip()
            if images:
                pil = [Image.open(p).convert("RGB") for p in images]
                x = torch.stack([preprocess(im) for im in pil])
                ci = torch.nn.functional.normalize(model.encode_image(x), dim=-1)
                out["clip_image"] = ci.tolist()
                dmodel, proc = self._load_dino()
                d = dmodel(**proc(images=pil, return_tensors="pt")).last_hidden_state[:, 0]
                di = torch.nn.functional.normalize(d, dim=-1)
                out["dino_image"] = di.tolist()
                if len(images) > 1:
                    metrics["dino_sim_to_first"] = [round(float(v), 4) for v in (di @ di[0])]
            if texts:
                ct = torch.nn.functional.normalize(model.encode_text(tokenizer(texts)), dim=-1)
                out["clip_text"] = ct.tolist()
            if images and texts:
                metrics["clip_image_text"] = [
                    [round(float(v), 4) for v in row] for row in (ci @ ct.T)
                ]
        data = json.dumps(out).encode()
        return Result(
            model=self.model,
            data=data,
            text=None,
            mime="application/json",
            ext="json",
            metrics=metrics,
        )

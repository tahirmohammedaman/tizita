"""MMS-TTS Amharic (`facebook/mms-tts-amh`, CC-BY-NC-4.0) on CPU from $MODELS_DIR.

The checkpoint was trained on uroman-romanised text (tokenizer `is_uroman: true`), so Ethiopic
input is romanised with `uroman` first. Heavy imports stay inside functions.
"""

from __future__ import annotations

import io

from tizita.providers.base import Availability, Provider, Request, Result, wav_duration_s
from tizita.providers.errors import BadRequest


class MMSTTS(Provider):
    executor = "local"
    _model = None
    _tok = None
    _uroman = None

    def available(self) -> Availability:
        av = super().available()
        if not av.ok:
            return av
        try:
            import importlib.util as u

            missing = [m for m in ("torch", "transformers", "uroman") if u.find_spec(m) is None]
        except ValueError:
            missing = []
        if missing:
            return Availability(
                False, f"python deps missing: {', '.join(missing)}", "uv sync --extra ml"
            )
        return av

    def _load(self):
        if self._model is None:
            from transformers import AutoTokenizer, VitsModel
            from transformers.utils import logging as hf_logging

            hf_logging.disable_progress_bar()

            path = str(self.weights_path())
            type(self)._tok = AutoTokenizer.from_pretrained(path)
            type(self)._model = VitsModel.from_pretrained(path).eval()
        return self._model, self._tok

    def romanize(self, text: str) -> str:
        if self._uroman is None:
            import uroman

            type(self)._uroman = uroman.Uroman()
        return self._uroman.romanize_string(text)

    def call(self, req: Request) -> Result:
        import numpy as np
        import soundfile as sf
        import torch

        text = (req.prompt or "").strip()
        if not text:
            raise BadRequest("empty narration text")
        model, tok = self._load()
        roman = self.romanize(text)
        inputs = tok(roman, return_tensors="pt")
        if inputs["input_ids"].shape[-1] == 0:
            raise BadRequest("text has no characters the MMS vocabulary covers")
        if req.seed is not None:
            torch.manual_seed(req.seed)  # VITS duration/noise sampling is stochastic
        with torch.no_grad():
            wav = model(**inputs).waveform[0].cpu().numpy()
        rate = int(model.config.sampling_rate)
        buf = io.BytesIO()
        sf.write(buf, np.clip(wav, -1, 1), rate, format="WAV", subtype="PCM_16")
        data = buf.getvalue()
        return Result(
            model=self.model,
            data=data,
            mime="audio/wav",
            ext="wav",
            seed_used=req.seed,
            metrics={
                "duration_s": round(wav_duration_s(data), 3),
                "sample_rate": rate,
                "romanized_head": roman[:80],
            },
        )

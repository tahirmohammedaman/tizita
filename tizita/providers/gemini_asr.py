"""Gemini speech-to-text: one audio file in, a verbatim transcript out (Ceiling A round trip).
The reference text is never sent."""

from __future__ import annotations

from pathlib import Path

from tizita.providers.base import Provider, Request, Result
from tizita.providers.errors import BadRequest
from tizita.providers.gemini_text import call_rotating, check_blocked


class GeminiASR(Provider):
    def call(self, req: Request) -> Result:
        from google.genai import types

        audio = req.inputs.get("audio")
        if not audio or not req.prompt:
            raise BadRequest("gemini_asr needs inputs.audio and a transcription prompt")
        part = types.Part.from_bytes(data=Path(audio).read_bytes(), mime_type="audio/wav")
        cfg = types.GenerateContentConfig(temperature=0)
        resp = call_rotating(
            self,
            lambda c: c.models.generate_content(
                model=self.model, contents=[req.prompt, part], config=cfg
            ),
        )
        check_blocked(resp)
        text = (resp.text or "").strip()
        return Result(model=self.model, text=text, data=text.encode(), mime="text/plain", ext="txt")

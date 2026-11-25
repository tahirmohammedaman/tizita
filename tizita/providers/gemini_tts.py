"""Gemini TTS via google-genai. Returns 24 kHz mono 16-bit WAV. Only the approved narration text
is ever sent (SPEC §11.4)."""

from __future__ import annotations

from tizita.providers.base import Provider, Request, Result, pcm16_to_wav, wav_duration_s
from tizita.providers.errors import Transient
from tizita.providers.gemini_text import call_rotating, check_blocked

SAMPLE_RATE = 24000


class GeminiTTS(Provider):
    def call(self, req: Request) -> Result:
        from google.genai import types

        voice = req.inputs.get("voice") or self.params.get("voice_name", "Kore")
        style = req.inputs.get("style_instruction")
        # Measured 2026-11-25: with a style prefix the model reads (part of) the instruction aloud
        # (a 2.7 s line became 9-10 s). Default off; `style_mode: prefix` opts back in.
        prefixed = style and self.params.get("style_mode") == "prefix"
        contents = f"{style}: {req.prompt}" if prefixed else req.prompt
        cfg = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        )
        resp = call_rotating(
            self,
            lambda c: c.models.generate_content(model=self.model, contents=contents, config=cfg),
        )
        check_blocked(resp)
        try:
            pcm = resp.candidates[0].content.parts[0].inline_data.data
        except (AttributeError, IndexError, TypeError) as e:
            raise Transient("Gemini TTS returned no audio part") from e
        if not pcm:
            raise Transient("Gemini TTS returned empty audio")
        wav = pcm16_to_wav(pcm, SAMPLE_RATE)
        return Result(
            model=self.model,
            data=wav,
            mime="audio/wav",
            ext="wav",
            metrics={"duration_s": round(wav_duration_s(wav), 3), "sample_rate": SAMPLE_RATE},
            params_used={"voice": voice},
        )

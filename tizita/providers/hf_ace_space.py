"""`hf_ace_space`: ACE-Step 1.5 text-to-music on the official Hugging Face Space through
`gradio_client` (free ZeroGPU quota, authenticated with HF_TOKEN). One call = one track.

Space id, endpoint and model come from `config/providers.yaml`. Tempo and key go in their own
fields, not the caption (SPEC §9.4); instrumental = lyrics "[Instrumental]"."""

from __future__ import annotations

import time
from pathlib import Path

from tizita.providers.base import Provider, Request, Result
from tizita.providers.errors import BadRequest, QuotaExhausted, Transient, Unavailable


def _classify(e: Exception) -> Exception:
    msg = str(e)
    low = msg.lower()
    if "quota" in low or "exceeded" in low:
        return QuotaExhausted(f"hf space quota: {msg[:200]}")
    if "timeout" in low or "queue" in low or "too many" in low or "429" in low:
        return Transient(f"hf space busy: {msg[:200]}")
    return Unavailable(f"hf space error: {msg[:200]}")


class HFAceSpace(Provider):
    def call(self, req: Request) -> Result:
        p = {**self.params, **{k: v for k, v in req.params.items() if v is not None}}
        dur = float(p.get("duration_s") or 0)
        if dur <= 0 or not req.prompt:
            raise BadRequest("hf_ace_space needs a caption and params.duration_s")
        seed = req.seed if req.seed is not None else 0
        if self.cfg.get("flavor") in ("v1", "jam"):
            return self._call_v1(req, p, dur, seed)
        args = {
            "selected_model": self.model,
            "generation_mode": "custom",
            # inputs without defaults are required by the Space even when the mode ignores them
            "simple_query_input": req.prompt,
            "simple_vocal_language": "unknown",
            "param_4": req.prompt,
            "param_5": "[Instrumental]" if p.get("instrumental", True) else p.get("lyrics", ""),
            "param_6": float(p.get("bpm") or 0),
            "param_7": str(p.get("key") or ""),
            "param_8": str(p.get("time_signature") or "4"),
            "param_10": int(p.get("steps", 8)),
            "param_12": False,  # random seed off
            "param_13": str(seed),
            "param_14": None,  # reference audio
            "param_15": dur,
            "param_16": 1,  # batch size (the Space needs an int)
            "param_17": None,  # source audio (cover/repaint only)
            "param_18": "",  # audio codes
            "param_30": "flac",
            "param_47": None,  # stem track (lego mode only)
        }
        return self._predict(args, dur, seed, status_index=10)

    def _call_v1(self, req: Request, p: dict, dur: float, seed: int) -> Result:
        """ACE-Step v1 Space (`/__call__`): no tempo/key fields, so they go into the tags, the
        v1 convention ("..., 68 BPM, G major")."""
        tags = ", ".join(
            x for x in [req.prompt.rstrip("."), f"{p['bpm']} BPM" if p.get("bpm") else "",
                        str(p.get("key") or ""), "instrumental, no vocals"
                        if p.get("instrumental", True) else ""] if x
        )  # fmt: skip
        lyrics = "[instrumental]" if p.get("instrumental", True) else p.get("lyrics", "")
        if self.cfg.get("flavor") == "jam":  # victor/ace-step-jam `/generate`
            args = {
                "prompt": tags,
                "lyrics": lyrics,
                "audio_duration": dur,
                "infer_step": int(p.get("steps", 8)),
                "guidance_scale": float(p.get("guidance_scale", 7.0)),
                "seed": int(seed),
                "lora_name_or_path": "",
                "lora_weight": 0.8,
            }
            return self._predict(args, dur, seed, status_index=None)
        args = {
            "audio_duration": dur,
            "prompt": tags,
            "lyrics": "[instrumental]" if p.get("instrumental", True) else p.get("lyrics", ""),
            "infer_step": int(p.get("steps", 60)),
            "guidance_scale": float(p.get("guidance_scale", 15.0)),
            "manual_seeds": str(seed),
            "oss_steps": "",
            "ref_audio_input": None,
        }
        return self._predict(args, dur, seed, status_index=None)

    def _predict(self, args: dict, dur: float, seed: int, status_index: int | None) -> Result:
        from gradio_client import Client

        t0 = time.time()
        try:
            client = Client(self.cfg["space"], token=self.env.get("HF_TOKEN"), verbose=False)
            out = client.predict(**args, api_name=self.cfg.get("api_name", "/generation_wrapper"))
        except (QuotaExhausted, Transient, Unavailable):
            raise
        except Exception as e:  # gradio_client raises AppError / httpx errors / ValueError
            raise _classify(e) from e
        path = out[0] if isinstance(out, list | tuple) else out
        if isinstance(path, dict):
            path = path.get("path") or path.get("value")
        if isinstance(path, str) and path.startswith("data:audio/"):  # jam returns a data URI
            import base64

            head, b64 = path.split(",", 1)
            ext = head.split("/")[1].split(";")[0]
            return Result(
                model=self.model,
                data=base64.b64decode(b64),
                mime=f"audio/{ext}",
                ext=ext,
                params_used={k: v for k, v in args.items() if k not in ("param_4", "prompt")},
                seed_used=seed,
                metrics={"duration_s": dur, "space_latency_s": round(time.time() - t0, 1)},
            )
        if not path or not Path(path).is_file():
            ok = status_index is not None and isinstance(out, list | tuple) and len(out) > 10
            status = out[status_index] if ok else ""
            raise Unavailable(f"hf space returned no audio ({str(status)[:200]})")
        data = Path(path).read_bytes()
        ext = Path(path).suffix.lstrip(".") or "flac"
        return Result(
            model=self.model,
            data=data,
            mime=f"audio/{ext}",
            ext=ext,
            params_used={k: v for k, v in args.items() if k not in ("param_4", "prompt")},
            seed_used=seed,
            metrics={"duration_s": dur, "space_latency_s": round(time.time() - t0, 1)},
        )

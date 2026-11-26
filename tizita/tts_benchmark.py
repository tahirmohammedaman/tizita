"""Ceiling A (SPEC §12.2): Gemini TTS in four languages, scored by an ASR round trip (CER).

    tizita exp tts-benchmark            # translate (once), synthesise, transcribe, report
    tizita exp tts-benchmark --report   # re-score from the saved transcripts, no model calls

Every call goes through the router (stage "exp"). TTS uses one provider with no fallback, so no
other voice can slip into the results, and the run stops at the first quota error to protect the
film's retake budget. Finished items are never requested again.
"""

from __future__ import annotations

import csv
import io
import json
import re
import statistics
import unicodedata

import yaml

from tizita.cache import Manifest
from tizita.providers.base import Request
from tizita.providers.errors import ProviderError, QuotaExhausted, RateLimited
from tizita.util import Project, atomic_write_bytes, atomic_write_json, atomic_write_text

# Amharic letters that sound the same: folding them separates spelling choices from wrong sounds.
# Each pair is (first code point of a 7-8 letter series, series it folds onto). NOT used for
# Tigrinya, where these series are different sounds.
_AM_SERIES = (
    (0x1210, 0x1200),
    (0x1280, 0x1200),
    (0x1220, 0x1230),
    (0x12D0, 0x12A0),
    (0x1340, 0x1338),
)
_AM_FOLD = {src + i: dst + i for src, dst in _AM_SERIES for i in range(7)}


def normalise(text: str) -> str:
    """NFC, lower case, punctuation and symbols removed (Ethiopic ones included), one space."""
    text = unicodedata.normalize("NFC", text).lower()
    kept = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in text)
    return re.sub(r"\s+", " ", kept).strip()


def fold_amharic(text: str) -> str:
    return text.translate(_AM_FOLD)


def score(reference: str, hypothesis: str, lang: str) -> dict:
    import jiwer

    ref, hyp = normalise(reference), normalise(hypothesis)
    out = {"cer": round(jiwer.cer(ref, hyp), 4), "cer_folded": None}
    if lang == "am":
        out["cer_folded"] = round(jiwer.cer(fold_amharic(ref), fold_amharic(hyp)), 4)
    return out


class Bench:
    def __init__(self, project: Project, router=None, say=print):
        self.project, self.router, self.say = project, router, say
        self.dir = project.root / "experiments" / "tts_benchmark"
        self.cfg = yaml.safe_load((self.dir / "benchmark.yaml").read_text(encoding="utf-8"))
        self.state_path = self.dir / "state.json"
        self.state = (
            json.loads(self.state_path.read_text())
            if self.state_path.is_file()
            else {"translations": {}, "audio": {}, "transcripts": {}}
        )

    def save(self) -> None:
        atomic_write_json(self.state_path, self.state)

    def _call(self, pid: str, req: Request):
        result = self.router.call_one(pid, req)
        return result, self.router.runlog.run_id

    def translate(self) -> None:
        sentences = self.cfg["sentences"]
        for lang, meta in self.cfg["languages"].items():
            if lang == "am" or lang in self.state["translations"]:
                continue
            prompt = (
                self.cfg["translate_prompt"].format(**meta)
                + "\n"
                + json.dumps([s["en"] for s in sentences])
            )
            req = Request(
                capability="text",
                stage="exp",
                unit=f"translate_{lang}",
                prompt=prompt,
                params={"max_tokens": 4096, "response_mime_type": "application/json"},
            )
            result, run_id = self._call(self.cfg["translator"], req)
            body = re.sub(r"^```(json)?|```$", "", (result.text or "").strip()).strip()
            lines = json.loads(body)
            if len(lines) != len(sentences) or not all(isinstance(x, str) for x in lines):
                raise RuntimeError(f"{lang}: translator did not return {len(sentences)} strings")
            self.state["translations"][lang] = {
                "run_id": run_id,
                "model": result.model,
                "lines": {s["id"]: t.strip() for s, t in zip(sentences, lines, strict=True)},
            }
            self.save()
            self.say(f"translated {lang}")

    def text_for(self, lang: str, sentence: dict) -> str:
        if lang == "am":
            return sentence["am"]
        return self.state["translations"][lang]["lines"][sentence["id"]]

    def items(self):
        for lang in self.cfg["languages"]:
            for s in self.cfg["sentences"]:
                yield f"{lang}/{s['id']}", lang, s

    def synthesise(self) -> None:
        manifest = Manifest.load(self.project.manifest)
        for key, lang, s in self.items():
            saved = self.state["audio"].get(key)
            if saved and (self.project.root / saved["path"]).is_file():
                continue
            out = self.dir / "audio" / f"{lang}_{s['id']}.wav"
            if lang == "am":  # reuse the film's take of the same text and voice
                entry = manifest.get("narration", s["id"])
                atomic_write_bytes(out, (self.project.root / entry.path).read_bytes())
                run_id, model, source = entry.run_id, entry.provider["model"], "film take"
            else:
                req = Request(
                    capability="tts",
                    stage="exp",
                    unit=f"tts_{lang}_{s['id']}",
                    prompt=self.text_for(lang, s),
                    inputs={"voice": self.cfg["voice"]},
                    output_path=out,
                )
                result, run_id = self._call(self.cfg["tts_provider"], req)
                model, source = result.model, "benchmark"
            self.state["audio"][key] = {
                "path": self.project.rel(out),
                "run_id": run_id,
                "model": model,
                "source": source,
            }
            self.save()
            self.say(f"audio {key} ({source})")

    def transcribe(self) -> None:
        for pid in self.cfg["asr_providers"]:
            for key, lang, s in self.items():
                meta = self.cfg["languages"][lang]
                slot = f"{pid}:{key}"
                audio = self.state["audio"].get(key)
                if slot in self.state["transcripts"] or audio is None:
                    continue
                if pid == "cf_whisper" and meta["whisper_code"] is None:
                    continue  # unsupported: reported as such, not scored
                params = {"language": meta["whisper_code"]} if pid == "cf_whisper" else {}
                prompt = None if pid == "cf_whisper" else self.cfg["asr_prompt"].format(**meta)
                req = Request(
                    capability="asr",
                    stage="exp",
                    unit=f"asr_{lang}_{s['id']}",
                    prompt=prompt,
                    params=params,
                    inputs={"audio": str(self.project.root / audio["path"])},
                )
                try:
                    result, run_id = self._call(pid, req)
                except (QuotaExhausted, RateLimited) as e:
                    self.say(f"{pid} stopped on quota: {e.message[:120]}")
                    break
                except ProviderError as e:
                    self.say(f"{slot} failed: {e.message[:120]}")
                    continue
                self.state["transcripts"][slot] = {
                    "text": result.text or "",
                    "run_id": run_id,
                    "model": result.model,
                }
                self.save()
                self.say(f"transcript {slot}")

    # ---------------------------------------------------------------- report
    def rows(self) -> list[dict]:
        rows = []
        for key, lang, s in self.items():
            for pid in self.cfg["asr_providers"]:
                t = self.state["transcripts"].get(f"{pid}:{key}")
                audio = self.state["audio"].get(key)
                if not t or not audio:
                    continue
                ref = self.text_for(lang, s)
                rows.append(
                    {
                        "lang": lang,
                        "sentence": s["id"],
                        "asr": pid,
                        **score(ref, t["text"], lang),
                        "reference": ref,
                        "transcript": t["text"],
                        "tts_run_id": audio["run_id"],
                        "asr_run_id": t["run_id"],
                    }
                )
        return rows

    def report(self) -> list[dict]:
        rows = self.rows()
        if not rows:
            return rows
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        atomic_write_text(self.dir / "results.csv", buf.getvalue())

        ratings = self.dir / "ratings_template.csv"
        if not ratings.exists():  # never overwrite ratings a person has filled in
            body = "lang,sentence,audio_file,text,rater,intelligibility_1_5,naturalness_1_5,notes\n"
            for key, lang, s in self.items():
                if key in self.state["audio"]:
                    text = self.text_for(lang, s).replace('"', '""')
                    body += f'{lang},{s["id"]},audio/{lang}_{s["id"]}.wav,"{text}",,,,\n'
            atomic_write_text(ratings, body)
        atomic_write_text(self.dir / "tables.md", self.tables(rows))
        return rows

    def tables(self, rows: list[dict]) -> str:
        out = [
            "| Language | ASR | n | median CER | mean CER | best | worst | "
            "median CER, homophones folded |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for lang, meta in self.cfg["languages"].items():
            for pid in self.cfg["asr_providers"]:
                sel = [r for r in rows if r["lang"] == lang and r["asr"] == pid]
                if not sel:
                    why = (
                        "no Whisper language support"
                        if pid == "cf_whisper" and meta["whisper_code"] is None
                        else "not run"
                    )
                    out.append(f"| {meta['name']} | {pid} | 0 | {why} | | | | |")
                    continue
                c = [r["cer"] for r in sel]
                f = [r["cer_folded"] for r in sel if r["cer_folded"] is not None]
                folded = f"{statistics.median(f):.3f}" if f else "n/a"
                out.append(
                    f"| {meta['name']} | {pid} | {len(c)} | {statistics.median(c):.3f} | "
                    f"{statistics.mean(c):.3f} | {min(c):.3f} | {max(c):.3f} | {folded} |"
                )
        return "\n".join(out) + "\n"

    def run(self) -> None:
        self.translate()
        try:
            self.synthesise()
        except (QuotaExhausted, RateLimited) as e:
            self.say(f"TTS stopped on quota (no retry, film budget protected): {e.message[:160]}")
        self.transcribe()

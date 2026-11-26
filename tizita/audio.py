"""Small pure audio helpers (no numpy needed)."""

from __future__ import annotations

import math
import wave
from array import array
from pathlib import Path


def frame_db(samples: list[int] | array, rate: int, frame_s: float = 0.01) -> list[float]:
    """RMS level in dBFS per frame of 16-bit mono samples."""
    n = max(1, int(rate * frame_s))
    out = []
    for i in range(0, len(samples) - n + 1, n):
        chunk = samples[i : i + n]
        ms = sum(x * x for x in chunk) / n
        out.append(10 * math.log10(ms / 32768**2) if ms > 0 else -120.0)
    return out


def speech_end_s(
    db: list[float],
    frame_s: float = 0.01,
    *,
    burst_db: float = -12.0,
    quiet_db: float = -45.0,
    min_quiet_s: float = 0.08,
    max_tail_s: float = 0.4,
) -> float | None:
    """Gemini TTS ends every take with a ~0.16 s burst of full-scale noise (-3..-7 dBFS, with a
    30 ms digital-zero gap) after the speech has decayed to quiet (measured 26 Nov, all 11 takes).
    If the take ends with [quiet >= min_quiet_s][loud flat burst <= max_tail_s], return the time in
    the middle of the quiet run (keeps the natural decay); else None (take is clean)."""
    i = len(db)
    while i > 0 and (db[i - 1] > burst_db or db[i - 1] <= -110):  # burst frames or digital zero
        i -= 1
    tail = db[i:]
    loud = [x for x in tail if x > -110]
    if not loud or len(tail) * frame_s > max_tail_s or sum(loud) / len(loud) < -9:
        return None
    j = i
    while j > 0 and quiet_db >= db[j - 1] > -110:
        j -= 1
    if (i - j) * frame_s < min_quiet_s or j == 0:
        return None
    return round((j + (i - j) / 2) * frame_s, 3)


def wav_speech_end_s(path: Path) -> float | None:
    with wave.open(str(path)) as w:
        if w.getsampwidth() != 2:
            return None
        rate, ch = w.getframerate(), w.getnchannels()
        s = array("h", w.readframes(w.getnframes()))
    if ch > 1:
        s = s[::ch]
    return speech_end_s(frame_db(s, rate))

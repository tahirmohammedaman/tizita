"""Circuit breaker persisted in `.state/circuits.json` (SPEC §7.3).

A provider whose quota is exhausted is skipped until `open_until`. With no known reset time the
circuit stays open for the rest of the run (in-memory) and is written with `open_until: null`,
which later runs ignore.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from tizita.util import atomic_write_json, iso_ms, utc_now


def _parse(ts: str | None) -> dt.datetime | None:
    if not ts:
        return None
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def next_reset(rule: str | None, now: dt.datetime | None = None) -> str | None:
    """`daily_utc`, `daily_pacific` (Gemini) or `hours:N` → ISO timestamp of the next reset."""
    if not rule:
        return None
    now = now or utc_now()
    if rule.startswith("hours:"):
        return iso_ms(now + dt.timedelta(hours=float(rule.split(":", 1)[1])))
    tz = {"daily_utc": dt.UTC, "daily_pacific": ZoneInfo("America/Los_Angeles")}.get(rule)
    if tz is None:
        return None
    local = now.astimezone(tz)
    midnight = (local + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return iso_ms(midnight.astimezone(dt.UTC))


class CircuitStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._run_open: set[str] = set()
        self.state: dict[str, dict] = {}
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                self.state = {}

    def is_open(self, pid: str, now: dt.datetime | None = None) -> bool:
        if pid in self._run_open:
            return True
        entry = self.state.get(pid)
        if not entry:
            return False
        until = _parse(entry.get("open_until"))
        if until is None:
            return False  # run-scoped circuit from an earlier run
        if (now or utc_now()) >= until:
            self.close(pid)
            return False
        return True

    def open(self, pid: str, *, reset_at: str | None, error_class: str, reason: str) -> None:
        if reset_at is None:
            self._run_open.add(pid)
        self.state[pid] = {
            "open_until": reset_at,
            "error_class": error_class,
            "reason": reason[:300],
            "opened_at": iso_ms(),
        }
        atomic_write_json(self.path, self.state)

    def close(self, pid: str) -> None:
        self._run_open.discard(pid)
        if self.state.pop(pid, None) is not None:
            atomic_write_json(self.path, self.state)

    def open_until(self, pid: str) -> str | None:
        if pid in self._run_open:
            return "end of run"
        return (self.state.get(pid) or {}).get("open_until")

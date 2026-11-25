"""Event bus (SPEC §7.4, §8.2): one emit fans out to the CLI printer, events.jsonl, the
failures draft log and (M7) the API SSE stream."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tizita.util import Project, append_jsonl, iso_ms

Event = dict[str, Any]
Sink = Callable[[Event], None]


@dataclass
class FallbackEvent:
    stage: str
    unit: str
    from_: str  # provider id
    to: str | None  # None = chain exhausted
    from_tier: str
    to_tier: str | None
    error_class: str
    message: str
    reset_at: str | None = None
    from_label: str | None = None
    to_label: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["from"] = d.pop("from_")
        return d

    def cli_line(self) -> str:
        frm = self.from_label or self.from_
        if self.to is None:
            tail = "no more providers in the chain"
        else:
            to = self.to_label or self.to
            tier = f" [{self.from_tier} → {self.to_tier}]" if self.to_tier != self.from_tier else ""
            tail = f"falling back to {to}{tier}"
        reason = self.error_class.replace("_", " ")
        return f"⚠ {self.stage} {self.unit}: {frm} {reason} → {tail}"


class EventBus:
    def __init__(self, run_id: str | None = None):
        self.run_id = run_id
        self._sinks: list[Sink] = []

    def subscribe(self, sink: Sink) -> None:
        self._sinks.append(sink)

    def emit(self, type_: str, **data: Any) -> Event:
        event = {"ts": iso_ms(), "type": type_, "run_id": self.run_id, **data}
        for sink in self._sinks:
            sink(event)
        return event

    def fallback(self, fe: FallbackEvent) -> Event:
        return self.emit("fallback", **fe.to_dict(), cli=fe.cli_line())


def file_sink(path: Path) -> Sink:
    def _sink(event: Event) -> None:
        append_jsonl(path, {k: v for k, v in event.items() if k != "cli"})

    return _sink


def failures_sink(path: Path) -> Sink:
    """Draft FAILURES.md entries; Tahir curates them."""

    def _sink(event: Event) -> None:
        if event["type"] not in ("fallback", "provider_moved"):
            return
        append_jsonl(
            path,
            {
                "ts": event["ts"],
                "run_id": event.get("run_id"),
                "kind": event["type"],
                "stage": event.get("stage"),
                "unit": event.get("unit"),
                "provider": event.get("from") or event.get("provider"),
                "error_class": event.get("error_class"),
                "message": event.get("message"),
                "fallback_to": event.get("to"),
                "reset_at": event.get("reset_at"),
                "draft": True,
            },
        )

    return _sink


def cli_sink(console: Any) -> Sink:
    def _sink(event: Event) -> None:
        t = event["type"]
        if t == "fallback":
            console.print(f"[yellow]{event['cli']}[/]", highlight=False)
        elif t == "circuit_open":
            console.print(
                f"[yellow]⚠ circuit open: {event.get('provider')} until "
                f"{event.get('reset_at') or 'end of run'} ({event.get('error_class')})[/]",
                highlight=False,
            )
        elif t == "provider_moved":
            console.print(f"[yellow]⚠ {event.get('message')}[/]", highlight=False)

    return _sink


def default_bus(project: Project, run_id: str | None = None, console: Any = None) -> EventBus:
    bus = EventBus(run_id)
    bus.subscribe(file_sink(project.events))
    bus.subscribe(failures_sink(project.failures))
    if console is not None:
        bus.subscribe(cli_sink(console))
    return bus

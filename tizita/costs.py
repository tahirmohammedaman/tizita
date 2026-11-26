"""`tizita costs` (SPEC §8.3): aggregate runs.jsonl into the generated section of COSTS.md.

Nothing here calls a model. A list price that pricing.yaml leaves `null` is reported as
unknown, never as $0, even though the run log stores 0.0 for those lines.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from tizita.runlog import iter_runs
from tizita.util import atomic_write_text

BEGIN = "<!-- BEGIN GENERATED -->"
END = "<!-- END GENERATED -->"
FREE_BASIS = "free"


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile (q in 0..100)."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def list_price(line: dict, prices: dict) -> float | None:
    """The line's list-price estimate in USD, or None if it is not known."""
    basis = (line.get("cost_basis") or "").removeprefix("pricing.yaml#")
    if not basis:
        # local CPU and deterministic providers have no price list: nothing would be billed
        return 0.0 if line.get("tier") in ("local", "deterministic") else None
    if basis != FREE_BASIS and (prices.get(basis) or {}).get("usd") is None:
        return None
    if line.get("status") != "ok":
        return 0.0
    value = line.get("cost_list_price_usd")
    return None if value is None else float(value)


def summarise(lines: Iterable[dict], prices: dict, key) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for line in lines:
        groups[key(line)].append(line)
    rows = []
    for group_key, items in sorted(groups.items()):
        ok = [r for r in items if r["status"] == "ok"]
        latencies = [r["latency_ms"] / 1000 for r in ok if r.get("latency_ms") is not None]
        priced = [list_price(r, prices) for r in items]
        rows.append(
            {
                "key": group_key,
                "calls": len(items),
                "ok": len(ok),
                "failed": len(items) - len(ok),
                "p50_s": percentile(latencies, 50),
                "p95_s": percentile(latencies, 95),
                "gpu_min": sum(r.get("gpu_seconds") or 0 for r in items) / 60,
                "list_usd": sum(p for p in priced if p is not None),
                "unpriced": sum(1 for p in priced if p is None),
                "actual_usd": sum(r.get("cost_actual_usd") or 0 for r in items),
            }
        )
    return rows


def cache_stats(events: Iterable[dict]) -> dict:
    runs = [e for e in events if e.get("type") == "run_summary"]
    hits = sum(e.get("cache_hits", 0) for e in runs)
    ran = sum(len(e.get("ran", [])) for e in runs)
    return {"runs": len(runs), "hits": hits, "ran": ran}


def _secs(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}"


def _usd(row: dict) -> str:
    if row["unpriced"] == row["calls"]:
        return "unknown"
    text = f"${row['list_usd']:.4f}"
    return f"{text} + {row['unpriced']} unpriced" if row["unpriced"] else text


def _table(rows: list[dict], names: list[str]) -> list[str]:
    head = [*names, "calls", "ok", "failed", "p50 s", "p95 s", "GPU min", "list price", "actual"]
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        gpu = f"{r['gpu_min']:.1f}" if r["gpu_min"] else "not logged"
        cells = [
            *r["key"],
            r["calls"],
            r["ok"],
            r["failed"],
            _secs(r["p50_s"]),
            _secs(r["p95_s"]),
            gpu,
            _usd(r),
            f"${r['actual_usd']:.2f}",
        ]
        out.append("| " + " | ".join(str(c) for c in cells) + " |")
    return out


def render(lines: list[dict], events: list[dict], prices: dict, pools: dict[str, str]) -> str:
    """The markdown between the markers. A pure function of its inputs."""
    if not lines:
        return "_No model calls logged yet._"
    total = summarise(lines, prices, lambda r: ())[0]
    cache = cache_stats(events)
    seen = cache["hits"] + cache["ran"]
    stamps = sorted(r["ts"] for r in lines)
    out = [
        f"Source: `runs.jsonl`, {total['calls']} lines from {stamps[0]} to {stamps[-1]} (UTC): "
        f"{total['ok']} ok, {total['failed']} failed attempts (errors and fallbacks).",
        "",
        f"**Actual spend: ${total['actual_usd']:.2f}.** List-price equivalent of the priced calls: "
        f"${total['list_usd']:.4f}. **{total['unpriced']} of {total['calls']} calls have no "
        "list price** (`usd: null` in `config/pricing.yaml`, or no entry), so that figure is a "
        "partial estimate, not the cost of the film on a paid tier.",
        "",
        "Latencies are wall-clock seconds of successful calls (nearest-rank percentiles). "
        '"GPU min" is "not logged" where a provider reports no GPU time, including the hosted '
        "ZeroGPU Space.",
        "",
        "### Per stage",
        "",
        *_table(summarise(lines, prices, lambda r: (r["stage"],)), ["stage"]),
        "",
        "`director`, `smoke`, `exp` and `music_qa` are development calls, not part of `make film`.",
        "",
        "### Per provider",
        "",
        *_table(
            summarise(lines, prices, lambda r: (r["provider"], r["tier"])), ["provider", "tier"]
        ),
        "",
        "### Quota pools",
        "",
        "Calls that draw on the same free allowance. Deterministic and local calls use none.",
        "",
        "| quota pool | calls | ok | failed | providers |",
        "|---|---|---|---|---|",
    ]
    by_pool: dict[str, list[dict]] = defaultdict(list)
    for r in lines:
        if r["tier"] in ("free_hosted", "paid"):
            by_pool[pools.get(r["provider"]) or r["provider"]].append(r)
    for pool, items in sorted(by_pool.items()):
        ok = sum(1 for r in items if r["status"] == "ok")
        used = ", ".join(sorted({r["provider"] for r in items}))
        out.append(f"| {pool} | {len(items)} | {ok} | {len(items) - ok} | {used} |")
    limits = [r for r in lines if r.get("error_class") in ("quota_exhausted", "rate_limited")]
    out += ["", "### Quota and rate-limit errors in the log", ""]
    if limits:
        out += [
            "| ts (UTC) | run_id | provider | class | message (start) |",
            "|---|---|---|---|---|",
        ]
        for r in limits:
            message = " ".join((r.get("error_message") or "").split())[:140].replace("|", "/")
            out.append(
                f"| {r['ts']} | `{r['run_id']}` | {r['provider']} | {r['error_class']} "
                f"| {message} |"
            )
    else:
        out.append("None logged.")
    out += [
        "",
        "A rotated Gemini key (429, next key tried) has had its own line only since the "
        "afternoon of 26 Nov 2026; earlier rotations are not in the log.",
    ]
    rate = f"{100 * cache['hits'] / seen:.0f}%" if seen else "—"
    out += [
        "",
        "### Cache",
        "",
        f"Over {cache['runs']} `tizita run` invocations in `logs/events.jsonl`: {cache['hits']} "
        f"unit cache hits and {cache['ran']} units generated ({rate} hit rate). Run summaries "
        "do not split hits by stage.",
        "",
        "### T4 vs RTX 4060",
        "",
        "Not measured: no Kaggle or local-GPU job has run (no `kaggle` or `local` GPU executor "
        "calls in `runs.jsonl`).",
    ]
    return "\n".join(out)


def inject(document: str, body: str) -> str:
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(document):
        raise ValueError(f"COSTS.md has no {BEGIN} / {END} markers")
    return pattern.sub(lambda _: f"{BEGIN}\n{body}\n{END}", document, count=1)


def write_costs(
    doc: Path, runs: Path, events: Path, prices: dict, pools: dict[str, str]
) -> tuple[int, str]:
    lines = list(iter_runs(runs))
    body = render(lines, list(iter_runs(events)), prices, pools)
    atomic_write_text(doc, inject(Path(doc).read_text(encoding="utf-8"), body))
    return len(lines), body

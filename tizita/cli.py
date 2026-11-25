"""Tizita CLI (SPEC §13).

Heavy ML imports stay out of this module: `tizita --help`, `validate` and `plan` must work on a
base install with no GPU. Commands that later milestones implement are stubs for now and
exit with code 2.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tizita import __version__

REPO_ROOT = Path(__file__).resolve().parent.parent
console = Console()
err_console = Console(stderr=True)

_PASSTHROUGH = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="tizita",
    help="Tizita Studio: a storyboard-driven AI short-film pipeline.",
    no_args_is_help=True,
    add_completion=False,
)
models_app = typer.Typer(help="Local model weights (SPEC §19).", no_args_is_help=True)
gpu_app = typer.Typer(help="GPU batches: export / import / status (SPEC §9).", no_args_is_help=True)
exp_app = typer.Typer(help="Ceiling experiments (SPEC §12).", no_args_is_help=True)
motion_app = typer.Typer(help="Ceiling B: blind motion A/B.", no_args_is_help=True)
app.add_typer(models_app, name="models")
app.add_typer(gpu_app, name="gpu")
app.add_typer(exp_app, name="exp")
exp_app.add_typer(motion_app, name="motion-ab")


def _pending(command: str, milestone: str) -> None:
    err_console.print(f"[yellow]tizita {command}[/] is not implemented yet (lands in {milestone}).")
    raise typer.Exit(code=2)


def models_dir() -> Path:
    """$MODELS_DIR from the environment or .env, default ~/models/tizita."""
    value = os.environ.get("MODELS_DIR")
    if not value:
        from dotenv import dotenv_values

        value = (
            dotenv_values(REPO_ROOT / ".env").get("MODELS_DIR")
            if (REPO_ROOT / ".env").exists()
            else None
        )
    return Path(os.path.expanduser(value or "~/models/tizita"))


@app.command()
def version() -> None:
    """Print the package version."""
    console.print(f"tizita {__version__}")


# ---------------------------------------------------------------- models
@models_app.command("download")
def models_download(
    only: Annotated[
        str | None,
        typer.Option(
            "--only",
            help="One item: env fonts mms-tts-amh clip-vit-b32 dinov2-small frontend docker | "
            "optional: ace flux wan ltx musicgen whisper gpu",
        ),
    ] = None,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Don't ask before optional items.")
    ] = False,
) -> None:
    """Run scripts/download_models.sh (default set, or one item with --only)."""
    cmd = ["bash", str(REPO_ROOT / "scripts" / "download_models.sh")]
    if only:
        cmd += ["--only", only]
    if yes:
        cmd.append("--yes")
    env = {**os.environ, "MODELS_DIR": str(models_dir())}
    if not only:
        console.print("Default set runs in the foreground; output goes to logs/downloads.log.")
    raise typer.Exit(code=subprocess.call(cmd, cwd=REPO_ROOT, env=env))


@models_app.command("status")
def models_status() -> None:
    """Show $MODELS_DIR/MANIFEST.json."""
    manifest = models_dir() / "MANIFEST.json"
    if not manifest.exists():
        console.print(f"No manifest at {manifest}. Run [bold]tizita models download[/].")
        return
    data = json.loads(manifest.read_text())
    table = Table("item", "status", "repo / kind", "size", "updated")
    colours = {"ok": "green", "failed": "red", "skipped": "yellow", "downloading": "cyan"}
    for name, e in sorted(data.items()):
        size = e.get("size_bytes")
        size_s = f"{int(size) / 1e6:.0f} MB" if size else ""
        st = e.get("status", "?")
        table.add_row(
            name,
            f"[{colours.get(st, 'white')}]{st}[/]",
            e.get("repo_id") or e.get("kind") or e.get("reason") or "",
            size_s,
            e.get("updated_at", ""),
        )
    console.print(table)


# ---------------------------------------------------------------- pipeline (stubs)
@app.command(context_settings=_PASSTHROUGH)
def smoke() -> None:
    """Call each configured provider once; log latency to runs.jsonl."""
    _pending("smoke", "M1")


@app.command(context_settings=_PASSTHROUGH)
def providers() -> None:
    """List providers with tier, status, quota pool and licence."""
    _pending("providers", "M1")


@app.command(context_settings=_PASSTHROUGH)
def new() -> None:
    """Director interview -> storyboard.draft.json (--write promotes it)."""
    _pending("new", "M2")


@app.command(context_settings=_PASSTHROUGH)
def validate() -> None:
    """JSON Schema + semantic lint of storyboard.json."""
    _pending("validate", "M1")


@app.command(context_settings=_PASSTHROUGH)
def lint() -> None:
    """Semantic lint report (--json for machines)."""
    _pending("lint", "M1")


@app.command(context_settings=_PASSTHROUGH)
def plan() -> None:
    """Dry run: which units are cached, dirty, missing or fallback-upgradable."""
    _pending("plan", "M1")


@app.command(context_settings=_PASSTHROUGH)
def run() -> None:
    """Run the stage graph, regenerating only dirty units."""
    _pending("run", "M2")


@app.command("radio-cut", context_settings=_PASSTHROUGH)
def radio_cut() -> None:
    """Narration + placeholder pad + burned subtitles on black."""
    _pending("radio-cut", "M2")


@app.command(context_settings=_PASSTHROUGH)
def approve() -> None:
    """tizita approve <stage> <unit>"""
    _pending("approve", "M3")


@app.command(context_settings=_PASSTHROUGH)
def choose() -> None:
    """tizita choose music <N> --reason '…'"""
    _pending("choose", "M4")


@gpu_app.command("export", context_settings=_PASSTHROUGH)
def gpu_export() -> None:
    """Build a manual GPU bundle."""
    _pending("gpu export", "M4")


@gpu_app.command("import", context_settings=_PASSTHROUGH)
def gpu_import() -> None:
    """Import GPU results into the cache."""
    _pending("gpu import", "M4")


@gpu_app.command("status", context_settings=_PASSTHROUGH)
def gpu_status() -> None:
    """Show Kaggle / worker batch status."""
    _pending("gpu status", "M4")


@app.command(context_settings=_PASSTHROUGH)
def costs() -> None:
    """Regenerate the generated section of COSTS.md from runs.jsonl."""
    _pending("costs", "M6")


@exp_app.command("tts-benchmark", context_settings=_PASSTHROUGH)
def exp_tts_benchmark() -> None:
    """Ceiling A: multilingual TTS benchmark."""
    _pending("exp tts-benchmark", "M6")


@motion_app.command("build", context_settings=_PASSTHROUGH)
def motion_build() -> None:
    """Build blind A/B pairs."""
    _pending("exp motion-ab build", "M6")


@motion_app.command("analyze", context_settings=_PASSTHROUGH)
def motion_analyze() -> None:
    """Analyse A/B votes."""
    _pending("exp motion-ab analyze", "M6")


@app.command(context_settings=_PASSTHROUGH)
def serve() -> None:
    """Showcase API (FastAPI)."""
    _pending("serve", "M7")


@app.command(context_settings=_PASSTHROUGH)
def worker() -> None:
    """Showcase GPU worker (tizita worker --api-url … --token …)."""
    _pending("worker", "M7")


if __name__ == "__main__":
    app()

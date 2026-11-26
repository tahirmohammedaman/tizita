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
from tizita.util import Project

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
choose_app = typer.Typer(help="Pick a candidate (reference, music).", no_args_is_help=True)
app.add_typer(choose_app, name="choose")
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
@app.command()
def providers(
    profile: ProfileOpt = None,
    provider: ProviderOpt = None,
    capability: Annotated[str | None, typer.Option("--capability", "-c")] = None,
) -> None:
    """List providers with tier, status, quota pool, licence and chain position."""
    project = _project()
    router = _router(project, profile, provider, quiet=True)
    reg = router.registry
    sel = router.sel
    paid = "on" if sel.paid_ok else "off (needs allow_paid + budget_usd)"
    console.print(f"profile [bold]{sel.profile}[/] · paid {paid}")
    for cap, ids in reg.chains.items():
        if capability and cap != capability:
            continue
        active = router.chain_ids(cap)
        table = Table(title=f"[bold]{cap}[/]", title_justify="left")
        table.add_column("#")
        table.add_column("provider", no_wrap=True)
        for col in ("tier", "status", "quota pool", "model", "private", "licence"):
            table.add_column(col, overflow="fold")
        for pid in ids:
            p = reg.get(pid)
            ok, reason, hint = router.usable(pid)
            colour = "green" if ok else ("dim" if reason.startswith("planned") else "yellow")
            status = f"[{colour}]{reason}[/]" + (f" ({hint})" if hint and not ok else "")
            pos = str(active.index(pid) + 1) if pid in active else "—"
            table.add_row(
                pos,
                f"{p.label}\n[dim]{pid}[/]",
                p.tier,
                status,
                p.quota_pool,
                p.model or "",
                "yes" if p.accepts_private_media else "no",
                p.licence,
            )
        console.print(table)
    for issue in reg.lint(router.active_chains()):
        console.print(f"[yellow]{issue.level}[/] {issue.code} {issue.path}: {issue.message}")


@app.command()
def smoke(
    profile: ProfileOpt = None,
    only: Annotated[
        list[str] | None, typer.Option("--only", help="Provider id(s) to smoke.")
    ] = None,
    no_discover: Annotated[
        bool, typer.Option("--no-discover", help="Skip the model-catalogue check.")
    ] = False,
) -> None:
    """One real call per configured provider; each call writes a runs.jsonl line."""
    from tizita.providers.smoke import discover, run_smoke

    project = _project()
    router = _router(project, profile)
    console.print(f"smoke run [bold]{router.runlog.run_id}[/] (profile {router.sel.profile})")
    if not no_discover:
        for f in discover(router):
            colour = {"ok": "green", "moved": "yellow"}.get(f["status"], "red")
            extra = f["message"] if "message" in f else f.get("model", "")
            console.print(f"  catalogue [{colour}]{f['status']}[/] {f['provider']}: {extra}")
            if f["status"] == "moved" and f.get("candidates"):
                console.print(f"    candidates: {', '.join(f['candidates'])}")
    rows = run_smoke(router, set(only) if only else None)
    table = Table("provider", "capability", "model", "status", "latency", "detail")
    for r in rows:
        colour = "green" if r.status == "ok" else ("yellow" if r.status == "skipped" else "red")
        table.add_row(
            r.provider,
            r.capability,
            r.model,
            f"[{colour}]{r.status}[/]",
            f"{r.latency_ms} ms" if r.latency_ms is not None else "",
            r.detail,
        )
    console.print(table)
    n_ok = sum(r.status == "ok" for r in rows)
    console.print(f"{n_ok}/{len(rows)} ok; runs.jsonl lines tagged run_id {router.runlog.run_id}")
    if any(r.status.startswith("error") for r in rows):
        raise typer.Exit(code=1)


@app.command()
def new(
    answers: Annotated[
        Path | None, typer.Option("--answers", help="YAML answers (skips the interview).")
    ] = None,
    write: Annotated[
        bool,
        typer.Option(
            "--write",
            help="Promote storyboard.draft.json to storyboard.json after lint (never otherwise).",
        ),
    ] = False,
    profile: ProfileOpt = None,
    provider: ProviderOpt = None,
) -> None:
    """Director interview -> storyboard.draft.json. `--write` promotes the draft."""
    from tizita import director

    project = _project()
    draft_path = project.root / "storyboard.draft.json"
    if write and answers is None and draft_path.exists():
        ok, errs = director.promote(project)
        if not ok:
            for e in errs:
                err_console.print(f"[red]✗[/] {e}")
            raise typer.Exit(code=1)
        console.print(
            f"[green]✓[/] {project.rel(draft_path)} → storyboard.json (old one backed up)"
        )
        return
    if answers is not None:
        data = director.load_answers(answers)
    else:
        console.print(f"[yellow]⚠ {director.PRIVACY_WARNING}[/]")
        data = director.ask_interactively(lambda q: typer.prompt(q))
    router = _router(project, profile, provider)
    try:
        sb, report, prov = director.draft(router, project, data)
    except Exception as e:  # surface any provider or lint failure
        err_console.print(f"[red]director failed:[/] {e}")
        raise typer.Exit(code=1) from e
    path = director.save_draft(project, sb)
    _print_report(report, verbose=True)
    st = report.stats
    console.print(
        f"drafted by [bold]{prov.label}[/]: {st.get('shots')} shots, {st.get('planned_total_s')} s "
        f"planned, {len(report.errors)} error(s), {len(report.warnings)} warning(s) → "
        f"[bold]{project.rel(path)}[/]"
    )
    if not report.ok:
        raise typer.Exit(code=1)
    if write:
        ok, errs = director.promote(project)
        console.print("[green]✓ promoted to storyboard.json[/]" if ok else f"[red]{errs}[/]")
    else:
        console.print("Review the draft, then run [bold]tizita new --write[/] to promote it.")


StoryboardOpt = Annotated[
    Path | None, typer.Option("--storyboard", "-s", help="Default: <project>/storyboard.json")
]


def _project() -> Project:
    return Project.default()


def _load(project: Project, storyboard: Path | None) -> tuple[Path, dict]:
    from tizita.storyboard import load_storyboard

    path = storyboard or project.storyboard
    if not path.exists():
        err_console.print(f"[red]No storyboard at {path}[/]")
        raise typer.Exit(code=1)
    try:
        return path, load_storyboard(path)
    except json.JSONDecodeError as e:
        err_console.print(f"[red]{path}: invalid JSON: {e}[/]")
        raise typer.Exit(code=1) from e


def _print_report(report, verbose: bool = True) -> None:
    colours = {"error": "red", "warning": "yellow"}
    for i in report.issues if verbose else report.errors:
        console.print(
            f"[{colours[i.level]}]{i.level:7}[/] [bold]{i.code}[/] {i.path}: {i.message}",
            highlight=False,
        )


@app.command()
def validate(storyboard: StoryboardOpt = None) -> None:
    """JSON Schema + semantic lint of storyboard.json (exit 1 on errors)."""
    from tizita.storyboard import lint as run_lint

    project = _project()
    path, sb = _load(project, storyboard)
    report = run_lint(sb, project)
    _print_report(report, verbose=False)
    st = report.stats
    if report.ok:
        console.print(
            f"[green]✓[/] {project.rel(path)} valid: {st.get('shots')} shots, "
            f"{st.get('planned_total_s')} s planned, {len(report.warnings)} warning(s)"
            + (" (run [bold]tizita lint[/])" if report.warnings else "")
        )
    else:
        console.print(f"[red]✗ {len(report.errors)} error(s)[/] in {project.rel(path)}")
        raise typer.Exit(code=1)


@app.command()
def lint(
    storyboard: StoryboardOpt = None,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable report.")] = False,
) -> None:
    """Semantic lint report (--json for the API/frontend). Exit 1 on errors."""
    from tizita.stages.timing import measured_for_lint
    from tizita.storyboard import lint as run_lint

    project = _project()
    _, sb = _load(project, storyboard)
    report = run_lint(sb, project, measured=measured_for_lint(project))
    extra = _extra_lint(project)
    report.issues.extend(extra)
    if as_json:
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_report(report)
        console.print(
            f"{len(report.errors)} error(s), {len(report.warnings)} warning(s); "
            f"stats: {json.dumps(report.stats, ensure_ascii=False)}"
        )
    if not report.ok:
        raise typer.Exit(code=1)


ProfileOpt = Annotated[
    str | None,
    typer.Option("--profile", help="free | free+local | local-first | paid | custom"),
]
ProviderOpt = Annotated[
    list[str] | None,
    typer.Option("--provider", help="Per-capability override: image=cf_flux2_klein[:model]"),
]


def _router(project: Project, profile=None, overrides=None, quiet: bool = False):
    from tizita.providers.session import make_router

    try:
        return make_router(project, profile, overrides, console=None if quiet else console)
    except ValueError as e:
        err_console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2) from e


def _extra_lint(project: Project) -> list:
    """Provider-config lint: unknown ids, capability mismatch, same-pool first fallback."""
    router = _router(project, quiet=True)
    return router.registry.lint(router.active_chains())


def _resolver(project: Project, profile=None, overrides=None):
    return _router(project, profile, overrides, quiet=True).plan_provider


@app.command()
def plan(
    storyboard: StoryboardOpt = None,
    profile: ProfileOpt = None,
    provider: ProviderOpt = None,
    stage: Annotated[list[str] | None, typer.Option("--stage", help="Only these stages.")] = None,
    check: Annotated[bool, typer.Option("--check", help="Exit 1 if anything is dirty.")] = False,
) -> None:
    """Dry run: which units are cached, dirty, missing or fallback-upgradable."""
    from tizita.dag import plan as run_plan
    from tizita.dag import summarize
    from tizita.events import default_bus

    project = _project()
    _, sb = _load(project, storyboard)
    rows = run_plan(sb, project, resolver=_resolver(project, profile, provider))
    if stage:
        rows = [r for r in rows if r.stage in stage]
    colours = {
        "cached": "green",
        "dirty": "yellow",
        "missing": "red",
        "fallback-upgradable": "cyan",
    }
    stage = None
    table = None
    tables = []
    for r in rows:
        if r.stage != stage:
            stage = r.stage
            table = Table(
                "unit",
                "status",
                "provider",
                "est. latency",
                "est. GPU min",
                title=f"[bold]{stage}[/]",
                title_justify="left",
                min_width=80,
            )
            tables.append(table)
        status = f"[{colours[r.status]}]{r.status}[/]" + (f": {r.detail}" if r.detail else "")
        table.add_row(
            r.unit,
            status,
            r.provider,
            f"{r.est_latency_s:.0f} s",
            f"{r.est_gpu_min:.0f}" if r.est_gpu_min else "",
        )
    for t in tables:
        console.print(t)
    summary = summarize(rows)
    counts = ", ".join(f"{v} {k}" for k, v in sorted(summary["counts"].items()))
    console.print(
        f"[bold]{summary['units']} units[/]: {counts}. To run: {summary['to_run']} "
        f"(≈ {summary['est_latency_s'] / 60:.1f} min wall, {summary['est_gpu_min']:.0f} GPU min)"
    )
    default_bus(project).emit(
        "plan",
        summary=summary,
        dirty=[f"{r.stage}/{r.unit}: {r.status} {r.detail}".strip() for r in rows if r.needs_work],
    )
    if check and summary["to_run"]:
        raise typer.Exit(code=1)


def _run_stages(
    stages: set[str] | None,
    unit: str | None,
    profile,
    provider,
    force: bool = False,
    upgrade: bool = False,
) -> None:
    from tizita.dag import execute

    project = _project()
    _, sb = _load(project, None)
    router = _router(project, profile, provider)
    res = execute(
        sb,
        project,
        router,
        stages=stages,
        unit_id=unit,
        force=force,
        upgrade_fallbacks=upgrade,
    )
    for u in res.ran:
        console.print(f"  [green]✓[/] {u}")
    for msg in res.skipped:
        console.print(f"  [dim]- {msg}[/]")
    for u, msg in res.failed:
        console.print(f"  [red]✗ {u}:[/] {msg}")
    console.print(res.line())
    if res.failed:
        raise typer.Exit(code=1)


@app.command()
def run(
    stage: Annotated[list[str] | None, typer.Option("--stage", help="Repeatable.")] = None,
    unit: Annotated[str | None, typer.Option("--unit")] = None,
    force: Annotated[bool, typer.Option("--force", help="Re-run even if cached.")] = False,
    upgrade_fallbacks: Annotated[bool, typer.Option("--upgrade-fallbacks")] = False,
    profile: ProfileOpt = None,
    provider: ProviderOpt = None,
) -> None:
    """Run the stage graph, regenerating only dirty units."""
    _run_stages(set(stage) if stage else None, unit, profile, provider, force, upgrade_fallbacks)


@app.command("radio-cut")
def radio_cut(profile: ProfileOpt = None, provider: ProviderOpt = None) -> None:
    """Narration + placeholder pad + burned subtitles on black (outputs/radio_cut/<key>.mp4)."""
    _run_stages({"narration", "timing", "subtitles", "radio_cut"}, None, profile, provider)
    from tizita.cache import Manifest

    project = _project()
    e = Manifest.load(project.manifest).get("radio_cut", "project")
    if e:
        console.print(f"radio cut: [bold]{e.path}[/]")


@app.command(context_settings=_PASSTHROUGH)
def approve() -> None:
    """tizita approve <stage> <unit>"""
    _pending("approve", "M3")


@choose_app.command("reference")
def choose_reference(ref: str, n: int) -> None:
    """tizita choose reference <ref> <N>: pick candidate N (1-based) as the golden reference."""
    from tizita.util import atomic_write_text

    project = _project()
    path, sb = _load(project, None)
    r = next((x for x in sb["references"] if x["id"] == ref), None)
    if r is None:
        console.print(f"[red]unknown reference {ref}[/]")
        raise typer.Exit(1)
    if not 1 <= n <= r["sheet"]["candidates"]:
        console.print(f"[red]N must be 1..{r['sheet']['candidates']}[/]")
        raise typer.Exit(1)
    r["sheet"]["chosen"] = n - 1
    atomic_write_text(path, json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
    console.print(f"[green]{ref}: candidate {n} is now the golden reference[/]")


@choose_app.command("music")
def choose_music(
    n: int,
    reason: str = typer.Option(..., "--reason", help="why this candidate (kept in the storyboard)"),
) -> None:
    """tizita choose music <N> --reason '…': pick music candidate N (1-based)."""
    from tizita.util import atomic_write_text

    project = _project()
    path, sb = _load(project, None)
    m = sb["music"]
    if not 1 <= n <= m["candidates"]:
        console.print(f"[red]N must be 1..{m['candidates']}[/]")
        raise typer.Exit(1)
    m["chosen"] = n - 1
    m["chosen_reason"] = reason
    atomic_write_text(path, json.dumps(sb, indent=2, ensure_ascii=False) + "\n")
    console.print(f"[green]music: candidate {n} chosen[/] ({reason})")


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

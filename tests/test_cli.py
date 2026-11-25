import subprocess
import sys

from typer.testing import CliRunner

from tizita.cli import app

runner = CliRunner()


def test_help_lists_spec_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ["smoke", "models", "validate", "plan", "run", "radio-cut", "costs", "serve"]:
        assert cmd in result.output


def test_stub_exits_2_with_milestone():
    result = runner.invoke(app, ["approve"])
    assert result.exit_code == 2


def test_models_status_without_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    result = runner.invoke(app, ["models", "status"])
    assert result.exit_code == 0
    assert "No manifest" in result.output


def test_models_status_reads_manifest(tmp_path, monkeypatch):
    (tmp_path / "MANIFEST.json").write_text(
        '{"dinov2-small": {"name": "dinov2-small", "status": "ok", '
        '"repo_id": "facebook/dinov2-small", "size_bytes": 88000000}}'
    )
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    result = runner.invoke(app, ["models", "status"])
    assert result.exit_code == 0
    assert "dinov2-small" in result.output


def test_cli_import_is_light():
    """Heavy ML libraries must be imported lazily (CLAUDE.md engineering rules)."""
    code = (
        "import sys, tizita.cli; "
        "bad=[m for m in ('torch','transformers','open_clip','diffusers') if m in sys.modules]; "
        "print(','.join(bad)); sys.exit(1 if bad else 0)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout


def test_validate_lint_plan_on_fixture(project, monkeypatch):
    monkeypatch.setenv("TIZITA_ROOT", str(project.root))
    assert runner.invoke(app, ["validate"]).exit_code == 0
    res = runner.invoke(app, ["lint", "--json"])
    assert res.exit_code == 0 and '"ok": true' in res.output
    res = runner.invoke(app, ["plan"])
    assert res.exit_code == 0 and "narration" in res.output
    assert runner.invoke(app, ["plan", "--check"]).exit_code == 1
    assert (project.root / "logs" / "events.jsonl").exists()


def test_providers_lists_chains(project, monkeypatch):
    monkeypatch.setenv("TIZITA_ROOT", str(project.root))
    monkeypatch.setenv("MODELS_DIR", str(project.root / "none"))
    res = runner.invoke(app, ["providers", "--capability", "image"])
    assert res.exit_code == 0, res.output
    assert "cf_flux2_klein" in res.output and "profile free" in res.output

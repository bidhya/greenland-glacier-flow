#!/usr/bin/env python3
"""
Step 1 smoke test - job file generation.

Generates job files for both satellites with --dry-run true and asserts the
important lines are present. Takes seconds, downloads nothing, submits nothing.

WHY THIS EXISTS
---------------
Catches config/argparse breakage before a production run: a renamed flag, a
config.ini key that stopped resolving, a broken f-string in the job template.
None of that shows up until a job is submitted and fails hours later - or
worse, runs on the wrong interpreter and succeeds with the wrong output.

The activation guard is the specific line worth protecting. Job scripts have no
`set -e`, and `eval "$(conda shell.bash hook)"` exits 0 even when broken, so a
failed activation silently falls through to the ambient PATH and the job appears
to succeed on the wrong Python. The guard aborts instead. If it ever goes
missing from the template, this test fails.

BOTH GENERATORS ARE EXERCISED
-----------------------------
submit_satellite_job.py has two job builders - create_bash_job (local) and
create_slurm_job (HPC) - and only one runs on any given machine. --execution-mode
forces each in turn, so both are covered from either machine.

WRITES NOTHING PERMANENT
------------------------
Everything is redirected to a temporary directory, so the real output tree is
untouched.

Redirection is done with a temporary --config file, NOT --base-dir. In local
execution mode the generator overrides base_dir with config.ini's
local_base_dir (submit_satellite_job.py, in the execution-mode block), so
--base-dir alone does not redirect a local-mode run - it would write into the
real local output tree. Rewriting both keys in a temp config is the only way to
redirect both modes. That precedence quirk is pre-existing behaviour and is
deliberately NOT worked around anywhere except here.

EXIT CODES
----------
  0  all generated job files contain the expected content
  1  a job file was missing, or missing expected content

USAGE
-----
    python check_job_generation.py
    python check_job_generation.py --env glacier_velocity1

See 1_download_merge_and_clip/tests/README.md for copy-paste ready commands.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import typer

app = typer.Typer()

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "submit_satellite_job.py"

# Region and dates are arbitrary - nothing is downloaded. They only need to
# reach the generated command line so we can assert they were passed through.
TEST_REGION = "138_SermiitsiaqInTasermiut"
TEST_DATE1 = "2024-08-01"
TEST_DATE2 = "2024-08-07"

PROCESSING_SCRIPT = {
    "sentinel2": "sentinel2/download_merge_clip_sentinel2.py",
    "landsat": "landsat/download_clip_landsat.py",
}


def required_lines(satellite: str, env: str):
    """(description, substring) pairs that must appear in the generated job."""
    return [
        ("conda activation", f"conda activate {env}"),
        ("activation guard", "FATAL: conda activate failed"),
        ("guard checks env name", f"'{env}'"),
        ("processing script", PROCESSING_SCRIPT[satellite]),
        ("region passed through", TEST_REGION),
        ("date1 passed through", TEST_DATE1),
        ("date2 passed through", TEST_DATE2),
    ]


def temp_config(base_dir: Path, tmp: Path) -> Path:
    """Copy config.ini with both output paths pointed at a temp dir.

    Both keys must be rewritten: local execution mode ignores --base-dir in
    favour of local_base_dir (see module docstring).
    """
    import configparser

    source = REPO_ROOT / "config.ini"
    if not source.exists():
        raise FileNotFoundError(
            f"config.ini not found at {source}. Copy config.template.ini to config.ini first."
        )

    cfg = configparser.ConfigParser()
    cfg.read(source)
    if not cfg.has_section("PATHS"):
        raise KeyError(f"{source} has no [PATHS] section - cannot redirect output for testing")

    cfg["PATHS"]["base_dir"] = str(base_dir)
    cfg["PATHS"]["local_base_dir"] = str(base_dir)

    path = tmp / f"config_{base_dir.name}.ini"
    with open(path, "w") as fh:
        cfg.write(fh)
    return path


def generate(satellite: str, mode: str, base_dir: Path, env: str, tmp: Path, generator: Path):
    """Run the generator in dry-run mode. Returns (job_path_or_None, stdout)."""
    cmd = [
        sys.executable, str(generator),
        "--config", str(temp_config(base_dir, tmp)),
        "--satellite", satellite,
        "--regions", TEST_REGION,
        "--date1", TEST_DATE1,
        "--date2", TEST_DATE2,
        "--base-dir", str(base_dir),
        "--execution-mode", mode,
        "--env", env,
        "--dry-run", "true",
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    output = proc.stdout + proc.stderr

    if proc.returncode != 0:
        return None, output

    # The generator prints the path it wrote; trust the filesystem over parsing.
    candidates = sorted((base_dir / "slurm_jobs" / satellite).glob("*.job"))
    return (candidates[-1] if candidates else None), output


@app.command()
def main(
    env: str = typer.Option("glacier_velocity", help="Conda environment name the job should activate"),
    keep: bool = typer.Option(False, "--keep", help="Keep generated job files for inspection"),
    generator: str = typer.Option(None, help="Alternative job generator to test (default: submit_satellite_job.py). Useful for checking a modified generator before committing it."),
):
    """Smoke-test job file generation for both satellites and both execution modes."""
    generator_path = Path(generator) if generator else GENERATOR
    if not generator_path.exists():
        typer.echo(f"Error: generator not found: {generator_path}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Generator: {generator_path}")
    typer.echo(f"Env:       {env}")
    typer.echo("")

    failures = []
    tmp = tempfile.mkdtemp(prefix="step1_smoke_")
    base_dir = Path(tmp)

    for satellite in ("sentinel2", "landsat"):
        for mode in ("local", "hpc"):
            label = f"{satellite} / {mode}"
            job_path, output = generate(satellite, mode, base_dir / mode, env, base_dir, generator_path)

            if job_path is None:
                typer.echo(f"❌ {label}: no job file generated")
                for line in output.strip().splitlines()[-5:]:
                    typer.echo(f"     {line}")
                failures.append(f"{label}: no job file generated")
                continue

            content = job_path.read_text()
            missing = [d for d, s in required_lines(satellite, env) if s not in content]

            if missing:
                typer.echo(f"❌ {label}: {job_path.name}")
                for d in missing:
                    typer.echo(f"     missing: {d}")
                    failures.append(f"{label}: missing {d}")
            else:
                typer.echo(f"✅ {label}: {job_path.name}")

    typer.echo("")
    typer.echo("=" * 60)
    if keep:
        typer.echo(f"Job files kept at: {base_dir}")
    else:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        typer.echo("Temporary job files removed (--keep to retain)")
    typer.echo("=" * 60)

    if failures:
        typer.echo("")
        typer.echo("❌ SMOKE TEST FAILED", err=True)
        for f in failures:
            typer.echo(f"     - {f}", err=True)
        typer.echo("", err=True)
        typer.echo("   If the activation guard is missing, a failed conda activate will", err=True)
        typer.echo("   fall through to the ambient PATH and the job will appear to succeed", err=True)
        typer.echo("   on the wrong interpreter.", err=True)
        raise typer.Exit(1)

    typer.echo("✅ All 4 job files generated with the expected content.")


if __name__ == "__main__":
    app()

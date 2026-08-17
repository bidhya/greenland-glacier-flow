#!/usr/bin/env python3
"""
Step 1 output structure check.

Asserts each processed region has the directories its workflow is supposed to
produce. Catches a run that exited 0 having produced only part of its output.

WHY THIS EXISTS
---------------
A Step 1 run can fail partway and still exit 0 - job scripts have no `set -e`.
The clipped rasters may be fine while `metadata/` or `template/` never got
written, and nothing downstream complains until Step 2 or Step 3 does.

This is cheap (directory stats only, no raster reads) and answers a question the
other tools do not: "is the output COMPLETE?", as opposed to "does it match?"
(compare_raster.py) or "is it well-formed?" (check_raster_sanity.py).

EXPECTED LAYOUT (verified against production output, August 14, 2026)
---------------
    sentinel2/{region}/clipped/     clipped scenes -> input to Step 2
    sentinel2/{region}/download/    raw downloads, nested by year
    sentinel2/{region}/metadata/    processing metadata
    sentinel2/{region}/template/    reference templates

    landsat/{region}/               clipped scenes directly, no subdirectories
    landsat/_reference/             STAC metadata/templates, shared across regions

⚠️ The two layouts are NOT symmetric. Sentinel-2 and Landsat were written by
different people, and reconciling them is an ongoing goal, not a finished state.
Do not "fix" the asymmetry here.

⚠️ `download/` is optional by design: it can be deleted after processing to free
storage (~15.56 TB was freed for 2024), so a missing download/ is reported as a
note, not a failure. clipped/ is the one that feeds Step 2 and must exist.

EXIT CODES
----------
  0  every region has its required directories
  1  at least one region is missing a required directory
  2  nothing found to check (not a pass)

USAGE
-----
    python check_output_structure.py sentinel2
    python check_output_structure.py landsat --run-mode hpc

See 1_download_merge_and_clip/tests/README.md for copy-paste ready commands.
"""

from pathlib import Path

import typer

from compare_raster import (
    HPC_CANDIDATE_ROOT,
    LOCAL_CANDIDATE_ROOT,
    detect_execution_mode,
    discover_regions,
)

app = typer.Typer()

# Per-region subdirectories that must exist.
REQUIRED = {
    "sentinel2": ["clipped", "metadata", "template"],
    "landsat": [],  # the region directory itself holds the scenes
}

# Present in normal operation but legitimately absent - reported, never fatal.
OPTIONAL = {
    "sentinel2": ["download"],  # deleted after processing to reclaim storage
    "landsat": [],
}

# Directories expected once per satellite, not per region.
SATELLITE_LEVEL = {
    "sentinel2": [],
    "landsat": ["_reference"],
}


@app.command()
def main(
    satellite: str = typer.Argument(..., help="Satellite type: 'sentinel2' or 'landsat'"),
    region: str = typer.Option(None, help="Region to check (default: every region found)"),
    run_mode: str = typer.Option("auto", help="Run mode: 'auto' (detect), 'local', or 'hpc'"),
    candidate: str = typer.Option(None, help="Explicit output root to check"),
):
    """Check that Step 1 output directories are complete."""
    if satellite not in REQUIRED:
        typer.echo(f"Error: Unsupported satellite '{satellite}'. Use 'sentinel2' or 'landsat'.", err=True)
        raise typer.Exit(1)

    if run_mode == "auto":
        run_mode = detect_execution_mode()

    if candidate:
        root = candidate
    elif run_mode == "local":
        root = LOCAL_CANDIDATE_ROOT
    elif run_mode == "hpc":
        root = HPC_CANDIDATE_ROOT
    else:
        typer.echo(f"Error: Invalid run_mode '{run_mode}'. Use 'auto', 'local', or 'hpc'", err=True)
        raise typer.Exit(1)

    satellite_root = Path(root) / "1_download_merge_and_clip" / satellite
    typer.echo(f"Satellite: {satellite}")
    typer.echo(f"Output:    {satellite_root}")
    typer.echo("")

    failures, notes = [], []

    # Satellite-level directories (e.g. landsat/_reference)
    for name in SATELLITE_LEVEL[satellite]:
        path = satellite_root / name
        if path.is_dir():
            typer.echo(f"✅ {name}/  (satellite level)")
        else:
            typer.echo(f"❌ {name}/  (satellite level) - MISSING")
            failures.append(f"{satellite}/{name} missing")

    if region:
        regions = [region]
    else:
        try:
            regions = discover_regions(satellite, root)
        except FileNotFoundError as e:
            typer.echo(f"🚫 {e}", err=True)
            typer.echo("   Nothing to check. This is NOT a pass.", err=True)
            raise typer.Exit(2)

    if not regions:
        typer.echo("🚫 No regions found. This is NOT a pass.", err=True)
        raise typer.Exit(2)

    typer.echo("")
    checked = 0

    for region_name in regions:
        region_path = satellite_root / region_name
        if not region_path.is_dir():
            typer.echo(f"❌ {region_name}: region directory missing")
            failures.append(f"{region_name}: region directory missing")
            continue

        checked += 1
        missing = [d for d in REQUIRED[satellite] if not (region_path / d).is_dir()]
        absent_optional = [d for d in OPTIONAL[satellite] if not (region_path / d).is_dir()]

        if missing:
            typer.echo(f"❌ {region_name}")
            for d in missing:
                typer.echo(f"     missing required: {d}/")
                failures.append(f"{region_name}: missing {d}/")
        else:
            tif_count = len(list(region_path.rglob("*.tif")))
            typer.echo(f"✅ {region_name}  ({tif_count} .tif)")

        for d in absent_optional:
            notes.append(f"{region_name}: {d}/ absent (optional)")

    typer.echo("")
    typer.echo("=" * 60)
    typer.echo(f"Regions checked: {checked}")
    typer.echo(f"Notes:           {len(notes)}")
    typer.echo(f"FAILED:          {len(failures)}")
    typer.echo("=" * 60)

    if notes:
        typer.echo("")
        typer.echo("Notes (not failures):")
        for n in notes[:10]:
            typer.echo(f"     - {n}")
        if len(notes) > 10:
            typer.echo(f"     ... and {len(notes) - 10} more")
        typer.echo("   download/ is deleted after processing to reclaim storage.")

    if checked == 0:
        typer.echo("🚫 No regions checked. This is NOT a pass.", err=True)
        raise typer.Exit(2)

    if failures:
        typer.echo("")
        typer.echo("❌ STRUCTURE CHECK FAILED", err=True)
        for f in failures:
            typer.echo(f"     - {f}", err=True)
        typer.echo("", err=True)
        typer.echo("   A Step 1 run can exit 0 having produced only part of its output.", err=True)
        raise typer.Exit(1)

    typer.echo("")
    typer.echo(f"✅ All {checked} regions have their expected directories.")


if __name__ == "__main__":
    app()

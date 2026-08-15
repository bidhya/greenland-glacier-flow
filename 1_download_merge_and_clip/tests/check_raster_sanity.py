#!/usr/bin/env python3
"""
Step 1 baseline-free sanity checks.

Validates Step 1 raster output against known invariants WITHOUT comparing to a
production baseline.

WHY THIS EXISTS
---------------
compare_raster.py answers "did anything change?" - it needs a baseline, so it
is structurally unable to check data that has no baseline. The 2026 season will
have none by definition. This script answers a different question: "is this
output sane?", which works on any data, new or old.

It is also the class of check that would have caught the historical `x_` prefix
corruption without needing a reference.

INVARIANTS (verified against production output, August 14, 2026)
----------
                CRS         resolution   dtype    nodata   bands
    sentinel2   EPSG:3413   10 m         uint16   0        1
    landsat     EPSG:3413   15 m         uint16   0        1

Derived by inspecting real production rasters, not assumed. Note that
landsat/_reference/*.tif are uint8 templates, NOT scene output - they live in a
directory starting with '_' and are excluded by region discovery, same as in
compare_raster.py.

CONTENT CHECKS
--------------
  - not entirely nodata (an all-nodata raster is a failed clip)
  - not constant (a single-valued raster is not imagery)
  - rasters within a region are not byte-identical to each other, which would
    mean the same scene was written repeatedly under different names

EXIT CODES
----------
  0  all rasters passed
  1  at least one raster failed a check
  2  nothing was found to check (not a pass)

USAGE
-----
    python check_raster_sanity.py sentinel2 --region 138_SermiitsiaqInTasermiut
    python check_raster_sanity.py landsat --run-mode hpc

See 1_download_merge_and_clip/tests/README.md for copy-paste ready commands.
"""

import hashlib
from pathlib import Path

import numpy as np
import rasterio
import typer
from rasterio.errors import RasterioIOError

# Reuse path logic rather than restating it. Sentinel-2 and Landsat nest at
# different depths, and duplicating that asymmetry is a known way to get it wrong.
from compare_raster import (
    HPC_CANDIDATE_ROOT,
    LOCAL_CANDIDATE_ROOT,
    build_paths,
    detect_execution_mode,
    discover_regions,
)

app = typer.Typer()

# Verified against production output, August 14, 2026.
EXPECTED = {
    "sentinel2": {"crs": "EPSG:3413", "res": (10.0, 10.0), "dtype": "uint16", "nodata": 0.0, "count": 1},
    "landsat":   {"crs": "EPSG:3413", "res": (15.0, 15.0), "dtype": "uint16", "nodata": 0.0, "count": 1},
}


def check_one(path: Path, expect: dict):
    """Check a single raster. Returns a list of failure strings (empty = passed)."""
    problems = []
    with rasterio.open(path) as src:
        if str(src.crs) != expect["crs"]:
            problems.append(f"CRS {src.crs} != {expect['crs']}")
        if src.res != expect["res"]:
            problems.append(f"resolution {src.res} != {expect['res']}")
        if src.dtypes[0] != expect["dtype"]:
            problems.append(f"dtype {src.dtypes[0]} != {expect['dtype']}")
        if src.nodata != expect["nodata"]:
            problems.append(f"nodata {src.nodata} != {expect['nodata']}")
        if src.count != expect["count"]:
            problems.append(f"{src.count} bands != {expect['count']}")

        data = src.read(1)

        nodata = expect["nodata"]
        if np.all(data == nodata):
            problems.append("entirely nodata - failed clip")
        elif data.min() == data.max():
            problems.append(f"constant value {data.min()} - not imagery")

    digest = hashlib.md5(data.tobytes()).hexdigest()
    return problems, digest


@app.command()
def main(
    satellite: str = typer.Argument(..., help="Satellite type: 'sentinel2' or 'landsat'"),
    region: str = typer.Option(None, help="Region to check (default: every region found)"),
    run_mode: str = typer.Option("auto", help="Run mode: 'auto' (detect), 'local', or 'hpc'"),
    candidate: str = typer.Option(None, help="Explicit candidate root to check"),
):
    """
    Validate Step 1 output against known invariants. No baseline required.
    """
    if satellite not in EXPECTED:
        typer.echo(f"Error: Unsupported satellite '{satellite}'. Use 'sentinel2' or 'landsat'.", err=True)
        raise typer.Exit(1)

    if run_mode == "auto":
        run_mode = detect_execution_mode()

    if candidate:
        candidate_root = candidate
    elif run_mode == "local":
        candidate_root = LOCAL_CANDIDATE_ROOT
    elif run_mode == "hpc":
        candidate_root = HPC_CANDIDATE_ROOT
    else:
        typer.echo(f"Error: Invalid run_mode '{run_mode}'. Use 'auto', 'local', or 'hpc'", err=True)
        raise typer.Exit(1)

    expect = EXPECTED[satellite]
    typer.echo(f"Satellite: {satellite}")
    typer.echo(f"Candidate: {candidate_root}")
    typer.echo(f"Expecting: {expect['crs']}, {expect['res'][0]}m, {expect['dtype']}, "
               f"nodata={expect['nodata']:g}, {expect['count']} band")
    typer.echo("")

    if region:
        regions = [region]
    else:
        try:
            regions = discover_regions(satellite, candidate_root)
        except FileNotFoundError as e:
            typer.echo(f"🚫 {e}", err=True)
            typer.echo("   Nothing to check. This is NOT a pass.", err=True)
            raise typer.Exit(2)

    checked, failed, empty_regions = 0, [], []

    for region_name in regions:
        # build_paths returns (candidate, baseline); only the candidate is used here.
        region_path = build_paths(satellite, region_name, candidate_root, candidate_root)[0]
        files = sorted(region_path.glob("*.tif"))

        if not files:
            empty_regions.append(region_name)
            continue

        typer.echo(f"--- {region_name} ({len(files)} raster{'' if len(files) == 1 else 's'}) ---")
        digests = {}

        for f in files:
            try:
                problems, digest = check_one(f, expect)
            except (RasterioIOError, OSError) as e:
                typer.echo(f"  ❌ {f.name}: unreadable ({e})", err=True)
                failed.append(f"{region_name}/{f.name}: unreadable")
                continue

            checked += 1

            # Two scenes with byte-identical pixels means the same data was
            # written twice under different names.
            if digest in digests:
                problems.append(f"pixel-identical to {digests[digest]}")
            else:
                digests[digest] = f.name

            if problems:
                typer.echo(f"  ❌ {f.name}")
                for p in problems:
                    typer.echo(f"       {p}")
                    failed.append(f"{region_name}/{f.name}: {p}")
            else:
                typer.echo(f"  ✅ {f.name}")

    typer.echo("")
    typer.echo("=" * 60)
    typer.echo(f"Rasters checked: {checked}")
    typer.echo(f"Regions with no data: {len(empty_regions)}")
    typer.echo(f"FAILED: {len(failed)}")
    typer.echo("=" * 60)

    if checked == 0:
        typer.echo("🚫 No rasters found to check. This is NOT a pass.", err=True)
        raise typer.Exit(2)

    if failed:
        typer.echo("")
        typer.echo("❌ SANITY CHECK FAILED", err=True)
        for f in failed:
            typer.echo(f"     - {f}", err=True)
        raise typer.Exit(1)

    typer.echo(f"✅ All {checked} rasters passed. Output is structurally sane.")
    typer.echo("   Note: this proves the output is well-formed, NOT that it matches")
    typer.echo("   production. Use compare_raster.py for that.")


if __name__ == "__main__":
    app()

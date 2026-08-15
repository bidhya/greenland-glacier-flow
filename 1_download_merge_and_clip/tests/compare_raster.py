#!/usr/bin/env python3
"""
Step 1 raster regression test.

Compares Step 1 output against a known-good production baseline, asserting the
rasters are bit-identical. This is the test that proves a code or environment
change did not alter delivered data.

PROVENANCE
----------
Copied from `qaqc/Step1/compare_raster.py` on August 14, 2026.

**This copy is authoritative.** The `qaqc/Step1/` version is the older
prototype, kept for reference only. `qaqc/` is gitignored, so it does not
travel with the repo; this copy does.

Changes made relative to the prototype (Phase 1 of docs/STEP1_TEST_PLAN.md):
  - A real value mismatch now FAILS. The prototype caught AssertionError in the
    same handler as missing data, so in all-regions mode a genuine regression
    printed "Skipped" and the script exited 0.
  - A missing or unreadable baseline file now SKIPS with a distinct exit code
    instead of crashing with an uncaught RasterioIOError.
  - Distinct exit codes (see below).
  - The subset-download skip is preserved exactly: if a candidate region has no
    .tif files it is skipped, because downloading a subset of regions is a
    legitimate, routine thing to do.

EXIT CODES
----------
  0  every raster compared was identical (or nothing was left to compare)
  1  at least one raster differed  -> REGRESSION, investigate
  2  at least one baseline was missing/unreadable, and nothing mismatched
     -> the comparison could not be made; not a pass

Note that 1 outranks 2: if anything mismatched, the exit code is 1.

USAGE
-----
    python compare_raster.py sentinel2 --region 138_SermiitsiaqInTasermiut
    python compare_raster.py landsat --region 140_CentralLindenow --run-mode hpc
    python compare_raster.py sentinel2 --region 104_sorgenfri --year 2025
    python compare_raster.py sentinel2 --baseline /path/to/tree --candidate /path/to/tree

    On HPC, allocate resources first - do not run on a login node:
    srun --cpus-per-task=1 --mem=16gb -t 01:00:00 -p howat,batch --pty bash -i

    Copy-paste ready commands: see 1_download_merge_and_clip/tests/README.md

CHOOSING A BASELINE
-------------------
`--year` selects which production tree to compare against on HPC:

    2025  /fs/project/howat.4-3/greenland_glacier_flow    (DEFAULT)
    2024  /fs/project/howat.4/greenland_glacier_flow      (shorter lifetime)

⚠️ The year must match the dates the CANDIDATE was produced with. Comparing
2024-dated output against the 2025 tree reports mismatches that are NOT
regressions. To reproduce the August 14, 2026 verification runs - which used
2024-dated data - pass --year 2024 explicitly.

2025 is the default because it survives until 2026 data is delivered, making
it the longer-lived reference. The resolved baseline is printed at the top of
every run, so check that line before trusting a result.

`--baseline` / `--candidate` override the roots entirely, for trees that are
not one of the known years.
"""

import os
import shutil
from pathlib import Path

import rioxarray
import typer
import xarray as xr
from rasterio.errors import RasterioIOError

app = typer.Typer()

# Production baseline roots per processing year.
# Origin: qaqc/data_paths.yml. That file lives in gitignored qaqc/, so the
# mapping is duplicated here to keep tests/ self-contained on a fresh clone.
# If a new year is added there, add it here too.
HPC_BASELINE_ROOTS = {
    "2024": "/fs/project/howat.4/greenland_glacier_flow",
    "2025": "/fs/project/howat.4-3/greenland_glacier_flow",
}
HPC_CANDIDATE_ROOT = "/fs/project/howat.4/yadav.111/greenland_glacier_flow"

# Local: a single saved production snapshot, not per-year. DO NOT DELETE the
# _prod tree - it is the only local baseline.
LOCAL_BASELINE_ROOT = "/home/bny/greenland_glacier_flow_prod"
LOCAL_CANDIDATE_ROOT = "/home/bny/greenland_glacier_flow"

# 2025 is the default: it survives until 2026 data is delivered, so it is the
# longer-lived reference. 2024 is the shorter-lived tree and may be cleared.
DEFAULT_YEAR = "2025"


class BaselineUnavailable(Exception):
    """The baseline file is missing or unreadable, so no comparison is possible.

    Distinct from 'the candidate region has no data', which is a legitimate
    subset download and is handled as an ordinary skip.
    """


def detect_execution_mode():
    """Auto-detect whether we're on HPC or local machine"""
    # Check if we're already in a SLURM job
    if os.getenv('SLURM_JOB_ID'):
        return 'hpc'

    # Check if sbatch command is available
    if shutil.which('sbatch'):
        return 'hpc'

    # Default to local execution
    return 'local'


def resolve_roots(run_mode: str, year: str, baseline: str, candidate: str):
    """
    Work out which candidate and baseline trees to compare.

    Explicit --baseline / --candidate win over --year, which wins over the
    run-mode defaults.

    Returns:
        tuple: (candidate_root, baseline_root, description)
    """
    if run_mode == "local":
        default_candidate, default_baseline = LOCAL_CANDIDATE_ROOT, LOCAL_BASELINE_ROOT
        # Local holds one saved snapshot, not a tree per year.
        source = "local snapshot"
        if year != DEFAULT_YEAR and not baseline:
            # Don't let --year look like it did something when it did not.
            typer.echo(
                f"⚠️  --year {year} ignored: local holds a single saved snapshot, "
                f"not a tree per year. Use --baseline to point elsewhere.",
                err=True,
            )
    elif run_mode == "hpc":
        if year not in HPC_BASELINE_ROOTS:
            known = ", ".join(sorted(HPC_BASELINE_ROOTS))
            raise ValueError(f"Unknown --year '{year}'. Known years: {known}")
        default_candidate, default_baseline = HPC_CANDIDATE_ROOT, HPC_BASELINE_ROOTS[year]
        source = f"HPC {year} production"
    else:
        raise ValueError(f"Invalid run_mode '{run_mode}'. Use 'auto', 'local', or 'hpc'")

    candidate_root = candidate or default_candidate
    baseline_root = baseline or default_baseline

    if candidate or baseline:
        source = "explicit path override"

    return candidate_root, baseline_root, source


def build_paths(satellite: str, region: str, candidate_root: str, baseline_root: str):
    """
    Build candidate and baseline paths for a given satellite and region.

    Sentinel-2 and Landsat use different output layouts - this is deliberate,
    the two workflows were written by different people. Do not "unify" it here.

    Returns:
        tuple: (candidate_path, baseline_path)
    """
    if satellite == "sentinel2":
        candidate_path = Path(f'{candidate_root}/1_download_merge_and_clip/{satellite}/{region}/clipped')
        baseline_path = Path(f'{baseline_root}/1_download_merge_and_clip/{satellite}/{region}/clipped')
    elif satellite == "landsat":
        candidate_path = Path(f'{candidate_root}/1_download_merge_and_clip/{satellite}/{region}')
        baseline_path = Path(f'{baseline_root}/1_download_merge_and_clip/{satellite}/{region}')
    else:
        raise ValueError(f"Unsupported satellite type '{satellite}'. Use 'sentinel2' or 'landsat'.")

    return candidate_path, baseline_path


def discover_regions(satellite: str, candidate_root: str):
    """
    Discover all available regions in the candidate output for a satellite.

    Returns:
        list: List of region names
    """
    candidate_path = Path(f"{candidate_root}/1_download_merge_and_clip/{satellite}/")

    if not candidate_path.exists():
        raise FileNotFoundError(f"Candidate path not found: {candidate_path}")

    # Get all subdirectories that look like regions (exclude _reference and other non-region dirs)
    regions = []
    for item in candidate_path.iterdir():
        if item.is_dir() and not item.name.startswith('_') and item.name != 'slurm_jobs':
            regions.append(item.name)

    return sorted(regions)


def compare_raster_files(candidate_path: Path, baseline_path: Path, region: str, satellite: str):
    """
    Compare raster files between candidate output and production baseline.

    `satellite` is passed in rather than inferred from path depth: Sentinel-2
    and Landsat nest at different depths, so inferring it printed
    "Satellite: 1_download_merge_and_clip" for Landsat.

    Returns:
        int: number of raster pairs compared

    Raises:
        FileNotFoundError:    candidate region has no .tif files (subset download)
        BaselineUnavailable:  baseline file missing or unreadable
        AssertionError:       rasters differ - a real regression
    """
    print(f"Satellite: {satellite}")
    print(f"Region: {region}")
    print(f"Comparing rasters in:")
    print(f"Candidate:  {candidate_path}")
    print(f"Baseline:   {baseline_path}")

    # Find raster files in the candidate output (the new files to verify)
    candidate_files = list(candidate_path.glob('*.tif'))
    if not candidate_files:
        # Legitimate: you can download a subset of regions and the rest have nothing.
        raise FileNotFoundError(f"No .tif files found in candidate output: {candidate_path}")

    print(f"Found {len(candidate_files)} raster files to compare")

    for candidate_file in candidate_files:
        baseline_file = baseline_path / candidate_file.name
        print(f"Comparing: {candidate_file.name}")

        da_candidate = rioxarray.open_rasterio(candidate_file, chunks="auto")

        # Open the baseline separately so a missing/unreadable baseline is
        # reported as "cannot compare", never as a pass and never as a crash.
        try:
            da_baseline = rioxarray.open_rasterio(baseline_file, chunks="auto")
        except (RasterioIOError, OSError) as e:
            raise BaselineUnavailable(f"baseline not readable: {baseline_file} ({e})") from e

        # Bit-identical check: values, coords, dtype, attrs.
        xr.testing.assert_identical(da_candidate, da_baseline)

    print(f"✅ Found and compared {len(candidate_files)} raster pairs - all identical!")
    return len(candidate_files)


@app.command()
def main(
    satellite: str = typer.Argument(..., help="Satellite type: 'sentinel2' or 'landsat'"),
    region: str = typer.Option(None, help="Region to compare (if not specified, compares all regions found in the candidate output)"),
    run_mode: str = typer.Option("auto", help="Run mode: 'auto' (detect), 'local', or 'hpc'"),
    year: str = typer.Option(DEFAULT_YEAR, help="Processing year selecting the HPC baseline tree: '2024' or '2025'. Must match the dates the candidate was produced with."),
    baseline: str = typer.Option(None, help="Explicit baseline root, overriding --year"),
    candidate: str = typer.Option(None, help="Explicit candidate root"),
):
    """
    Compare Step 1 raster output against the production baseline.

    Exits 0 if all identical, 1 on any mismatch, 2 if a baseline was unavailable.
    """
    if run_mode == "auto":
        run_mode = detect_execution_mode()

    try:
        candidate_root, baseline_root, source = resolve_roots(run_mode, year, baseline, candidate)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Run mode:  {run_mode}")
    typer.echo(f"Baseline:  {baseline_root}  ({source})")
    typer.echo(f"Candidate: {candidate_root}")
    typer.echo("")

    # Fail fast and unambiguously if the baseline tree is gone entirely - e.g.
    # the 2024 allocation being cleared. Without this the per-region handler
    # would report a pile of confusing "no baseline" messages instead.
    if not Path(baseline_root).exists():
        typer.echo(f"🚫 Baseline tree does not exist: {baseline_root}", err=True)
        typer.echo("   Nothing can be compared. This is NOT a pass.", err=True)
        if run_mode == "hpc":
            known = ", ".join(f"{y} -> {p}" for y, p in sorted(HPC_BASELINE_ROOTS.items()))
            typer.echo(f"   Known baselines: {known}", err=True)
        raise typer.Exit(2)

    if region is None:
        # Auto-discover and compare all regions
        try:
            regions = discover_regions(satellite, candidate_root)
        except FileNotFoundError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

        if not regions:
            typer.echo(f"Error: No regions found in candidate output for {satellite}", err=True)
            raise typer.Exit(1)

        typer.echo(f"Found {len(regions)} regions in candidate output: {', '.join(regions)}")

        matched, rasters, skipped, mismatched, unavailable = 0, 0, [], [], []

        for region_name in regions:
            typer.echo(f"\n--- Comparing region: {region_name} ---")
            try:
                candidate_path, baseline_path = build_paths(satellite, region_name, candidate_root, baseline_root)
                rasters += compare_raster_files(candidate_path, baseline_path, region_name, satellite)
                matched += 1
            except AssertionError as e:
                # A real regression. Must never be reported as a skip.
                typer.echo(f"❌ MISMATCH {region_name}: {e}", err=True)
                mismatched.append(region_name)
            except BaselineUnavailable as e:
                typer.echo(f"🚫 No baseline for {region_name}: {e}", err=True)
                unavailable.append(region_name)
            except (ValueError, FileNotFoundError) as e:
                # No candidate data for this region - a subset download. Fine.
                typer.echo(f"⚠️  Skipped {region_name}: {e}", err=True)
                skipped.append(region_name)

        typer.echo("\n" + "=" * 60)
        typer.echo(f"Satellite: {satellite}   Baseline: {baseline_root}")
        typer.echo("-" * 60)
        typer.echo(f"Matched:              {matched}/{len(regions)} regions ({rasters} raster{'' if rasters == 1 else 's'})")
        typer.echo(f"Skipped (no data):    {len(skipped)}")
        typer.echo(f"Baseline unavailable: {len(unavailable)}")
        typer.echo(f"MISMATCHED:           {len(mismatched)}")
        if mismatched:
            typer.echo(f"  -> {', '.join(mismatched)}")
        if unavailable:
            typer.echo(f"  no baseline: {', '.join(unavailable)}")
        typer.echo("=" * 60)

        if mismatched:
            typer.echo("❌ FAILED - output differs from baseline", err=True)
            raise typer.Exit(1)
        if unavailable:
            typer.echo("🚫 INCOMPLETE - baseline unavailable, comparison not made", err=True)
            raise typer.Exit(2)
        typer.echo("🎉 All compared regions identical to baseline")

    else:
        # Compare a specific region
        try:
            candidate_path, baseline_path = build_paths(satellite, region, candidate_root, baseline_root)
            compare_raster_files(candidate_path, baseline_path, region, satellite)
        except AssertionError as e:
            typer.echo(f"❌ MISMATCH: {e}", err=True)
            raise typer.Exit(1)
        except BaselineUnavailable as e:
            typer.echo(f"🚫 {e}", err=True)
            raise typer.Exit(2)
        except (ValueError, FileNotFoundError) as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
Step 1 preflight environment check.

Verifies the conda environment matches what Step 1 is known to produce correct
output with, BEFORE a production run starts. Environment drift is the failure
mode that changes delivered data without changing a line of code, so this is
designed to fail loudly rather than warn quietly.

WHY THIS EXISTS
---------------
`gdal=3.10.3` in environment.yml is the SINGLE point of protection against a
rasterio upgrade. rasterio links against a specific libgdal-core minor:

    rasterio 1.4.4  requires libgdal-core >=3.10.3,<3.11
    rasterio 1.5.0  requires libgdal-core >=3.13.2

There is no separate `rasterio<1.5` guard anywhere. If the GDAL pin is relaxed,
rasterio moves too, reopening the 1.5.0 compatibility work (CPLE warnings,
bilinear vs cubic resampling). Step 1 output goes to NSIDC and must match the
legacy format, so a silent resampling change is a delivery bug.

TWO TIERS
---------
environment.yml pins only `python=3.13` and `gdal=3.10.3`. rioxarray, xarray,
geopandas and numpy all FLOAT - a legitimate `conda env create` months from now
may resolve them differently. Hard-failing on those would fire on an honest
rebuild, and a check that cries wolf gets switched off.

    PINNED   (hard fail)  python 3.13.x, GDAL 3.10.3, rasterio 1.4.x
    ADVISORY (warn only)  rioxarray, xarray, geopandas, numpy

rasterio is checked at minor level: the constraint is "not 1.5", and a 1.4.5
patch release is not a reason to block production. GDAL is checked exactly,
because environment.yml says `gdal=3.10.3`, not a range.

GDAL version is read from `rasterio.__gdal_version__`, NOT `from osgeo import
gdal`. Step 1 has zero osgeo imports - all six live in Step 3 - and this keeps
it that way.

EXIT CODES
----------
  0  environment is good (advisory drift may still be reported)
  1  a PINNED dependency drifted, or a required package is missing

USAGE
-----
    python check_environment.py
    python check_environment.py --allow-version-drift   # warn instead of fail

See 1_download_merge_and_clip/tests/README.md for copy-paste ready commands.
"""

import sys

import typer

app = typer.Typer()

# What environment.yml actually pins. Drift here is a hard failure.
#   name -> (expected, how many version components to compare)
PINNED = {
    "python":   ("3.13",   2),   # environment.yml: python=3.13
    "GDAL":     ("3.10.3", 3),   # environment.yml: gdal=3.10.3 (exact)
    "rasterio": ("1.4",    2),   # transitive from the GDAL pin; must not reach 1.5
}

# Verified-good snapshot, August 14, 2026 - the set that produced 104 rasters
# bit-identical to production. NOT pinned in environment.yml, so drift here is
# reported but does not fail.
ADVISORY = {
    "rioxarray": "0.23.0",
    "xarray":    "2026.7.0",
    "geopandas": "1.1.4",
    "numpy":     "2.5.2",
}


def collect_versions():
    """Read installed versions. Returns (versions, import_errors)."""
    versions, errors = {}, {}

    versions["python"] = ".".join(str(n) for n in sys.version_info[:3])

    try:
        import rasterio
        versions["rasterio"] = rasterio.__version__
        # The GDAL rasterio is linked against - the thing that actually matters.
        versions["GDAL"] = rasterio.__gdal_version__
    except ImportError as e:
        errors["rasterio"] = str(e)

    for pkg in ADVISORY:
        try:
            versions[pkg] = __import__(pkg).__version__
        except ImportError as e:
            errors[pkg] = str(e)

    return versions, errors


def truncate(version: str, parts: int) -> str:
    """'3.13.15' with parts=2 -> '3.13'."""
    return ".".join(version.split(".")[:parts])


@app.command()
def main(
    allow_version_drift: bool = typer.Option(
        False,
        "--allow-version-drift",
        help="Report pinned-dependency drift as a warning instead of failing. "
             "For deliberate experiments in a non-production environment.",
    )
):
    """Check the conda environment against Step 1's pinned dependencies."""
    versions, errors = collect_versions()

    failures = []
    typer.echo("Step 1 preflight environment check")
    typer.echo("=" * 62)
    typer.echo(f"{'package':<12} {'found':<12} {'expected':<12} status")
    typer.echo("-" * 62)

    # Tier 1: pinned - drift is a hard failure
    for pkg, (expected, parts) in PINNED.items():
        found = versions.get(pkg)
        if found is None:
            typer.echo(f"{pkg:<12} {'MISSING':<12} {expected:<12} ❌ not importable")
            failures.append(f"{pkg} could not be imported: {errors.get(pkg, 'unknown')}")
            continue
        if truncate(found, parts) == expected:
            typer.echo(f"{pkg:<12} {found:<12} {expected:<12} ✅")
        else:
            typer.echo(f"{pkg:<12} {found:<12} {expected:<12} ❌ PINNED DRIFT")
            failures.append(f"{pkg}: expected {expected}, found {found}")

    # Tier 2: advisory - reported, never fatal
    advisory_drift = []
    for pkg, expected in ADVISORY.items():
        found = versions.get(pkg)
        if found is None:
            typer.echo(f"{pkg:<12} {'MISSING':<12} {expected:<12} ⚠️  not importable")
            advisory_drift.append(f"{pkg} not importable")
            continue
        if found == expected:
            typer.echo(f"{pkg:<12} {found:<12} {expected:<12} ✅")
        else:
            typer.echo(f"{pkg:<12} {found:<12} {expected:<12} ⚠️  differs (unpinned)")
            advisory_drift.append(f"{pkg}: verified-good {expected}, found {found}")

    typer.echo("=" * 62)

    if advisory_drift:
        typer.echo("")
        typer.echo("⚠️  Advisory: these packages are NOT pinned in environment.yml, so a")
        typer.echo("   legitimate rebuild can resolve them differently. Not a failure, but")
        typer.echo("   worth knowing before trusting a regression result:")
        for d in advisory_drift:
            typer.echo(f"     - {d}")

    if not failures:
        typer.echo("")
        typer.echo("✅ Environment matches the pinned dependencies. Safe to run Step 1.")
        raise typer.Exit(0)

    typer.echo("")
    typer.echo("❌ PINNED DEPENDENCY DRIFT", err=True)
    for f in failures:
        typer.echo(f"     - {f}", err=True)
    typer.echo("", err=True)
    typer.echo("   environment.yml pins python=3.13 and gdal=3.10.3. The GDAL pin is the", err=True)
    typer.echo("   only thing holding rasterio below 1.5.0 - there is no separate guard.", err=True)
    typer.echo("   Running Step 1 in this environment risks changing delivered output.", err=True)
    typer.echo("", err=True)
    typer.echo("   Rebuild:  conda env create -f environment.yml", err=True)

    if allow_version_drift:
        typer.echo("")
        typer.echo("⚠️  --allow-version-drift set: continuing despite the drift above.")
        typer.echo("   Do NOT use this for a production run.")
        raise typer.Exit(0)

    raise typer.Exit(1)


if __name__ == "__main__":
    app()

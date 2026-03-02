#!/usr/bin/env python3
"""
Count Step 1 imagery files per region for QAQC.

Reads HPC paths from qaqc/data_paths.yml and counts image files for each
glacier/region across three categories:
  - sentinel2_downloads : {sentinel2}/{region}/download/*.tif
  - sentinel2_clipped   : {sentinel2}/{region}/clipped/*.tif
  - landsat             : {landsat}/{region}/*.tif  (flat; skips _reference/)

Output is a CSV with one row per region, saved to qaqc/Step1/ so it can be
compared across years.

Usage:
    python count_step1_files.py              # defaults to 2025
    python count_step1_files.py --year 2024
    python count_step1_files.py --year 2025 --out-dir /tmp

NOTE: Run on HPC (or with the HPC filesystem mounted).  Paths are read from
qaqc/data_paths.yml — update that file first if paths change.
"""

import re
import time
from pathlib import Path

import pandas as pd
import typer
import yaml

app = typer.Typer()

# Image file extensions to count
IMAGE_EXTS = {".tif", ".tiff"}


# Only include directories that look like glacier regions: 3-digit prefix e.g. 001_, 022_, 192_
GLACIER_RE = re.compile(r"^\d{3}_")


def is_glacier_dir(name: str) -> bool:
    return bool(GLACIER_RE.match(name))


def count_images(directory: Path) -> int:
    """Count image files (tif/tiff) directly inside a directory (non-recursive)."""
    if not directory.exists():
        return 0
    return sum(1 for f in directory.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS)


def load_paths(year: str) -> dict:
    """Load qaqc/data_paths.yml and resolve full paths for the given year."""
    repo_root = Path(__file__).resolve().parents[2]
    yml_path = repo_root / "qaqc" / "data_paths.yml"
    with open(yml_path) as f:
        data = yaml.safe_load(f)

    if year not in data:
        raise ValueError(f"Year '{year}' not found in data_paths.yml. Available: {list(data.keys())}")

    p = data[year]
    root = Path(p["root"])
    step1 = p["step1"]

    return {
        "sentinel2": root / step1["subfolder"] / step1["sentinel2"],
        "landsat":   root / step1["subfolder"] / step1["landsat"],
    }


@app.command()
def main(
    year: str = typer.Option("2025", help="Processing year to count files for (must exist in data_paths.yml)"),
    out_dir: Path = typer.Option(
        None,
        file_okay=False,
        help="Directory to write output CSV (default: QAQC_Results/Step1/ from data_paths.yml, or qaqc/Step1/results/ on HPC)",
    ),
):
    """Count Step 1 imagery files per region and write a summary CSV."""
    t0 = time.time()

    # resolve output directory
    repo_root = Path(__file__).resolve().parents[2]
    if out_dir is None:
        out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    # load paths from data_paths.yml
    try:
        paths = load_paths(year)
    except ValueError as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(1)

    s2_root   = paths["sentinel2"]
    ls_root   = paths["landsat"]

    typer.echo(f"Year          : {year}")
    typer.echo(f"Sentinel-2 dir: {s2_root}")
    typer.echo(f"Landsat dir   : {ls_root}")

    # ------------------------------------------------------------------ #
    # Collect all region names across both satellites
    # ------------------------------------------------------------------ #
    s2_regions = sorted(
        d.name for d in s2_root.iterdir()
        if d.is_dir() and is_glacier_dir(d.name)
    ) if s2_root.exists() else []

    ls_regions = sorted(
        d.name for d in ls_root.iterdir()
        if d.is_dir() and is_glacier_dir(d.name)
    ) if ls_root.exists() else []

    all_regions = sorted(set(s2_regions) | set(ls_regions))
    typer.echo(f"Total regions : {len(all_regions)}  "
               f"(S2: {len(s2_regions)}, Landsat: {len(ls_regions)})")

    # ------------------------------------------------------------------ #
    # Count files per region
    # ------------------------------------------------------------------ #
    records = []
    for region in all_regions:
        # downloads are nested under a year subfolder: download/{year}/*.tif
        s2_downloads = count_images(s2_root / region / "download" / year)
        s2_clipped   = count_images(s2_root / region / "clipped")
        ls_files     = count_images(ls_root / region)

        records.append({
            "region":               region,
            "sentinel2_downloads":  s2_downloads,
            "sentinel2_clipped":    s2_clipped,
            "landsat":              ls_files,
        })

    df = pd.DataFrame(records)

    # ------------------------------------------------------------------ #
    # Save CSV
    # ------------------------------------------------------------------ #
    csv_path = out_dir / f"step1_file_counts_{year}.csv"
    df.to_csv(csv_path, index=False)

    elapsed = time.time() - t0
    typer.echo(f"Wrote {len(df)} rows → {csv_path}  ({elapsed:.1f}s)")

    # quick summary
    typer.echo("\nSummary:")
    typer.echo(f"  Regions with S2 downloads : {(df['sentinel2_downloads'] > 0).sum()}")
    typer.echo(f"  Regions with S2 clipped   : {(df['sentinel2_clipped'] > 0).sum()}")
    typer.echo(f"  Regions with Landsat      : {(df['landsat'] > 0).sum()}")
    typer.echo(f"  Regions with ALL three    : {((df['sentinel2_downloads'] > 0) & (df['sentinel2_clipped'] > 0) & (df['landsat'] > 0)).sum()}")


if __name__ == "__main__":
    app()

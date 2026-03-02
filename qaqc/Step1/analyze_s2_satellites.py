#!/usr/bin/env python3
"""
Breakdown of Sentinel-2 clipped (and downloaded) files per satellite
(S2A, S2B, S2C) per region for a given processing year.

Satellite is determined from the first field of the filename, e.g.:
  S2B_MSIL2A_20250520T233739_N0511_R073.tif  →  S2B
  S2A_MSIL2A_20250120T143521_N0511_R139_T22VFP_20250120T171148_B08.tif  →  S2A

Downloads are counted from  sentinel2/{region}/download/{year}/*.tif
Clipped   are counted from  sentinel2/{region}/clipped/*.tif  (flat, no year subfolder)

Output CSV columns:
  region,
  s2a_downloads, s2b_downloads, s2c_downloads, total_downloads,
  s2a_clipped,   s2b_clipped,   s2c_clipped,   total_clipped

## Sentinel-2 Constellation Context
S2C launched November 2024 and replaced S2A as the primary "A-unit" from January 2025.
S2A dropped to a ~20-day revisit cycle outside Europe due to orbital maneuvers and
experimental nighttime imaging campaigns (ref: Copernicus S2A Extended Campaign Mar 2025).

Expected satellite mix:
  2024: S2A ✓  S2B ✓  S2C ∅ (none, or trace from late-2024 launch)
  2025: S2A ⚠ (fewer)  S2B ✓  S2C ✓ (new primary)

Expected outcomes when comparing 2024 vs 2025 clipped counts:
  S2B       : comparable between years (fully operational both years)
  S2C       : ~0 in 2024, substantial in 2025
  S2A       : fewer in 2025 than 2024 (maneuver/reduced revisit)
  net total : 2025 >= 2024 if S2C adoption was successful in the workflow

Confirmed from HPC (glacier 101):
  2024 clipped: S2A=89, S2B=103, S2C=0   total=192
  2025 clipped: S2A=75, S2B=99,  S2C=87  total=261
  → S2C present and well-represented in 2025 ✓
  → S2A reduced in 2025 as expected ✓
  → net 2025 total higher than 2024 ✓

Usage:
    python analyze_s2_satellites.py              # defaults to 2025
    python analyze_s2_satellites.py --year 2024
    python analyze_s2_satellites.py --year 2025 --out-dir /some/path

Run on HPC via SLURM wrapper (from qaqc/):
    sbatch run_qaqc_job.sh --step Step1 --script analyze_s2_satellites.py --year 2025
"""

import re
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import typer
import yaml

app = typer.Typer()

IMAGE_EXTS   = {".tif", ".tiff"}
GLACIER_RE   = re.compile(r"^\d{3}_")
SATELLITE_RE = re.compile(r"^(S2[ABC])_", re.IGNORECASE)
SATELLITES   = ["S2A", "S2B", "S2C"]


def is_glacier_dir(name: str) -> bool:
    return bool(GLACIER_RE.match(name))


def satellite_of(filename: str) -> str | None:
    """Return 'S2A', 'S2B', or 'S2C' from a filename, or None if unrecognised."""
    m = SATELLITE_RE.match(filename)
    return m.group(1).upper() if m else None


def count_by_satellite(directory: Path) -> dict[str, int]:
    """Count image files in a directory, keyed by satellite prefix."""
    counts: dict[str, int] = defaultdict(int)
    if not directory.exists():
        return counts
    for f in directory.iterdir():
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
            sat = satellite_of(f.name)
            if sat:
                counts[sat] += 1
            else:
                counts["OTHER"] += 1
    return counts


def load_s2_root(year: str) -> Path:
    """Resolve the sentinel2 root directory from qaqc/data_paths.yml."""
    repo_root = Path(__file__).resolve().parents[2]
    yml_path = repo_root / "qaqc" / "data_paths.yml"
    with open(yml_path) as f:
        data = yaml.safe_load(f)
    if year not in data:
        raise ValueError(f"Year '{year}' not found in data_paths.yml. Available: {list(data.keys())}")
    p = data[year]
    step1 = p["step1"]
    return Path(p["root"]) / step1["subfolder"] / step1["sentinel2"]


@app.command()
def main(
    year: str = typer.Option("2025", help="Processing year (must exist in data_paths.yml)"),
    out_dir: Path = typer.Option(
        None,
        file_okay=False,
        help="Directory to write output CSV (default: QAQC_Results/Step1/ from data_paths.yml, or qaqc/Step1/results/ on HPC)",
    ),
):
    """Count S2 clipped and downloaded files per region broken down by satellite."""
    t0 = time.time()

    if out_dir is None:
        out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        s2_root = load_s2_root(year)
    except ValueError as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(1)

    typer.echo(f"Year          : {year}")
    typer.echo(f"Sentinel-2 dir: {s2_root}")

    if not s2_root.exists():
        typer.echo(f"ERROR: directory does not exist: {s2_root}")
        raise typer.Exit(1)

    regions = sorted(d.name for d in s2_root.iterdir() if d.is_dir() and is_glacier_dir(d.name))
    typer.echo(f"Regions       : {len(regions)}")

    records = []
    for region in regions:
        dl_counts  = count_by_satellite(s2_root / region / "download" / year)
        cl_counts  = count_by_satellite(s2_root / region / "clipped")

        records.append({
            "region":         region,
            "s2a_downloads":  dl_counts.get("S2A", 0),
            "s2b_downloads":  dl_counts.get("S2B", 0),
            "s2c_downloads":  dl_counts.get("S2C", 0),
            "total_downloads": sum(dl_counts.values()),
            "s2a_clipped":    cl_counts.get("S2A", 0),
            "s2b_clipped":    cl_counts.get("S2B", 0),
            "s2c_clipped":    cl_counts.get("S2C", 0),
            "total_clipped":  sum(cl_counts.values()),
        })

    df = pd.DataFrame(records)

    csv_path = out_dir / f"s2_satellite_counts_{year}.csv"
    df.to_csv(csv_path, index=False)

    elapsed = time.time() - t0
    typer.echo(f"Wrote {len(df)} rows → {csv_path}  ({elapsed:.1f}s)")

    # Summary totals
    typer.echo("\nSummary (all regions):")
    typer.echo(f"  {'Satellite':<8} {'Downloads':>12} {'Clipped':>12}")
    typer.echo(f"  {'-'*34}")
    for sat in SATELLITES:
        dl = df[f"{sat.lower()}_downloads"].sum()
        cl = df[f"{sat.lower()}_clipped"].sum()
        typer.echo(f"  {sat:<8} {dl:>12,} {cl:>12,}")
    typer.echo(f"  {'TOTAL':<8} {df['total_downloads'].sum():>12,} {df['total_clipped'].sum():>12,}")


if __name__ == "__main__":
    app()

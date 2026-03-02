#!/usr/bin/env python3
"""
Simple metadata extractor for Step 3 delivery NetCDF files.

This command‑line utility is intentionally lightweight and designed for
iterative exploration. It visits each NetCDF, extracts basic information
(shape, glacier identifier, mean velocities, ice coverage, etc.), and
writes the results into a CSV table.

Output is broken out by year (parsed from the filename), with each invocation
replacing the previous CSV for that year.  Optionally the run can be forced
to write a custom prefix and/or execute serially for timing comparisons.

Usage examples:
```bash
# process an entire delivery directory (parallel by default)
python3 extract_metadata.py /fs/project/howat.4-3/…/nsidic_v01.1_delivery/

# run on a single sample file
python extract_metadata.py sample/014_Courtauld_2025_v01.1.nc

# specify a different output directory
python extract_metadata.py /data/2024/*.nc --out-dir /tmp/meta

# run serially and use a custom prefix for output file names
python extract_metadata.py /data/2025/*.nc --prefix serial_metadata --no-parallel
```

Metadata currently recorded per file:
- `glacier` (e.g. `014_Courtauld`)
- `year`
- dimensions (`index_size`, `y_size`, `x_size`)
- mean velocities (`mean_vx`, `mean_vy`)
- mean ice coverage (`mean_ice_pct`)
- `creation_date` attribute

Additional fields and statistics can be added later as the QAQC workflow
matures.
"""
import re
import time
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ProcessPoolExecutor

import pandas as pd
import typer
import xarray as xr
import yaml

app = typer.Typer()

# ---------------------------------------------------------------------------
# testing helper: list of glacier prefixes to restrict processing to a small
# subset when developing.  Each entry should include the trailing underscore so
# that we match only glacier IDs (e.g. '001_', '050_', '180_').  Leave the list
# empty to process every file in the directory.
SAMPLE_PREFIXES: List[str] = [
    # "001_", "140_", "138_", "178_",
    # "180_",
]
# ---------------------------------------------------------------------------

YEAR_RE = re.compile(r"_(\d{4})_")


def extract_year_from_name(name: str) -> str:
    match = YEAR_RE.search(name)
    return match.group(1) if match else ""


def file_to_record(path: Path) -> dict:
    """Extract a dict of metadata for a single NetCDF file."""
    ds = xr.open_dataset(path, decode_timedelta=True)
    rec: dict = {}

    # use glacier prefix as identifier
    rec["glacier"] = path.stem.split("_")[:2]  # e.g. "014_Courtauld"
    rec["glacier"] = "_".join(rec["glacier"])
    rec["year"] = extract_year_from_name(path.name)
    rec["index_size"] = ds.sizes.get("index", "")
    rec["y_size"] = ds.sizes.get("y", "")
    rec["x_size"] = ds.sizes.get("x", "")

    # statistics (assume variables exist)
    rec["mean_vx"] = float(ds["vx"].mean().item())
    rec["mean_vy"] = float(ds["vy"].mean().item())
    rec["mean_ice_pct"] = float(ds["percent_ice_area_notnull"].mean().item())

    # capture creation_date attribute if present
    rec["creation_date"] = ds.attrs.get("creation_date", "")

    ds.close()
    return rec


def _resolve_delivery_dir(year: str) -> Path:
    """Resolve delivery directory from data_paths.yml for the given year."""
    repo_root = Path(__file__).resolve().parents[2]
    yml_path = repo_root / "qaqc" / "data_paths.yml"
    with open(yml_path) as f:
        data = yaml.safe_load(f)
    if year not in data:
        raise ValueError(f"Year '{year}' not found in data_paths.yml. Available: {list(data.keys())}")
    p = data[year]
    return Path(p["root"]) / p["step3"]["subfolder"] / p["step3"]["delivery"]


@app.command()
def main(
    dirs: Optional[List[Path]] = typer.Argument(default=None, help="Directory(ies) containing NetCDF files. If omitted, --year must be provided to resolve path from data_paths.yml."),
    year: Optional[str] = typer.Option(None, help="Processing year (e.g. 2025). Resolves delivery dir from data_paths.yml. Ignored if dirs are provided explicitly."),
    out_dir: Path = typer.Option(
        None,
        file_okay=False,
        help="Directory where yearly CSVs will be stored; defaults to the qaqc/Step3 folder in the repo root (created if necessary)",
    ),
    parallel: bool = typer.Option(True, help="Run file_to_record calls in parallel (set to false for serial test)"),
    prefix: str = typer.Option("metadata", help="Prefix to use for output filename (e.g. 'serial_metadata' or 'parallel_metadata')"),
):
    """Extract metadata from each NetCDF file and append to yearly CSV."""

    # resolve delivery directory: explicit dirs take priority, then --year via data_paths.yml
    if not dirs:
        if not year:
            typer.echo("ERROR: provide either a directory argument or --year.", err=True)
            raise typer.Exit(1)
        delivery_dir = _resolve_delivery_dir(year)
        typer.echo(f"Resolved delivery dir for {year}: {delivery_dir}")
        dirs = [delivery_dir]

    # compute default output directory relative to repository root
    if out_dir is None:
        repo_root = Path(__file__).resolve().parents[2]
        out_dir = repo_root / "qaqc" / "Step3"

    # ensure the output directory exists
    out_dir.mkdir(parents=True, exist_ok=True)

    # start timer for overall run
    t0 = time.time()

    # gather all .nc files from the provided directory list
    all_files: List[Path] = []
    for d in dirs:
        all_files.extend(sorted(d.glob("*.nc")))
    # all_files = all_files[:50]  # TEMP: limit to few files for testing; remove this line to process all files

    # if SAMPLE_PREFIXES is populated, restrict to those glaciers only
    if SAMPLE_PREFIXES:
        filtered: List[Path] = []
        for p in all_files:
            for pref in SAMPLE_PREFIXES:
                if p.name.startswith(pref):
                    filtered.append(p)
                    break
        all_files = filtered

    # group files by year
    by_year: dict[str, List[Path]] = {}
    for p in all_files:
        yr = extract_year_from_name(p.name)
        if yr == "":
            typer.echo(f"⚠️  cannot determine year from filename '{p.name}'")
            continue
        by_year.setdefault(yr, []).append(p)

    for yr, paths in by_year.items():
        year_start = time.time()
        csv_path = out_dir / f"{prefix}_{yr}.csv"
        cols = [
            "glacier",
            "year",
            "index_size",
            "y_size",
            "x_size",
            "mean_vx",
            "mean_vy",
            "mean_ice_pct",
            "creation_date",
        ]

        # always overwrite existing file with fresh data
        write_header = True
        mode = "w"

        # gather records serially or in parallel according to flag
        if parallel:
            with ProcessPoolExecutor() as pool:
                records = list(pool.map(file_to_record, paths))
        else:
            records = [file_to_record(p) for p in paths]

        df = pd.DataFrame(records)
        df = df[cols]
        df.to_csv(csv_path, mode=mode, header=write_header, index=False)

        year_elapsed = time.time() - year_start
        typer.echo(f"Wrote {len(paths)} records to {csv_path} (took {year_elapsed:.1f}s)")

    total_elapsed = time.time() - t0
    typer.echo(f"Total runtime: {total_elapsed:.1f}s")


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
NetCDF Comparison Script for Step 3
**WARNING:** this script is a rapidly‑evolving prototype stored in the
`qaqc/Step3` folder. The folder itself is git‑ignored; you must manually
copy or rsync the latest version to the HPC node and update the hard‑coded
paths/years in the file whenever you switch datasets. Do *not* expect
changes here to be tracked by git.

Compares NetCDF files between development and production environments.

This script runs on HPC (or any environment) as long as the paths are correctly configured.
The development environment typically contains a subset of glaciers compared to production.
The script discovers glaciers from development and compares only those that exist in both environments.

Usage:
    python compare_netcdf.py --glacier 134_Arsuk
    python compare_netcdf.py --mode structure  # check only x/y dimensions
    python compare_netcdf.py  # Compare all glaciers in base1 environment (default 'data' mode)

Additional runtime options allow you to point at arbitrary directory roots:
    --base1 PATH   # first environment (default points at current dev path)
    --base2 PATH   # second environment (default points at current prod path)
    --reverse      # swap the two bases before performing comparisons

The script will automatically extract a year tag from each base path
and substitute between them when matching filenames. This makes it easier
to compare, for example, 2025 development data against a 2024 production
baseline without editing the script.

The script verifies that NetCDF files in base1 match those in base2
(or checks structural consistency when run in 'structure' mode').
"""
import typer
from pathlib import Path
import xarray as xr
import time

# Configuration constants
app = typer.Typer()

def build_paths(filename: str, dev_base: str, prod_base: str):
    """
    Build development and production paths for a given NetCDF file.

    Args:
        filename: NetCDF filename (e.g., '134_Arsuk_2025_v01.1.nc')
        dev_base: Base WD path for development environment
        prod_base: Base WD path for production environment

    Returns:
        tuple: (development_path, production_path)
    """
    # Step 3 final delivery structure: {WD}/nsidic_v01.1_delivery/{filename}
    dev_path = Path(f'{dev_base}/nsidic_v01.1_delivery/{filename}')
    prod_path = Path(f'{prod_base}/nsidic_v01.1_delivery/{filename}')

    return dev_path, prod_path

def discover_glaciers(dev_base: str):
    """
    Discover all available NetCDF files in the development environment.

    Args:
        dev_base: Base WD path for development environment

    Returns:
        list: List of .nc filenames
    """
    delivery_path = Path(f"{dev_base}/nsidic_v01.1_delivery")

    # if the directory doesn't exist, return empty list rather than crashing
    if not delivery_path.exists():
        return []

    # Get all .nc files
    nc_files = []
    for item in delivery_path.iterdir():
        if item.is_file() and item.suffix == '.nc':
            nc_files.append(item.name)

    return sorted(nc_files)

def compare_netcdf_files(dev_path: Path, prod_path: Path, filename: str):
    """
    Compare NetCDF files between development and production environments.

    Args:
        dev_path: Development environment NetCDF file path
        prod_path: Production environment NetCDF file path
        filename: NetCDF filename for logging
    """
    # print(f"Comparing NetCDF files:")
    # print(f"Development: {dev_path}")
    # print(f"Production: {prod_path}")

    # Load NetCDF files with xarray
    try:
        dev_ds = xr.open_dataset(dev_path, decode_timedelta=True)
        prod_ds = xr.open_dataset(prod_path, decode_timedelta=True)
    except Exception as e:
        raise RuntimeError(f"Error loading NetCDF files: {e}")

    # Remove creation_date attribute as it will differ between environments
    dev_ds.attrs.pop('creation_date', None)
    prod_ds.attrs.pop('creation_date', None)

    # Compare data variables (the actual scientific data) instead of requiring identical metadata
    try:
        # xr.testing.assert_equal(dev_ds, prod_ds)  # will ignore attrs difference 
        xr.testing.assert_identical(dev_ds, prod_ds)  #  
        print(f"✅ {filename:<40} NetCDF data is identical!")

    except AssertionError as e:
        print(f"❌ {filename:<40} NetCDF data differs: {e}")
        raise
    finally:
        # Close datasets
        dev_ds.close()
        prod_ds.close()


def compare_structure(dev_path: Path, prod_path: Path, filename: str):
    """
    Perform a lightweight structural comparison of two NetCDF files.

    Currently checks that the x and y dimensions match. Other structural
    sanity checks can be added later as needed.
    """
    try:
        dev_ds = xr.open_dataset(dev_path, decode_timedelta=True)
        prod_ds = xr.open_dataset(prod_path, decode_timedelta=True)
    except Exception as e:
        raise RuntimeError(f"Error loading NetCDF files: {e}")

    try:
        # use `.sizes` rather than `.dims` to avoid FutureWarning about return type
        dx = dev_ds.sizes.get("x")
        dy = dev_ds.sizes.get("y")
        px = prod_ds.sizes.get("x")
        py = prod_ds.sizes.get("y")
        idx_dev = dev_ds.sizes.get("index")
        idx_prod = prod_ds.sizes.get("index")
        if dx != px or dy != py:
            raise AssertionError(f"shape mismatch x:{dx}/{px}, y:{dy}/{py}")
        pct = None
        if idx_prod and idx_dev is not None:
            pct = round(idx_dev / idx_prod * 100, 1)
        pct_str = f" ({pct}%)" if pct is not None else ""
        print(
            f"🔍 {filename:<40} x/y dims match ({dx}×{dy}); index(dev/prod)={idx_dev}/{idx_prod}{pct_str}"
        )
    finally:
        dev_ds.close()
        prod_ds.close()

@app.command()
def main(
    glacier: str = typer.Option(None, help="Glacier to compare (if not specified, compares all NetCDF files found in development environment that also exist in production)"),
    mode: str = typer.Option("data", help="Comparison mode: 'data' (pixel-perfect) or 'structure' (dims/attrs only)"),
    base1: str = typer.Option(
        "/fs/project/howat.4-3/greenland_glacier_flow/2025_3_orthocorrect_and_netcdf-package",
        help="First environment root (default = development)",
    ),
    base2: str = typer.Option(
        "/fs/project/howat.4/greenland_glacier_flow/2024_3_orthocorrect_and_netcdf-package",
        help="Second environment root (default = production)",
    ),
    reverse: bool = typer.Option(False, help="Swap the two bases before comparing"),
):
    """
    Compare NetCDF files between development and production environments.
    """
    # Allow CLI options for the two roots and optionally swap them
    if reverse:
        dev_base, prod_base = base2, base1
    else:
        dev_base, prod_base = base1, base2

    # convenience helper to pull a year tag from the path name (first 4-digit component)
    def extract_year(path_str: str) -> str:
        name = Path(path_str).name
        for part in name.split("_"):
            if part.isdigit() and len(part) == 4:
                return part
        return ""

    # count files in delivery directories for quick sanity check
    dev_delivery = Path(f"{dev_base}/nsidic_v01.1_delivery")
    prod_delivery = Path(f"{prod_base}/nsidic_v01.1_delivery")
    dev_count = len(list(dev_delivery.glob("*.nc"))) if dev_delivery.exists() else 0
    prod_count = len(list(prod_delivery.glob("*.nc"))) if prod_delivery.exists() else 0
    print(f"Delivery counts - base1: {dev_count}, base2: {prod_count}")
    time.sleep(1)

    # derive year tags from the base paths (used for filename substitution)
    dev_year = extract_year(dev_base)
    prod_year = extract_year(prod_base)

    print("Pixel-Perfect NetCDF Comparison (but remove `creation_date` attribute)")
    print("======================================================================")
    print(f"Base1 (dev): {dev_base}  [year={dev_year}]")
    print(f"Base2 (prod): {prod_base}  [year={prod_year}]")
    print(f"Comparison mode: {mode}\n")
    print("---------------------------------------------------------------------\n")

    # Determine which files to compare
    if glacier:
        # Compare specific glacier - find matching .nc file in development
        delivery_path = Path(f"{dev_base}/nsidic_v01.1_delivery")
        matching_files = []
        if delivery_path.exists():
            for item in delivery_path.iterdir():
                if item.is_file() and item.suffix == '.nc' and item.name.startswith(glacier):
                    matching_files.append(item.name)
        
        if not matching_files:
            print(f"❌ No NetCDF file found for glacier '{glacier}' in development environment")
            return
        
        if len(matching_files) > 1:
            # also count how many matching files exist in production
            prod_delivery = Path(f"{prod_base}/nsidic_v01.1_delivery")
            prod_matches = []
            if prod_delivery.exists():
                for p in prod_delivery.iterdir():
                    if p.is_file() and p.suffix == '.nc' and p.name.startswith(glacier):
                        prod_matches.append(p.name)
            print(f"⚠️  Multiple files found for glacier '{glacier}': {matching_files} (prod has {len(prod_matches)})")
            print("Comparing all matching files...")
        
        files_to_compare = matching_files
    else:
        # Discover all available NetCDF files in the first base (base1)
        files_to_compare = discover_glaciers(dev_base)
        print(f"Found {len(files_to_compare)} NetCDF files in base1 environment")

    # Compare each file (only if it exists in both environments)
    success_count = 0
    skipped_count = 0
    for filename in files_to_compare:
        try:
            # adjust prod filename if year differs
            prod_filename = filename
            if dev_year != prod_year:
                prod_filename = filename.replace(dev_year, prod_year)
            dev_path, prod_path = build_paths(filename, dev_base, prod_base)
            prod_path = Path(f"{prod_base}/nsidic_v01.1_delivery/{prod_filename}")

            # Check if files exist in both environments
            if not dev_path.exists():
                print(f"⚠️  {filename}: base1 file not found")
                skipped_count += 1
                continue

            if not prod_path.exists():
                print(f"⚠️  {filename}: base2 file not found")
                skipped_count += 1
                continue

            if mode == "data":
                compare_netcdf_files(dev_path, prod_path, filename)
            else:
                compare_structure(dev_path, prod_path, filename)
            success_count += 1

        except Exception as e:
            print(f"❌ {filename}: Failed to compare: {e}")
            if glacier:  # If specific glacier requested, exit on error
                raise

    print(f"\n✅ Successfully compared {success_count}/{len(files_to_compare)} files")
    if skipped_count > 0:
        print(f"⚠️  Skipped {skipped_count} files (missing in one environment)")


if __name__ == "__main__":
    app()
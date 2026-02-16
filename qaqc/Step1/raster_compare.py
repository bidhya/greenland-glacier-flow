#!/usr/bin/env python3
"""
Satellite Raster Comparison Script
Compares rasters between glacier_velocity1 (development, new files) and glacier_velocity (production, baseline)

Usage:
    python raster_compare.py sentinel2  # Auto-compares all regions in development environment
    python raster_compare.py landsat --region 140_CentralLindenow  # Compare specific region
    conda run -n glacier_velocity1 python raster_compare.py landsat

The script verifies that new files in development match the production baseline.
"""

import rioxarray
import xarray as xr
from pathlib import Path
import typer

# Configuration constants
app = typer.Typer()

def build_paths(satellite: str, region: str, dev_base: str, prod_base: str):
    """
    Build development and production paths for a given satellite and region.
    
    Args:
        satellite: Satellite type ('sentinel2' or 'landsat')
        region: Region name
        dev_base: Base path for development environment
        prod_base: Base path for production environment
    
    Returns:
        tuple: (development_path, production_path)
    """
    if satellite == "sentinel2":
        dev_path = Path(f'{dev_base}/1_download_merge_and_clip/{satellite}/{region}/clipped')
        prod_path = Path(f'{prod_base}/1_download_merge_and_clip/{satellite}/{region}/clipped')
    elif satellite == "landsat":
        dev_path = Path(f'{dev_base}/1_download_merge_and_clip/{satellite}/{region}')
        prod_path = Path(f'{prod_base}/1_download_merge_and_clip/{satellite}/{region}')
    else:
        raise ValueError(f"Unsupported satellite type '{satellite}'. Use 'sentinel2' or 'landsat'.")
    
    return dev_path, prod_path

def discover_regions(satellite: str, dev_base: str):
    """
    Discover all available regions in the development environment for a satellite.
    
    Args:
        satellite: Satellite type ('sentinel2' or 'landsat')
        dev_base: Base path for development environment
    
    Returns:
        list: List of region names
    """
    dev_base_path = f"{dev_base}/1_download_merge_and_clip/{satellite}/"
    dev_path = Path(dev_base_path)
    
    if not dev_path.exists():
        raise FileNotFoundError(f"Development path not found: {dev_path}")
    
    # Get all subdirectories that look like regions (exclude _reference and other non-region dirs)
    regions = []
    for item in dev_path.iterdir():
        if item.is_dir() and not item.name.startswith('_') and item.name != 'slurm_jobs':
            regions.append(item.name)
    
    return sorted(regions)

def compare_raster_files(dev_path: Path, prod_path: Path, region: str):
    """
    Compare raster files between development and production environments.
    
    Args:
        dev_path: Development environment path (new files, subset of production)
        prod_path: Production environment path (baseline)
        region: Region name for logging
    """
    print(f"Satellite: {dev_path.parent.parent.name}")  # Extract satellite from path
    print(f"Region: {region}")
    print(f"Comparing rasters in:")
    print(f"Development: {dev_path}")
    print(f"Production: {prod_path}")

    # Find raster files in development (new files to verify)
    dev_files = list(dev_path.glob('*.tif'))
    if not dev_files:
        raise FileNotFoundError(f"No .tif files found in development: {dev_path}")

    print(f"Found {len(dev_files)} raster files to compare")

    for dev_file in dev_files:
        prod_file = prod_path / dev_file.name
        print(f"Comparing: {dev_file.name}")

        # Load rasters
        da_dev = rioxarray.open_rasterio(dev_file, chunks="auto")
        da_prod = rioxarray.open_rasterio(prod_file, chunks="auto")

        # Compare rasters directly
        xr.testing.assert_identical(da_dev, da_prod)
        # da_dev.close()
        # da_prod.close()

    print(f"✅ Found and compared {len(dev_files)} raster pairs - all identical!")


@app.command()
def main(
    satellite: str = typer.Argument(..., help="Satellite type: 'sentinel2' or 'landsat'"),
    region: str = typer.Option(None, help="Region to compare (if not specified, compares all regions in development environment)"),
    run_mode: str = typer.Option("local", help="Run mode: 'local' or 'hpc'")
):
    """
    CLI entry point: Compare raster files between production and development environments.
    If no region is specified, automatically compares all regions found in development environment.
    """
    # Set paths based on run mode
    if run_mode == "local":
        prod_base = "/home/bny/greenland_glacier_flow_glacier_velocity"
        dev_base = "/home/bny/greenland_glacier_flow_glacier_velocity1"
    elif run_mode == "hpc":
        prod_base = "/fs/project/howat.4/greenland_glacier_flow"
        dev_base = "/fs/project/howat.4/yadav.111/greenland_glacier_flow_glacier_velocity1"
    else:
        typer.echo(f"Error: Invalid run_mode '{run_mode}'. Use 'local' or 'hpc'", err=True)
        raise typer.Exit(1)
    if region is None:
        # Auto-discover and compare all regions
        try:
            regions = discover_regions(satellite, dev_base)
        except FileNotFoundError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

        if not regions:
            typer.echo(f"Error: No regions found in development environment for {satellite}", err=True)
            raise typer.Exit(1)

        typer.echo(f"Found {len(regions)} regions in development environment: {', '.join(regions)}")

        success_count = 0
        for region_name in regions:
            typer.echo(f"\n--- Comparing region: {region_name} ---")
            try:
                dev_path, prod_path = build_paths(satellite, region_name, dev_base, prod_base)
                compare_raster_files(dev_path, prod_path, region_name)
                success_count += 1
            except (ValueError, FileNotFoundError, AssertionError) as e:
                typer.echo(f"⚠️  Skipped {region_name}: {e}", err=True)
                continue

        typer.echo(f"\n🎉 Completed: {success_count}/{len(regions)} regions compared successfully")

    else:
        # Compare specific region
        try:
            dev_path, prod_path = build_paths(satellite, region, dev_base, prod_base)
            compare_raster_files(dev_path, prod_path, region)
        except (ValueError, FileNotFoundError, AssertionError) as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
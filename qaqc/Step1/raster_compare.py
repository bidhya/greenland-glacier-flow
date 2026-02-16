#!/usr/bin/env python3
"""
Satellite Raster Comparison Script - Flat Version
Compares clipped rasters between glacier_velocity (production) and glacier_velocity1 (Python 3.14) environments

Usage:
    python raster_compare.py sentinel2
    python raster_compare.py landsat
"""

import rioxarray
import xarray as xr
import numpy as np
from pathlib import Path
import typer

app = typer.Typer()

@app.command()
def compare_rasters(
    satellite: str = typer.Argument(..., help="Satellite type: 'sentinel2' or 'landsat'")
):
    """
    Compare raster files between production and development environments.
    """
    # Define the region to compare
    region = "138_SermiitsiaqInTasermiut"

    # Define paths to the two run directories
    base_folder = "/home/bny/greenland_glacier_flow_glacier_velocity"

    # Set up paths based on satellite
    if satellite == "sentinel2":
        path1 = Path(f'{base_folder}/1_download_merge_and_clip/{satellite}/{region}/clipped')
        path2 = Path(f'{base_folder}1/1_download_merge_and_clip/{satellite}/{region}/clipped')
    elif satellite == "landsat":
        path1 = Path(f'{base_folder}/1_download_merge_and_clip/{satellite}/{region}')
        path2 = Path(f'{base_folder}1/1_download_merge_and_clip/{satellite}/{region}')
    else:
        typer.echo(f"Error: Unsupported satellite type '{satellite}'. Use 'sentinel2' or 'landsat'.")
        raise typer.Exit(1)

    typer.echo(f"Satellite: {satellite}")
    typer.echo(f"Comparing rasters in:")
    typer.echo(f"Production: {path1}")
    typer.echo(f"Development: {path2}")

    # Find corresponding raster files
    files1 = list(path1.glob('*.tif'))
    if not files1:
        typer.echo(f"Error: No .tif files found in {path1}")
        raise typer.Exit(1)

    typer.echo(f"Found {len(files1)} raster files to compare")

    for f1 in files1:
        f2 = path2 / f1.name
        typer.echo(f"Comparing: {f1.name}")

        # Load rasters
        da1 = rioxarray.open_rasterio(f1, chunks="auto")
        da2 = rioxarray.open_rasterio(f2, chunks="auto")

        # Compare rasters directly
        xr.testing.assert_identical(da1, da2)
        # da1.close()
        # da2.close()

    typer.echo(f"✅ Found and compared {len(files1)} raster pairs - all identical!")


if __name__ == "__main__":
    app()
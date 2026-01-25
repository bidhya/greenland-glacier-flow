
#!/usr/bin/env python
# """
# Batch Glacier Processor for Step 3: Orthocorrection & NetCDF Packaging
#
# This script handles argument parsing, configuration loading, and parallel processing
# of multiple glaciers. It reads glacier regions from a GeoPackage, filters them,
# and calls the main orchestrator (orthocorrect_netcdf-package.py) for each glacier
# in parallel using joblib.
#
# Features:
# - Loads glacier list from AOI_SHP GeoPackage
# - Filters glaciers by ID (>100)
# - Processes glaciers in parallel (configurable n_jobs)
# - Handles logging per glacier
# - Uses config values from lib/config.py for dates and base directory
#
# Usage:
#     python batch_glacier_processor.py              # Process all for current IMGDIR
#     python batch_glacier_processor.py --glaciers "001_alison,002_anoritup"
#
# Author: Bidhya N. Yadav
# Date: December 2025
# """

import argparse
import os
import sys
import subprocess
import geopandas as gpd
from joblib import Parallel, delayed
import re
import glob


def has_complete_data(glacier_dir):
    """Check if glacier has complete data by verifying
    clipped .tif files exist."""
    clipped_dir = os.path.join(glacier_dir, 'clipped')
    
    # Check if clipped directory exists
    if not os.path.exists(clipped_dir):
        return False
    
    # Check for .tif files in clipped directory
    tif_files = glob.glob(os.path.join(clipped_dir, '*.tif'))
    
    # Require at least one .tif file (adjust threshold as needed)
    return len(tif_files) > 0


def process_glacier(glacier, start_date, end_date, base_dir,
                    project_root, log_dir):
    """Process a single glacier by calling orthocorrect_netcdf-package.py."""
    # Handle log setup for this glacier
    shared_log_dir = log_dir
    os.makedirs(shared_log_dir, exist_ok=True)
    log_name = f"{shared_log_dir}/{glacier}_step3.log"
    
    # Build the command
    orchestrator_path = os.path.join(project_root,
                                     'orthocorrect_netcdf-package.py')
    cmd = [
        sys.executable,
        orchestrator_path,
        '--glaciers', glacier,
        '--start_date', start_date,
        '--end_date', end_date,
        '--base_dir', base_dir,
        '--log_name', log_name
    ]
    
    # Run the command
    result = subprocess.run(cmd)
    return result.returncode


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Run Step 3: Orthocorrection & NetCDF Packaging'
    )
    parser.add_argument(
        '--glaciers', '-g',
        help='Specific glaciers (comma-separated). If not provided, '
             'processes ALL available for current IMGDIR.',
        type=str
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Get project root (this script is now at project root level)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = script_dir  # Script is at project root
    
    # Import config values
    sys.path.append(project_root)
    from lib.config import AOI_SHP, START_DATE, END_DATE, WD, LOG_DIR, IMGDIR
    
    start_date = START_DATE
    end_date = END_DATE
    base_dir = WD

    # # Read geopackage to get glacier list
    # glacier_regions_path = (f"{project_root}/reference/glaciers_roi_geog_v2_300m.gpkg")  # noqa
    # regions = gpd.read_file(glacier_regions_path)
    regions = gpd.read_file(AOI_SHP)
    regions.index = regions.region
    # Extract list of regions (glaciers)
    regions_list = list(regions.region)
    print(f"Number of regions before filtering: {len(regions_list)}")
    
    # NEW: Filter based on data availability in IMGDIR
    available_glaciers = os.listdir(IMGDIR)
    # Filter: start with 3 digits + underscore, exclude 'ancillary'
    available_glaciers = [g for g in available_glaciers
                          if re.match(r'^\d{3}_', g) and g != 'ancillary']
    print(f"Number of available glaciers in IMGDIR: {len(available_glaciers)}")
    
    # Filter glaciers that have complete data (clipped .tif files exist)
    complete_data_glaciers = []
    excluded_glaciers = []
    
    for glacier in available_glaciers:
        glacier_dir = os.path.join(IMGDIR, glacier)
        if has_complete_data(glacier_dir):
            complete_data_glaciers.append(glacier)
        else:
            excluded_glaciers.append(glacier)
    
    print(f"Found {len(complete_data_glaciers)} glaciers with complete data")
    print(f"Excluded {len(excluded_glaciers)} glaciers with "
          f"incomplete/missing data")
    
    # PROMINENTLY LOG EXCLUDED GLACIERS FOR POST-ANALYSIS
    if excluded_glaciers:
        print("\n" + "="*60)
        print("⚠️  GLACIERS EXCLUDED DUE TO INCOMPLETE DATA:")
        print("="*60)
        for glacier in sorted(excluded_glaciers):
            print(f"  ❌ {glacier} - Missing or incomplete clipped/.tif files")
        print("="*60 + "\n")
    
    available_glaciers = complete_data_glaciers
    
    # BACKUP: Manual exclusion of known problematic glaciers (commented out)
    # Keep this as fallback in case file existence checks miss edge cases
    # if "gravina.2" in IMGDIR:
    #     problematic_glaciers = [
    #         "013_comell", "014_courtauld", "042_hubbard",
    #         "074_midgard_nord", "075_mogens_mid", "090_petermann",
    #         "091_pituffik"
    #     ]
    #     available_glaciers = [g for g in available_glaciers
    #                           if g not in problematic_glaciers]
    #     print(f"Excluded {len(problematic_glaciers)} problematic "
    #           f"glaciers from Gravina's IMGDIR")
    #     print(f"Number of available glaciers after exclusion: "
    #           f"{len(available_glaciers)}")
    
    # Only process glaciers that are both in AOI_SHP and have data available
    regions_list = [r for r in regions_list if r in available_glaciers]
    regions_list.sort()  # Sort in order of number.
    print(f"Number of regions after filtering: {len(regions_list)}")

    # Process glaciers
    if args.glaciers:
        # Specific glaciers provided
        glaciers_to_process = [g.strip() for g in args.glaciers.split(',')]
        print(f"Processing specific glaciers: {glaciers_to_process}")
    else:
        # Process ALL available glaciers for current IMGDIR
        glaciers_to_process = regions_list
        print(f"Processing ALL {len(glaciers_to_process)} available glaciers "
              f"for current IMGDIR")
        
        # LOG FINAL PROCESSING LIST FOR POST-ANALYSIS
        print("\n" + "="*60)
        print("📋 FINAL GLACIER PROCESSING LIST:")
        print("="*60)
        for i, glacier in enumerate(glaciers_to_process, 1):
            print(f"{i:2d}. {glacier}")
        print("="*60 + "\n")
    # Use SLURM allocated CPUs if available, else os.cpu_count() as fallback
    slurm_cpus = os.environ.get('SLURM_CPUS_PER_TASK')
    allocated_cpus = int(slurm_cpus) if slurm_cpus else (os.cpu_count() or 1)
    print(f"slurm_cpus = {slurm_cpus} and allocated_cpus={allocated_cpus}")
    n_jobs = min(len(glaciers_to_process), allocated_cpus)
    print(f"Using n_jobs={n_jobs} for parallel processing")
    
    results = Parallel(n_jobs=n_jobs)(delayed(process_glacier)(
        g, start_date, end_date, base_dir, project_root, LOG_DIR
    ) for g in glaciers_to_process)
    
    # Check results
    # NOTE: Lines below are not strictly correct - glaciers may report
    # "completed successfully" even when they actually failed. This needs
    # investigation in the future. Some glaciers that return code 0 are
    # known to have failed processing.
    for glacier, code in zip(glaciers_to_process, results):
        if code != 0:
            print(f"Glacier {glacier} failed with code {code}")
        else:
            print(f"Glacier {glacier} completed successfully")


if __name__ == '__main__':
    main()

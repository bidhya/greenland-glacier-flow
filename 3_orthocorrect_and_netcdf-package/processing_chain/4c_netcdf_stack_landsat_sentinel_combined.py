"""
Combine NetCDF files from Landsat and Sentinel-2.
"""



###################################################################################################
# Imports.
###################################################################################################

# Import basic python resources.
import argparse, os, sys
# Import geographic-data-handling libraries.
import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr

# Import config values.
sys.path.append(".")
from lib.config import VELDIR_LS, WD, AOI_NAMES, OUTDIRNAME, GLAC, START_DATE, END_DATE, VERSION
# Import utility functions.
from lib.log import setUpBasicLoggingConfig, log_to_stdout_and_file



###################################################################################################
# Parse command-line arguments.
###################################################################################################

# Parse command-line arguments.
parser = argparse.ArgumentParser(description='Orthocorrect and NetCDF-package glacier velocity data.')
parser.add_argument(
    '--glacier',
    help='Name of glacier region to process',
    type=str
)
parser.add_argument(
    '--start_date',
    help='First day of data to process, in YYYYMMDD format',
    type=str
)
parser.add_argument(
    '--end_date',
    help='Last day of data to process, in YYYYMMDD format',
    type=str
)
parser.add_argument(
    '--base_dir',
    help='Base folder for outputs from processing',
    type=str
)
parser.add_argument(
    '--log_name',
    help='Name of log file',
    type=str,
    default='sentinel_glacier.log'
)
args = parser.parse_args()
glacier = args.glacier
if not glacier:
    glacier = GLAC
start_date = args.start_date
if not start_date:
    start_date = START_DATE
end_date = args.end_date
if not end_date:
    end_date = END_DATE
base_dir = args.base_dir
if not base_dir:
    base_dir = WD
log_name = args.log_name


###################################################################################################
# Set up logging.
###################################################################################################

# Set up basic logging configuration.
setUpBasicLoggingConfig(log_name, f"Attempting to combine NetCDF files from Landsat and Sentinel-2 sources.")



###################################################################################################
# Set up directories and file paths.
###################################################################################################

# Set up directories.
vel_dir = os.path.join(VELDIR_LS, glacier, "SETSM_SDM_100")
out_dir = os.path.join(base_dir, OUTDIRNAME, glacier)
msk_dir = os.path.join(out_dir, "gimp_masks")
orb_dir = os.path.join(out_dir, "orbits")
mrg_dir = os.path.join(out_dir, "netcdf")

# Set up file paths.
l8_netcdf_fpath = os.path.join(mrg_dir, f"L8_{glacier}_v{VERSION}.nc")
s2_netcdf_fpath = os.path.join(mrg_dir, f"S2_{glacier}_v{VERSION}.nc")

# Set up/create the final output directory (processed files will be output to a separate output
# location for delivery).
FINALOUTDIR = os.path.join(base_dir, f"{OUTDIRNAME}_delivery")
if not os.path.exists(FINALOUTDIR):
    os.mkdir(FINALOUTDIR)



###################################################################################################
# Import NetCDFs produced by scripts 4a and 4b.
###################################################################################################

# Check which NetCDF files exist
l8_exists = os.path.exists(l8_netcdf_fpath)
s2_exists = os.path.exists(s2_netcdf_fpath)

log_to_stdout_and_file(f"Landsat NetCDF exists: {l8_exists}")
log_to_stdout_and_file(f"Sentinel-2 NetCDF exists: {s2_exists}")

# Load available datasets
datasets_to_merge = []
if s2_exists:
    log_to_stdout_and_file("Opening Sentinel-2 NetCDF...")
    s2_ds = xr.open_dataset(s2_netcdf_fpath, engine="netcdf4")
    datasets_to_merge.append(s2_ds)
else:
    log_to_stdout_and_file("Sentinel-2 NetCDF not found, skipping...")
    s2_ds = None

if l8_exists:
    log_to_stdout_and_file("Opening Landsat 8 NetCDF...")
    l8_ds = xr.open_dataset(l8_netcdf_fpath, engine="netcdf4")
    datasets_to_merge.append(l8_ds)
else:
    log_to_stdout_and_file("Landsat NetCDF not found, skipping...")
    l8_ds = None

# Check if we have any datasets to merge
if not datasets_to_merge:
    log_to_stdout_and_file("ERROR: No NetCDF files found to merge. Both Sentinel-2 and Landsat processing must have failed.")
    sys.exit(1)

if len(datasets_to_merge) == 1:
    log_to_stdout_and_file("WARNING: Only one data source available. Proceeding with single-source dataset.")
    merge = datasets_to_merge[0]
else:
    log_to_stdout_and_file("Merging datasets...")
    merge = xr.concat(datasets_to_merge, dim="index")

    # Fix quibbles that have emerged from concat function for some reason.
    # Only apply to concatenated datasets
    merge["scene_1_orbit"] = merge["scene_1_orbit"].sel(tindexiindexme=0)

# Re-index and sort, starting from zero and sorted by scene_1 then scene_2 datetime
merge["index"] = range(len(merge.index.values))
merge = merge.sortby(["scene_1_datetime", "scene_2_datetime"])

# Assign attributes to the merged dataset.
public_id_gdf = gpd.read_file(AOI_NAMES)
public_id_dict = pd.Series(
    public_id_gdf.ID.values, index=public_id_gdf.internal_processing_ID
).to_dict()
public_id = public_id_dict[glacier]
merge = merge.assign_attrs(
    {
        "glacier_id": public_id,
        "creation_date": pd.Timestamp.now().strftime("%Y-%m-%d %X"),
    }
)

# Sort by scene_1 datetime, then scene_2 datetime, then reset the index.
merge = merge.sortby(["scene_1_datetime", "scene_2_datetime"])
merge["index"] = range(len(merge.index.values))

# Modify the dataset, changing datatypes to be more efficient.
stringtype = "S"
merge["scene_1_satellite"] = merge["scene_1_satellite"].astype(stringtype)
merge["scene_2_satellite"] = merge["scene_2_satellite"].astype(stringtype)
merge["scene_1_orbit"] = merge["scene_1_orbit"].astype(stringtype)
merge["scene_2_orbit"] = merge["scene_2_orbit"].astype(stringtype)
merge["scene_1_processing_version"] = merge["scene_1_processing_version"].astype(stringtype)
merge["scene_2_processing_version"] = merge["scene_2_processing_version"].astype(stringtype)

# Ensure output of days is as an integer.
try:
    merge["baseline_days"] = merge["baseline_days"].dt.days.astype("int64")
except:
    pass
merge.baseline_days.attrs[
    "long_name"
] = "temporal baseline between scene 1 and scene 2"
merge.baseline_days.attrs["units"] = "days"



###################################################################################################
# Export to NetCDF files for each year.
###################################################################################################

log_to_stdout_and_file("Splitting into years and exporting...")

# For each year in the data, export to NetCDF.
years = merge.midpoint_datetime.dt.year
years = np.unique(years)
for year in years:
    log_to_stdout_and_file(f"Extracting {year}...")

    # Get a dataset for just this year.
    year_ds = merge.where(
        (merge.midpoint_datetime >= np.datetime64(f"{year}-01-01"))
        & (merge.midpoint_datetime <= np.datetime64(f"{year}-12-31")),
        drop=True,
    )
    
    # Set baseline_days attribute as int64 type.
    year_ds["baseline_days"] = year_ds["baseline_days"].astype("int64")
    
    # Reindex the year dataset.
    year_ds["index"] = range(len(year_ds.index.values))

    # Fix quibbles that have emerged from concat function for some reason.
    year_ds["crs"] = year_ds.crs[0]
    year_ds.vx.encoding["grid_mapping"] = "crs"
    year_ds.vy.encoding["grid_mapping"] = "crs"
    year_ds.vx.attrs["grid_mapping"] = "crs"
    year_ds.vy.attrs["grid_mapping"] = "crs"

    # BNY 2025-12-06: Convert velocity variables to float32 dtype in-memory
    # This ensures data is stored as float32, not just encoded as float32 in NetCDF
    # Prevents xarray defaulting to float64 which doubles data size
    year_ds["vx"].data = year_ds["vx"].data.astype(np.float32)
    year_ds["vy"].data = year_ds["vy"].data.astype(np.float32)

    # Export to NetCDF.
    log_to_stdout_and_file(f"Exporting {year}... (Memory size: {year_ds.nbytes / (1024 * 1024)} MB.)")

    comp = dict(zlib=True, complevel=5)
    encoding_comp = {var: comp for var in year_ds}
    encoding_time = {
        "scene_1_datetime": {"units": "seconds since 1970-01-01 00:00:00"},
        "scene_2_datetime": {"units": "seconds since 1970-01-01 00:00:00"},
        "midpoint_datetime": {"units": "seconds since 1970-01-01 00:00:00"},
    }
    encoding = {**encoding_comp, **encoding_time}

    # Get the filepath as the final output NetCDF.
    combined_netcdf_fpath = os.path.join(
        FINALOUTDIR, f"{public_id}_{year}_v{VERSION}.nc"
    )

    # Export to NetCDF.
    year_ds.to_netcdf(combined_netcdf_fpath, encoding=encoding)

# Close input datasets to free resources (after all operations complete)
if s2_ds is not None:
    s2_ds.close()
if l8_ds is not None:
    l8_ds.close()
log_to_stdout_and_file("Finished.")
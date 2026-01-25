"""
Combine NetCDF files from pre- and pos-DEM-switch periods.
"""



###################################################################################################
# Imports.
###################################################################################################

# Import basic python resources.
import argparse, os, sys
import sys
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
setUpBasicLoggingConfig(log_name, f"Attempting to combine NetCDF files across pre- and post-DEM-switch periods.")



###################################################################################################
# Set up directories and file paths.
###################################################################################################

# Set up directories.
vel_dir = os.path.join(VELDIR_LS, glacier, "SETSM_SDM_100")
out_dir = os.path.join(base_dir, OUTDIRNAME, glacier)
msk_dir = os.path.join(out_dir, "gimp_masks")
orb_dir = os.path.join(out_dir, "orbits")
mrg_dir = os.path.join(out_dir, "netcdf")

# Get the directory of the 2021 intermediate output files (which are split around the DEM switch
# date).
PREDEMSWITCHOUTDIR = os.path.join(f"{base_dir}_pre_dem_switch", f"{OUTDIRNAME}_delivery")
POSTDEMSWITCHOUTDIR= os.path.join(f"{base_dir}_post_dem_switch", f"{OUTDIRNAME}_delivery")

# Set up/create the final output directory (processed files will be output to a separate output
# location for delivery).
FINALOUTDIR = os.path.join(base_dir, f"{OUTDIRNAME}_delivery")
if not os.path.exists(FINALOUTDIR):
    os.mkdir(FINALOUTDIR)



###################################################################################################
# Get glacier public ID.
###################################################################################################

public_id_gdf = gpd.read_file(AOI_NAMES)
public_id_dict = pd.Series(
    public_id_gdf.ID.values, index=public_id_gdf.internal_processing_ID
).to_dict()
public_id = public_id_dict[glacier]




###################################################################################################
# Merge NetCDFs for each year.
###################################################################################################

# Loop through each year in the data and merge the NetCDFs for that year.
years = list(range(
    int(start_date[:4]),
    int(end_date[:4])+1
))
for year in years:
    ###############################################################################################
    # Import NetCDFs produced by pre- and post-DEM-switch workflows.
    ###############################################################################################

    # Set up file paths.
    pre_dem_switch_fpath = os.path.join(
        PREDEMSWITCHOUTDIR, f"{public_id}_{year}_v{VERSION}.nc"
    )

    post_dem_switch_fpath = os.path.join(
        POSTDEMSWITCHOUTDIR, f"{public_id}_{year}_v{VERSION}.nc"
    )

    # Import NetCDFs.
    log_to_stdout_and_file("Opening pre-DEM-switch NetCDF...")
    pre_dem_switch_ds = xr.open_dataset(pre_dem_switch_fpath)

    log_to_stdout_and_file("Opening post-DEM-switch NetCDF...")
    post_dem_switch_ds = xr.open_dataset(post_dem_switch_fpath)



    ###############################################################################################
    # Merge them into one dataset.
    ###############################################################################################

    log_to_stdout_and_file("Merging datasets...")

    # Merge and set creation time.
    merge = xr.concat([pre_dem_switch_ds, post_dem_switch_ds], dim="index")

    # Fix quibbles that have emerged from concat function for some reason.
    merge["crs"] = merge.crs[0]
    merge.vx.encoding["grid_mapping"] = "crs"
    merge.vy.encoding["grid_mapping"] = "crs"
    merge.vx.attrs["grid_mapping"] = "crs"
    merge.vy.attrs["grid_mapping"] = "crs"

    # Re-index and sort, starting from zero and sorted by scene_1 then scene_2 datetime.
    merge["index"] = range(len(merge.index.values))
    merge = merge.sortby(["scene_1_datetime", "scene_2_datetime"])

    # Assign attributes to the merged dataset.
    merge = merge.assign_attrs(
        {
            "glacier_id": public_id,
            "creation_date": pd.Timestamp.now().strftime("%Y-%m-%d %X")
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



    ###############################################################################################
    # Export the dataset to NetCDF.
    ###############################################################################################

    log_to_stdout_and_file(f"Exporting... (Memory size: {merge.nbytes / (1024 * 1024)} MB.)")

    comp = dict(zlib=True, complevel=5)
    encoding_comp = {var: comp for var in merge}
    encoding_time = {
        "scene_1_datetime": {"units": "seconds since 1970-01-01 00:00:00"},
        "scene_2_datetime": {"units": "seconds since 1970-01-01 00:00:00"},
        "midpoint_datetime": {"units": "seconds since 1970-01-01 00:00:00"},
    }
    encoding = {**encoding_comp, **encoding_time}

    combined_netcdf_fpath = os.path.join(
        FINALOUTDIR, f"{public_id}_{year}_v{VERSION}.nc"
    )

    merge.to_netcdf(combined_netcdf_fpath, encoding=encoding)

log_to_stdout_and_file("Finished.")

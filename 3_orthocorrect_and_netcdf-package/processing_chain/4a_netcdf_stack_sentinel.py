"""
Stack velocity fields into xarray. Export this.
"""



###################################################################################################
# Imports.
###################################################################################################

# Import basic python resources.
import argparse, os, sys, glob
from tqdm import tqdm
# Import geographic-data-handling libraries.
import pandas as pd
import xarray as xr

# Import config values.
sys.path.append(".")
from lib.config import WD, OUTDIRNAME, GLAC, START_DATE, END_DATE, VERSION
# Import utility functions.
from lib.utility import create_dir
from lib.log import setUpBasicLoggingConfig, log_to_stdout_and_file
# Import subfunctions for main program.
from lib.functions import create_xr_dataset




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
setUpBasicLoggingConfig(log_name, f"Attempting to stack Sentinel-2 data into NetCDF format.")



###################################################################################################
# Set up directories.
###################################################################################################

# Get directory paths.
vel_dir = os.path.join(base_dir, OUTDIRNAME, glacier)
mrg_dir = os.path.join(vel_dir, "netcdf")
orb_dir = os.path.join(vel_dir, "orbits")
cor_dir = os.path.join(vel_dir, "velocities")
msk_dir = os.path.join(vel_dir, "gimp_masks")
netcdf_fpath = os.path.join(mrg_dir, f"S2_{glacier}_v{VERSION}.nc")

# Create merge directory.
create_dir(mrg_dir)



###################################################################################################
# Get a big dataset for all the velocity directories.
###################################################################################################

log_to_stdout_and_file(f"Stacking velocity fields for {glacier}...")

# Get a list of the velocity directories for the relevant years.
directories = glob.glob(os.path.join(cor_dir, "S2*"))
years = list(range(
    int(start_date[:4]),
    int(end_date[:4])+1,
))
directories = [
    directory
    for directory in directories
    if (
            any([directory.split("_")[-2].startswith(str(year)) for year in years])
            and any([directory.split("_")[-1].startswith(str(year)) for year in years])
    )
]





# Get a list of rioxarray datasets corresponding to each directory.
ds_list = []
for directory in tqdm(directories):
    ds_single = create_xr_dataset(glacier, directory)
    ds_list.append(ds_single)

# Concatenate all the datasets in the list into one big dataset.
ds = xr.concat(ds_list, dim="index")


###################################################################################################
# Modify the dataset by changing datatypes and setting attributes.
###################################################################################################

# Modify the velocities dataset, changing datatypes to be more efficient.
stringtype = 'S'
ds["id"] = ds["id"].astype(stringtype)
ds["scene_1_satellite"] = ds["scene_1_satellite"].astype(stringtype)
ds["scene_2_satellite"] = ds["scene_2_satellite"].astype(stringtype)
ds["scene_1_orbit"] = ds["scene_1_orbit"].astype(stringtype)
ds["scene_2_orbit"] = ds["scene_2_orbit"].astype(stringtype)
ds["scene_1_processing_version"] = ds["scene_1_processing_version"].astype(
    stringtype)
ds["scene_2_processing_version"] = ds["scene_2_processing_version"].astype(
    stringtype)
ds["percent_ice_area_notnull"] = ds["percent_ice_area_notnull"].astype(
    "float32")
ds["error_mag_rmse"] = ds["error_mag_rmse"].astype("float32")
ds["error_dx_mean"] = ds["error_dx_mean"].astype("float32")
ds["error_dx_sd"] = ds["error_dx_sd"].astype("float32")
ds["error_dy_mean"] = ds["error_dy_mean"].astype("float32")
ds["error_dy_sd"] = ds["error_dy_sd"].astype("float32")

# Set variable attributes of the velocities dataset.
ds.index.attrs["long"] = "index number (sorted by order of scene_1_datetime then scene_2_datetime."

ds = ds.rename({"spatial_ref": "crs"})
ds.vx.encoding["grid_mapping"] = "crs"
ds.vy.encoding["grid_mapping"] = "crs"

ds.x.attrs["standard_name"] = "projection_x_coordinate"
ds.x.attrs["coverage_content_type"] = "coordinate"
ds.x.attrs["units"] = "metres"
ds.x.attrs["comment"] = "value refers to centre of grid cell"

ds.y.attrs["standard_name"] = "projection_y_coordinate"
ds.y.attrs["coverage_content_type"] = "coordinate"
ds.y.attrs["units"] = "metres"
ds.y.attrs["comment"] = "value refers to centre of grid cell"

ds.vx.attrs["long_name"] = "x component of ice velocity"
ds.vx.attrs["standard_name"] = "land_ice_x_velocity"
ds.vx.attrs["units"] = "metres per day"

ds.vy.attrs["long_name"] = "y component of ice velocity"
ds.vy.attrs["standard_name"] = "land_ice_y_velocity"
ds.vy.attrs["units"] = "metres per day"

ds.id.attrs["long_name"] = "velocity field ID in format {glacier ID}_{datetime1}_{datetime2}_{satellite}"

ds.scene_1_datetime.attrs["long_name"] = "scene 1 acquisition time"
ds.scene_2_datetime.attrs["long_name"] = "scene 2 acquisition time"

ds.baseline_days.attrs["long_name"] = "temporal baseline between scene 1 and scene 2"
ds.baseline_days.attrs["units"] = "days"

ds.midpoint_datetime.attrs["long_name"] = "midpoint between scene 1 and scene 2 acquisition time"

ds.scene_1_satellite.attrs["long_name"] = "scene 1 source satellite"
ds.scene_2_satellite.attrs["long_name"] = "scene 2 source satellite"

orbital_comment = "Sentinel-2: Relative Orbit number. e.g. '125' = Relative Orbit R125. Landsat 8: Path/Row in format PPPRRR e.g. '008011' = Path 008, Row 011."
ds.scene_1_orbit.attrs["long_name"] = "scene 1 orbital information"
ds.scene_2_orbit.attrs["long_name"] = "scene 2 orbital information"
ds.scene_1_orbit.attrs["comment"] = orbital_comment
ds.scene_2_orbit.attrs["comment"] = orbital_comment

processing_comment = "Sentinel-2: Processing baseline version e.g. '301' = Processing Baseline 03.01. Landsat 8: Collection, tier, and prcessing level e.g. 'C01_T1_L1TP' = Collection-1, Tier-1, Precision and Terrain Correction."
ds.scene_1_processing_version.attrs["long_name"] = "scene 1 processing version"
ds.scene_2_processing_version.attrs["long_name"] = "scene 2 processing version"
ds.scene_1_processing_version.attrs["comment"] = processing_comment
ds.scene_2_processing_version.attrs["comment"] = processing_comment

ds.percent_ice_area_notnull.attrs["units"] = "percent"
ds.percent_ice_area_notnull.attrs["long_name"] = "percentage of gimp ice mask region containing valid data"

ds.error_mag_rmse.attrs["long_name"] = "root mean square of off-ice velocity magnitude"
ds.error_mag_rmse.attrs["units"] = "metres per day"
ds.error_dx_mean.attrs["long_name"] = "mean of off-ice velocity in x direction"
ds.error_dx_mean.attrs["units"] = "metres per day"
ds.error_dx_sd.attrs["long_name"] = "standard deviation of off-ice velocity in x direction"
ds.error_dx_sd.attrs["units"] = "metres per day"
ds.error_dy_mean.attrs["long_name"] = "mean of off-ice velocity in y direction"
ds.error_dy_mean.attrs["units"] = "metres per day"
ds.error_dy_sd.attrs["long_name"] = "standard deviation of off-ice velocity in y direction"
ds.error_dy_sd.attrs["units"] = "metres per day"

# Get information about minimum/maximum dates and years.
date_min = pd.to_datetime(ds.midpoint_datetime.values.min()).date()
date_max = pd.to_datetime(ds.midpoint_datetime.values.max()).date()
year_min = date_min.year
year_max = date_max.year

# Set non-variable attributes of the velocities dataset.
ds = ds.assign_attrs({
    "project": "MEaSUREs Greenland Ice Mapping Project (GIMP)",
    "title": "MEaSUREs Greenland Ice Velocity: Selected Glacier Site Singel-Pair Velocity Maps from Optical Images.",
    "version": f"{VERSION}",
    "glacier_id": glacier,
    "data": "ice surface velocity",
    "units": "m d^{-1}",
    "source": "Landsat-8 and Sentinel-2 optical imagery",
    "projection": "WGS 84 / NSDIC Sea Ice Polar Stereographic North",
    "epsg": "3413",
    "coordinate_unit": "m",
    "spatial_resolution": "100 m",
    "institution": "Byrd Polar & Climate Research Center | Ohio State University",
    "contributors": "Tom Chudley, Ian Howat, Bidhya Yadev, MJ Noh, Michael Gravina",
    "contact_name": "Ian Howat",
    "contact_email": "howat.4@osu.edu",
    "software": "Feature-tracking performed using SETSM SDM module | https://github.com/setsmdeveloper/SETSM",
    "funding_acknowledgement": "Supported by National Aeronautics and Space Administration MEaSUREs programme (80NSSC18M0078)",
    "data_acknowledgement": f"Contains modified Copernicus Sentinel data [{year_min} to {year_max}].",
    "Conventions": "CF-1.7",
})

# Sort by scene_1 datetime, then scene_2 datetime, then reset the index.
ds = ds.sortby(["scene_1_datetime", "scene_2_datetime"])
ds["index"] = range(len(ds.index.values))

# Reorder the indices to correct order (time, y, x).
current_indexes = ds.indexes
desired_order = ['index', 'y', 'x']
reordered_indexes = {
    indexame: current_indexes[indexame] for indexame in desired_order}
ds = ds.reindex(reordered_indexes)


###################################################################################################
# Export the dataset to NetCDF.
###################################################################################################

log_to_stdout_and_file(f"Exporting... (Sentinel-2 memory size: {ds.nbytes / (1024 * 1024)} MB.)")

# Get encoding information.
comp = dict(zlib=True, complevel=1)
encoding_comp = {var: comp for var in ds}
encoding_time = {
    'scene_1_datetime': {'units': 'seconds since 1970-01-01 00:00:00'},
    'scene_2_datetime': {'units': 'seconds since 1970-01-01 00:00:00'},
    'midpoint_datetime': {'units': 'seconds since 1970-01-01 00:00:00'},
}
encoding = {**encoding_comp, **encoding_time}

# Generate a NetCDF file from the velocities dataset.
ds.to_netcdf(netcdf_fpath, encoding=encoding)

log_to_stdout_and_file("Finished.")

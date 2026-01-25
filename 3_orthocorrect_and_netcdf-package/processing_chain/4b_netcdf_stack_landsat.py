"""
Generate an equivalent netcdf stack of Landsat SETSM output, with
equivalent estimates of error, variable names and types, etc.
"""



###################################################################################################
# Imports.
###################################################################################################

# Import basic python resources.
import argparse, os, sys, glob, warnings
from tqdm import tqdm
# Import geographic-data-handling libraries.
import numpy as np
import pandas as pd
import rasterio as rs
from rasterio.enums import Resampling
from osgeo import gdal
import xarray as xr
import rioxarray as rxr

# Import config values.
sys.path.append(".")
from lib.config import (VELDIR_LS, WD, OUTDIRNAME, GLAC, START_DATE, END_DATE, VERSION)
# Import utility functions.
from lib.utility import load_resampled_array
from lib.log import setUpBasicLoggingConfig, log_to_stdout_and_file
# Import subfunctions of main program.
from lib.functions import globsingle, landsat_metadata_from_ids, get_landsat_ids




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
setUpBasicLoggingConfig(log_name, f"Attempting to stack Landsat data into NetCDF format.")



###################################################################################################
# Set up directories.
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
combined_netcdf_fpath = os.path.join(mrg_dir, f"vel_{glacier}_v{VERSION}.nc")



###################################################################################################
# Get reference data and masks.
###################################################################################################

log_to_stdout_and_file(f"Getting reference data and velocities for {glacier}...")

# Get reference geospatial data for reading/writing.
example_tif_fpath = glob.glob(os.path.join(orb_dir, "*orbitmatch_dmag.tif"))[0]

# Get global xmin, xmax, ymin, ymax, etc.
with rs.open(example_tif_fpath) as src:
    global xmin, ymin, xmax, ymax
    xmin, ymin, xmax, ymax = src.bounds
    global bounds
    bounds = src.bounds
    global extent
    extent = (xmin, xmax, ymin, ymax)

# Load sample .tif as rioxarray dataset for projection-matching later.
xds_match = rxr.open_rasterio(example_tif_fpath)

# Load mask, resampled to size/resolution of velocity.
rock_mask_fpath = os.path.join(msk_dir, "mask_rock.tif")
rockmask_array = load_resampled_array(
    rock_mask_fpath, example_tif_fpath, resamp_alg=gdal.GRA_NearestNeighbour
)
ice_mask_fpath = os.path.join(msk_dir, "mask_ice.tif")
icemask_array = load_resampled_array(
    ice_mask_fpath, example_tif_fpath, resamp_alg=gdal.GRA_NearestNeighbour
)


###################################################################################################
# Construct a dataframe of velocities info.
###################################################################################################

# Get list of "good" Landsat fields. The output of the Surface Displacement Mapping workflow
# includes a set of `list_good_*.txt` files, which say which velocity files got acceptable QA
# scores.
years = list(range(
    int(start_date[:4]),
    int(end_date[:4])+1,
))
good_vel_fpaths = []
for year in years:
    good_ls_filter_str = os.path.join(vel_dir, f"list_good_{year}.txt")
    good_vel_fpaths.extend(glob.glob(good_ls_filter_str))
log_to_stdout_and_file(good_vel_fpaths)

for fpath in good_vel_fpaths: # Remove where *.txt file is empty (otherwise messes up pandas load).
    if len(open(fpath, "r").read()) == 0:
        good_vel_fpaths.remove(fpath)

# Load .CSVs for each good Landsat field to a single dataframe.
df_list = []
for fpath in good_vel_fpaths:
    try:
        df_single = pd.read_csv(fpath, header=None, sep="\t")
    except:
        continue
    df_list.append(df_single)

df = pd.concat(df_list, axis=0)
df.columns = ["id", "filter_ratio_1", "filter_ratio_2"]
df.drop(columns=["filter_ratio_1", "filter_ratio_2"], inplace=True)
df["dir"] = vel_dir + "/" + df["id"]


###################################################################################################
# Get a big dataset for all the velocity directories.
###################################################################################################

log_to_stdout_and_file(f"Stacking velocity fields for {glacier}...")

ds_list = []
for fdir in tqdm(df["dir"].values):
    # Import meta.txt and interpret variables to get orbit and processing baseline columns.
    meta_fpath = globsingle(fdir, "*meta.txt")
    ls_ids = get_landsat_ids(meta_fpath)
    satellite1, orbit1, pb1 = landsat_metadata_from_ids(ls_ids[0])
    satellite2, orbit2, pb2 = landsat_metadata_from_ids(ls_ids[1])

    # Skip if either are aster.
    if (satellite1 == "AST") or (satellite2 == "AST"):
        log_to_stdout_and_file(f"ASTER detected. Skipping {meta_fpath}")
        continue

    # Calculate temporal variables.
    vel_id = os.path.basename(fdir)
    df = pd.DataFrame({"id": [vel_id]})
    regex = r"\d{14}"  # Find datetime format
    date_1 = pd.to_datetime(df["id"].str.findall(regex).str[0])
    date_2 = pd.to_datetime(df["id"].str.findall(regex).str[1])
    date_min = pd.to_datetime(start_date)
    date_max = pd.to_datetime(end_date)
    if (date_1 < date_min)[0] or (date_2 > date_max)[0]:
        continue
    df["date1"] = date_1
    df["date2"] = date_2
    df["day_sep"] = pd.to_numeric(
        (df["date2"] - df["date1"]) / np.timedelta64(1, "D"),  # downcast="integer"
    )
    df["year"] = pd.DatetimeIndex(df["date1"]).year
    df["midpoint"] = df["date1"] + (df["date2"] - df["date1"]) / 2
    df["baseline"] = df["date2"] - df["date1"]
    df["baseline"] = df["baseline"] / np.timedelta64(1, "D")

    # Set time index.
    date1str = pd.to_datetime(df["date1"].values[0]).strftime("%Y%m%dT%H%M%S")
    date2str = pd.to_datetime(df["date2"].values[0]).strftime("%Y%m%dT%H%M%S")
    time_index = f"{date1str}_{date2str}"
    temp_index = np.random.randint(0, 2**63)

    vel_id = f"{glacier}_{date1str}_{date2str}_L8"

    # Load vx, vy datasets.
    vx_fpath = globsingle(fdir, "*dx.tif")
    vx = (
        rxr.open_rasterio(vx_fpath)
        .sel(band=1, drop=True)
        .expand_dims({"index": [temp_index]})
    )

    vy_fpath = globsingle(fdir, "*dy.tif")
    vy = (
        rxr.open_rasterio(vy_fpath)
        .sel(band=1, drop=True)
        .expand_dims({"index": [temp_index]})
    )

    # Merge vx and vy datasets into one.
    ds = xr.Dataset()
    ds["vx"] = vx
    ds["vy"] = vy

    # Mask, if the mask exists.
    mask_fpath = vx_fpath.rsplit("_", 1)[0] + "_mask.tif"
    if os.path.exists(mask_fpath):
        mask = rxr.open_rasterio(mask_fpath)  # .set(band=1, drop=True)
        ds = ds.where(mask == 1).sel(band=1, drop=True)

    # Filter to valid data.
    ds = ds.where((ds.vx.values != 0.0) & (ds.vx.values != -9999.0))

    # Resample with rioxarray.
    ds = ds.rio.reproject_match(xds_match, resampling=Resampling.bilinear)

    # Generate rock-masked data.
    dx_rock = np.where(
        (rockmask_array == 1) & (ds.vx.values != -9999.0), ds.vx.values, np.nan
    )
    dy_rock = np.where(
        (rockmask_array == 1) & (ds.vy.values != -9999.0), ds.vy.values, np.nan
    )
    dmag_rock = np.sqrt(np.square(dx_rock) + np.square(dy_rock))

    # Find error variables.
    def ztn(n):
        """
        zero to nan (ztn)
        to resolve meanslice issue - if returns 0, return nan
        """
        if n == 0.0:
            return np.nan
        else:
            return n

    # Suppress error "mean of empty slice".
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)

        rmse = ztn(np.sqrt(np.nanmean(np.square(dmag_rock))))
        dxmn, dxsd = ztn(np.nanmean(dx_rock)), ztn(np.nanstd(dx_rock))
        dymn, dysd = ztn(np.nanmean(dy_rock)), ztn(np.nanstd(dy_rock))

    # Generate ice-masked data.
    dx_ice = np.where(
        (icemask_array == 1) & (ds.vx.values != -9999.0), ds.vx.values, np.nan
    )
    valid_ice = np.where(dx_ice != np.nan, 1, 0)

    # Find valid coverage.
    total_ice = np.sum(icemask_array)
    valid_ice = np.sum(valid_ice)
    valid_ice_fraction = round((total_ice / valid_ice * 100), 2)

    # Assign variables to the dataset.
    ds = ds.assign(
        {
            "id": ("index", [vel_id]),
            "scene_1_datetime": ("index", [pd.to_datetime(df["date1"].values[0])]),
            "scene_2_datetime": ("index", [pd.to_datetime(df["date2"].values[0])]),
            "baseline_days": ("index", [df["baseline"].values[0]]),
            "midpoint_datetime": ("index", [df["midpoint"].values[0]]),
            "scene_1_satellite": ("index", [satellite1]),
            "scene_2_satellite": ("index", [satellite2]),
            "scene_1_orbit": ("tindexiindexme", [orbit1]),
            "scene_2_orbit": ("index", [orbit2]),
            "scene_1_processing_version": ("index", [pb1]),
            "scene_2_processing_version": ("index", [pb2]),
            "percent_ice_area_notnull": ("index", [valid_ice_fraction]),
            "error_mag_rmse": ("index", [rmse]),
            "error_dx_mean": ("index", [dxmn]),
            "error_dx_sd": ("index", [dxsd]),
            "error_dy_mean": ("index", [dymn]),
            "error_dy_sd": ("index", [dysd]),
        }
    )

    # Add the dataset to the list.
    ds_list.append(ds)

# Concatenate the list of datasets into one big dataset.
if len(ds_list) == 0:
    log_to_stdout_and_file(f"Error: No Landsat data found to concatenate for {glacier}. Exiting script.")
    sys.exit(1)
ds = xr.concat(ds_list, dim="index")


###################################################################################################
# Modify the dataset by changing datatypes and setting attributes.
###################################################################################################

# Modify the velocities dataset, changing datatypes to be more efficient.
stringtype = "S"
ds["id"] = ds["id"].astype(stringtype)
ds["scene_1_satellite"] = ds["scene_1_satellite"].astype(stringtype)
ds["scene_2_satellite"] = ds["scene_2_satellite"].astype(stringtype)
ds["scene_1_orbit"] = ds["scene_1_orbit"].astype(stringtype)
ds["scene_2_orbit"] = ds["scene_2_orbit"].astype(stringtype)
ds["scene_1_processing_version"] = ds["scene_1_processing_version"].astype(
    stringtype
)
ds["scene_2_processing_version"] = ds["scene_2_processing_version"].astype(
    stringtype
)
ds["percent_ice_area_notnull"] = ds["percent_ice_area_notnull"].astype("float32")
ds["error_mag_rmse"] = ds["error_mag_rmse"].astype("float32")
ds["error_dx_mean"] = ds["error_dx_mean"].astype("float32")
ds["error_dx_sd"] = ds["error_dx_sd"].astype("float32")
ds["error_dy_mean"] = ds["error_dy_mean"].astype("float32")
ds["error_dy_sd"] = ds["error_dy_sd"].astype("float32")

# Set variable attributes of the velocities dataset.
ds.index.attrs[
    "long"
] = "index number (sorted by order of scene_1_datetime then scene_2_datetime."

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

ds.id.attrs[
    "long_name"
] = "velocity field ID in format {glacier ID}_{datetime1}_{datetime2}_{satellite}"

ds.scene_1_datetime.attrs["long_name"] = "scene 1 acquisition time"
ds.scene_2_datetime.attrs["long_name"] = "scene 2 acquisition time"

ds.baseline_days.attrs[
    "long_name"
] = "temporal baseline between scene 1 and scene 2"
ds.baseline_days.attrs["units"] = "days"

ds.midpoint_datetime.attrs[
    "long_name"
] = "midpoint between scene 1 and scene 2 acquisition time"

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
ds.percent_ice_area_notnull.attrs[
    "long_name"
] = "percentage of gimp ice mask region containing valid data"

ds.error_mag_rmse.attrs[
    "long_name"
] = "root mean square of off-ice velocity magnitude"
ds.error_mag_rmse.attrs["units"] = "metres per day"
ds.error_dx_mean.attrs["long_name"] = "mean of off-ice velocity in x direction"
ds.error_dx_mean.attrs["units"] = "metres per day"
ds.error_dx_sd.attrs[
    "long_name"
] = "standard deviation of off-ice velocity in x direction"
ds.error_dx_sd.attrs["units"] = "metres per day"
ds.error_dy_mean.attrs["long_name"] = "mean of off-ice velocity in y direction"
ds.error_dy_mean.attrs["units"] = "metres per day"
ds.error_dy_sd.attrs[
    "long_name"
] = "standard deviation of off-ice velocity in y direction"
ds.error_dy_sd.attrs["units"] = "metres per day"

# Set non-variable attributes of the velocities dataset.
ds = ds.assign_attrs(
    {
        "project": "MEaSUREs Greenland Ice Mapping Project (GIMP)",
        "title": "MEaSUREs Greenland Ice Velocity: Selected Glacier Site Single-Pair Velocity Maps from Optical Images.",
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
        "Conventions": "CF-1.7",
    }
)


# Sort by scene_1 datetime, then scene_2 datetime, then reset the index.
ds = ds.sortby(["scene_1_datetime", "scene_2_datetime"])
ds["index"] = range(len(ds.index.values))

# Reorder the indices to correct order (time, y, x).
current_indexes = ds.indexes
desired_order = ["index", "y", "x"]
reordered_indexes = {
    index_name: current_indexes[index_name] for index_name in desired_order
}
ds = ds.reindex(reordered_indexes)


###################################################################################################
# Export to NetCDF.
###################################################################################################

log_to_stdout_and_file(f"Exporting... (Landsat-8 memory size: {ds.nbytes / (1024 * 1024)} MB.)")

# Get encoding information.
comp = dict(zlib=True, complevel=1)
encoding_comp = {var: comp for var in ds}
encoding_time = {
    "scene_1_datetime": {"units": "seconds since 1970-01-01 00:00:00"},
    "scene_2_datetime": {"units": "seconds since 1970-01-01 00:00:00"},
    "midpoint_datetime": {"units": "seconds since 1970-01-01 00:00:00"},
}
encoding = {**encoding_comp, **encoding_time}

# Generate a NetCDF file from the velocities dataset.
ds.to_netcdf(l8_netcdf_fpath, encoding=encoding)

log_to_stdout_and_file("Finished.")

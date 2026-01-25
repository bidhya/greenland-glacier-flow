"""
For a given glacier, get average of the offset from the average velocity
from all fields with matching orbital pairings.

For each relative orbit pair, produces a .tif representing the difference field between:
    1. The median field of all velocity .tifs for that relative orbit pair, and
    2. The median field of all velocity .tifs across *all* orbit pairs.
"""



###################################################################################################
# Imports.
###################################################################################################

# Import basic python resources.
import argparse, sys, os, glob
# Import geographic-data-handling libraries.
import numpy as np
import matplotlib
matplotlib.use("agg") # Write to file rather than window.
import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
import rasterio as rs
from osgeo import gdal
gdal.UseExceptions() # Enable GDAL exceptions.

# Import config values.
sys.path.append(".")
from lib.config import IMGDIR, VELDIR, WD, OUTDIRNAME, GLAC, START_DATE, END_DATE
# Import utility functions.
from lib.plot import plot_velocity
from lib.log import setUpBasicLoggingConfig, log_to_stdout_and_file
# Import subfunctions of main program.
from lib.functions import get_median_field_of_arrays_from_df, generate_flow_direction_tif, get_offset_of_orbit_pairs_from_a_priori




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
setUpBasicLoggingConfig(log_name, f"Attempting to generate orbital average offset fields.")



###################################################################################################
# Set up directories.
###################################################################################################

# Generate source directory paths.
clipped_dir = os.path.join(IMGDIR, glacier, "clipped")
# veldir = os.path.join(VELDIR, glacier, 'SETSM_SDM_100')
veldir = os.path.join(VELDIR, glacier, 'SETSM_SDM_100_new')

# Get working directory paths.
outdir_container = os.path.join(base_dir, OUTDIRNAME, glacier)
outdir = os.path.join(outdir_container, "orbits")
orbital_df_fpath = os.path.join(outdir, glacier + "_orbits.csv")


###################################################################################################
# Generate metadata dictionaries for images in the glacier AOI.
###################################################################################################

log_to_stdout_and_file("Generating dictionaries of metadata for images in the glacier AOI, keyed to the datehours of the image.")

# Retrieve orbital metadata dictionary for this glacier (from the CSV generated in script 1).
# Set the datatypes appropriately by column.
orbital_df = pd.read_csv(orbital_df_fpath)
orbital_df["orbits"] = orbital_df["orbits"].astype(str)
orbital_df["processing_baselines"] = orbital_df["processing_baselines"].astype(str)

# Filter out any dataframe rows that aren't between the minimum and maximum dates."
orbital_df = orbital_df[
    orbital_df["datetime"] >= start_date
]
orbital_df = orbital_df[
    orbital_df["datetime"] <= end_date
]
log_to_stdout_and_file(orbital_df)

# Create a dictionary of metadata for images in the glacier AOI. Use the image datehours as the
# index, and the orbit numbers as the values.
orbital_dict = pd.Series(
    orbital_df.orbits.values,
    index=orbital_df.datehour
).to_dict()

# Create a dictionary of metadata for images in the glacier AOI. Use the image datehours as the
# index and the orbital baselines as the values.
pb_dict = pd.Series(
    orbital_df.processing_baselines.values,
    index=orbital_df.datehour
).to_dict()

# Create a dictionary of metadata for images in the glacier AOI. Use the image datehours as the
# index and the orbit datetimes as the values.
time_dict = pd.Series(
    orbital_df.datetime.values,
    index=orbital_df.datehour
).to_dict()


###################################################################################################
# Generate a big table of metadata for the to-be-corrected velocity files for this glacier (and
# save it as `<glacier name>_orbit_pairs.csv`).
###################################################################################################

log_to_stdout_and_file("Generating metadata .CSV that matches velocity pairs to orbits...")

# Get a list of paths for "good" velocity files for Greenland. (The output of the Surface
# Displacement Mapping workflow includes a set of `list_good_*.txt` files, which say which velocity
# files got acceptable QA scores.)
good_vel_fpaths = glob.glob(os.path.join(veldir, "list_good_20??.txt"))

# Remove the paths of any empty files (otherwise causes an error in the Pandas loading function).
good_vel_paths = [
    fpath
    for fpath in good_vel_fpaths.copy()
    if len(open(fpath, "r").read()) != 0
]

# Catch cases where there a no "good", non-empty velocity files.
if len(good_vel_paths) == 0:
    log_to_stdout_and_file(f"No good, non-empty velocity files found for {glacier}. Stopping script.")
    sys.exit(1)

# Create a big dataframe that concatenates all the "good", non-empty velocity files.
df = pd.concat(
    [
        pd.read_csv(fpath, header=None, sep='\t')
        # for fpath in good_vel_fpaths  # ORIGINAL: think this was typo
        for fpath in good_vel_paths  # CORRECT: excludes empty files
    ],
    axis=0
)

# Edit the dataframe to contain only IDs and the corresponding directories.
df.columns = ["id", "filter_ratio_1", "filter_ratio_2"]
df.drop(columns=["filter_ratio_1", "filter_ratio_2"], inplace=True)
df["dir"] = veldir + "/" + df["id"]

# Add date1 and date2 columns.
regex = r"(?<!\d)(\d{8}\D\d{2})(?!\d)" # Find datetime format.
df["date1"] = pd.to_datetime(df["id"].str.findall(regex).str[0])
df["date2"] = pd.to_datetime(df["id"].str.findall(regex).str[1])

# Filter out any records that aren't between the minimum and maximum dates.
df = df[(df['date1'] >= start_date) & (df['date2'] <= end_date)]


# Add datetime string columns based on both date 1 and date 2.
df["datehourstr_1"] = df["id"].str.findall(regex).str[0]
df["datehourstr_2"] = df["id"].str.findall(regex).str[1]

# Filter out any records whose datetime strings aren't in the glacier image metadata dictionary for this AOI.
df = df[
    (df['datehourstr_1'].isin(list(time_dict.keys())))
    &
    (df['datehourstr_2'].isin(list(time_dict.keys())))
]

# Add datetime object columns based on both date 1 and date 2.
df["datetimestr_1"] = [time_dict[x] for x in df["datehourstr_1"]]
df["datetimestr_2"] = [time_dict[x] for x in df["datehourstr_2"]]
df["datetime_1"] = pd.to_datetime(df["datetimestr_1"])
df["datetime_2"] = pd.to_datetime(df["datetimestr_2"])
df.drop(
    labels=["datehourstr_1", "datehourstr_2", "datetimestr_1", "datetimestr_2"],
    axis=1,
    inplace=True
)

# Add the rest of the time-based columns.
df["day_sep"] = pd.to_numeric(
    (df["datetime_1"] - df["datetime_2"]) / np.timedelta64(1, "D"),
    downcast="integer"
)
df["year"] = pd.DatetimeIndex(df["date1"]).year
df["midpoint"] = df["datetime_1"] + (df["datetime_2"] - df["datetime_1"]) / 2
df["baseline"] = df["datetime_2"] - df["datetime_1"]
df["baseline"] = df["baseline"] / np.timedelta64(1, "D")
df["halfbaseline"] = df["datetime_2"] - df["midpoint"]
df["halfbaseline"] = df["halfbaseline"] / np.timedelta64(1, "D")

# Add the orbit and PDGS columns (making use of the image-metadata dictionaries
# generated above).
regex = r"(?<!\d)(\d{8}\D\d{2})(?!\d)"  # Datetime format.
df["datehr1"] = df["id"].str.findall(regex).str[0]
df["datehr2"] = df["id"].str.findall(regex).str[1]
df["orbit1"] = df["datehr1"].map(orbital_dict)
df["processingbaseline1"] = df["datehr1"].map(pb_dict)
df["orbit2"] = df["datehr2"].map(orbital_dict)
df["processingbaseline2"] = df["datehr2"].map(pb_dict)
df["orbit_pair"] = "R" + df["orbit1"] + "_R" + df["orbit2"]
df["orbit_match"] = np.where((df["orbit1"] == df["orbit2"]), 1, 0)
df.drop(columns=["datehr1", "datehr2"], inplace=True)

# Save the dataframe to a .csv.
out_fpath = os.path.join(outdir, glacier + "_orbit_pairs.csv")
df.to_csv(out_fpath, index=False)

# Plot, from the dataframe, image counts for each orbital pair.
valuecounts = df.orbit_pair.value_counts().sort_index()
valuecounts.plot(kind="bar")
plt.xlabel("Orbital Pairing")
plt.ylabel("Count")
plt.tight_layout()
out_fpath = os.path.join(outdir, glacier + "_orbit_pairs.png")
plt.savefig(os.path.join(out_fpath), dpi=600)
plt.close()


###################################################################################################
# Construct a profile of metadata the whole glacier AOI (including bounds, resolution, etc.).
###################################################################################################

log_to_stdout_and_file("Creating metadata profile of whole glacier AOI...")

# Retrieve the glacier AOI bounding-box geopackage and read it into a geodataframe.
aoi_fpath = os.path.join(outdir_container, glacier + ".gpkg")
aoi_gdf = gpd.read_file(aoi_fpath).to_crs(3413)

# Get the bounds of the glacier AOI (in several formats).
global bounds
bounds = aoi_gdf.loc[aoi_gdf['region'] == glacier].iloc[0].geometry.bounds
global xmin, ymin, xmax, ymax
xmin, ymin, xmax, ymax = bounds
global extent
extent = (xmin, xmax, ymin, ymax)

# Extract the resolution from an example raw velocity field.
raw_fpath = glob.glob(os.path.join(veldir, "vmap*", f"*dmag.tif"))[0]
with rs.open(raw_fpath) as src:

    # Round to the nearest hundreth (this corrects for cases where x and y resolutions are extremely close but off by a tiny, tiny number).
    vel_resolution = round(src.res[0], 2)

# Update the profile based on an example clipped mosaic image file.
src_fpath = glob.glob(os.path.join(clipped_dir, f"*.tif"))[0]
with rs.open(src_fpath) as src:

    # Verify the resolution of the image is equal in the x and y directions.
    if round(src.res[0], 2) == round(src.res[1], 2):
        # Round to the nearest hundreth (this corrects for cases where x and y resolutions are extremely close but off by a tiny, tiny number).
        ortho_resolution = round(src.res[0], 2)
    else:
        log_to_stdout_and_file(f"Error: resolution of ortho fields are not equal in x and y direction: ({src.res}). Exiting script.")
        sys.exit(1)

    # Get the width and height in pixels of the glacier AOI.
    width = (xmax - xmin) / vel_resolution
    height = (ymax - ymin) / vel_resolution

    # Create a new transform using the AOI bounds, width and height.
    transform = rs.transform.from_bounds(*bounds, width, height)

    # Update the source profile for the glacier AOI.
    global write_profile
    write_profile = src.profile
    write_profile.update(
        transform=transform,
        driver='GTiff',
        height=height,
        width=width,
        dtype=rs.float32,
        nodata=-9999.0
    )


###################################################################################################
# Get "a priori" velocity field (median of all repeat-track velocity fields).
###################################################################################################

log_to_stdout_and_file("Geting a priori velocity fields (median of all repeat-track velocity fields)...")

# If the file containing median orbit-match information doesn't already exist, create it.
median_fpath = os.path.join(outdir, f"{glacier}_median_orbitmatch_dy.tif")  # Fixed f-string syntax
if not os.path.exists(median_fpath):

    # Construct median of all velocities made from "repeat-track" orbits (rather than cross-track orbits).
    # Create a version of the dataframe of to-be-corrected velocity file metadata, including only those
    # velocity files that are repeat-track.
    df_filtered = df.loc[(df["orbit_match"] == 1)]

    if df_filtered.empty:
        log_to_stdout_and_file(f"Error: No repeat-track entries in the list of \"good\" velocity fields for {glacier}. Exiting script.")
        sys.exit(1)

    # Generate a .tif file which is the median of all the velocity arrays in the repeat-track
    # velocities dataframe:
    vel_orbitmatch = get_median_field_of_arrays_from_df(glacier, df_filtered, bounds, "dmag.tif", outdir, write_profile)
    
    # Plot the median velocity .tif.
    if vel_orbitmatch is not None:
        vmax = 30
        out_fname = f"{glacier}_median_orbitmatch_map.png"
        out_fpath = os.path.join(outdir, out_fname)
        plot_velocity(vel_orbitmatch, extent, vmax, out_fpath)


    ###############################################################################################
    # Also calculate a .tif representing the flow direction derived from the a priori field.
    ###############################################################################################

    log_to_stdout_and_file("\t\tCalculating flow direction of a priori field...")

    # Generate 2 more median velocity .tif files, but for the x and y components separately.
    get_median_field_of_arrays_from_df(glacier, df_filtered, bounds, "dx.tif", outdir, write_profile)
    get_median_field_of_arrays_from_df(glacier, df_filtered, bounds, "dy.tif", outdir, write_profile)

    # Generate the flow-direction .tif from the x- and y- component median velocity .tifs.
    dx_fname = f"{glacier}_median_orbitmatch_dx.tif"
    dx_fpath = os.path.join(outdir, dx_fname)
    dy_fname = f"{glacier}_median_orbitmatch_dy.tif"
    dy_fpath = os.path.join(outdir, dy_fname)
    generate_flow_direction_tif(glacier, dx_fpath, dy_fpath, outdir)


###################################################################################################
# For each orbit pair, create a .tif file representing the difference (offset) between the median
# velocities for that orbit pair and the a priori field.
###################################################################################################

log_to_stdout_and_file("Calculate displacement offset of each orbit pair from a priori field...")

# Get a dataframe of all unique, non-nan orbit pair IDs in the velocities files.
orbit_pairs = df["orbit_pair"].unique()
orbit_pairs = [x for x in orbit_pairs if str(x) != "nan"]

# For each unique orbit pair ID, generate a .tif representing the difference between: 1. the
# median of all the images from that orbit pair, and 2: the "a priori" field.
for orbit_pair in orbit_pairs:
    get_offset_of_orbit_pairs_from_a_priori(
        glacier,
        orbit_pair,
        df,
        extent,
        bounds,
        outdir,
        write_profile,
        diff_from_average=True,
        displacement=True,
        medfilt=True
    )

log_to_stdout_and_file("Finished.")

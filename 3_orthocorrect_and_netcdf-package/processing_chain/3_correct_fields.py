"""
Generate mask of study area.
Loop through velocity fields, deriving uncertainty (using mask), filtering data,
and outputting metadata.
"""



###################################################################################################
# Imports.
###################################################################################################

# Import basic python resources.
import argparse, sys, os, glob
from tqdm import tqdm
# Import geographic-data-handling libraries.
import numpy as np
import pandas as pd
import rasterio as rs
from osgeo import gdal

# Import config values.
sys.path.append(".")
from lib.config import GIMPMASKDIR, WD, OUTDIRNAME, GLAC, START_DATE, END_DATE
# Import utility functions.
from lib.utility import create_dir, load_resampled_array, shapely_bounds, read_raster
from lib.log import setUpBasicLoggingConfig, log_to_stdout_and_file
# Import subfunctions of main program.
from lib.correct_fields_parts import get_gimp_tiles, clip_gimp_tiles, create_offset_dict, correct_velocity





###############################################################################################
# Parse command-line arguments.
###############################################################################################

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
setUpBasicLoggingConfig(log_name, f"Attempting to apply correction fields.")



###################################################################################################
# Set up directories and file paths.
###################################################################################################

# Get directory paths.
out_dir = os.path.join(base_dir, OUTDIRNAME, glacier)
orb_dir = os.path.join(out_dir, "orbits")
cor_dir = os.path.join(out_dir, "velocities")
plt_dir = os.path.join(out_dir, "velocities", "previews")
msk_dir = os.path.join(out_dir, "gimp_masks")

# Create directories.
create_dir(cor_dir)
create_dir(plt_dir)
create_dir(msk_dir)

# Get file paths.
orbits_fpath = os.path.join(orb_dir, f"{glacier}_orbit_pairs.csv")
flow_fpath = os.path.join(
    orb_dir, f"{glacier}_median_orbitmatch_flowdir.tif")



###################################################################################################
# Open orbital metadata and flow-direction image.
###################################################################################################

# Get reasonable max velocity for plotting (high percentile rounded up to nearest 10).
with rs.open(os.path.join(orb_dir, f"{glacier}_median_orbitmatch_dmag.tif")) as src:
    VMAX_VEL = np.ceil(np.nanpercentile(src.read(), 95)/10) * 10

# Load orbital metadata dictionary.
orbital_df = pd.read_csv(orbits_fpath)

# Load flow direction .tif.
flowdir_array = read_raster(flow_fpath)


###################################################################################################
# Get the resolution and write profile.
###################################################################################################

# Get reference geospatial data for reading/writing, and then...
example_tif_fpath = glob.glob(
    os.path.join(orb_dir, "*orbitmatch_dmag.tif"))[0]
with rs.open(example_tif_fpath) as src:
    # Get the resolution.
    if round(src.res[0], 2) == round(src.res[1], 2):
        global res
        res = src.res[0]
    else:
        log_to_stdout_and_file(
            f"Error: resolution of orbit fields are not equal in x and y direction ({src.res}). Exiting script.")
        sys.exit(1)

    # Update the write profile based on the reference data.
    global write_profile
    write_profile = src.profile

    # Set global xmin, xmax, ymin, ymax, bounds and extent from the reference data.
    global xmin, ymin, xmax, ymax
    xmin, ymin, xmax, ymax = src.bounds
    global bounds
    bounds = src.bounds
    global extent
    extent = (xmin, xmax, ymin, ymax)


###################################################################################################
# Create/load AOI rock/ice masks.
###################################################################################################

# Create AOI rock/ice masks if necessary.
rock_mask_fpath = os.path.join(msk_dir, "mask_rock.tif")
ice_mask_fpath = os.path.join(msk_dir, "mask_ice.tif")
if not os.path.exists(rock_mask_fpath):
    aoi = shapely_bounds(example_tif_fpath)
    tiles = get_gimp_tiles(GIMPMASKDIR, aoi)
    clip_gimp_tiles(tiles, bounds, msk_dir)

# Load masks (resampled to the appropriate size/resolution for the velocity fields).
rockmask_array = load_resampled_array(
    rock_mask_fpath, example_tif_fpath, resamp_alg=gdal.GRA_NearestNeighbour)
icemask_array = load_resampled_array(
    ice_mask_fpath, example_tif_fpath, resamp_alg=gdal.GRA_NearestNeighbour)


###################################################################################################
# Get dx and dy offsets to apply to the velocity fields.
###################################################################################################

# Get dx and dy offsets to apply to the velocity fields.
log_to_stdout_and_file("Getting dx/dy offsets to apply to the velocity fields...")
orbit_pairs = orbital_df["orbit_pair"].unique()
orbit_pairs = [x for x in orbit_pairs if str(x) != "nan"]  # clean list
dx_diff_dict = create_offset_dict("dx", orb_dir, orbit_pairs, example_tif_fpath)
dy_diff_dict = create_offset_dict("dy", orb_dir, orbit_pairs, example_tif_fpath)


###################################################################################################
# Apply the offsets to the velocity fields.
###################################################################################################

# For each velocity field,
log_to_stdout_and_file(f"Applying offsets to {len(orbital_df)} velocity fields...")
for _, row in tqdm(orbital_df.iterrows()):
    # Get the dx and dy offset arrays for this orbit pair.
    dx_diff_array = dx_diff_dict.get(row["orbit_pair"])
    dy_diff_array = dy_diff_dict.get(row["orbit_pair"])

    # Skip if they are None.
    if dx_diff_array is None:
        del dx_diff_array, dy_diff_array
        continue

    # Apply the offsets to correct the velocity field.
    correct_velocity(
        glacier,
        row,
        dx_diff_array,
        dy_diff_array,
        flowdir_array,
        rockmask_array,
        icemask_array,
        example_tif_fpath,
        VMAX_VEL,
        cor_dir,
        plt_dir,
        bounds,
        res,
        write_profile,
        extent
    )
    del dx_diff_array, dy_diff_array

log_to_stdout_and_file("Finished.")


###################################################################################################
# Imports.
###################################################################################################

import os
import glob
import warnings
import sys

import rasterio as rs
from osgeo import gdal
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("agg") # Write to file rather than window.
import cv2
from shapely.geometry import Polygon
gdal.UseExceptions() # Enable GDAL exceptions.
from rasterio.windows import from_bounds

sys.path.append(".")
from lib.config import GLAC
from lib.utility import read_to_bounds
from lib.log import log_to_stdout_and_file



###################################################################################################
# Parse parameters.
###################################################################################################

# Override GLAC and OUTDIRNAME variables when run in batch.
try:
    GLAC = sys.argv[1]
except IndexError:
    pass
try:
    OUTDIRNAME = sys.argv[2]
except IndexError:
    pass


###################################################################################################
# Utility functions.
###################################################################################################


def get_list_of_masked_and_filtered_velocity_arrays_from_df(
        vel_files_df,
        wildcard,
        bounds,
        orbit_pair,
        medfilt
    ):

    ###############################################################################################
    # Get list of velocity image files and list of corresponding arrays based on those files.
    ###############################################################################################

    # Get a list paths for files with the specified wildcard in the velocities directories (and exit
    # if there's no such files).
    fpath_list = [glob.glob(x+f"/*{wildcard}")[0] for x in vel_files_df["dir"]]
    if len(fpath_list) == 0:
        log_to_stdout_and_file(f"Error: No velocity field files were found for orbit pair {orbit_pair}.")
        quit()

    # Get a list of arrays based on the input files (and exit if they're malformed).
    array_list = get_list_of_arrays_from_list_of_files(
        fpath_list,
        bounds
    )

    ###############################################################################################
    # Mask and 3x3 filter the input arrays.
    ###############################################################################################

    # Where applicable (i.e. the 2021 dataset), if there is a `_mask.tif` file, apply it as a mask
    # (with nan values for nodata) before continuing.
    array_list = mask_list_of_arrays(fpath_list, array_list, bounds)

    # If filtering has been specified, filter the list of arrays using a 3x3 median filter to
    # reduce noise.
    if medfilt is True:
        array_list = [cv2.medianBlur(x, 3) for x in array_list]

    return fpath_list, array_list


def generate_average_products_from_array_list(
    glacier,
    fpath_list,
    array_list,
    orbit_pair,
    medfilt,
    outdir,
    out_fpath,
    write_profile,
    metadata
):

    ###############################################################################################
    # Get the median field of all the arrays from the list produced above. (3x3 filter it if
    # required.)
    ###############################################################################################

    # Get a single array that is the median (excluding nan values) of all the arrays in the list.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        array_average = np.nanmedian(array_list, axis=0)

    # If filtering has been specified, filter the list of arrays using a 3x3 median filter to
    # reduce noise.
    if medfilt is True:
        array_average = cv2.medianBlur(array_average, 3)


    ###############################################################################################
    # Generate output files and return the filtered median array.
    ###############################################################################################

    # Write the median array to a file.
    with rs.open(out_fpath, "w", **write_profile) as dst:
        dst.write(array_average.astype(rs.float32), 1)

    # If metadata generation has been specified, generate the metadata file.
    if metadata is True:
        out_fname = os.path.join(
            f"{glacier}_median_offset_{orbit_pair}_list.txt"
        )
        out_fpath = os.path.join(outdir, out_fname)
        txt_file = open(out_fpath, "w")
        txt_list = map(lambda x: x + "\n", fpath_list)
        txt_file.writelines(txt_list)
        txt_file.close()

    return array_average


def calc_diff_from_avg(
    avg_fpath,
    bounds,
    array_list
):    
    median_array = read_to_bounds(
        avg_fpath,
        bounds,
        how='gdal',
        gdal_resamp=gdal.GRA_NearestNeighbour,
        nodata_values=[0, -9999]
    )

    # Calculate offset from the a priori average.
    array_list = [(median_array - x) for x in array_list]

    return array_list


def convert_velocity_array_list_to_displacement_array_list(
    vel_files_df,
    fpath_list,
    array_list
):
    # Get a list of separations between the begin and end dates for each velocity field (and
    # exit if this list isn't the same length as the number of file paths with the specified
    # wildcard).
    day_sep_list = vel_files_df["day_sep"].tolist()
    if len(fpath_list) != len(day_sep_list):
        log_to_stdout_and_file("There are fewer valid velocity field files than the number of entries in `day_sep_list`. Quitting.")
        quit()

    array_list = [(x * t) for x, t in zip(array_list, day_sep_list)]

    return array_list




def get_list_of_arrays_from_list_of_files(
    fpath_list,
    bounds
):
    """
    fpath_list      List of file paths to get the arrays from.
    bounds          Bounds of the glacier AOI.
    """

    ###############################################################################################
    # Get a list of arrays based on the input files (and exit if they're malformed).
    ###############################################################################################

    # Create a list of arrays based on each .tif file with the specified wildcard, trimmed to the
    # bounds of the glacier AOI.
    array_list = [
        read_to_bounds(
            fpath,
            bounds,
            how='gdal',
            gdal_resamp=gdal.GRA_Cubic,
            nodata_values=[0, -9999]
        )
        for fpath in fpath_list
    ]
    
    # Check that all of the arrays in the list are the same size, and raise an error if they're
    # malformed.
    array_shape_list = [x.shape for x in array_list]
    unique_shapes = list(set(array_shape_list))
    if len(unique_shapes) > 1:
        raise ValueError(
            f"Loaded rasters have multiple array sizes: {unique_shapes}")
    
    return array_list


def mask_list_of_arrays(
    fpath_list,
    array_list,
    bounds
):
    # Where applicable (i.e. the 2021 dataset), if there is a `_mask.tif` file, apply it as a mask
    # (with nan values for nodata) before continuing.
    for fpath, array, i in zip(fpath_list, array_list, range(len(array_list))):
        mask_fpath = fpath.rsplit("_", 1)[0] + "_mask.tif"
        if os.path.exists(mask_fpath):
            mask = read_to_bounds(
                mask_fpath,
                bounds,
                how='gdal',
                gdal_resamp=gdal.GRA_NearestNeighbour
            )
            array[mask == 0] = np.nan
            array_list[i] = array
        else:
            continue

    return array_list

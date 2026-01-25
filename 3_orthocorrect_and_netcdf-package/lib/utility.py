
###################################################################################################
# Imports.
###################################################################################################

import os, sys

import rasterio as rs
from osgeo import gdal
import numpy as np
import matplotlib
matplotlib.use("agg") # Write to file rather than window.
from shapely.geometry import Polygon
gdal.UseExceptions() # Enable GDAL exceptions.
from rasterio.windows import from_bounds
from lib.log import error_messages_to_ignore, log_to_stdout_and_file




###################################################################################################
# Utility functions (originally from `chudley_utils` package).
###################################################################################################

def try_command_with_log_and_discontinue_on_error(glacier, start_date, end_date, base_dir, log_name, command_string):
    """ 
        Tries to run the specified command. If there's an error, exits this Python process with
        an error code.

        Parameters
        ----------
        glacier: The name of the glacier that the command will be run for.
        start_date: The start date of the data that the command will be run for.
        end_date: The end date of the data that the command will be run for.
        base_dir: The working directory that outputs of the command should go to.
        command_string: The command, as a string.
    """

    # Get the command string completed with arguments.
    command_string_with_arguments = f"{command_string} --glacier {glacier} --start_date {start_date} --end_date {end_date} --base_dir {base_dir} --log_name {log_name}"

    # Run the command and get the exit code (0 if succesful, not 0 if errored).
    exit_code = os.system(command_string_with_arguments)

    # If there was an error,
    if exit_code != 0:
        # Add the glacier name and the command string to the "errored glaciers" list.
        errored_glaciers_log_name = f"{'/'.join(log_name.split('/')[:-1])}/errored_glaciers.log"
        with open(errored_glaciers_log_name, "a") as errored_glaciers:
            errored_glaciers.write(f"\nGLACIER: {glacier}, COMMAND: {command_string}")
            
    # Return the exit code.
    return exit_code




def try_command_with_log_and_continue_on_error(glacier, start_date, end_date, base_dir, log_name, command_string):
    """
        Tries to run the specified command. If there's an error, logs it but continues processing.
        Used for optional steps that should not stop the workflow if they fail.

        Added 2025-12-15 for graceful degradation: allows NetCDF packaging steps (4a/4b) to fail
        without stopping the entire workflow, enabling partial outputs when data sources are missing.

        Works complementarily with try_command_with_log_and_discontinue_on_error:
        - This function: Used for Steps 4a/4b (data packaging) - allows graceful failures
        - Sister function: Used for Steps 1-3,4c (infrastructure) - stops on critical failures

        Example: Glaciers 154_Heinkel, 178_AlangorssupSermia, 184_Usugdlup failed Landsat processing
        but produced usable Sentinel-2 only velocity data instead of complete failure.

        Parameters
        ----------
        glacier: The name of the glacier that the command will be run for.
        start_date: The start date of the data that the command will be run for.
        end_date: The end date of the data that the command will be run for.
        base_dir: The working directory that outputs of the command should go to.
        command_string: The command, as a string.

        Returns
        -------
        exit_code: 0 if successful, non-zero if failed
    """

    # Get the command string completed with arguments.
    command_string_with_arguments = f"{command_string} --glacier {glacier} --start_date {start_date} --end_date {end_date} --base_dir {base_dir} --log_name {log_name}"

    # Run the command and get the exit code (0 if succesful, not 0 if errored).
    exit_code = os.system(command_string_with_arguments)

    # If there was an error,
    if exit_code != 0:
        # Log the error but don't stop processing
        log_to_stdout_and_file(f"Command failed but continuing workflow: {command_string}")
        # Still add to errored glaciers log for tracking
        errored_glaciers_log_name = f"{'/'.join(log_name.split('/')[:-1])}/errored_glaciers.log"
        with open(errored_glaciers_log_name, "a") as errored_glaciers:
            errored_glaciers.write(f"\nGLACIER: {glacier}, COMMAND: {command_string} (CONTINUED)")

    # Return the exit code.
    return exit_code




def create_dir(dir_path):
    """
    Create a directory from a given directory path, if it doesn't already exist.
    """
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
        except FileExistsError:
            pass
    return




def load_resampled_array(
    in_fpath, target_fpath, nodata_values=None, resamp_alg=gdal.GRA_Bilinear
):
    """
    Returns an array of the tif located at in_fpath, resampled to the bounds and
    resolution of the tif located at target_fpath.

    In current format, does not transform spatial reference system (EPSG)
    """

    # Get geolocation info from the target to apply when resampling mask
    with rs.open(target_fpath) as src:
        # get target_xres, target_yres, xmin, xmax, ymin, xymax
        xmin, ymin, xmax, ymax = src.bounds
        dst_xres, dst_yres = src.res
        dst_shape = src.shape
        # dst_crs = src.crs
        dst_transform = src.transform

    # Resample mask to target projection in-memory
    # ERROR 1: PROJ: proj_create_from_database: crs not found
    resamp_ds = gdal.Warp(
        "",
        in_fpath,
        format="MEM",
        outputBounds=[xmin, ymin, xmax, ymax],
        xRes=dst_xres,
        yRes=dst_yres,
        # dstSRS=target_proj,
        resampleAlg=resamp_alg,
        # options=["COMPRESS=LZW"],  # BNY removed for GDAL 3.8+
    )
    # load resampled mask into global variable space
    array = resamp_ds.GetRasterBand(1).ReadAsArray()
    del resamp_ds

    if nodata_values is not None:
        if not isinstance(nodata_values, list):
            raise TypeError("nodata_values should be a list of values.")
        else:
            for value in nodata_values:
                array[array == value] = np.nan

    return array


# getBoundsAsShapelyPolygon
def shapely_bounds(fpath):
    """
    From a given tif fpath, return bounds as shapely polgyon using rasterio
    and shapely.
    Output: shapely polygon

    fpath   path to .tif file
    """
    with rs.open(fpath) as src:
        xmin, ymin, xmax, ymax = src.bounds
        tl, bl, tr, br = (xmin, ymax), (xmin, ymin), (xmax, ymax), (xmax, ymin)
    bounds = Polygon([tl, bl, br, tr])
    return bounds


def read_to_bounds(fpath, bounds, how='gdal', gdal_resamp=gdal.GRA_Bilinear, epsg=3413, nodata_values=None):
    """ 
    Read array with set bounds, derived from global variables xmin/ymin/xmax/ymax
    fpath: path to raster
    bounds: bounds in format (xmin, ymin, xmax, ymax)
    """

    how_options = ['gdal', 'rasterio']

    if how not in how_options:
        raise ValueError(f"Invalid how option. Expected one of: {how_options}")

    if how == 'rasterio':

        with rs.open(fpath) as src:
            array = src.read(1, window=from_bounds(*bounds, src.transform))

    if how == 'gdal':

        # with rs.open(fpath) as src:
        #     proj = src.crs.to_epsg()
        array = gdal.Warp(
            "",
            fpath,
            format="MEM",
            outputBounds=[*bounds],  # [xmin, ymin, xmax, ymax]
            # xRes=target_res, yRes=target_res,
            srcSRS=f"EPSG:{epsg}",
            dstSRS=f"EPSG:{epsg}",
            resampleAlg=gdal_resamp,
            # options=["COMPRESS=LZW"],
        )        
        array = array.GetRasterBand(1).ReadAsArray()

    # array[array == 0] = np.nan
    # array[array == -9999] = np.nan
    if nodata_values is not None:
        if not isinstance(nodata_values, list):
            raise TypeError("nodata_values should be a list of values.")
        else:
            for value in nodata_values:
                array[array == value] = np.nan

    return array


def read_raster(fpath, band=1, nodata_values=None):
    """
    Simple read of one band of a geotif to numpy array.
    fpath:          file path of geotiff
    band:           band number. defaults to 1 (as per gdal, count is 
                    from 1, not 0)
    nodata_values:  list of band values to set to np.nan
    """
    with rs.open(fpath) as src:
        array = src.read(band)

    if nodata_values is not None:
        if not isinstance(nodata_values, list):
            raise TypeError("nodata_values should be a list of values.")
        else:
            for value in nodata_values:
                array[array == value] = np.nan
    # array[array == 0] = np.nan
    # array[array == -9999] = np.nan

    return array



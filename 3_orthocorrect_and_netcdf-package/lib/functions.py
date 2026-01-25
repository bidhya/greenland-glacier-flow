
###################################################################################################
# Imports.
###################################################################################################

import os
import sys
import json
import glob
import numpy as np
import pandas as pd
import rasterio as rs
import rioxarray as rxr
import xarray as xr

from lib.config import GLAC, THRESH_COUNT
from lib.function_parts import get_list_of_masked_and_filtered_velocity_arrays_from_df, generate_average_products_from_array_list, calc_diff_from_avg, convert_velocity_array_list_to_displacement_array_list
from lib.plot import plot_velocity_diff, plot_velocity
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
# Functions.
###################################################################################################
    

def get_median_field_of_arrays_from_df(
    glacier,
    vel_files_df,
    bounds,
    wildcard,
    outdir,
    write_profile
):
    """
    vel_files_df    Velocity field file list (in dataframe form). Contains a 'dir' column, listing the directories
                    containing the .tif files to be averaged. Also contains a "day_sep" column, listing
                    the difference in aquisition times (in days) between the images used to construct
                    each velocity field.
    bounds          Bounds of the glacier AOI.
    wildcard        Wildcard string indicating which velocity field files to use. (i.e.
                    'dmag.tif', 'dx.tif', or 'dy.tif').
    outdir          Output directory.
    """

    log_to_stdout_and_file(f"\t\tMerging {len(vel_files_df['dir'])} {wildcard} rasters")
    
    # Set the output filepath (and exit if it exists).
    out_fname = f"{glacier}_median_orbitmatch_{wildcard}"
    out_fpath = os.path.join(outdir, out_fname)
    if os.path.exists(out_fpath):
        log_to_stdout_and_file(f"\t\t{os.path.basename(out_fpath)} already exists. Skipping.")
        return

    # Get list of velocity image files and list of corresponding masked and filtered arrays based
    # on those files.
    fpath_list, array_list = get_list_of_masked_and_filtered_velocity_arrays_from_df(
        vel_files_df,
        wildcard,
        bounds,
        "orbitmatch",
        True
    )

    # Return the median field of all the arrays from the list produced above. (3x3 filter it if
    # required.) Generate output files and return the filtered median array.
    array_average = generate_average_products_from_array_list(
        glacier,
        fpath_list,
        array_list,
        "orbitmatch",
        True,
        outdir,
        out_fpath,
        write_profile,
        False
    )
    array_list = None
    return array_average
    

def generate_flow_direction_tif(glacier, dx_fpath, dy_fpath, outdir):
    """
    Get an array of the local flow direction, defined in degrees anti-clockwise from x-axis, from
    the x- and y-displacement array .tifs. Write it to a .tif file.

    dx_fpath        The path for the x-displacement .tif file.
    dy_fpath        The path for the y-displacement .tif file.
    outdir          The directory to write the output flow-direction .tif file to.
    """
    # Open x-displacement .tif file (and get metadata from it).
    with rs.open(dx_fpath) as src:
        dx = src.read(1)
        meta = src.meta
        meta.update(dtype=rs.float32)

    # Open y-displacement .tif file.
    with rs.open(dy_fpath) as src:
        dy = src.read(1)

    # Calculate an array of the flow direction based on the x- and y-displacement arrays. Confine
    # this between -180 to 180 degrees.
    angle = np.degrees(np.arctan(dy / dx))
    angle = np.where(dx > 0, angle, angle + 180)
    angle = np.where(angle > 180, angle - 360, angle)

    # Write the flow-direction array to a .tif file.
    flow_fname = f"{glacier}_median_orbitmatch_flowdir.tif"
    flow_fpath = os.path.join(outdir, flow_fname)
    with rs.open(flow_fpath, "w", **meta) as dst:
        dst.write(angle.astype(rs.float32), 1)

    del dx, dy


def get_offset_of_orbit_pairs_from_a_priori(
    glacier,
    orbit_pair,
    df,
    extent,
    bounds,
    outdir,
    write_profile,
    diff_from_average=False,
    displacement=False,
    medfilt=False
):
    """
    Generate offset-to-correct array .tif files for the x- and y-displacement components, and save
    them to .tif files.

    orbit_pair      String indicating which orbit pair the velocity fields are for, for naming
                    purposes (e.g. 'R096_R053').
    df              Dataframe of orbit-pair info.
    extent          The minimum and maximum x and y coordinates of the glacier AOI.
    outdir          Output directory to save files to.
    diff_from_average       If the function should output the _difference_ from the a priori median
                    flow field rather than the average, this should be filled with the file
                    path of the  a priori median flow field.
    displacement    Whether the function should correct velocities to displacements by making
                    use of the orbit temporal baseline (The 'day_sep' column of the dataframe).
                    (d = v * t)
    medfilt         Whether to 3x3-median-filter the output before saving.
    """

    log_to_stdout_and_file(f"\tFinding average offsets for orbit_pair: {orbit_pair}")


    ###############################################################################################
    # Filter the dataframe for relevant orbit pairs.
    ###############################################################################################

    # Filter the dataframe to contain only those rows related to the desired orbit pair.
    df_filtered = df.loc[(df["orbit_pair"] == orbit_pair)]

    # If there are too few rows to construct a reliable median, exit.
    if len(df_filtered) < THRESH_COUNT:
        log_to_stdout_and_file(
            f"Insufficient velocity fields to construct median. {orbit_pair} has {len(df_filtered)} pairs, threshold set to {THRESH_COUNT}."
        )
        return


    ###############################################################################################
    # Generate the offset-to-correct arrays.
    ###############################################################################################
    
    # Construct two offset-to-correct arrays, one for the x-displacement component and one for the
    # y-displacement component, using the filtered dataframe. Save to .tif files.
    array_dx = get_offset_of_orbit_pair_from_a_priori(
        glacier,
        df_filtered,
        bounds,
        "dx.tif",
        orbit_pair,
        outdir,
        write_profile,
        False
    )
    if array_dx is None:
        return
    array_dy = get_offset_of_orbit_pair_from_a_priori(
        glacier,
        df_filtered,
        bounds,
        "dy.tif",
        orbit_pair,
        outdir,
        write_profile,
        False
    )


    ###############################################################################################
    # Calculate and plot the absolute offset-to-correct array.
    ###############################################################################################

    # Calculate the absolute offset for plotting.
    array_mag = np.sqrt(np.square(array_dx) + np.square(array_dy))
    del array_dx, array_dy

    # If calculating the difference from average, plot the absolute magnitude of that.
    if diff_from_average is True:
        vmax = 70
        out_fname = f"{glacier}_median_offset_{orbit_pair}_map.png"
        out_fpath = os.path.join(outdir, out_fname)
        plot_velocity_diff(array_mag, extent, vmax, out_fpath)

    # if calculating the average, just plot the velocity [NOT USED].
    else:
        vmax = 30
        out_fname = f"{glacier}_median_{orbit_pair}_map.png"
        out_fpath = os.path.join(outdir, out_fname)
        plot_velocity(array_mag, extent, vmax, out_fpath)

    del array_mag


def get_offset_of_orbit_pair_from_a_priori(
    glacier,
    vel_files_df,
    bounds,
    wildcard,
    orbit_pair,
    outdir,
    write_profile,
    medfilt=False,
):
    """
    vel_files_df    Velocity field file list (in dataframe form). Contains a 'dir' column, listing the directories
                    containing the .tif files to be averaged. Also contains a "day_sep" column, listing
                    the difference in aquisition times (in days) between the images used to construct
                    each velocity field.
    bounds          Bounds of the glacier AOI.
    wildcard        Wildcard string indicating which velocity field files to use. (i.e.
                    'dmag.tif', 'dx.tif', or 'dy.tif').
    orbit_pair      String indicating which orbit pair the velocity fields are for, for naming
                    purposes (e.g. 'R096_R053').
    outdir          Output directory.
    medfilt         Whether to 3x3-median-filter the output before saving.
    """

    log_to_stdout_and_file(f"\t\tMerging {len(vel_files_df['dir'])} {wildcard} rasters")
    
    # Set the output filepath (and exit if that file already exists).
    out_fname = f"{glacier}_median_offset_{orbit_pair}_{wildcard}"
    out_fpath = os.path.join(outdir, out_fname)
    if os.path.exists(out_fpath):
        log_to_stdout_and_file(f"\t\t{os.path.basename(out_fpath)} already exists. Skipping.")
        return

    # Get list of velocity image files and list of corresponding masked and filtered arrays based
    # on those files.
    fpath_list, array_list = get_list_of_masked_and_filtered_velocity_arrays_from_df(
        vel_files_df,
        wildcard,
        bounds,
        orbit_pair,
        medfilt
    )

    # Convert the array list to offsets from the a-priori field.
    median_fpath = os.path.join(outdir, f"{glacier}_median_orbitmatch_{wildcard}")
    array_list = calc_diff_from_avg(median_fpath, bounds, array_list)

    # Convert the arrays from velocity to displacement.
    array_list = convert_velocity_array_list_to_displacement_array_list(vel_files_df, fpath_list, array_list)

    # Get the median field of all the arrays from the list produced above. (3x3 filter it if
    # required.) Generate output files and return the filtered median array.
    array_average = generate_average_products_from_array_list(
        glacier,
        fpath_list,
        array_list,
        orbit_pair,
        medfilt,
        outdir,
        out_fpath,
        write_profile,
        False
    )
    array_list = None
    return array_average


def create_xr_dataset(glacier, dir_fpath):
    """
    Using rioxarray, combine vv/vx/vy fields into single dataset,
    also adding key metadata variables.
    """
    md_fpath = glob.glob(os.path.join(dir_fpath, "*metadata*"))[0]
    md = json.load(open(md_fpath))

    date1 = md["field_info"]["scene_1_datetime"]
    date2 = md["field_info"]["scene_2_datetime"]
    baseline = md["field_info"]["baseline_days"]
    midpoint = md["field_info"]["midpoint_datetime"]
    satellite1 = md["field_info"]["scene_1_satellite"]
    satellite2 = md["field_info"]["scene_2_satellite"]
    orbit1 = md["field_info"]["scene_1_orbit"]
    orbit2 = md["field_info"]["scene_2_orbit"]
    processingbaseline1 = md["field_info"]["scene_1_processing_baseline"]
    processingbaseline2 = md["field_info"]["scene_2_processing_baseline"]
    pct = md["field_info"]["percent_ice_area_notnull"]
    rmse = md["error_units_velocity"]["mag_rmse"]
    dxmn = md["error_units_velocity"]["dx_mean"]
    dxsd = md["error_units_velocity"]["dx_sd"]
    dymn = md["error_units_velocity"]["dy_mean"]
    dysd = md["error_units_velocity"]["dy_sd"]

    date1_datetime = pd.to_datetime(date1)
    date2_datetime = pd.to_datetime(date2)
    midpoint_datetime = pd.to_datetime(midpoint)

    # Set time index
    # time_index = midpoint_datetime
    date1str = pd.to_datetime(
        date1).strftime("%Y%m%dT%H%M%S")
    date2str = pd.to_datetime(
        date2).strftime("%Y%m%dT%H%M%S")
    time_index = f"{date1str}_{date2str}"

    temp_index = np.random.randint(0, 2**63)

    vel_id = f"{glacier}_{date1str}_{date2str}_S2"

    # https://stackoverflow.com/questions/65616979/adding-band-description-to-rioxarray-to-raster

    # vv_fpath = glob.glob(os.path.join(dir_fpath, "*_vv_*"))[0]
    # vv = rxr.open_rasterio(vv_fpath).sel(
    #     band=1, drop=True).expand_dims({"time": [midpoint_datetime]})

    vx_fpath = glob.glob(os.path.join(dir_fpath, "*_vx_*"))[0]
    vx = rxr.open_rasterio(vx_fpath).sel(
        band=1, drop=True).expand_dims({"index": [temp_index]})  # {"time": [time_index]})

    vy_fpath = glob.glob(os.path.join(dir_fpath, "*_vy_*"))[0]
    vy = rxr.open_rasterio(vy_fpath).sel(
        band=1, drop=True).expand_dims({"index": [temp_index]})  # ({"time": [time_index]})

    ds = xr.Dataset()

    # ds["vv"] = vv
    ds["vx"] = vx
    ds["vy"] = vy

    ds = ds.assign({
        "id": ("index", [vel_id]),
        "scene_1_datetime": ("index", [date1_datetime]),
        "scene_2_datetime": ("index", [date2_datetime]),
        "baseline_days": ("index", [baseline]),
        "midpoint_datetime": ("index", [midpoint_datetime]),
        "scene_1_satellite": ("index", [satellite1]),
        "scene_2_satellite": ("index", [satellite2]),
        "scene_1_orbit": ("index", [orbit1]),
        "scene_2_orbit": ("index", [orbit2]),
        "scene_1_processing_version": ("index", [processingbaseline1]),
        "scene_2_processing_version": ("index", [processingbaseline2]),
        "percent_ice_area_notnull": ("index", [pct]),
        "error_mag_rmse": ("index", [rmse]),
        "error_dx_mean": ("index", [dxmn]),
        "error_dx_sd": ("index", [dxsd]),
        "error_dy_mean": ("index", [dymn]),
        "error_dy_sd": ("index", [dysd]),
    })

    return ds



def globsingle(fdir, fpath):
    """returns first glob result of a single directory and wildcard"""
    return glob.glob(os.path.join(fdir, fpath))[0]



def landsat_metadata_from_ids(vel_id):
    """from landsat filename string, return relevant metadata"""

    if (len(vel_id)) > 80:
        satellite = vel_id[37:41]
        cor_lvl = vel_id[42:46]
        pth_row = vel_id[47:53]
        collection = vel_id[72:74]
        tier = vel_id[75:77]
        baseline = f"C{collection}_{tier}_{cor_lvl}"

    # ASTER files are mixed in - ignore these for now
    elif vel_id[15:18] == "AST":
        satellite = "AST"
        pth_row = "AST"
        baseline = "AST"

    else:
        # sat_num = vel_id[17]
        satellite = f"LC0{vel_id[17]}"
        pth_row = vel_id[18:24]
        baseline = "Pre Collection-1"

    return satellite, pth_row, baseline


def get_landsat_ids(meta_fpath):
    """from setsm sdm *meta.txt file, return constituent landsat filenames as list"""
    with open(meta_fpath) as file:
        lines = file.readlines()

    image_ids = []
    for line in lines:
        if line[:5] == "Image":
            image_id = os.path.basename(line[8:-1])
            image_ids.append(image_id)

    return image_ids

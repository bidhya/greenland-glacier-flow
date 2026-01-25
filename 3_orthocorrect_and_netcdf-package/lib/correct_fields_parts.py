###################################################################################################
# Imports.
###################################################################################################

# Import basic python resources.
import sys, os, glob, json
from tqdm import tqdm
# Import geographic-data-handling libraries.
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("agg")  # Write to file rather than window.
import pandas as pd
import rasterio as rs
from osgeo import gdal

# Import config values.
sys.path.append(".")
from lib.config import GIMPMASKDIR, VERSION
# Import utility functions.
from lib.utility import create_dir, load_resampled_array, read_to_bounds, shapely_bounds
from lib.log import log_to_stdout_and_file




###################################################################################################
# Functions.
###################################################################################################

def create_offset_dict(wildcard, orb_dir, orbit_pairs, example_tif_fpath):
    """
    Given a wildcard (dmag, dx, dy) and a list of orbit pairs, get a
    dictionary of offset arrays (from script 2) for every unique orbit pair.
    """

    dictionary = {}

    for orbit_pair in orbit_pairs:

        # Get fpath of orbit pair *diff.tif
        diff_fpath = glob.glob(
            os.path.join(
                orb_dir, f"*offset_{orbit_pair}_{wildcard}.tif")
        )
        if len(diff_fpath) == 0:  # Skip if no offset map exists
            continue
        diff_fpath = diff_fpath[0]

        # Open raster clipped to AOI
        crop_src = load_resampled_array(
            diff_fpath, example_tif_fpath, resamp_alg=gdal.GRA_NearestNeighbour)

        # Add offset to dictionary
        dictionary[orbit_pair] = crop_src

    return dictionary


def correct_velocity(
    glacier,
    row,
    dx_offset,
    dy_offset,
    flowdir_ref,
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
):
    """Create bias-corrected velocity field, calculate uncertainty, filter
    by flow direction.

    row             row of *orbit_pairs.csv dataframe, from script 1.
    dx_diff_array   orbit_pair-specific dx offset, from script 2
    dy_diff_array   orbit_pair-specific dy offset, from script 2
    flowdir_array   median flow direction, from script 2.
    rockmask_array  rockmask_array for numpy, from this script.
    icemask_array   icemask_array for numpy, from this script
    example_tif_fpath  tif of correct (full) size and resolution, as reference
                    for loading smaller tifs with gdal_warp
    """

    # input directory
    in_dir = row["dir"]

    # TODO CHANGE TO DATETIME FROM DATEHOUR
    date1str = pd.to_datetime(row["datetime_1"]).strftime('%Y%m%dT%H%M%S')
    date2str = pd.to_datetime(row["datetime_2"]).strftime('%Y%m%dT%H%M%S')

    # create output id in the format S2_{glacier}_DATE1_DATE2
    vel_id = os.path.basename(in_dir)
    id_part = vel_id.split('_')
    vel_id = f"S2_{glacier}_{date1str}_{date2str}"

    # output directory
    out_dir = os.path.join(cor_dir, vel_id)

    # Create dmag output name, and skip if it already exists
    dmag_raster_name = f"{vel_id}_vv_v{VERSION}.tif"
    dmag_raster_outpath = os.path.join(out_dir, dmag_raster_name)
    if os.path.exists(dmag_raster_outpath):
        # skip if already exists
        log_to_stdout_and_file(f"Skipping -- {vel_id} already exists")
        return

    # create dx/dy input/output name
    dx_raster_inpath = glob.glob(os.path.join(in_dir, "*dx*"))[0]
    dx_raster_name = f"{vel_id}_vx_v{VERSION}.tif"
    dx_raster_outpath = os.path.join(out_dir, dx_raster_name)
    dy_raster_inpath = glob.glob(os.path.join(in_dir, "*dy*"))[0]
    dy_raster_name = f"{vel_id}_vy_v{VERSION}.tif"
    dy_raster_outpath = os.path.join(out_dir, dy_raster_name)

    # metadata/preview figure output fpaths
    metadata_json_outpath = os.path.join(
        out_dir, vel_id + f"_v{VERSION}_metadata.json")
    plot_fig_outpath_1 = os.path.join(
        plt_dir, vel_id + f"_vv_v{VERSION}_preview.jpg")
    plot_fig_outpath_2 = os.path.join(
        out_dir, vel_id + f"_vv_v{VERSION}_preview.jpg")

    # load velocities
    dx = load_resampled_array(
        dx_raster_inpath, example_tif_fpath, nodata_values=[0, -9999], resamp_alg=gdal.GRA_Cubic)
    dy = load_resampled_array(
        dy_raster_inpath, example_tif_fpath, nodata_values=[0, -9999], resamp_alg=gdal.GRA_Cubic)

    # apply *_mask.tif where applicable (2021 dataset)
    mask_fpath = dx_raster_inpath.rsplit("_", 1)[0] + "_mask.tif"
    if os.path.exists(mask_fpath):
        mask = read_to_bounds(
            mask_fpath, bounds, how='gdal', gdal_resamp=gdal.GRA_NearestNeighbour)

        dx[mask == 0] = np.nan
        dy[mask == 0] = np.nan

    # basic filtering
    dx_offset = np.where(dx == np.nan, np.nan, dx_offset)
    dy_offset = np.where(dx == np.nan, np.nan, dy_offset)

    # Apply offset to get final values
    dx_cor = dx + (dx_offset / row["day_sep"])
    dy_cor = dy + (dy_offset / row["day_sep"])

    # generate uncertainty / metadata
    with rs.open(example_tif_fpath) as src:
        resX, resY = res, res
    metadata_dict = generate_metadata(
        glacier,
        vel_id,
        id_part,
        dx_cor,
        dy_cor,
        row["day_sep"],
        rockmask_array,
        row,
        bounds,
        resX,
        resY,
    )

    # filter for flow direction (after uncertainty)
    # Calculate difference between reference and corrected flow direction, in degrees
    with np.errstate(divide="ignore"):  # ignore divide by zero warmings
        angle = np.degrees(np.arctan(dy_cor / dx_cor))
    angle = np.where(dx > 0, angle, angle + 180)
    # from -180 - 180 degrees
    angle = np.where(angle > 180, angle - 360, angle)
    flow_diff = np.abs(flowdir_ref - angle)
    flow_diff = np.where(flow_diff > 180, 360 - flow_diff, flow_diff)
    # filter ice where flowdir difference is > 20 deg
    dx_cor[(flow_diff > 20) & (icemask_array == 1)] = np.nan

    # if <1% ice pixel coverage, skip (do not save)
    ice_px_count = np.count_nonzero(icemask_array)
    vel_icemasked = np.where(icemask_array == 1, dx_cor, np.nan)
    ice_px_vel_count = np.count_nonzero(~np.isnan(vel_icemasked))
    del vel_icemasked
    proportion = ice_px_vel_count / ice_px_count
    if ice_px_vel_count == 0 or proportion < 0.01:
        return

    # add proportion of valid measurements to metadata dictionary
    metadata_dict["field_info"].update(
        {"percent_ice_area_notnull": round(proportion*100, 2)}
    )

    # apply filters to other arrays
    dy_cor[np.isnan(dx_cor)] = np.nan

    # calculate dmag
    dmag_cor = np.sqrt(np.square(dx_cor) + np.square(dy_cor))

    # export velocities
    create_dir(out_dir)
    export_tif(dx_cor, dx_raster_outpath, write_profile)
    export_tif(dy_cor, dy_raster_outpath, write_profile)
    export_tif(dmag_cor, dmag_raster_outpath, write_profile)

    # export metadata
    with open(metadata_json_outpath, "w") as outfile:
        json.dump(metadata_dict, outfile, indent=4)

    del dx, dy, dx_cor, dy_cor, angle, flow_diff, metadata_dict

    # plot velocity
    plt.figure(figsize=(8, 6))
    im = plt.imshow(dmag_cor, extent=extent,
                    cmap="turbo", vmin=0, vmax=VMAX_VEL)
    plt.gca().ticklabel_format(useOffset=False, style="plain")
    plt.title(vel_id)
    plt.xticks(fontsize=7)
    plt.yticks(fontsize=7, rotation=90, va="center")
    cbar = plt.colorbar(im)
    cbar.set_label("Velocity [m d$^{-1}$]")
    plt.tight_layout()
    plt.savefig(plot_fig_outpath_1, dpi=300)
    plt.savefig(plot_fig_outpath_2, dpi=300)
    plt.close()

    del dmag_cor, im, cbar


def generate_metadata(
    glacier, vel_id, id_part, dx, dy, day_sep, rockmask_array, vel_info, bounds, resX, resY
):
    """Generate metadata as json file"""

    # Generate dmag and displacement
    dmag = np.sqrt(np.square(dx) + np.square(dy))

    # Generate rock-masked data
    dx_rock = np.where(rockmask_array == 1, dx, np.nan)
    dy_rock = np.where(rockmask_array == 1, dy, np.nan)
    dmag_rock = np.sqrt(np.square(dx_rock) + np.square(dy_rock))
    dx_rock_disp = dx_rock * day_sep
    dy_rock_disp = dy_rock * day_sep
    dmag_rock_disp = dmag_rock * day_sep

    # Find error variables
    mag_rock_rmse = np.sqrt(np.nanmean(np.square(dmag_rock)))
    dx_rock_mean, dx_rock_sd = np.nanmean(dx_rock), np.nanstd(dx_rock)
    dy_rock_mean, dy_rock_sd = np.nanmean(dy_rock), np.nanstd(dy_rock)
    mag_rock_disp_rmse = np.sqrt(np.nanmean(np.square(dmag_rock_disp)))
    dx_rock_disp_mean = np.nanmean(dx_rock_disp)
    dx_rock_disp_sd = np.nanstd(dx_rock_disp)
    dy_rock_disp_mean = np.nanmean(dy_rock_disp)
    dy_rock_disp_sd = np.nanstd(dy_rock_disp)

    # save uncertainty estimates as json files in original directory
    metadata_dict = {
        "field_info": {
            "id": vel_id,
            "glacier_id": glacier,
            "data": "ice surface velocity",
            "units": "m d^{-1}",
            "source_product": id_part[2],
            "scene_1_satellite": id_part[1],
            "scene_2_satellite": id_part[4],
            "scene_1_datetime": pd.to_datetime(vel_info["datetime_1"]).strftime('%Y-%m-%d T%H:%M:%S'),
            "scene_2_datetime": pd.to_datetime(vel_info["datetime_2"]).strftime('%Y-%m-%d T%H:%M:%S'),
            "midpoint_datetime": pd.to_datetime(vel_info["midpoint"]).strftime('%Y-%m-%d T%H:%M:%S'),
            "baseline_days": (round(vel_info["baseline"], 2)),
            "scene_1_orbit": int(round(vel_info["orbit1"], 0)),
            "scene_2_orbit": int(round(vel_info["orbit2"], 0)),
            "scene_1_processing_baseline": vel_info["processingbaseline1"],
            "scene_2_processing_baseline": vel_info["processingbaseline2"],
        },
        "error_units_velocity": {
            "mag_rmse": round(float(mag_rock_rmse), 2),
            "dx_mean": round(float(dx_rock_mean), 2),
            "dx_sd": round(float(dx_rock_sd), 2),
            "dy_mean": round(float(dy_rock_mean), 2),
            "dy_sd": round(float(dy_rock_sd), 2),
        },
        "error_units_displacement": {
            "mag_displacement_rmse": round(float(mag_rock_disp_rmse), 2),
            "dx_displacement_mean": round(float(dx_rock_disp_mean), 2),
            "dx_displacement_sd": round(float(dx_rock_disp_sd), 2),
            "dy_displacement_mean": round(float(dy_rock_disp_mean), 2),
            "dy_displacement_sd": round(float(dy_rock_disp_sd), 2),
        },
        "geospatial_info": {
            "projection": "WGS 84 / NSDIC Sea Ice Polar Stereographic North",
            "epsg": "3413",
            "coordinate_unit": "m",
            "data_format": "GeoTiff",
            "x_resolution": resX,
            "y_resolution": resY,
            "extent": {
                "xmin": bounds[0],
                "ymin": bounds[1],
                "xmax": bounds[2],
                "ymax": bounds[3],
            },
        },
        "project_info": {
            "project": "MEaSUREs Greenland Ice Mapping Project (GIMP)",
            "dataset": "MEaSUREs Greenland Ice Velocity: Selected Glacier Site Velocity Maps from Sentinel-2 Images.",
            "version": f"{VERSION}",
            "institution": "Byrd Polar & Climate Research Center | Ohio State University",
            "contributors": "Tom Chudley, Ian Howat, Bidhya Yadev, MJ Noh, Michael Gravina",
            "contact_name": "Ian Howat",
            "contact_email": "howat.4@osu.edu",
            "software": "Feature-tracking performed using SETSM SDM module | https://github.com/setsmdeveloper/SETSM",
            "funding_acknowledgement": "Supported by National Aeronautics and Space Administration MEaSUREs programme (80NSSC18M0078)",
            "data_acknowledgement": f"Contains modified Copernicus Sentinel data [{vel_info['midpoint'][:4]}].",
            # "citation": "TBD",
            # "dataset_doi": "TBD",
        },
    }

    return metadata_dict


def export_tif(array, fpath, profile):
    """Export an array to a raster, with rasterio
    """

    profile.update(
        compress='lzw',
        predictor=3  # gdal floating point predictor
    )

    with rs.open(fpath, "w", **profile) as dst:
        dst.write(array.astype(rs.float32), 1)


def get_gimp_tiles(gimp_mask_dir, aoi):
    """
    Returns a list of tile numbers (e.g ['4_2','4_3']) of the GIMP tiles that
    intersect the aoi polygon. Requires gimp_mask_dir to be set to the path
    of GIMP  mask tiles in format 'GimpOceanMask_15m_tile*.tif', and aoi to
    be a shapely Polygon.
    """
    tiles = []
    for fpath in glob.iglob(os.path.join(gimp_mask_dir, "GimpOceanMask_15m_tile*.tif")):
        # Get extent of raster dataset as polygon
        extent = shapely_bounds(fpath)
        # If intersects aoi, add to list
        intersect = extent.intersects(aoi)
        if intersect == True:
            tiles.append(fpath[-7:-4])
    return tiles


def clip_gimp_tiles(tile_code_list, bounds, msk_dir):
    """
    Crop 15m GIMP files (found at GIMP_MASK_DIR) at specified tile code(s)
    (tiles will be merged if multiple tile codes exist in tile_code_list),
    and return an array of the rock mask
    """
    # If AOI covers single GIMP tile, read single raster.
    if len(tile_code_list) == 1:
        ocean_mask_fpath = os.path.join(
            GIMPMASKDIR, "GimpOceanMask_15m_tile{}.tif".format(
                tile_code_list[0])
        )
        ocean_mask_ds = read_single_gimp(ocean_mask_fpath)

        ice_mask_fpath = os.path.join(
            GIMPMASKDIR, "GimpIceMask_15m_tile{}.tif".format(tile_code_list[0])
        )
        ice_mask_ds = read_single_gimp(ice_mask_fpath)

    # If AOI covers multiple GIMP tiles, merge using gdal.Warp function.
    elif len(tile_code_list) > 1:
        ocean_mask_ds = merge_multiple_gimp(
            GIMPMASKDIR, "GimpOceanMask_15m_tile", tile_code_list, ".tif"
        )
        ice_mask_ds = merge_multiple_gimp(
            GIMPMASKDIR, "GimpIceMask_15m_tile", tile_code_list, ".tif"
        )

    # Load ocean mask cropped to AOI
    cropped_ocean_mask_ds = gimp_ds_to_bounds(ocean_mask_ds, bounds)
    cropped_ocean_mask = cropped_ocean_mask_ds.GetRasterBand(1).ReadAsArray()
    ocean_mask_fpath = os.path.join(msk_dir, "mask_ocean.tif")
    del ocean_mask_ds

    # Load ice mask cropped to AOI
    cropped_ice_mask_ds = gimp_ds_to_bounds(ice_mask_ds, bounds)
    cropped_ice_mask = cropped_ice_mask_ds.GetRasterBand(1).ReadAsArray()
    ice_mask_fpath = os.path.join(msk_dir, "mask_ice.tif")
    del ice_mask_ds

    # Generate rock mask cropped to aoi
    cropped_rock_mask = np.where(
        (cropped_ice_mask == 0) & (cropped_ocean_mask == 0), 1, 0
    )
    rock_mask_fpath = os.path.join(msk_dir, "mask_rock.tif")

    # Export masks to masks directory in WD
    export_tif_to_target_geotransform(
        ice_mask_fpath, cropped_ice_mask, cropped_ice_mask_ds, gdal.GDT_Byte
    )
    export_tif_to_target_geotransform(
        ocean_mask_fpath, cropped_ocean_mask, cropped_ice_mask_ds, gdal.GDT_Byte
    )
    export_tif_to_target_geotransform(
        rock_mask_fpath, cropped_rock_mask, cropped_ice_mask_ds, gdal.GDT_Byte
    )

    return


def read_single_gimp(fpath):
    """
    Reads raster at path 'fpath' and returns a read-only GDAL dataset object.
    """
    if not os.path.isfile(fpath):
        raise Exception("Cannot find file to read at {}.".format(fpath))
    return gdal.Open(fpath, gdal.GA_ReadOnly)


def merge_multiple_gimp(directory, prefix, tile_code_list, suffix):
    """
    Use GDAL warp function to return merged DS from multiple tile codes.
    Returns single gdal dataset object of merged GIMP tiles.
    """
    tile_paths = []
    for tile in tile_code_list:
        tile_paths.append(os.path.join(directory, prefix + tile + suffix))
    merged_ds = gdal.Warp(
        "", tile_paths, format="MEM"
        # options=["COMPRESS=LZW"]  # BNY removed for GDAL 3.8+
    )
    return merged_ds


def gimp_ds_to_bounds(gimp_ds, bounds):
    """
    Crop raster to extent (extent = [xmin, xmax, ymin, ymax])
    """
    xmin, ymin, xmax, ymax = bounds
    cropped_ds = gdal.Warp(
        "",
        gimp_ds,
        format="MEM",
        outputBounds=[xmin, ymin, xmax, ymax],
        # options=["COMPRESS=LZW"]  # BNY removed for GDAL 3.8+
    )
    return cropped_ds


def export_tif_to_target_geotransform(out_fpath, array, target_ds, target_type):
    """ Creates an output for a given array, nicking the metadata from
    the target_ds. Uses gdal.
    https://gis.stackexchange.com/questions/58517/python-gdal-save-array-as-raster-with-projection-from-other-file
    """
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(
        out_fpath, target_ds.RasterXSize, target_ds.RasterYSize, 1, target_type
    )
    dataset.SetGeoTransform(target_ds.GetGeoTransform())
    dataset.SetProjection(target_ds.GetProjectionRef())
    dataset.GetRasterBand(1).WriteArray(array)
    dataset.FlushCache()  # Write to disk.

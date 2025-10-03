#!usr/bin/env python


###################################################################################################
# Imports.
###################################################################################################

# Import basic Python resources.
import os, glob, logging, traceback
# Import geographic-data-handling libraries.
from shapely.geometry import shape
import numpy as np
import pandas as pd
import geopandas as gpd
import rioxarray as rxr
import rasterio as rs
from rasterio.enums import Resampling
# Import AWS-interfacing resources.
from rasterio.session import AWSSession
import boto3
# Import STAC search client.
from pystac_client import Client

# Import default parameter values.
from lib.defaults import NSIDC_EPSG_CODE, RESOLUTION, AWS_CREDENTIALS_FPATH, STAC_URL
# Import column-related info.
from lib.columns import NIR_COLUMNS_SELECT, PAN_COLUMNS_SELECT, COLUMNS_RENAME



###################################################################################################
# Functions.
###################################################################################################

def search_and_download_region(
    region_name,
    aoi_gdf,
    daterange,
    intersect_frac_thresh,
    base_dir,
    reference_dir,
    errored_downloads_log_name
):
    """
    Runs a STAC query on a region of the specified AOI, then downloads the files from the results.

    Parameters
    ----------
    region_name: AOI region name as string (e.g. `049_jakobshavn`).
    aoi_gdf: The geodataframe containing all the regions for the area of interest.
    daterange: The date-range for the search, in `YYYY-MM-DD/YYYY-MM-DD` format.
    intersect_frac_thresh: Fraction of AOI coverage, below which to reject partial scenes. For example, 0.05 is 5 percent.
    base_dir: The root of the folder structure where output files will be placed.
    reference_dir: Folder for reference information like the STAC query results CSV and the reprojection template image.
    """

    print(region_name)
    logging.info(
        f"\n\n-----------------------DOWNLOADING {region_name}-----------------------\n"
    )

    ###########################################################################################
    # Get the geodataframe for just this region from the full AOI geodataframe.
    ###########################################################################################

    region_aoi_gdf = aoi_gdf[aoi_gdf["region"] == region_name]

    
    ###########################################################################################
    # Run the STAC search for this region and date range.
    ###########################################################################################
    
    # Create and run the STAC search, retrieving a geodataframe as a result.
    stac_gdf = stac_search_aoi(
        region_aoi_gdf,
        daterange,
        intersect_threshold=intersect_frac_thresh
    )

    # If the number of results returned was 0, skip this region and continue to the next.
    len_query = len(stac_gdf)
    logging.info(f"STAC query returned {len_query} scenes.")
    print(f"STAC query returned {len_query} scenes.")
    if len_query == 0:
        logstr='Skipping region...'
        logging.info(logstr)
        print(logstr)
        return


    ###########################################################################################
    # Filter the results geodataframe to remove scenes that were already downloaded.
    ###########################################################################################

    # Filter the results geodataframe to remove scenes that were already downloaded.
    stac_gdf_flt = filter_to_new_scenes(stac_gdf, region_name, base_dir)

    # If no results remain after filtering, skip this region and continue to the next.
    len_query = len(stac_gdf_flt)
    logstr = f"After removing already downloaded, {len_query} scenes remain to download."
    logging.info(logstr)
    print(logstr)
    if len_query == 0:
        logstr='Skipping region...'
        logging.info(logstr)
        print(logstr)
        return

    # Export a CSV of results for error-checking purposes.
    csv_fpath = os.path.join(reference_dir, f"{region_name}_stac_query_results.csv")
    stac_gdf_flt.to_csv(csv_fpath)


    ###########################################################################################
    # Create the template image that will be used for reprojection later.
    ###########################################################################################

    # Get the path for the to-be-created template.
    sample_fpath = os.path.join(reference_dir, f"{region_name}.tif")

    # Create the template if necessary.
    if not os.path.exists(sample_fpath):
        logstr = "Creating reference image to resample to..."
        logging.info(logstr)
        print(logstr)
        create_template_tif(
            region_aoi_gdf,
            sample_fpath
        )

    # Open the template as a Rasterio dataarray.
    sample_raster = rxr.open_rasterio(sample_fpath)


    ###########################################################################################
    # Download the imagery for the region.
    ###########################################################################################

    # NOTE - Currently, this step is  done in serial. But as we're also reprojecting, consider
    # using parallel-processing to download. Would have to ensure rs.Env() remains open.

    # Get AWS access credentials.
    # Try to read from CSV file, but fall back to default credentials (e.g., Lambda execution role)
    credentials_path = os.path.expanduser(AWS_CREDENTIALS_FPATH)
    if os.path.exists(credentials_path):
        aws_creds = pd.read_csv(credentials_path)
        access_key = aws_creds["Access key ID"].values[0]
        secret_access_key = aws_creds["Secret access key"].values[0]
        aws_session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_access_key,
        )
    else:
        # Use default credential chain (environment variables, IAM role, etc.)
        aws_session = boto3.Session()

    # Create the output directory.
    output_dir = os.path.join(base_dir, region_name)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    logstr = f"Downloading {len(stac_gdf_flt)} scenes."
    logging.info(logstr)
    print(logstr)

    # Set up a Rasterio session, then...
    with rs.Env(
        AWSSession(
            aws_session,
            requester_pays=True,
        )
    ) as env:

        # For each file listed in the filtered query-results geodataframe for this region,
        for subset_id, aws_href in zip(
            stac_gdf_flt["subset_id"], stac_gdf_flt["s3_href"]
        ):
            # Download, clip/reproject and squeeze that file.
            try:
                download_clip_and_squeeze_one_stac_result(
                    output_dir,
                    subset_id,
                    aws_href,
                    region_name,
                    region_aoi_gdf,
                    sample_raster,
                    errored_downloads_log_name
                )
            except Exception as e:
                logging.error(f"Error while downloading/clipping/squeezing subset {subset_id}, {aws_href}: {repr(e)}\nTraceback: {traceback.format_exc()}")
                continue


def stac_search_aoi(
    region_aoi_gdf,
    daterange,
    intersect_threshold
):
    """
    Given a geopandas dataframe containing an ROI and a daterange, query the STAC API to query
    and get a geodataframe containing the results.

    Parameters
    ----------
    region_aoi_gdf : A geopandas dataframe of length 1, containing the region.
    daterange : A string in the format 'YYYY-MM-DD/YYYY-MM-DD'.
    intersect_threshold : Minimum coverage of ROI to retain scene (e.g. 0.05 = 5%)

    Returns
    -------
    gdf : A geodataframe containing the query results.

    Notes
    -----
        Only selected columns are retained (and renamed) as detailed in `columns.py`.
    """

    # Get the geometry of the region in both NSIDC and WGS84.
    geometry_nsidc = region_aoi_gdf.geometry.values[0]
    geometry_wgs84 = region_aoi_gdf.to_crs(4326).geometry.values[0]

    # Perform the STAC query and get the results back as a dictionary.
    stac = Client.open(STAC_URL, headers=[])
    search = stac.search(
        intersects=geometry_wgs84,
        datetime=daterange,
        collections=["landsat-c2l1"],
        limit=500,  # Number of items per page of results
        max_items=1e9,  # Abritrarily large max_items to return, to ensure we get them all.
    )
    items = [i.to_dict() for i in search.items()]

    # Create a geodataframe from the query results dictionary.
    df = pd.json_normalize(items)
    df["geometry"] = df.apply(
        lambda x: shape(
            {"type": x["geometry.type"], "coordinates": x["geometry.coordinates"]}
        ),
        axis=1,
    )
    gdf = gpd.GeoDataFrame(df, geometry=df.geometry, crs=4326)

    # Filter the STAC geodataframe based on content and intersect fraction.
    gdf = filter_stac_gdf(
        gdf,
        geometry_nsidc,
        intersect_threshold
    )
    
    # Add a subset ID for scenes.
    gdf["subset_id"] = (
        pd.to_datetime(gdf["datetime"], format="mixed").dt.strftime("%Y%m%d%H%M%S")
        + "_"
        + gdf["landsat:scene_id"]
        + "_"
        + gdf["id"]
        + "_ortho"
    )

    # Return the geodataframe.
    return gdf


def filter_stac_gdf(
    gdf,
    geometry_nsidc,
    intersect_threshold
):
    # Filter out landsat 2 and 3 results.
    gdf = gdf[~gdf["properties.platform"].str.contains("LANDSAT_1|LANDSAT_2|LANDSAT_3")]

    # Get separate geodataframes for Landsat 4 and 5 (NIR data hrefs) and Landsat 7-9 (pan data hrefs).
    gdf_nir = gdf[gdf["properties.platform"].str.contains("LANDSAT_4|LANDSAT_5")]
    gdf_pan = gdf[
        gdf["properties.platform"].str.contains("LANDSAT_7|LANDSAT_8|LANDSAT_9")
    ]

    # Filter the Landsat 4/5 geodataframe to TM data only (MSS data is only 60 m resolution, not 30 m).
    gdf_nir = gdf_nir[gdf_nir["properties.instruments"].explode().str.contains("TM")]

    # Rename columns to preferred names (making nir and pan hrefs the same column names).
    gdf_nir = gdf_nir[NIR_COLUMNS_SELECT]
    gdf_nir.columns = COLUMNS_RENAME

    # If there is no pan data, skip to avoid raising error with trying to find assets.pan.href and
    # assets.pan.alternate.s3.href .
    if len(gdf_pan) == 0:
        gdf = gdf_nir
    # Otherwise, concatenate the Landsat 4/5 and Landsat 7-9 geodataframes back together.
    else:  # else rename and concatenate back together
        gdf_pan = gdf_pan[PAN_COLUMNS_SELECT]
        gdf_pan.columns = COLUMNS_RENAME
        gdf = pd.concat([gdf_nir, gdf_pan])
        gdf = gpd.GeoDataFrame(gdf, geometry=gdf["geometry"], crs=4326)
    gdf = gdf.to_crs(NSIDC_EPSG_CODE)

    # Filter the geodataframe based on intersect fraction.
    gdf["geometry_intersect"] = gdf["geometry"].intersection(geometry_nsidc)
    aoi_area = geometry_nsidc.area
    gdf["aoi_intersect_frac"] = gdf["geometry_intersect"].area / aoi_area
    gdf = gdf[gdf["aoi_intersect_frac"] > intersect_threshold]

    return gdf



def filter_to_new_scenes(
        stac_gdf,
        region_name,
        base_dir
    ):
    """
    Takes STAC query and removes scenes already downloaded and stored in the output directory.

    Parameters
    ----------
    stac_gdf : gdf containing stad query output - output of stac_search_aoi()
    region_name : AOI region name as string (e.g. `049_jakobshavn`)
    base_dir: The root directory that data will be downloaded to.

    Returns
    -------
    A STAC geodataframe with any already-existing scenes removed.


    Notes
    -----
        Comparisons are made after removing the end of the scene ID, containing the
        Collection ID. This is so that Collection 2 data is not downloaded when
        Collection 1 data already exists.
    """

    # Get a dataframe listing already-downloaded files.
    output_dir = os.path.join(base_dir, region_name)
    subsets = glob.glob(os.path.join(output_dir, "*.tif"))
    df = pd.DataFrame({"fpath": subsets})
    df["fpath"] = df["fpath"].astype(str)
    df["fname"] = df["fpath"].apply(os.path.basename)
    df["fname_without_collection"] = df["fname"].str.slice(stop=14)

    # Remove any files from the query-results gdf that are in the already-downloaded list.
    stac_gdf["subset_id_no_collection"] = stac_gdf["subset_id"].str.slice(stop=14)
    stac_gdf_flt = stac_gdf[
        ~stac_gdf.subset_id_no_collection.str.contains(
            "|".join(df.fname_without_collection.values)
        )
    ] if df.fname_without_collection.values.size > 0 else stac_gdf
    # Return the filtered geodataframe.
    return stac_gdf_flt


def create_template_tif(
        region_aoi_gdf,
        out_fpath
    ):
    """
    Creates a geotiff of the desired shape and extent with random data. This file is used later on,
    during the Rioxarray reproject-to-match process.

    Parameters
    ----------
    region_aoi_gdf : A geopandas dataframe of length 1, containing the ROI, in NSIDC EPSG.
    out_fpath : The desired output filepath.
    """

    # Get the width and height of the region in pixels.
    width = int(
        (region_aoi_gdf.total_bounds[2] - region_aoi_gdf.total_bounds[0]) / RESOLUTION
    )
    height = int(
        (region_aoi_gdf.total_bounds[3] - region_aoi_gdf.total_bounds[1]) / RESOLUTION
    )

    # Generate a random array of those dimensions.
    sample_array = np.round(np.random.rand(height, width))

    # Create a profile of the array.
    sample_transform = rs.transform.from_bounds(
        *region_aoi_gdf.total_bounds, width, height
    )
    sample_profile = rs.profiles.DefaultGTiffProfile()
    sample_profile.update(
        {
            "crs": NSIDC_EPSG_CODE,
            "transform": sample_transform,
            "width": width,
            "height": height,
            "count": 1,
        }
    )

    # Write the array to file.
    with rs.open(out_fpath, "w", nbits=1, **sample_profile) as dst:
        dst.write(sample_array.astype(np.uint8), 1)


def download_clip_and_squeeze_one_stac_result(
    output_dir,
    subset_id,
    aws_href,
    region_name,
    region_aoi_gdf,
    sample_raster,
    errored_downloads_log_name
):
    """
    Takes one of the results of a STAC search, downloads the file, then clips it to the region's
    bounds, reprojects it to the appropriate CRS, and squeezes it to a single band.

    Parameters
    ----------
    output_dir: The folder to download the file to.
    subset_id: The subset ID of the STAC result.
    aws_href: The URL of the file on AWS.
    region_aoi_gdf: The geodataframe for the region.
    sample_raster: The template raster used for reprojection.
    """

    # Do a last=minute check if file already exists (and if so, skip it).
    output_fpath = os.path.join(output_dir, f"{subset_id}.tif")
    if os.path.exists(output_fpath):
        return

    logging.info(f"Download/clip/squeeze subset ID: {subset_id}")
    print(subset_id)

    # Get the remote file as a Rioxarray dataset.
    try:
        rxr_ds = rxr.open_rasterio(aws_href)

        # Get clipping bounds (in the appropriate CRS) of that dataset.
        epsg_aws = rxr_ds.rio.crs
        aws_clip_bounds = region_aoi_gdf.to_crs(epsg_aws).total_bounds

        # Clip the dataset to those bounds, and squeeeze to a single band.
        rxr_ds = rxr_ds.rio.clip_box(*aws_clip_bounds)
        rxr_ds = rxr_ds.squeeze("band", drop=True)

        # Reproject the dataset to the template.
        rxr_ds = rxr_ds.rio.reproject_match(
            sample_raster,
            resampling=Resampling.cubic,
        )

        # Export (save) the dataset as a geotiff.
        rxr_ds.rio.to_raster(output_fpath)

    # Catch and record any errors, but keep going to the rest of the STAC results.
    except Exception as error:
        logstr = f"Download of {subset_id} failed. Continuing... Err: {error}"
        logging.info(logstr)

        with open(errored_downloads_log_name, "a") as errored_downloads:
            errored_downloads.write(f"\nREGION: {region_name}, SUBSET ID: {subset_id}, Err: {str(error)}")

        print(logstr)
        return
    

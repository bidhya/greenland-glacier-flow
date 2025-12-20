#!usr/bin/env python


###################################################################################################
# Imports.
###################################################################################################

# Import basic Python resources.
import os, shutil, logging, traceback
from joblib import Parallel, delayed
# Import STAC-search-related resources.
from pystac_client import Client
import requests
# Import geographic-data-handling libraries.
from shapely.geometry import mapping
import pandas as pd
import xarray as xr
import rioxarray
from rioxarray.merge import merge_arrays
from rioxarray.exceptions import NoDataInBounds
from rasterio.enums import Resampling 
from rasterio.errors import RasterioIOError

# Import default config values.
from lib.config import STAC_URL, DEFAULT_COLLECTION_NAME, EPSG_CODE_STRING



###################################################################################################
# Functions.
###################################################################################################

def download_region(
    download_folder,
    geom,
    aoi,
    start_date='2021-10-01',
    end_date='2021-02-28',
    collection_name=DEFAULT_COLLECTION_NAME
):
    """ 
        Download Sentinel-2 Cloud-Optimized Geotiffs from AWS Cloud using the satsearch api.

        Parameters
        ----------
        download_folder - Full path to the folder where Sentinel-2 .tifs will be downloaded.
        geom - AOI geometry. (Single-polygon Shapely geometry extracted from Geopandas DataFrame).
        start_date - Beginning date of the interval to search.
        end_date - End date of the interval to search.
        collection_name - The name of the image collection to search.
    """

    # Search the STAC for all images in the specified collection and date-range that intersect the
    # AOI.
    client = Client.open(STAC_URL)
    search = client.search(
        datetime=f'{start_date}/{end_date}',
        collections=[collection_name],
        intersects=geom
    )

    # Report on the number of results found.
    items = search.item_collection().items
    logging.info(f'{len(items)} items found that intersect with the search area/date range.')

    # Aside: New Oct 05, 2025: use pre-existing tiles to select only the matching items. So
    # unnecessary downloads are avoided.
    # Get the UTM tile IDs in the region (taken from pre-selected IDs from a manually-
    # edited geopandas dataframe).
    tile_ids = aoi['utm_grid'].values[0]
    tile_ids = tile_ids.split(',')
    print(f"Tile IDs in the region: {tile_ids}")
    print(type(tile_ids))
    # Filter the items to only those that match the tile IDs.
    if len(items) > 0:
        items = [item for item in items if item.id.split("_")[1] in tile_ids]
        logging.info(f'{len(items)} items found that match the UTM tile IDs in the region.')


    # If there are any results, download the associated files from Band 8 (near infrared).
    if len(items) > 0:
        for item in items:
            download_year_folder = item.properties["datetime"][0:4]
            download_filename = f'{item.properties["s2:product_uri"][:-5]}_B08.tif'
            try:
                for asset_key in item.assets:
                    if asset_key == "nir":
                        asset_url = item.assets[asset_key].href
                        download_year_folder_path = f'{download_folder}/{download_year_folder}'
                        download_file_from_url(asset_url, download_year_folder_path, download_filename)
            except Exception as e:
                logging.error(f"Error while downloading files for {download_folder}/{download_year_folder}\nTraceback: {traceback.format_exc()}")
                raise Exception(f"Error while downloading files for {download_folder}/{download_year_folder}") from e
        logging.info("Finished downloading assets.")



def download_file_from_url(url, download_folder_path, download_filename, overwrite_if_exists=False):
    """ 
        Downloads a file from the specified URL to the specified local path/filename.

        Parameters
        ----------
        url - The URL of the file to download.
        download_folder_path - Full path to the folder where Sentinel-2 .tifs will be downloaded.
        download_filename - The filename to save the file to.
        overwrite_if_exists - Whether or not to overwrite the file if it already exists locally (if false, will skip instead).
    """

    # Construct the download path.
    download_path = f'{download_folder_path}/{download_filename}'

    # If the file already exists and `overwrite_if_exists` is true, skip.
    if (overwrite_if_exists == False and os.path.exists(download_path)):
        return

    # Make the download folder if necessary.
    os.makedirs(download_folder_path, exist_ok=True)

    # Download the file.
    response = requests.get(url, stream = True)
    with open(download_path, "wb") as image_file:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                image_file.write(chunk)


def post_process_region(
    aoi,
    start_date,
    end_date,
    download_folder,
    clip_folder,
    template_folder,
    region,
    cores,
    metadata_folder
):
    """ 
        Subsets, merges and clips downloaded Sentinel-2 .tifs.

        Parameters
        ----------
        aoi: The gdf of the region to process.
        start_date: The start date of the time-range to process.
        end_date: The end date of the time-range to process.
        download_folder: Full path to the folder where Sentinel-2 .tifs were downloaded.
        clip_folder: Full path to the folder where clipped outputs will be saved.
        template_folder: Full path to the folder of the template .tif for clipping.
        region: The region name.
        cores: The number of cores available for parallel processing.
        metadata_folder: Full path to the folder where image metadata is kept.
    """

    #######################################################################################
    # Subset, merge and clip TIFFs by AOI.
    #######################################################################################

    # Get the UTM tile IDs in the region (taken from pre-selected IDs from a manually-
    # edited geopandas dataframe).
    tile_ids = aoi['utm_grid'].values[0]
    tile_ids = tile_ids.split(',')

    # For every year between the start and end dates (inclusive),
    start_date_year = int(start_date[0:4])
    end_date_year = int(end_date[0:4])
    years = [start_date_year] if start_date_year == end_date_year else list(range(start_date_year, end_date_year + 1))
    for year in years:

        # Get the download folder associated with the year. (If no such folder exists, continue to the next year.)
        download_year_folder = f'{download_folder}/{year}'
        if not os.path.exists(download_year_folder):
            continue

        #######################################################################################
        # Get a list of downloaded .tifs for this year, MGRS tile, and band 8.
        #######################################################################################

        # Get a list of all downloaded .tifs for for the specified year and Band 8.
        all_tifs = os.listdir(download_year_folder)
        all_tifs = [tif.split('_B08.tif')[0] for tif in all_tifs if tif.endswith('_B08.tif')] # Only required if we have blue, green bands etc. as well.
        
        # Filter that list for only the .tifs for this region's MGRS tiles.
        aoi_tifs = []
        for tile_id in tile_ids:
            # Get all TIFFs that are only within AOI.
            tifs1 = [tif for tif in all_tifs if tif.split('_')[5][1:]==tile_id]  # Here tile_id as: '24WWU', '24WWV' etc.
            aoi_tifs.extend(tifs1)
        logging.info(f'Total Number of TIFFs corresponding to AOI = {len(aoi_tifs)}')

        # Get a unique version of this list that includes relative orbit number and truncates
        # the filename string after hour of acquisition.
        tifs_set = set([x[:37] for x in aoi_tifs])  # To 
        logging.info(f'Unique (tifs_set) TIFFs by same date time and orbit : {len(tifs_set)}')


        #######################################################################################
        # Merge the .tifs for the region and clip to the region bounds.
        #######################################################################################

        # If the clip folder doesn't exist yet, create it.
        if not os.path.exists(clip_folder):
            os.makedirs(clip_folder)

        # Otherwise, if the clip folder *does* exist,
        else:

            ###############################################################################
            # Avoid duplicating work.
            ###############################################################################

            # Filter the TIFFs set to remove any TIFFs that were already
            # processed (to save on processing time).
            logging.info(f"Existing {clip_folder}")
            processed_files = [f.split('.tif')[0] for f in os.listdir(clip_folder)]
            processed_files = set(processed_files)
            tifs_set = tifs_set.difference(processed_files)
            tifs_set = list(tifs_set)
            logging.info(f'tifs_set remaining to process: : {len(tifs_set)}')
            if len(tifs_set)<1:
                logging.info("Continuing to next region as all files already processed.")
                continue


        ###############################################################################
        # Merge the .tifs for the region and clip them to the region bounds.
        ###############################################################################

        # Sort the files before clipping.
        tifs_set = list(tifs_set)
        tifs_set = sorted(tifs_set, key=lambda x: pd.to_datetime(x.split('_')[2]))

        # Generate a template raster for clipping (saved inside clipped folder for now).
        template_tif_path = create_template_tif(
            template_folder,
            region,
            tifs_set,
            aoi_tifs,
            download_year_folder,
            aoi
        )
        
        # Merge the .tifs for the AOI and clip them to the region bounds. (Use parallel
        # processing if there are multiple cores available.)
        if cores == 1:
            logging.info(f'Serial processing because number of cores = {cores}')
            for tif_prefix in tifs_set:
                merge_and_clip_tifs(
                    clip_folder,
                    metadata_folder,
                    download_year_folder,
                    aoi_tifs,
                    tif_prefix,
                    aoi,
                    template_tif_path,
                    tile_ids
                )
        else:
            _ = Parallel(
                n_jobs=cores
            )(
                delayed(
                    merge_and_clip_tifs
                )(
                    clip_folder,
                    metadata_folder,
                    download_year_folder,
                    aoi_tifs,
                    tif_prefix,
                    aoi,
                    template_tif_path,
                    tile_ids
                ) for tif_prefix in tifs_set
            )


def merge_and_clip_tifs(
        clip_folder,
        metadata_folder,
        download_folder,
        aoi_tifs,
        tif_prefix,
        aoi,
        template_tif,
        tile_ids
    ):
    """ 
    Merge one or more .tif rasters, then clip the merged product by AOI and save to file.

    Parameters
    ----------
    clip_folder : Path to the folder where the clipped .tifs will be saved.
    metadata_folder: Path to the folder where image metadata files will be saved.
    download_folder : Path to the folder where previously downloaded .tifs were saved.
    aoi_tifs : List of all the .tifs within the AOI.
    tif_prefix : Filename substring up to the hour of .tif acquisition.
    aoi: The gdf of the region to process.
    template_tif: Path to the template .tif for clipping.
    tile_ids: The UTM tile IDs in the region.

    Notes
    ----- 
    To get tif_prefix, we first extract the sub-string for aoi_tifs list;
    then convert it to set.
    The idea is to get a unique names that correpond to same satellite-day-hour.
    Merge these tiffs to get seamless coverage of Tiles for same day and same satellite (A or B).
    """


    ###############################################################################################
    # Set up output filenames.
    ###############################################################################################

    # Get output filenames for the clipped .tif and the metadata file.
    clipped_tif = f'/{clip_folder}/{tif_prefix}.tif'
    metadata_file = f'/{metadata_folder}/{tif_prefix}.csv'

    # If the clipped .tif already exists, exit.
    if os.path.exists(clipped_tif):
        return


    ###############################################################################################
    # Subset and sort the list of .tifs for processing.
    ###############################################################################################

    # Get a list of .tif filenames with the specified prefix and in Band 8.
    subset = [f'{x}_B08.tif' for x in aoi_tifs if tif_prefix in x]

    # Sort list in order of Sentinel MGRS grid coverage (determined a priori and populated into AOI
    # shapefile with higest coverage to lowest; for regions with more than 1 mrgs_tile we sometimes
    # corrected this manually).
    order = {key: i for i, key in enumerate(tile_ids)}
    subset = sorted(subset, key=lambda x: order[x.split('_')[5][1:]])

    # Create a dictionary keyed by the .tif prefix, containing the list.
    tif_dict = {}
    tif_dict[tif_prefix] = subset


    ###############################################################################################
    # Get UTM-zone-related info.
    ###############################################################################################

    # Get the set of all UTM zones covered by the AOI.
    utm_zones = [f.split('_')[5][1:3] for f in subset]
    utm_set = set(utm_zones)


    ###############################################################################################
    # Open the .tifs in the list and merge them into one array.
    ###############################################################################################

    try:        
        # If there is only one UTM zone,
        if len(utm_set) == 1:
            # Merge the arrays into one array.
            merged = merge_arrays([rioxarray.open_rasterio(f'{download_folder}/{tif}') for tif in subset])

        # Otherwise, if there are multiple UTM zones (the maximum is 2 for the region we're looking at),
        elif len(utm_set) > 1:
            # Subset the .tif list for just the first UTM zone.
            subset1 = [f for f in subset if utm_zones[0] in f.split('_')[-3]]

            # If subset 1 has any members,
            if len(subset1) > 0:
                # Merge the arrays in that subset into one array.
                merged = merge_arrays([rioxarray.open_rasterio(f'{download_folder}/{tif}') for tif in subset1])

                # Reproject the merged array to Polar Stereographic North.
                merged = merged.rio.reproject(EPSG_CODE_STRING, resolution=10, resampling=Resampling.cubic)

                # Subset the .tif list for those .tifs *not* in the first UTM zone list.
                subset2 = [f for f in subset if not f in subset1]

                # If subset 2 has any members,
                if len(subset2) > 0:
                    # Merge the arrays in that subset into one array.
                    merged2 = merge_arrays([rioxarray.open_rasterio(f'{download_folder}/{tif}') for tif in subset2])

                    # Reproject the merged array to Polar Stereographic North.
                    merged2 = merged2.rio.reproject(EPSG_CODE_STRING, resolution=10, resampling=Resampling.cubic)

                    # Merge the two UTM zone subset arrays into one array.
                    merged = merge_arrays([merged, merged2])


        ###############################################################################################
        # Reproject/clip the merged array based on a template raster with the appropriate size, shape,
        # resolution, clip boundaries, etc.
        ###############################################################################################

        # Open the template raster and reproject/clip to it.
        dst10m = rioxarray.open_rasterio(f'{template_tif}', chunks=True)
        clipped = merged.rio.reproject_match(dst10m)


        ###############################################################################################
        # Save to file.
        ###############################################################################################

        # Determine what fraction of glacier is covered by the clipped raster.
        aoi_area = aoi.Area.item()
        clipped_area = xr.where(clipped > 0, 1, 0).sum().item()*100/1e6  # assume anything above 0 is foreground
        coverage_fraction = clipped_area/aoi_area

        # If that fraction is above the 50% threshold, save to file.
        if coverage_fraction > 0.5:
            # Save the .tif.
            clipped.rio.to_raster(clipped_tif)

            # Save the associated metadata file.
            with open(metadata_file, 'w') as outfile:
                for key in tif_dict.keys():
                    vals = ",".join(tif_dict[key])
                    outfile.write(f'{key},{vals}')

            # Return the prefix and the .tif list (used for NSIDC metadata).
            return tif_prefix, subset  
    
    ###############################################################################################
    # Catch errors.
    ###############################################################################################

    except RasterioIOError as e:
        # File does not exist probably
        logging.info(f'RasterioIOError for tif_prefix: {tif_prefix}. Error info: {repr(e)}')
        print(f'RasterioIOError for tif_prefix: {tif_prefix}')
    
    except NoDataInBounds:
        # No data found in bounds; for cases where overlap with aoi polygon is very small (and
        # perhaps only with area with nodata)
        print('NoDataInBounds error ')
        logging.info('NoDataInBounds error')

    except Exception as e:
        logging.error(f"Error while merging and clipping for file {clip_folder}/{tif_prefix}.tif: {repr(e)}\nTraceback: {traceback.format_exc()}")
        raise Exception(f"Error while merging and clipping for file {clip_folder}/{tif_prefix}.tif: {repr(e)}") from e


def concat_csv_files(
        base_metadata_folder,
        region,
        folder_structure='old'
    ):
    """ 
        Merge individual .csv files for each region into a single, combined file that can be used
        to track the constituent .tifs for each clipped file.
        Individual .csv files contain just one row corresponding to the clipped .tif, consisting
        of the file name and the actual Sentinel-2 files that were merged prior to clipping.

        Parameters
        ----------
        base_metadata_folder: Path to the folder where image metadata files have been saved.
        region: Region name.
        folder_structure: 'old' or 'new' folder structure.
    """

    # Set up file paths based on folder structure.
    if folder_structure == 'old':
        metadata_folder = f'{base_metadata_folder}/individual_csv'  # old workflow where files downloaded separately per region
    else:
        metadata_folder = f'{base_metadata_folder}/individual_csv/{region}'  # new workflow Oct 2025 where downloads are in common folder

    # Get a list of .csv files in the metadata folder.
    csv_files = [f for f in os.listdir(f'{metadata_folder}') if f.endswith('.csv')]
    csv_files = sorted(csv_files, key=lambda x: pd.to_datetime(x.split('_')[2]))

    # Get the first .csv file as a dataframe.
    df1 = pd.read_csv(f'{metadata_folder}/{csv_files[0]}', index_col=0, header=None, delimiter=',')

    # For each additional file, read it as a dataframe, then merge it with the big dataframe.
    for csv_file in csv_files[1:]:
        tmp_df = pd.read_csv(f'{metadata_folder}/{csv_file}', index_col=0, header=None, delimiter=',')
        df1 = pd.concat([df1, tmp_df])

    # Save the concatenated dataframe to a .csv file.
    combined_csv_folder = f'{base_metadata_folder}/combined_csv'
    os.makedirs(combined_csv_folder, exist_ok = True)
    df1.to_csv(f'{combined_csv_folder}/{region}.csv')


def create_template_tif(
        template_folder,
        region,
        tifs_set,
        aoi_tifs,
        download_folder,
        aoi
    ):
    """ 
        Create a template .tif file that can be used to reproject and clip other .tif files.

        Parameters
        ----------
        tifs_set: List of filenames of .tifs that have been downloaded for the AOI.
    """

    # If the template folder does not yet exist, create it.
    if not os.path.exists(template_folder):
        os.makedirs(template_folder)

    # Get the file path for this template, based on the region.
    template_tif = f'/{template_folder}/{region}.tif'

    # If the template doesn't exist yet, create it.
    if not os.path.exists(template_tif):

        # For the prefix string of every .tif that has been downloaded for the AOI,
        for tif_prefix in tifs_set:

            # Open the first file that matches that filename.
            subset = [f'{x}_B08.tif' for x in aoi_tifs if tif_prefix in x]
            merged = rioxarray.open_rasterio(f'{download_folder}/{subset[0]}')
            
            # Reproject to the target CRS, generating the template.
            merged = merged.rio.reproject(EPSG_CODE_STRING, resolution=10, resampling=Resampling.cubic)

            # Now if there are any *other* matching files,
            if len(subset) > 1:

                # Merge each of the additional files to the template (expanding its area).
                for tif in subset[1:]:
                    tmp_ds = rioxarray.open_rasterio(f'{download_folder}/{tif}')
                    tmp_ds = tmp_ds.rio.reproject(EPSG_CODE_STRING, resolution=10, resampling=Resampling.cubic)
                    merged = merge_arrays([merged, tmp_ds], res = 10)

            # Clip the merged template to the AOI bounds.
            clipped = merged.rio.clip(aoi.geometry.apply(mapping), aoi.crs)

            # Get the fraction of the AOI that is covered by the template.
            aoi_area = aoi.Area.item()
            clipped_area = xr.where(clipped > 0, 1, 0).sum().item()*100/1e6  # Assume anything above 0 is foreground
            coverage_fraction = clipped_area/aoi_area

            # If the coverage is above the 95% threshold, save the template to file.

            if coverage_fraction < 0.95:
                logging.info(f'Coverage is less than minimum of 95% for {tif_prefix}. Did not create template.')
            else:
                # Convert the x and y values to integer type.
                clipped['x'] = clipped['x'].astype(int)
                clipped['y'] = clipped['y'].astype(int)

                # Perform exact match with bounding box
                # Check discrepancy between bottom left corrdinates of vector and raster and
                # add this offset to x, y coordinates of raster.
                minx, miny, maxx, maxy = aoi.bounds.values[0]   # Vector bounds.
                left, bottom, right, top = clipped.rio.bounds() # Raster bounds.
                xoff = minx-left
                yoff = miny-bottom
                clipped['x'] = clipped['x'] + xoff
                clipped['y'] = clipped['y'] + yoff

                # Save the template to file.
                clipped.rio.to_raster(template_tif)
                break

    # Return the file path for the template.
    return template_tif






def delete_contents_of_folder(folder_path):
    """ 
        Deletes all the contents within the specified folder.

        Parameters
        ----------
        folder_path: The path of the folder to delete contents from.
    """

    # For every file name listed in the folder,
    for filename in os.listdir(folder_path):
        # Get the file path.
        file_path = os.path.join(folder_path, filename)

        try:
            # If the path is to a file or link, remove that.
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)

            # If the path is to a subfolder, remove that recursively.
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

        # Catch and report exceptions.
        except Exception as e:
            logging.error(f"Failed to delete contents of {folder_path}: {repr(e)}\nTraceback: {traceback.format_exc()}")
            raise Exception(f"Failed to delete contents of {folder_path}: {repr(e)}") from e

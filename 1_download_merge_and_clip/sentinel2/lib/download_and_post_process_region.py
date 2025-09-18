#!usr/bin/env python


###################################################################################################
# Imports.
###################################################################################################

# Import basic Python resources.
import os, logging, time, json

# Import subfunctions of main function.
from lib.functions import download_region, post_process_region, concat_csv_files



###################################################################################################
# Functions.
###################################################################################################

def download_and_post_process_region(
    region,
    regions,
    start_date,
    end_date,
    collection_name,
    base_dir,
    download_flag,
    post_processing_flag,
    cores
):
    """
    Downloads data for the specified region and date range, then post-processes it (merging and
    clipping).

    Parameters
    ----------
    region: AOI region name as string (e.g. `049_jakobshavn`).\
    regions: Full list of regions that are being processed along with this one.
    start_date: The start date for the search, as a string.
    end_date: The end date for the search, as a string.
    collection_name: The name of which cloud data collection to search.
    base_dir: The root of the folder structure where output files will be placed.
    download_flag: 0/1 boolean, indicating whether data should be downloaded.
    post_processing_flag: 0/1 boolean, indicating whether data should be post-processed.
    cores: How many cores are available for parallel processing.
    """

    ###########################################################################################
    # 1. Set up folder structure.
    ###########################################################################################

    # Create the output folders for this region.
    download_folder = f'{base_dir}/{region}/download'  # TODO: remove region subfolder to avoid deep paths
    clip_folder = f'{base_dir}/{region}/clipped'  # TODO: rename as clipped_year or clipped/year
    template_folder = f'{base_dir}/{region}/template'  # TODO: remove region subfolder to avoid deep paths
    base_metadata_folder = f'{base_dir}/{region}/metadata'  # TODO: put adjacent to clipped_year folder and rename as metadata_year
    metadata_folder = f'{base_metadata_folder}/individual_csv/'
    os.makedirs(metadata_folder, exist_ok=True)


    ###########################################################################################
    # 2. Get the geometry for region.
    ###########################################################################################

    # Get the geometry of the region (this will be passed to sat-search).
    aoi = regions[regions.region == region].copy() # `aoi` is used for clipping the merged TIFFs.
    aoi_lat_lon = aoi.to_crs('EPSG:4326') # This is necessary if `aoi` is not in lat/lon geographic coordinates.
    shp_json = aoi_lat_lon.to_json()
    geom = json.loads(shp_json)['features'][0]['geometry']


    ###########################################################################################
    # 3. Download .tifs for this region.
    ###########################################################################################

    print(f"DOWNLOADING {region}")
    logging.info(
        f"\n----------------------------DOWNLOADING {region} {start_date} {end_date}-----------------------"
    )

    # Download .tifs frow AWS Cloud using STAC.
    if download_flag == 1:
        download_region(
            download_folder,
            geom,
            start_date=start_date,
            end_date=end_date,
            collection_name=collection_name
        )
        time.sleep(1) # Delay the next request to the server to not overload it.


    ###########################################################################################
    # 3. Process data for this region after downloading.
    ###########################################################################################

    print(f"POST-PROCESSING {region}")
    logging.info(
        f"\n----------------------------POST-PROCESSING {start_date} {end_date}--------------------------------"
    )

    # Process data for this region after downloading.
    if post_processing_flag:
        post_process_region(
            aoi,
            start_date,
            end_date,
            download_folder,
            clip_folder,
            template_folder,
            region,
            cores,
            metadata_folder
        )

    ###########################################################################################
    # 3. Cleanup for this region.
    ###########################################################################################

    # Combine all indivisual .csv files corresponding to clipped_tif into a single .csv file. 
    # Note: This will include all the .csv files that were generated at any time (ie, just not
    # from this script).
    concat_csv_files(base_metadata_folder, region)

    logging.info(f'Finished all processing for: {region} \n---------------------------------------------------------------------------------------------------')
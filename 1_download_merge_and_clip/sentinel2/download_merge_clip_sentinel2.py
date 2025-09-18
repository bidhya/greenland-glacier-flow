#!usr/bin/env python


###############################################################################################
# Imports.
###############################################################################################

# Import basic python resources.
import argparse, logging, traceback, datetime, time
# Import geographic-data-handling libraries.
import geopandas as gpd

# Import config values.
from lib.config import DEFAULT_COLLECTION_NAME
# Import subfunctions of main routine.
from lib.download_and_post_process_region import download_and_post_process_region
from lib.functions import delete_contents_of_folder
from lib.utility import setUpBasicLoggingConfig




###############################################################################################
# Parse command-line arguments.
###############################################################################################

# Parse command-line arguments.
parser = argparse.ArgumentParser(description='Process Sentinel-2 from AWS.')
parser.add_argument(
    '--collection_name',
    help='Name of satellite data collection to download from',
    type=str,
    default=DEFAULT_COLLECTION_NAME
)
parser.add_argument(
    '--start_date',
    help='First day of data to download',
    type=str
)
parser.add_argument(
    '--end_date',
    help='Last day of data to download',
    type=str
)
parser.add_argument(
    '-r',
    '--regions',
    help='Regions to process (can be multiple, separated by commas but not spaces)',
    type=str
)
parser.add_argument(
    '--ignore_regions',
    help='Regions to skip (can be multiple, separated by commas but not spaces). Do not use at the same time as the --regions argument.',
    type=str
)
parser.add_argument(
    '--start_end_index',
    help='Start and End index of regions to process with colon',
    type=str
    )
parser.add_argument(
    '--min_area',
    help='Subset glaciers greater than or equal to',
    type=float
)
parser.add_argument(
    '--max_area',
    help='Subset glaciers lesser than',
    type=float
)
parser.add_argument(
    '--download_flag',
    help='Whether to download data (1=yes, 0=no (default))',
    type=int,
    default=0
)
parser.add_argument(
    '--post_processing_flag',
    help='Whether to process the data after downloading (1=yes, 0=no (default))',
    type=int,
    default=0
)
parser.add_argument(
    '--clear_downloads',
    help='Whether to delete the downloaded imagery after deriving post-processed products (1=yes, 0=no (default))',
    type=int,
    default=0
)
parser.add_argument(
    '--cores',
    help='Number of cores to use for multiprocessing',
    type=int,
    default=1
)
parser.add_argument(
    '--base_dir',
    help='Base folder for processing',
    type=str
)
parser.add_argument(
    '--log_name',
    help='Name of log file',
    type=str,
    default='sentinel_glacier.log'
)
args = parser.parse_args()
collection_name = args.collection_name
start_date = args.start_date
if not start_date:
    start_date = '2015-06-23'  # 23 June 2015 (S2A) and 7 March 2017 (S2B)
end_date = args.end_date
if not end_date:
    end_date = datetime.date.today().strftime('%Y-%m-%d')
ignore_regions = args.ignore_regions
start_end_index = args.start_end_index
min_area = args.min_area
max_area = args.max_area
download_flag = args.download_flag
post_processing_flag = args.post_processing_flag
clear_downloads = args.clear_downloads
cores = args.cores
base_dir = args.base_dir
log_name = args.log_name


###############################################################################################
# Set up logging.
###############################################################################################

# Set up basic logging configuration.
setUpBasicLoggingConfig(log_name, f"Attempting download/merge/clip of Sentinel-2 imagery for regions in Greenland between {start_date} and {end_date}, with starting region index {start_end_index}, on {cores} cores, outputting to {base_dir}.")

###############################################################################################
# Get a list of regions to process.
###############################################################################################

# Get the regions list from the AOI template geopackage.
# Get a geodataframe listing regions from the AOI template geopackage.
# BY: changing location of ancillary glaciers gpks adjacent to code. Reduce steps on initial setup of project.  
regions = gpd.read_file('../ancillary/glacier_roi_v2/glaciers_roi_proj_v3_300m.gpkg')  # new location. gpkg is adjacent to codes folder. NEW
# regions = gpd.read_file(f'{base_dir}/ancillary/glacier_roi_v2/glaciers_roi_proj_v3_300m.gpkg')  # Shapefile specifying the AOI for glaciers. OLD
regions.index = regions.region

# Subset the regions based on minimum and maximum area parameters.
if min_area:
    regions = regions[regions.Area>=min_area]
    logging.info(f'min_area: {min_area}  ')
if max_area:
    regions = regions[regions.Area < max_area]
    logging.info(f'max_area: {max_area}  ')

# Sort regions by "Area" column (so parallel job fails towards end rather than beginning of script).
# regions.sort_values(by='Area', inplace=True)  # commented by BY

# # BNY: next 3 lines newly added
# regions_list = list(regions.region)    
# regions_list = [f for f in regions_list if int(f.split("_")[0]) > 100]  # BY just processing regions  101 to 192 for now. 1st try
# regions_list.sort()  # Sort in order of number. Not ideal but good to download in numeric order

# Subset the regions by index if necessary.
if start_end_index:
    start, end = start_end_index.split(':')
    start = int(start)
    if end == '':
        end = len(regions)
    end = int(end)
    regions = regions.iloc[start:end]  # orginal lines. commented to process only 101-192 BY
    # regions_list = regions_list[start:end]  # BY: only temporary solution for to speed up processing 101-192
    logging.info(f'Processing regions index from {start} to {end}  ')

# If a region or list of regions was specified in the parameters, get the regions-to-process list from that.
if args.regions:
    regions_list = args.regions.split(",")
# Otherwise get the regions-to-process list from the AOI template geopackage.
else:
    regions_list = list(regions.region)

# Remove any "ignored" regions from the list.
if args.ignore_regions:
    ignore_regions_list = args.ignore_regions.split(",")
    for ignore_region in ignore_regions_list:
        if ignore_region in regions_list:
            regions_list.remove(ignore_region)
    logging.info(f'Forced skipping these regions: {ignore_regions_list}')

# Log info about the regions list.
logging.info(f'Regions list: {regions_list}')
Total_Regions = len(regions_list)
logging.info(f'Total Regions: {Total_Regions}')


###############################################################################################
# Download data for each region.
###############################################################################################

# Loop through the regions, downloading data for that region.
region_count = 0
for region in regions_list:
    # Log the start of processing for this region.
    logging.info(f'\n\n-------------------------Processing {region} : {region_count}/{Total_Regions}............')

    # Download the data for this region.
    try:
        download_and_post_process_region(
            region,
            regions,
            start_date,
            end_date,
            collection_name,
            base_dir,
            download_flag,
            post_processing_flag,
            cores
        )
    except Exception as e:
        logging.error(f"Error while downloading and processing region {region}: {repr(e)}\nTraceback: {traceback.format_exc()}")
        raise Exception(f"Error while downloading and processing region {region}: {repr(e)}") from e
    
    # If data-clearing was specified, delete the downloaded data for this region.
    if clear_downloads:
        time.sleep(60)
        try:
            download_folder = f'{base_dir}/{region}/download'
            delete_contents_of_folder(download_folder)
        except Exception as e:
            if not "not empty" in str(e):
                logging.error(f"Error while clearing downloaded imagery for region {region}: {repr(e)}\nTraceback: {traceback.format_exc()}")
                raise Exception(f"Error while clearing downloaded imagery for region {region}: {repr(e)}") from e
        time.sleep(60)
    

    # Increment the region count.
    region_count += 1


logging.info("\n\n-----------------------END LOG-----------------------\n")
print("Finished.")

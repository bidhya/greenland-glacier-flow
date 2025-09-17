#!/usr/bin/env python


###################################################################################################
# Imports.
###################################################################################################

# Import basic Python resources.
import argparse, logging, traceback, os, re
# Import geographic-data-handling libraries.
import geopandas as gpd

# Import default parameter values.
from lib.defaults import (
    BASE_DIR, AOI_FPATH, NSIDC_EPSG_CODE, ICESHEET_NAME, DATE_1, DATE_2,
    INTERSECT_FRAC_THRESH, LOG_NAME, TEST_RUN 
)
# Import subfunctions of main routine.
from lib.functions import search_and_download_region
from lib.utility import setUpBasicLoggingConfig




###############################################################################################
# Parse command-line arguments.
###############################################################################################

parser = argparse.ArgumentParser()
parser.add_argument(
    '-r',
    '--regions',
    help='Regions to process (can be multiple, separated by commas but not spaces)',
    type=str
)
parser.add_argument(
    '--start_end_index',
    help='Start and end indices of regions to process, with colon',
    type=str
)
parser.add_argument(
    "-d1",
    "--date1",
    help="First date in date range, format `YYYY-MM-DD`",
    dest="date1",
    type=str,
    default=DATE_1,
)
parser.add_argument(
    "-d2",
    "--date2",
    help="Second date in date range, format `YYYY-MM-DD`",
    dest="date2",
    type=str,
    default=DATE_2,
)
parser.add_argument(
    "-it",
    "--intersect_thresh",
    help="Fraction of AOI below which to reject partial scenes, e.g. 0.05 is 5 percent",
    dest="intersect_frac_thresh",
    type=float,
    default=INTERSECT_FRAC_THRESH,
)
parser.add_argument(
    "--base_dir",
    help="Base directory for outputs",
    dest="base_dir",
    type=str,
    default=BASE_DIR,
)
parser.add_argument(
    "-l",
    "--log_name",
    help="Log name",
    dest="log_name",
    type=str,
    default=LOG_NAME,
)
parser.add_argument(
    "-t",
    "--test_run",
    help="Test run with hardcoded test values (overrides other settings)",
    dest="test_run",
    type=str,
    default=TEST_RUN,
)
args = parser.parse_args()
start_end_index = args.start_end_index
date1 = args.date1
date2 = args.date2
intersect_frac_thresh = args.intersect_frac_thresh
base_dir = args.base_dir
log_name = args.log_name
test_run = args.test_run


###############################################################################################
# Set up logging.
###############################################################################################

# Set up basic logging configuration.
setUpBasicLoggingConfig(log_name, f"Attempting download/merge/clip of Landsat imagery for regions in {ICESHEET_NAME} between {date1} and {date2}, with intersect fraction threshold {intersect_frac_thresh}, outputting to {base_dir}.")



###############################################################################################
# Validate arguments.
###############################################################################################

# Validate test_run boolean (because argparse can't, even with type='bool'.)
if test_run in [True, 'true', 'True', 't']:
    test_run=True
elif test_run in [False, 'false', 'False', 'f']:
    test_run=False
else:
    logging.error(f"Incorrect `test_run` value (must be interpretable as boolean)\nTraceback: {traceback.format_exc()}")
    raise ValueError("Incorrect `test_run` value (must be interpretable as boolean)")


###############################################################################################
# Get AOI geopackage/shapefile.
###############################################################################################

aoi_gdf = gpd.read_file(AOI_FPATH)
if aoi_gdf.crs != f"epsg:{NSIDC_EPSG_CODE}":
    raise ValueError(
        f"AOI file is not in specified epsg:{NSIDC_EPSG_CODE}."
    )


###############################################################################################
# If this is a test-run, replace AOI and dates with test defaults.
###############################################################################################

# If test scenario, run only for Jakobshavn and 2023.
if test_run == True:
    aoi_gdf = aoi_gdf[aoi_gdf["region"] == "049_jakobshavn"]

    date1 = "2023-01-01"
    date2 = "2023-12-31"

    logstr = f"TEST MODE ACTIVATED: Downloading Jakobshavn data only between {date1} and {date2}."
    logging.info(logstr)
    print(logstr)


###############################################################################################
# Get the date range in a format appropriate for a STAC search.
###############################################################################################
    
date_pattern = r"\d{4}-\d{2}-\d{2}"
if not re.match(date_pattern, date1) and re.match(date_pattern, date2):
    logging.error(f"Date inputs must currently be in format`YYYY-MM-DD`, got {date1}, {date2}.\nTraceback: {traceback.format_exc()}")
    raise ValueError("Date inputs must currently be in format`YYYY-MM-DD`")
daterange = f"{date1}/{date2}"


###############################################################################################
# Create the reference directory.
###############################################################################################

reference_dir = os.path.join(
    base_dir, "_reference"
)
if not os.path.exists(reference_dir):
    os.makedirs(reference_dir)



###############################################################################################
# Download the data for each region in the AOI.
###############################################################################################

# Get a list of regions to process from the AOI geodataframe.
regions_list = list(aoi_gdf.region.values) # BY : changed to list, but also in original code

# # Aside: To download 100 to 192 only, do the following:
# regions_list = [f for f in regions_list if int(f.split("_")[0]) > 100]  # BY just processing regions  101 to 192 for now.
# regions_list.sort()  # Sort in order of number. Not ideal but good to download in numeric order

if test_run == False:
    # If a region or list of regions was specified, replace the regions list with these.
    if args.regions:
        regions_list = args.regions.split(",")
        logging.info(f'Regions_list: {regions_list}')

    # Subset the regions by index if necessary.
    if start_end_index:
        start, end = start_end_index.split(':')
        start = int(start)
        if end == '':
            end = len(regions_list)
        end = int(end)
        regions_list = regions_list[start:end]

# Log info about the regions list.
Total_Regions = len(regions_list)
logstr=f"{len(aoi_gdf)} regions of interest between {date1} to {date2} with starting region index = {start_end_index}"
logging.info(logstr)
print(logstr)
logging.info(f'Total regions = {Total_Regions}\n  Regions list: {regions_list}  \n')

errored_downloads_log_name = f"{log_name[:-4]}_errored_downloads{log_name[-4:]}"

# For each region in the AOI geodataframe,
for name in regions_list:
    # Search and download the imagery for that region.
    try:
        search_and_download_region(
            name,
            aoi_gdf,
            daterange,
            intersect_frac_thresh,
            base_dir,
            reference_dir,
            errored_downloads_log_name
        )
    except Exception as e:
        logging.error(f"Error while searching/downloading region {name}: {repr(e)}\nTraceback: {traceback.format_exc()}")
        continue

logging.info("\n\n-----------------------END LOG-----------------------\n")
print("Finished.")

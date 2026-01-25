"""
For each clipped, output Sentinel-2 image falling within a glacial AOI, export a .csv file
containing orbital metadata for that image. (The file is
`<working directory>/nsidic_v1.0/<glacier name>/orbits/<glacier name>_glacier_orbits.csv`.
Metadata includes satellite, date and hour, orbital paths and orbital baselines.)
"""


###################################################################################################
# Imports.
###################################################################################################

# Import basic python resources.
import argparse, sys, os, glob, re
from tqdm import tqdm
# Import geographic-data-handling libraries.
import pandas as pd
import geopandas as gpd

# Import config values.
sys.path.append(".")
from lib.config import AOI_SHP, IMGDIR, WD, OUTDIRNAME, GLAC, START_DATE, END_DATE
# Import utility functions.
from lib.utility import create_dir
from lib.log import setUpBasicLoggingConfig, log_to_stdout_and_file




###################################################################################################
# Parse command-line arguments.
###################################################################################################

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
setUpBasicLoggingConfig(log_name, f"Attempting generate orbit metadata .csv files.")



###################################################################################################
# Set up directories.
###################################################################################################

# Get source directory paths.
clipped = "clipped"
clipped_dir = os.path.join(IMGDIR, glacier, clipped)

# Get working directory paths.
topdir = os.path.join(base_dir, OUTDIRNAME)
outdir_container = os.path.join(base_dir, OUTDIRNAME, glacier)
aoi_fpath = os.path.join(outdir_container, glacier + ".gpkg")
outdir = os.path.join(outdir_container, "orbits")

# Create directories.
create_dir(topdir)
create_dir(outdir_container)
create_dir(outdir) 


###################################################################################################
# Create geopackage based on glacier bounding box in Greenland shapefile.
###################################################################################################

log_to_stdout_and_file("Getting geopackage based on glacier bounding box in shapefile...")

# Read the Greenland shapefile, and subset out the glacier's bounding box.
aoi_gdf = gpd.read_file(AOI_SHP)
aoi_gdf = aoi_gdf.loc[aoi_gdf['region'] == glacier]

# Save the bounding box to a geopackage file.
aoi_gdf.to_file(aoi_fpath, layer="aoi", driver="GPKG")


###################################################################################################
# Generate orbital metadata lists for images in glacier AOI.
###################################################################################################

log_to_stdout_and_file(f'Collecting orbital metadata for images in "{glacier}" AOI.')

# Create a list of daily, clipped mosaic images from the source images directory.
clipped_list = glob.glob(clipped_dir + "/S2*.tif")

# Loop through that list, parsing each filename to assemble lists specifying
# satellites, datetimes and datehours, orbits, and PGDS baselines.

# Set up empty lists for metadata.
satellites = []
datetimes = []
datehours = []
orbital_paths = []
orbital_baselines = []

# With a progress bar (tqdm), loop through each clipped-mosaic image path, and...
for fpath in tqdm(clipped_list):
    # Get the filename from this path.
    fname = os.path.basename(fpath)

    # Parse satellite, datetime and datehours, orbit, and PGDS baseline from filename
    # (which will be in a format like `S2B_MSIL2A_20200716T162839_N0214_R083.tif`).
    satellite = fname[:3]
    satellites.append(satellite)

    regex = r"(\d{8}\D\d{6})"  # Find string YYYYMMDDTHH
    datetimestring = re.findall(regex, fname)[0]
    datetimes.append(datetimestring)

    regex = r"(\d{8}\D\d{2})"  # Find string YYYYMMDDTHH
    datehourstring = re.findall(regex, fname)[0]
    datehours.append(datehourstring)

    orbit = fname.split("_R", 1)[1][:3]
    orbital_paths.append(orbit)

    pdgs_baseline = fname.split("_N", 1)[1][:4]
    orbital_baselines.append(pdgs_baseline)


###################################################################################################
# Export to .csv
###################################################################################################

log_to_stdout_and_file("Exporting to .csv...")

# Construct a dataframe from the above lists. It will contain metadata for all the images in the
# glacier AOI.
df = pd.DataFrame({
    "datetime": datetimes,
    "datehour": datehours,
    "satellite": satellites,
    "orbits": orbital_paths,
    "processing_baselines": orbital_baselines
})

# Filter the dataframe to only contain entries between the minimum and maximum dates.
df.sort_values("datetime", inplace=True)
datetime_as_int = pd.to_numeric([
    datestring[:8]
    for datestring in df['datetime']
])
df = df[(datetime_as_int > int(start_date)) & (datetime_as_int < int(end_date))]

# Export the dataframe to .csv.
out_fpath = os.path.join(outdir, glacier + "_orbits.csv")
df.to_csv(out_fpath, index=None)

log_to_stdout_and_file("Finished.")

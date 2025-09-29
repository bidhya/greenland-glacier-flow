import datetime



# Download files to folder directory at this location.
BASE_DIR = "/fs/project/howat.4-3/howat-data/"

# Name of icesheet.
ICESHEET_NAME = "greenland"

# Path to geopackage containing AOIs (in NSIDC Polar Stereographic CRS, and with ultimate directory
# titles as column "region").
# AOI_FPATH = "./regions/greenland_roi_v2_300m.gpkg"   # OLD
# AOI_FPATH = "./regions/glaciers_roi_proj_v3_300m.gpkg"  # NEW. same as sentinel2 but in different directory.
# AOI_FPATH = "../ancillary/glacier_roi_v2/glaciers_roi_proj_v3_300m.gpkg"  # NEW. same as sentinel2.
AOI_FPATH = "./ancillary/glacier_roi_v2/glaciers_roi_proj_v3_300m.gpkg"  # NEW. same as sentinel2.


# The numerical CRS code that the region is projected in (NSIDC Polar Stereographic: 3413 for Greenland).
NSIDC_EPSG_CODE = 3413

# The resolution of the imagery. Note: The default Greenland ROI geopackage has been desired with
# ROI extents with coordinates in multiples of 300, allowing for resolutions of 10, 15, 30, 50,
# 100, etc. This script has not been tested with resolutions that are not factors of 300.
RESOLUTION = 15

# URL for the STAC search service. Defaults to USGS landsatlook.
STAC_URL = "https://landsatlook.usgs.gov/stac-server"

# Location of AWS credentials csv, output as part of AWS token generation.
AWS_CREDENTIALS_FPATH = "~/AWS_user_credentials.csv"


# Default values for argument parser.
SATELLITE = "landsat"
ICESHEET = "greenland"
DATE_1 = "1970-01-01"
DATE_2 = datetime.datetime.now().strftime("%Y-%m-%d")
INTERSECT_FRAC_THRESH = 0.05
LOG_NAME = f'log_subset_{SATELLITE}_{ICESHEET}_{datetime.datetime.now().strftime("%Y%m%dT%H%M%S")}.log'
TEST_RUN = "False"
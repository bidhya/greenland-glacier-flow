#!usr/bin/env python


# URL for the STAC-search service.
STAC_URL = 'https://earth-search.aws.element84.com/v1'

# Default collection name (will be used if no collection name is specified on the command line).
DEFAULT_COLLECTION_NAME = 'sentinel-2-l2a'

# The numerical CRS code that the region is projected in (NSIDC Polar Stereographic: 3413 for Greenland).
EPSG_CODE_STRING = "EPSG:3413"
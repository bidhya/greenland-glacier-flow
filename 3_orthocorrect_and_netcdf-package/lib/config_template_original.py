# Shapefile or geopackage that contains the version 2 Greenland glacier AOIs.
AOI_SHP = "/fs/project/howat.4/gravina.2/greenland_test/ancillary/glacier_roi_v2/glaciers_roi_proj_v2_300m.shp"
# Glacier region names file.
AOI_NAMES = "/fs/project/howat.4/gravina.2/greenland_test/ancillary/glacier_roi_v2/glaciers_roi_names_v2_300m.gpkg"
# Directory containing the 15 m resolution GIMP ocean/ice/land masks in the format e.g.
# `GimpOceanMask_30m_tile1_2.tif`. The script will find all tiles that intersect the AOI in order
# to merge and create a relevant GIMP mask for the glacier AOIs.
GIMPMASKDIR = "/fs/project/howat.4-3/howat-data/gimp/mask2015"


# The folder where clipped Sentinel-2 data is located. (The script will search the `clipped` and
# `downloads` directories within this top-level directory to extract the relative orbit numbers for
# the appropriate Sentinel-2 scenes.)
IMGDIR = "/fs/project/howat.4/sentinel2"
# `VELDIR` is the directory containing the outputs from Sentinel-2 velocity processing. This top-
# level directory is full of subdirectories of relevant Greenland AOIs (e.g. `001_alison`,
# `002_anoritup_kangerdulua1, etc.).
VELDIR = "/fs/project/howat.4-3/howat-data/VelocityResults/Greenland/SETSM_SDM/sentinel2"
# `VELDIR_LS` is the same but for Landsat data.
VELDIR_LS = "/fs/project/howat.4-3/howat-data/VelocityResults/Greenland/SETSM_SDM/landsat"

# Top-level working directory that the output will be written to.
WD = "/fs/project/howat.4/gravina.2/sentinel2vel"
# Directory that will be created within the working directory to store the output in. This is
# useful to differentiate e.g. processing version, test runs, etc.
OUTDIRNAME = "nsidic_v01.1"
# Dataset version.
VERSION = "01.1"


# Glacier to process (for individual testing - overridden when using bulk SLURM workflow).
GLAC = "192_CH_Ostenfeld"

# The temporal limits of dataset. (For individual testing - overridden when using bulk SLURM workflow).
# 2021-08-23 is a key limit: this is the date on which the DEM used to correct the Sentinel-2
# scenes switched from _PlanetDEM-90_ to _GLO-90_. The whole principle of this empirical
# correction process is that the orthorecitifcation error remains constant, which it does not
# if the DEM switches (or if ice surface height changes too much). **Do not try and correct
# fields before and after 2021-08-23 on the same run** (at least until ESA reprocess their
# entire dataset to the same standard, _à la_ Landsat Collection-2).
START_DATE = "20230101"
END_DATE = "20240315"

# Minimum amount of velocity fields required to construct an empirical correction field. As the
# empirical field is constructed based on the median of the existing fields, low sample sizes
# will result in poor medians. The threshold has been set, by eye, to five. Any cross-track
# pairs with fewer than five samples will not be corrected.
THRESH_COUNT = 5
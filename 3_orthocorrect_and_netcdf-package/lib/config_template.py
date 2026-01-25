# Shapefile or geopackage that contains the version 2 Greenland glacier AOIs.
# AOI_SHP = "/fs/project/howat.4/gravina.2/greenland_test/ancillary/glacier_roi_v2/glaciers_roi_proj_v2_300m.shp"
# AOI_SHP = "/fs/project/howat.4/gravina.2/greenland_glacier_flow/3_orthocorrect_and_netcdf-package/reference/glaciers_roi_geog_v2_300m.gpkg"  # Gravina's
AOI_SHP = "reference/glaciers_roi_geog_v2_300m.gpkg"  # TODO Seems not used until I used it in run_step3.py. consider replacing with files from ancillary/glacier_roi_v2 used in step1

# used in 1_match_to_orbits.py (lines 22 and 114): Imported from config and used to read a shapefile with
# polar stereographic and just one column 'region' and used to subset one glacier and create a geopackage by picking glacier name.

# Glacier region names file.
# AOI_NAMES = "/fs/project/howat.4/gravina.2/greenland_test/ancillary/glacier_roi_v2/glaciers_roi_names_v2_300m.gpkg"
# AOI_NAMES = "/fs/project/howat.4/gravina.2/greenland_glacier_flow/3_orthocorrect_and_netcdf-package/reference/glaciers_roi_names_v2_300m.gpkg"  # Gravina's
AOI_NAMES = "reference/glaciers_roi_names_v2_300m.gpkg"  # Local reference file

# 4c_netcdf_stack_landsat_sentinel_combined.py (lines 22 and 138): Imported from config and used to read a geopackage with gpd.read_file(AOI_NAMES).
# 4d_netcdf_stack_pre_post_dem_switch.py (lines 22 and 113): Imported from config and used similarly to read the geopackage.
# uses "ID" and "internal_processing_ID" columns. ID=glacierName in proper case and internal_processing_ID=glacierName in lowercase 

# Directory containing the 15 m resolution GIMP ocean/ice/land masks in the format e.g.
# `GimpOceanMask_30m_tile1_2.tif`. The script will find all tiles that intersect the AOI in order
# to merge and create a relevant GIMP mask for the glacier AOIs.
GIMPMASKDIR = "/fs/project/howat.4-3/howat-data/gimp/mask2015"

# 3_correct_fields.py (lines 24 and 169): Imported from config and used to get GIMP tiles.
# correct_fields_parts.py (lines 19, 363, 369, 376, 379): Imported from config and used in multiple file path constructions for GIMP ocean and ice mask tiles.

# The folder where clipped Sentinel-2 data is located. (The script will search the `clipped` and
# `downloads` directories within this top-level directory to extract the relative orbit numbers for
# the appropriate Sentinel-2 scenes.)
# IMGDIR = "/fs/project/howat.4/sentinel2"
# IMGDIR = "/fs/project/howat.4/gravina.2/greenland_glacier_flow/1_download_merge_and_clip/sentinel2"  # Gravina's
IMGDIR = "/fs/project/howat.4/greenland_glacier_flow/1_download_merge_and_clip/sentinel2"  # BNY

# 1_match_to_orbits.py (lines 22 and 93): Imported from config and used to construct paths to clipped directories.
# 2_get_orbital_average_offset.py (lines 31 and 103): Imported from config and used similarly for clipped directory paths.

# `VELDIR` is the directory containing the outputs from Sentinel-2 velocity processing. This top-
# level directory is full of subdirectories of relevant Greenland AOIs (e.g. `001_alison`,
# `002_anoritup_kangerdulua1, etc.).
VELDIR = "/fs/project/howat.4-3/howat-data/VelocityResults/Greenland/SETSM_SDM/sentinel2"  # same to Gravina's
# VELDIR = "/fs/project/howat.4-3/howat-data/VelocityResults/Greenland/SETSM_SDM/sentinel2/‘region’/SETSM_SDM_100_new"   # from MJ
# `VELDIR_LS` is the same but for Landsat data.
VELDIR_LS = "/fs/project/howat.4-3/howat-data/VelocityResults/Greenland/SETSM_SDM/landsat"  # same to Gravina's
# VELDIR_LS = "/fs/project/howat.4-3/howat-data/VelocityResults/Greenland/SETSM_SDM/landsat/‘region’/SETSM_SDM_100"  # from MJ
# NOTE (2025-11-30): MJ's workflow uses "_new" suffix for Sentinel-2
# velocity subdirectories (SETSM_SDM_100_new) while Landsat uses SETSM_SDM_100.
# This is documented in docs/overview.md under technical debt.

# Top-level working directory that the output will be written to.
# Previously not used due to sourced from top level config.sh
# WD = "/fs/project/howat.4/gravina.2/sentinel2vel"
# WD = "/fs/project/howat.4/gravina.2/greenland_glacier_flow/3_orthocorrect_and_netcdf-package"  # Gravina's
WD = "/fs/project/howat.4/greenland_glacier_flow/D3_orthocorrect_and_netcdf-package"  # BNY
# WD = "/home/yadav.111/Github/greenland-glacier-flow1/slurm_step3/debug2/3_orthocorrect_and_netcdf-package"  # debug step 2b
# Directory for logging batch glacier processing output (New change BNY).
LOG_DIR = '/home/yadav.111/Github/greenland-glacier-flow1/slurm_step3/logsD'


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
START_DATE = "20240101"
END_DATE = "20241231"

# Minimum amount of velocity fields required to construct an empirical correction field. As the
# empirical field is constructed based on the median of the existing fields, low sample sizes
# will result in poor medians. The threshold has been set, by eye, to five. Any cross-track
# pairs with fewer than five samples will not be corrected.
THRESH_COUNT = 5

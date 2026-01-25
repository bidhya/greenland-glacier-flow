
# Greenland glacier-flow orthorectification-error correction and NetCDF packaging.

These scripts are to be used on OSU Unity to empirically correct Sentinel-2 velocity fields, then to package the results into NetCDF files for delivery.

For more details about the method, please see:

Chudley, T. R., Howat, I. M., Yadav, B. N., & Noh, M. J. (_in review_). Empirical correction of systematic orthorectification error in Sentinel-2 velocity fields for Greenlandic outlet glaciers. _Cryosphere Discussions_. https://doi.org/10.5194/tc-2022-33


## Setup

Install Python 3.7.11 and the following dependencies to a new environment called `greenland_glacier_flow_3`. (You will need to manage the environment with pip, not Mamba, since some of the packages are not available through Mamba.)

- osgeo (installed as GDAL)
- rasterio
- shapely
- numpy
- geopandas
- pyproj
- pandas
- pytz
- tqdm
- matplotlib
- cv2 (installed as opencv-python)
- xarray (must be version 0.17.0)
- rioxarray
- netcdf4-python (installed as netCDF4)

(The scripts also draw on some utility functions originally sourced from Tom Chudley's `chudley_utils` package, but you don't have to install this - they are now found in `lib/utility.py`).

Copy the file `lib/config_template.py` and remove the "_template" part of the copy's name. That is now the actual default-configuration file. You can make changes to this config without having to worry about Git tracking it.

If you haven't already created the output folder for this workflow, create it now. For reference here, we will assume you have named this `3_orthocorrect_and_netcdf-package` in order to fit it into the broader `greenland_glacier_flow` workflow. Under this folder, create a new `reference` folder, and copy the contents of the `starting_materials/reference` folder into it.


**

## Processing chain

The output from the processing chain will look as follows:

```
OUTDIRNAME/
└── 049_jakobshavn/
    ├── 049_jakobshavn.gpkg
    ├── gimp_masks/
    │   ├── mask_ice.tif
    │   ├── mask_ocean.tif
    │   └── mask_rock.tif
    ├── netcdf/
    │   ├── S2_049_jakobshavn_v01.0.nc
    │   └── vel_049_jakobshavn_v01.0.nc
    ├── orbits/
    │   ├── 049_jakobshavn_median_offset_R[XXX]_R[YYY]_d[Z].tif
    │   └── ...
    └── velocities/
        ├── previews
        │   ├── *_preview.jpg
        │   └── ...
        └── S2_049_jakobshavn_YYYYMMDDTHH_YYYYMMDDTHH
            ├── *vv*.tif
            ├── *vx*.tif
            ├── *vy*.tif
            ├── *_preview.jpg
            └── *_metadata.json
```

Every glacier directory will contain (i) a geopackage of the AOI; (ii) resampled GIMP masks of ice, ocean, and rock; (iii) generated orbital correction fields; (iv) the velocities folder, containing a preview directory and individual velocity field directories; and (v) netcdf stacks of the Sentinel-2 velocities and combined Sentinel-2 and Landsat 8 velocities.

### `1_match_to_orbits.py`

This script does some simple setup. It:

1. Creates a basic directory structure.
2. Creates a geopackage polygon of the glacier AOI from the existing /fs/project/howat.4/sentinel2/ancillary/glaciers_roi_proj.shp file.
3. Extracts the relative orbit (RO) and PGDS baseline from the filename of Bidhya's *.tif files, saving it as a csv file called `XXX_glacier_orbits.csv` in the orbits directory.

### `2_get_orbital_average_offset.py`

This script empirically calculates orthorectification offset for orbit_pairs and stores them in the `./orbit/` directory. It:

1. From the .csv created in script 1, creates a dictionary of scene dates to orbit pairs.
2. Creates a pandas dataframe of the 'good' velocity fields from MJ's 'list_good_20XX.txt' files, and populates this in more detail with information from each individual scene (dates, times, orbits, pgds, etc.) as well as information on both (e.g. temporal baseline, whether the velocity field is same-track or cross-track). This is saved as a .csv file called `XXX_glacier_orbit_pairs.csv` in the orbits directory.
3. Calculates the median vv, vx, and vy velocities from same-track pairs. Going forward, this is our _a priori_ velocity field.
4. For every cross-track pair, calculates the median displacement offset from the expected displacement. This is our empirical offset field going forward. They are saved in the `/orbits` directory.

**NOTE**: In the current form, the script outputs a lot of apparent errors that look like this:

```
ERROR 1: PROJ: proj_create_from_database: crs not found
```

In fact, two of these errors are reported every time gdal.Warp is used to load a clipped raster, so there's a _lot_ of these errors. They occur (I think) because of some bugs in the SETSM SDM software that result in EPSG metadata values being stored as `None` or some artritrary value. GDAL is identifying this and reporting an error but because GDAL errors/exceptions [are still not 'properly' implemented in Python](https://gdal.org/api/python_gotchas.html) I cannot suppress them. The good news is that that this doesn't impact the final results, and the errors will eventually stop. The bad news is that it doesn't stop until 1,000 errors have been reported...

### `3_correct_fields.py`

This script applied the empirical orthorectifcation offset to all velocity fields, and stores them in an appropriate file structure with metadata, previews, etc. It:

1. Loads the list of 'good' velocity fields created in script 2, alongside the offset fields and GIMP masks.
2. Applies appropriate offset and masking to the `good` velocity fields.
3. Creates metadata (including uncertainty estimates) and preview maps.

### `4a_netcdf_stack_sentinel.py`

Stacks the velocity data into a single netcdf file, with appropriate metadata.

This script is so short it's probably the one that's the most 'self-documenting', but note that the metadata attributes are hard-coded seperately to those in `3_correct_fields.py` and `4b_netcdf_stack_landsat.py` (apart from the processing chain `VERSION` from `variables.py`). So if you change e.g. the authors, spatial resolution, etc., that will require changes in all scripts.

Currently no compression is applied - that might be worth changing.

### `4b_netcdf_stack_landsat.py`

Produces an equivalent stack of Landsat 8 data (including error estimates, etc.).

### `4c_netcdf_stack_landsat_sentinel_combine.py`

Produces an combined stack of Sentinel-2 and Landsat 8 data (including error estimates, etc.) and stacks it into a single netcdf file (vel_*.nc).

### `4d_pre_post_dem_switch_combine.py`

If the data spans August 23, 2021, then the input files will have been produced with 2 different DEMs, and this script will need to be run to integrate the intermediate NetCDF files generated for each side of this split.


## Bulk processing

Parameters for bulk processing are set in `slurm_jobs/orthocorrect_netcdf-package.sh`.

After configuring parameters to your liking, navigate to the top-level folder of the repository and start the bulk processing with the following command:
- `sh slurm_jobs/orthocorrect_netcdf-package.sh`
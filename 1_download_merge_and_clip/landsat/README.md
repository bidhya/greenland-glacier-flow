# Greenland glacier flow: download/clip workflow, for Landsat

Workflow to download and subset Landsat Collection 2 optical satellite imagery from Amazon Web Services, specifically on the OSU Unity Cluster, to support Greenland glacier velocity calculations.

This was developed for the OSU Howat Group from the previous `aws-optical-subsetting` repository, which in turn replaced scripts written by Seongsu Jeong.

**Note that these scripts draw from AWS requester pays buckets.** 


## Notes

 - The "test_run" parameter was implemented to avoid high AWS costs. If "True", the scripts will download only a select range of Jakobshavn scenes for testing purposes.


## Setup

From the `starting_materials/` directory of this repository, install the Conda environment using Mamba: `mamba env create -f environment.yml`.

Copy the file `lib/defaults_template.py` and remove the "_template" part of the copy's name. That is now the actual default-parameter-values file. You can make changes to this config without having to worry about Git tracking it.

Copy the `AWS_user_credentials.csv.template` file from `starting_materials/` into your home directory. Remove the `.template` part of the filename and populate the file with your AWS user credentials, replacing the <placeholders>.



## Landsat Collection 2

The `download_clip_landsat.py` script loops through the AOI geopackage, performs a STAC search of the `https://landsatlook.usgs.gov/stac-server` STAC server for all intersecting scenes, before filtering only to scenes covering >5% (by default) of the AOI. Standardised scene names are constructed before scenes are downloaded from AWS.

Usage:

```
usage: subset_landsat.py [-h] [-d1 DATE1] [-d2 DATE2] [-it INTERSECT_FRAC_THRESH] [-l LOG_NAME] [-t TEST_RUN]

options:
  -h, --help            Show this help message and exit.
  -d1 DATE1, --date1 DATE1
                        First date in date range, format `YYYY-MM-DD`.
  -d2 DATE2, --date2 DATE2
                        Second date in date range, format `YYYY-MM-DD`.
  -it INTERSECT_FRAC_THRESH, --intersect_thresh INTERSECT_FRAC_THRESH
                        Fraction of AOI below which to reject partial scenes, e.g. 0.05 is 5 percent.
  -l LOG_NAME, --log_name LOG_NAME
                        Log name.
  -t TEST_RUN, --test_run TEST_RUN
                        Test run with hardcoded test values. overrides other settings.
```




## Notes for future development

### Scope for Sentinel-2

To align processing chain between Landsat and Sentinel-2 sources, there is scope for the Sentinel-2 download chain written by Bidhya Yadav (https://github.com/bidhya/s2_greenland) to be updated to match the Collection 2 workflow. Currently, Bidhya uses the alternative AWS Sentinel-2 datasource run by Element 84 (https://registry.opendata.aws/sentinel-2-l2a-cogs/). This dataset is free but the data is (currently) incomplete. It might be desirable to use the 'official' AWS bucket to infill the missing Element 84 scenes. Adapting the Landsat 8 script for Sentinel-2 would also involve replicating Bidhya's Sentinel-2 tile merging system.

### Multiprocessing

Currently downloads and resamples images in serial (~2 - 8 seconds per image for Jakobshavn test case) Embarrasingly parallel opportunity to download scenes using python `multiprocess` - just have to make sure a Rasterio/boto3 environment session will remain open across nodes.
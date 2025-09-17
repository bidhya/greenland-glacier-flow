# Greenland glacier flow: download/merge/clip workflow, for Sentinel-2

Sentinel-2 imagery download and processing, to support calculations of glacier velocity in Greenland.

Based on earlier repository by Bidhya N. Yadav <yadav.111@osu.edu>, modified by Mike Gravina <gravina.2@osu.edu>.


# Logic

The workflow is executed by region [because sat search only works for one polygon at a time]. The regions are taken from a tempate geopackage.

For each region:

    1. Get query information.
    Filter for min/max area
    Filter for start/end indexes
    Make named folders for metadata
    Get the region, project to lat/lon CRS if needed, convert to JSON, and extract the geometry from the JSON.

    2. Download data from the cloud.
    Save downloaded files in the downloads folder. The STAC package does *not* overwrite files by default, so this can be re-run to update the set of downloaded imagery.

    3. Post-process the downloaded files.
    Subset, merge and clip.
    Mergining is done for all tiles for a given day/AOI using MGRS grids. If necessary, the imagery is re-projected into a Greenland-appropriate CRS (EPSG:3413) first.
    Clipping is done to each merged .tif to limit it to the AOI bounds.
    

# Usage


## Setup

From the `starting materials/` directory of this repository, install the Conda environment using Mamba: `mamba env create -f environment.yml`.

Copy the file `lib/config_template.py` and remove the "_template" part of the copy's name. That is now the actual default-configuration file. You can make changes to this config without having to worry about Git tracking it.

Create the output folder for this workflow, and place a copy of the `ancillary` folder from `starting_materials/` in it. (As the workflow progresses, this folder will fill up with other folders for different regions. If you delete these, make sure not to delete the `ancillary` folder, as it is necessary for the workflow.)


## Parameters

### Data-source related
- collection_name: The name of the satellite data collection to download from.

### Date-related
- start_date: First day of data to download.
- end_date: Last day of data to download. By default, the current day is used.

### Glacier-related
- regions: The name of the region or regions. This is optional - if not used, the regions list will simply be drawn from the geopackage. This parameter can also be a comma-separated list of region names (note that there must be no spaces in the region names or between them).
- ignore_regions: Skip processing these regions.
- start_end_index: If used, provides the start and end indices (separated by a colon) of the subset of regions in the geopackage to process.
- min_area: Lower bounds for the area of the glacier; glaciers smaller than this won't be processed.
- max_area: Upper bounds for the area of the glacier; glaciers larger than this won't be processed.

### Processing-steps related
- download_flag: Whether to download the data (1=yes, 0=no (default)).
- post_processing_flag: Wheter to post-process the data (1=yes, 0=no (default)).

### General
- cores: Number of cores to use for multiprocessing.
- base_dir: Root folder for processing.
- log_name: Name of log file.


## How many regions to run at once

Make sure to run download for a subset of regions separately, else will take weeks for all the glaciers, even for a time range of 1 year!

Intial download and processing was time-consuming for all Greenlands glaciers
    - 12 hours to download only 30 glaciers
    - 24 hours to for all process (download and clipping) 50 glaciers with 186gb/20 cores.


## Batched runs on the Unity cluster

When running many regions for long time periods, these jobs should be automated using the provided SLURM shell scripts.

In the terminal, navigate to the `slurm_jobs` folder and find `download_merge_clip_sentinel2.sh`.
1. Open the file in a text editor and carefully update all parameters like runtime, memory, your email, zone name, dates, etc.
2. Run the script with `sbatch download_merge_clip_sentinel2.sh`.
3. Periodically check the status of the script using `squeue -j <job id>`, where `<job id>` is the job number that was provided when you started the SLURM job. If you supplied your email address when editing the SLURM shell file, you should also get updates in your email.
2. After running the job, it is a good idea to inspect the various output files and logs.
3. You should also check the `downloads` folder periodically. These are intermediate files which take up a very large amount of space, and can quickly overflow the lab's partition on the Unity cluster. Monitor which glacier regions are running and which are complete, and periodically delete the files in `downloads` for glaciers that are complete.

Note: If your job is queueing for a long time, it may be because someone else is using the Howat group's reserved cluster nodes. Ask around to see if this is the case. You can also try temporarily removing the `SBATCH --partition=howat` line from the SLURM shell file, making it so the script can run on other available nodes.
    

## Troubleshooting

Downloads: Downloads are done in serial, so if only downloading data, less than 1GB of memory should be enough.

Merge/clip: If you get a memory error while doing this in parallel: Reduce number of jobs/cores, and increase the memory (~8GB per core/process)
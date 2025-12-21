# Greenland glacier flow

Workflow to download and subset Landsat and Sentinel-2 imagery for Greenland, calculate Surface
Displacement Maps for glacier velocity flow estimation from them, orthocorrect the SDMs, and then
pack the results into NetCDF files for distribution.

## � Current Focus: HPC Batch Processing (December 2025)

**Primary Goal**: Production-scale processing of 192 glacier regions on HPC cluster using SLURM job submission.

- 🚀 **HPC Workflow**: Batch processing multiple regions with optimized resource allocation
- 🔬 **Local Testing**: Prototyping and validation on local machines (WSL/Ubuntu)
- ✅ **Multi-Satellite**: Unified workflow for both Sentinel-2 and Landsat processing
- ⚙️ **Configuration-Driven**: CLI overrides for flexible testing and production runs
- ⚠️ **AWS Constraint**: Maximum 4 concurrent downloads from AWS at any time (affects batch parallelization)

**Current Development Phase**: Refining HPC batch workflows and testing folder structure optimizations.

### AWS Status (De-prioritized)
AWS Lambda containerization was completed in October 2025 and is production-ready, but current focus has shifted to HPC batch processing for the full 192-region dataset. AWS infrastructure remains available in the `aws/` directory for future cloud processing needs. See `aws/docs/AWS_SETUP_STATUS.md` for technical details.

## 🚀 Sentinel-2 Optimizations (October 2025)

**Performance Breakthrough**: 50%+ reduction in downloads and storage through intelligent architecture!

- ✅ **Centralized Downloads**: Shared tile pool eliminates duplication across overlapping regions
- ✅ **Pre-Download Filtering**: Only downloads necessary MGRS tiles using curated metadata
- ✅ **Proven Results**: 134_Arsuk reduced from 6 tiles to 1 (83% savings)
- ✅ **Production Ready**: Validated on WSL, HPC, and AWS Lambda environments

**Key Benefits**:
- **Storage**: 50-85% reduction depending on region overlap
- **Bandwidth**: Critical for 192-region production runs (AWS limit: 4 concurrent downloads)
- **Speed**: Subsequent regions process nearly instantly if tiles exist

📁 **See**: `SENTINEL2_OPTIMIZATION_GUIDE.md` for complete technical details and implementation guide.

## 📖 Current Workflow Documentation

**For the current unified satellite processing workflow (Sentinel-2 & Landsat), see `AGENTS.md`** - this contains the complete guide for:
- **HPC Batch Processing**: SLURM job submission for production-scale processing
- **Local Testing**: Prototyping workflows on WSL/Ubuntu before HPC deployment
- Job submission using `submit_job.sh` wrapper or `submit_satellite_job.py` directly
- Configuration management and CLI overrides for flexible parameter testing
- Multi-environment execution patterns (local and HPC)
- Testing strategies and best practices

⚠️ **Important**: For local testing, use `./submit_job.sh` to ensure proper conda environment activation. Direct Python calls require manual environment setup.

**🤖 AI Agents**: See the "AI Agent Quick Command Reference" section in `AGENTS.md` for rapid command determination.


## Notes: Everything below this is older notes. DO NOT use this. Will be cleaned-up when the workflow is finalized.  

Currently this is an incomplete, but usable, automation workflow. There are 3 steps to the processing
pipeline, and the 1st and 3rd have been automated. The second step (2_velocity, which does the SDM
calculations) is not yet automated and must be run manually in between steps 1 and 3.

Be sure to read the READMEs for each of the component steps, as each one has its own nuances.


## Setup

Copy the file `control/config_template.sh` and remove the "_template" part of the copy's name. That is now the actual default-parameter-values file. You can make changes to this config without having to worry about Git tracking it.

Install each of the 4 sub-workflows in their own folder underneath this repository's top-level folder:

1. **Landsat downloader/clipper**
    - Code [here](https://code.osu.edu/BPCRC/outreach/glacier-dynamics/greenland-glacier-flow-download-clip-landsat).
    - Install at `<this repo's top level folder>/1_download_merge_and_clip/landsat`.

2. **Sentinel-2 downloader/merger/clipper**
    - Code [here](https://code.osu.edu/BPCRC/outreach/glacier-dynamics/greenland-glacier-flow-download-merge-clip-sentinel-2).
    - Install at `<this repo's top level folder>/1_download_merge_and_clip/sentinel2`.

3. **Veclocity calculator**
    - Code [here](https://code.osu.edu/BPCRC/outreach/glacier-dynamics/greenland-glacier-flow-velocity).
    - Install at `<this repo's top level folder>/2_velocity`.

4. **Orthocorrector and packager**
    - Code [here](https://code.osu.edu/BPCRC/outreach/glacier-dynamics/greenland-glacier-flow-orthocorrect-netcdf-package).
    - Install at `<this repo's top level folder>/3_orthocorrect_and_netcdf-package`.

Set up each of these sub-workflows according to their own READMEs. This must be done before this top-level script can be run.

You will need to create a destination folder to receive the data from the workflow. This folder will contain sub-folders which mirror the above structure of the application code (for example, the Sentinel-2 download/merge/clip step will output to `<top level output folder>/1_download_merge_and_clip/sentinel2`). It is a good idea to create this mirrored folder structure before you begin running the workflow. Also note that at least one of the sub-workflows (Sentinel 2) requires some files to pre-exist in the destination folder before a run. See the READMEs for those sub-workflows for details.


## How to run

Run the command from the root directory of this repository. Here is an example command (note that supplying arguments at the command line overrides the equivalent settings in the config file):

`sh control/run_greenland_velocity_workflow.sh -r '001_alison,002_anoritup' -s '2021-01-01' -e '2021-12-31' -b '/fs/project/howat.4/gravina.2/greenland_glacier_flow' -w '1a 1b 2'`

(Arguments stand for "region", "date1", "date2", "base_dir", and "which_steps", respectively.)

The above command will run the workflow for 2 regions for the entirety of 2021, and place the output files in the folder `/fs/project/howat.4/gravina.2/greenland_glacier_flow`. It will only run steps 1a/1b and 2 out of 1a/1b, 2, and 3. 

However, this assumes that the automation for step 2 is functional. Remember, it isn't, so in reality, DON'T DO THIS! You should run steps 1a and 1b using the `-which_steps '1a 1b'` flag, then run step 2 manually, then run step 3 using `-which_steps '3'` flag.

For information on how to run step 2 manually, see the README in that step's folder.

Also note these important details:

- Step 1b (Sentinel-2) is very disk-intensive. The intermediate files in the `download` folder for that step are huge and rapidly eat up your lab's available space. It is generally best to run a set of regions through this step, then once the run is done, delete the intermediate files in `download`.

- Currently, Step 3 overwrites data by year within a given glacier. For example, if you run glacier 001 for the year 2022, and then run it again for year 2023, the output NetCDF files for 2022 will be removed and replaced with 2023. Plan to run all the years you need in one run, or else isolate older output files before rerunning.

When you are done with a run, check the logs in `/control/logs`. They are a useful source of info and allow you to confirm whether there were errors during the run.


## Scope for future development

Step 2, which handles Surface Displacement Mapping, is written in MATLAB and uses the SETSM
package (written in C++) as its main component. Steps 1 and 3, in comparision, are written mostly
in Python.

In addition, Step 2 has multiple parts where jobs are submitted to the Unity Cluster and must
complete before the workflow can continue.

Automating step 2 would require finding a way to control MATLAB scripts from .sh or .py files.
Alternately, the MATLAB scripts could be rebuilt ground-up in Python on shell directly.

Either way, logic must be added to check the status of the jobs on the Unity cluster and only
allow the workflow to continue once the jobs have successfully completed.

Error-catching logic must also be added, which will log errors to the same error directory as
the rest of the workflow, and which will stop operation if encountered (ideally on a per-region
basis to avoid grinding huge, multi-region runs to a halt).

Step 3 should be written to be non-destructive (to leave data from pre-existing processed years in place instead of deleting and replacing them).

Finally, note that the "auto-clear" function on step 1b (Sentinel-2 download/merge/clip) doesn't work reliably. In order to avoid unpredictable failures, this has been disabled by default. However, the consequence is that the `downloads` folder for Sentinel-2 data must be frequently cleared out, manually by the person overseeing large automated runs of this integrated workflow, or it will grow very large (eventually overflowing the GD lab's partition on Unity. In the future, this should be solved if you want a truly autonomous workflow.
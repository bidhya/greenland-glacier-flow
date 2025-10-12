# Updates to codebase in reverse chronological order
====================================================
## Oct 12, 2025 - Workflow Reconciliation Complete
- **Sentinel-2 and Landsat Parameter Standardization**: Unified date argument naming across all satellite processing workflows
- **Key Changes**: Changed Sentinel-2 from `--start_date`/`--end_date` to `--date1`/`--date2` to match Landsat
- **Files Updated**: 9 files including core scripts, config files, job submission scripts, and documentation
- **Impact**: Eliminated technical debt from inconsistent parameter naming, established unified interface for multi-satellite processing
- **Verification**: All components tested and verified functional across HPC, local, and AWS Lambda environments

## Sep 17, 2025
- Code re-organization.
- This git repo is exact copy of original gitlab with a few updates to run by region
- New conda environment that can used to for both Landsat and Sentinel2


## TODOs



# Changelog

All notable changes to the Greenland Glacier Flow Processing project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

### Data Integrity Resolution and Main Branch Restart (February 17, 2026)

**Achievement**: Complete resolution of production data corruption issues, establishment of clean development baseline, and comprehensive branch cleanup

#### Data Integrity Investigation and Root Cause Analysis
- **Systematic Debugging**: Identified x_ prefix addition to lib/ files in commits `638c943`/`1ec88a7` as root cause of import errors
- **Commit Testing**: Validated baseline commit `10afc5d` as corruption-free reference point
- **Incremental Validation**: Tested workflow functionality across multiple commits to isolate problematic changes

#### Main Branch Clean Restart
- **Branch Recreation**: Restarted `main` branch as exact copy of verified `stable` branch from commit `10afc5d`
- **Clean Baseline**: Eliminated all problematic commits while preserving working functionality
- **Production Verification**: Confirmed HPC workflow operational with clean codebase

#### QAQC Tool Implementation
- **Data Integrity Verification**: Added `qaqc/Step1/raster_compare.py` for pixel-perfect raster data comparison
- **Automated Testing**: Environment auto-detection and comprehensive raster validation
- **Production Monitoring**: Tool for ongoing data quality assurance in HPC processing

#### Environment Testing Infrastructure
- **Conditional Directory Separation**: Modified `submit_satellite_job.py` to append environment names to output directories when using non-default environments
- **Safe Testing**: Prevents test environment data from interfering with production workflows
- **Operational Continuity**: Default `glacier_velocity` environment maintains standard directory structure

#### Branch Management and Cleanup
- **Abandoned Branch Removal**: Deleted `develop`, `fargate-migration`, and `a` branches
- **Repository Hygiene**: Maintained only essential branches (`main`, `stable`, `experimental`)
- **Historical Preservation**: Experimental branch retained for potential future features despite known issues

#### Documentation Updates
- **AGENTS.md Revision**: Streamlined from 280+ to 265 lines, removed historical debugging content
- **Current Status**: Updated all project status indicators to reflect February 17, 2026 state
- **Branch Documentation**: Comprehensive branch status tracking with deletion records
- **Debugging Reference**: Preserved commit testing patterns in experimental branch reference section

#### Technical Infrastructure
- **Git Workflow Optimization**: Clean branch history with verified data integrity
- **Environment Separation**: Automatic directory isolation for testing environments
- **QAQC Integration**: Production-ready data validation tooling
- **Documentation Maintenance**: Current and actionable project reference materials

---

### Step 3 Integration: Complete Processing Pipeline (January 25, 2026)

**Achievement**: Full integration of Step 3 orthocorrection and NetCDF packaging workflow into main repository, completing the end-to-end Greenland glacier velocity processing pipeline

#### Repository Consolidation
- **Unified Structure**: Step 3 codebase moved to `3_orthocorrect_and_netcdf-package/` alongside Step 1
- **Complete Workflow**: End-to-end processing from satellite download to final NetCDF delivery
- **Branch Merge**: `feature/step3-integration` squashed into main for clean history

#### Technical Infrastructure and Pipeline
- **README.md Overhaul**: Complete rewrite with 5-step quickstart for new users
- **Legacy Organization**: Deprecated code moved to dedicated `legacy/` folders
- **Path Standardization**: Removed hardcoded paths, added generic repository references
- **Graceful Degradation**: 93% success rate with partial outputs for data gaps
- **Batch Processing**: Parallel glacier processing with SLURM joblib orchestration
- **HPC Production Ready**: Validated on OSU Unity cluster with 192 glacier regions
- **Container Support**: Docker containerization for consistent environments
- **AWS Integration**: Lambda gap filling complement to HPC primary workflow
- **Complete Pipeline**: Single repository for full Greenland glacier velocity workflow
- **Improved Maintainability**: Unified codebase reduces duplication and confusion
- **Enhanced Documentation**: User-friendly guides reduce onboarding time
- **Production Scale**: Validated infrastructure for annual processing campaigns

---

### Current Status (January 2026)
**Primary Focus**: HPC batch processing for production-scale glacier analysis
- **Active Development**: Batch processing infrastructure complete and tested
- **Production Ready**: 192 glacier regions with predictable batch slicing

### Added
- **Container Implementation Complete** (January 14, 2026)
  - Fixed directory structure to properly nest outputs under `1_download_merge_and_clip/{satellite}/{region}/`
  - Modified wrapper.py to create satellite-specific base directories
  - Validated both Landsat and Sentinel-2 processing with correct output locations
  - Container now mirrors HPC workflow exactly with proper file ownership and AWS integration
- **Critical Bug Fix: Configuration Hierarchy** (December 22, 2025)
  - Fixed argparse defaults overriding config.ini production values
  - Removed `default='48G'` and `default='01:00:00'` from `--memory` and `--runtime` arguments
  - Moved runtime/memory to config.ini as single source of truth
  - Added CLI override support maintaining priority: CLI > config.ini > fallbacks
  - Automatic batch range suffix for job names (e.g., `sentinel2_20250101_0_25.job`)
  - Changed delimiter from dash to underscore for cross-system compatibility
  - Impact: Jobs now correctly use config.ini values (60G, 24:00:00) instead of hardcoded defaults

- **Configuration Documentation Enhancement** (December 22, 2025)
  - Added comprehensive batch processing usage guide in config.ini header
  - Documented configuration priority (CLI > config.ini > defaults)
  - Provided copy-paste ready batch command examples
  - Added critical ConfigParser warning: "DO NOT COMMENT OUT OR DELETE VARIABLE LINES"
  - Clarified regions and execution_mode behavior
  - Fixed execution_mode comment (removed "not currently used")

- **Documentation Cleanup** (December 22, 2025)
  - Reduced AGENTS.md from 1717 to 283 lines (83% reduction)
  - Consolidated repetitive command examples
  - Updated Python version references to 3.13
  - Streamlined for AI agent command determination focus

- **Batch Processing Infrastructure** (December 21, 2025)
  - Implemented `--start_end_index` CLI argument for predictable glacier batching
  - Mutual exclusivity between `--regions` and `--start_end_index` parameters
  - Alphabetical region sorting in both Sentinel-2 and Landsat workflows
  - Consistent glacier ordering across both satellite types
  - Full CLI → config → job file → processing script chain validated
  - Supports batch splitting: 0:48, 48:96, 96:144, 144:192 for 192 glaciers

- **Environment Debugging Enhancements** (December 21, 2025)
  - Added geospatial package version logging to all job outputs
  - Package-manager agnostic version reporting (works with conda, pip, pixi)
  - Displays versions: rioxarray, rasterio, osgeo (GDAL), geopandas, xarray
  - Tab-indented output for improved readability in SLURM logs
  - Available in both HPC and local execution modes

- **Code Cleanup** (December 21, 2025)
  - Removed unused `which_steps_to_run` parameter from config system
  - Legacy bash workflow parameter no longer loaded in Python scripts
  - Simplified configuration with only actively-used parameters
- **Landsat Coverage Quality Control** (December 2025)
  - Implemented 50% minimum glacier coverage threshold for Landsat processing (currently disabled)
  - Added pixel size calculation (225 m² per pixel for 15m × 15m resolution)
  - Consistent quality standards across Sentinel-2 and Landsat satellites
  - Scene-level rejection for low-coverage Landsat scenes (ready for activation)
  - Research-first approach: commented out pending Landsat data pattern validation

- **Sentinel-2 Folder Structure Automation** (December 2025)
  - Parameterized folder structure selection with `--folder_structure {old|new}` flag
  - Eliminated manual comment/uncomment operations for folder switching
  - Backward compatible with default 'old' structure
  - Version-controlled configuration management

- **Sentinel-2 Processing Optimizations** (October 2025)
  - 50%+ reduction in unnecessary downloads through tile filtering
  - Pre-download UTM grid tile ID filtering using region metadata
  - Centralized download location for future deduplication

- **Multi-Environment Data Synchronization** (October 2025)
  - Bidirectional S3 sync tool (`sync_from_s3.sh`)
  - Environment-aware path resolution (HPC vs local)
  - Safe multi-user defaults with `--force-overwrite` option
  - Bandwidth optimization with `--exclude-downloads` flag

### Changed
- **Documentation Reorganization** (December 2025)
  - Moved detailed technical docs to `docs/technical/` folder
  - Streamlined AGENTS.md for AI agent quick reference
  - Created dedicated technical documentation files

### Technical Details
- **Landsat Pixel Size**: 15m × 15m = 225 m² per pixel
- **Sentinel-2 Pixel Size**: 10m × 10m = 100 m² per pixel
- **Coverage Threshold**: 50% minimum glacier coverage for both satellites
- **Folder Structures**: Old (region-specific) vs New (shared download pool)

### Validation Status
- ✅ Landsat coverage control: Implemented and tested (currently disabled pending research)
- ✅ Folder structure automation: Command-line parsing and path generation validated
- ✅ Sentinel-2 optimizations: 50%+ download reduction confirmed
- ✅ Multi-environment sync: HPC and local path resolution working
# Step 3 - Orthocorrection & NetCDF Packaging

[![Status](https://img.shields.io/badge/status-production--ready-brightgreen)](https://github.com/bidhya/greenland-glacier-flow/3_orthocorrect_and_netcdf-package)
[![Python](https://img.shields.io/badge/python-3.13+-blue)](https://www.python.org/)
[![SLURM](https://img.shields.io/badge/HPC-SLURM-orange)](https://slurm.schedmd.com/)

---

**🚨 Follow steps exactly: single error can create invalid results that appear correct.**

### Key Requirements
- ✅ **Uses exact Python 3.13 conda environment `glacier_velocity` from step1**
- ✅ **Perfect path configuration** in `lib/config.py`
- ✅ **Complete data validation** before processing
- ✅ **Output verification** after processing

---

## 🎯 What is Step 3?

This is the final step in processing Greenland glacier velocity data:

1. **Step 1**: Download satellite imagery
2. **Step 2**: Calculate velocities (MATLAB): separate repo
3. **Step 3**: Correct orbital errors and package into NetCDF files

---

## 📁 Project Structure & Integration

**Repository Root**: `greenland-glacier-flow/` (your cloned repository)

**Recent Integration**: Step 1 and Step 3 workflows have been integrated into the same repository for streamlined processing.

**Directory Structure**:
```
greenland-glacier-flow/                    # Repository root
├── 1_download_merge_and_clip/            # Step 1: Satellite data download & processing
├── 3_orthocorrect_and_netcdf-package/    # Step 3: Orbital correction & NetCDF packaging
├── slurm_step3/                          # SLURM scripts (at root level for easy access)
└── environment.yml                       # Shared conda environment
```

**Navigation Notes**:
- **Step 3 Directory**: `3_orthocorrect_and_netcdf-package/` (current location)
- **SLURM Scripts**: `slurm_step3/` (at repository root, not in Step 3 folder)
- **Shared Environment**: Uses same `glacier_velocity` conda environment as Step 1

---

## 🚀 Quick Start for New Users

### 1. Environment Setup

```bash
# Conda (Python) environment - SAME as Step 1 (one-time setup)
# If you already created 'glacier_velocity' in Step 1, skip this
conda env create -f environment.yml
conda activate glacier_velocity
```

**Note**: Uses exact same conda environment as Step 1. Create once, reuse for both steps.

### 2. Configuration Setup

**⚠️ CRITICAL**: Step 3 requires outputs from Step 1 (Sentinel-2 data) and Step 2 (velocity calculations).

#### Quick Setup Script
```bash
# Navigate to Step 3 directory
cd 3_orthocorrect_and_netcdf-package

# Copy configuration template
cp lib/config_template.py lib/config.py

# Edit configuration (REQUIRED - set your paths)
nano lib/config.py  # or your preferred editor
```

#### Required Path Configuration
**Reference Data Paths** (relative to project, usually don't change):
- `AOI_SHP`: Glacier boundary shapefile
- `AOI_NAMES`: Glacier name mappings
- `GIMPMASKDIR`: GIMP mask directory

**Step1 Input Data Paths**
- `IMGDIR`: Sentinel-2 from Step 1

**Ask MJ for next two paths for velocity data**  (from Step2)
- `VELDIR`: Sentinel-2 velocity 
- `VELDIR_LS`: Landsat velocity 

**Output Paths** (must be writable):
- `WD`: Working Directory to save output of this step  
- `LOG_DIR`: Log directory (usually `slurm_step3/logs`)

**Date Range**:
- `START_DATE`: Processing start date
- `END_DATE`: Processing end date

**Note**: Some paths are hardcoded - verify all match your system before running.

### 3. Run on HPC
Designed only for HPC because of TB-scale data volume.

**✅ Automatic Path Detection**: The SLURM script automatically detects your repository location and copies the Step 3 folder to compute nodes. No manual path editing required.

**Manual Path Override (Optional)**: If auto-detection fails or repository structure changes, manually set the path in `orthocorrect_netcdf-package_batch.sh`:
```bash
# Find and replace this line in the script:
# STEP3_DIR="$REPO_DIR/3_orthocorrect_and_netcdf-package"
# With your specific path:
STEP3_DIR="/path/to/your/greenland-glacier-flow/3_orthocorrect_and_netcdf-package"
```

**SLURM Job Configuration**: Edit `orthocorrect_netcdf-package_batch.sh` for HPC account settings (time, memory, email) and optional manual path override.


#### HPC Execution Commands
```bash
# Navigate to SLURM scripts (from repository root)
cd greenland-glacier-flow/slurm_step3

# Process ALL available glaciers
sbatch orthocorrect_netcdf-package_batch.sh

# Process specific glaciers only
sbatch orthocorrect_netcdf-package_batch.sh --glaciers "049_jakobshavn,001_alison"
```


## 🚨 Step 3 Core Processing Architecture

**Critical Entry Point**: `orthocorrect_netcdf-package.py` is the core orchestrator for all scientific processing.

**Workflow Entry Point**:
```
SLURM Job (orthocorrect_netcdf-package_batch.sh)
    ↓
Batch Processor (batch_glacier_processor.py)
    ↓ (parallel subprocess calls for each glacier)
Core Orchestrator (orthocorrect_netcdf-package.py)
    ↓ (6-step processing chain)
1_match_to_orbits.py → 2_get_orbital_average_offset.py → 3_correct_fields.py → 
4a_netcdf_stack_sentinel.py → 4b_netcdf_stack_landsat.py → 4c_netcdf_stack_landsat_sentinel_combined.py
```

**Technical Details**:
- **SLURM Script**: `orthocorrect_netcdf-package_batch.sh` calls `batch_glacier_processor.py`
- **Batch Processing**: Designed for parallel processing of multiple glaciers using all available cores (~40, 48, 92)
- **Resource Allocation**: Uses 3GB memory per core; increase memory or reduce cores if memory errors occur
- **Scientific Processing**: `orthocorrect_netcdf-package.py` contains the actual orbital correction algorithms and NetCDF packaging logic
- **Batch Orchestration**: New wrapper scripts enable parallel processing of multiple glaciers
- **Graceful Degradation**: Workflow continues with Sentinel-2 only data if Landsat unavailable
- **Stable Core**: The core orchestrator has proven reliability - wrapper improvements don't affect scientific results

### 4. Monitor Progress

`slurm_step3/runs_output`: will have SLURM output messages  
`slurm_step3/logs`: will have logs for each glacier being processed  
Pay attention to any `errored_glaciers.log` as it indicates one or more glacier processing failed.

```bash
# From slurm_step3 directory (or use full paths)
cd slurm_step3

# View output (replace JOBID)
cat runs_output/ortho_nc_pkg_JOBID.out

# Check for errors
cat logs/errored_glaciers.log
```

## 📤 What You Get

- **Success**: NetCDF files in `${WD}/nsidic_v01.1_delivery/` with glacier names
- **Partial Success**: Sentinel-2 only data for glaciers with Landsat gaps
- **Failure**: Logged in `errored_glaciers.log` (graceful degradation prevents total loss)

**Expected runtime**: 3-4 hours for all 192 glaciers.

**Note**: Comprehensive testing/validation steps will be added in future updates.

---

## 📂 Output Structure

Two parallel output directories are created:

```
3_orthocorrect_and_netcdf-package/
├── nsidic_v01.1/                         # Intermediate processing outputs
│   └── {glacier}/
│       ├── {glacier}.gpkg                # AOI geopackage
│       ├── gimp_masks/                   # Ice/ocean/rock masks
│       ├── orbits/                       # Orbit metadata and offset fields
│       ├── velocities/                   # Corrected velocity directories
│       └── netcdf/
│           ├── S2_{glacier}_v{VERSION}.nc    # Sentinel-2 only
│           └── L8_{glacier}_v{VERSION}.nc    # Landsat only
│
└── nsidic_v01.1_delivery/                # FINAL DELIVERY (what we distribute)
    ├── {glacier}_2024_v01.1.nc           # Combined NetCDF per year
    └── ...
```

**Example**:
```
nsidic_v01.1/105_sortebrae/netcdf/       # Intermediate S2 and L8 NetCDFs
nsidic_v01.1_delivery/105_Sortebrae_2024_v01.1.nc   # Final combined product
```

**Note**: The `_delivery` folder contains the final combined NetCDFs (from 4c script) with public glacier IDs and year in the filename. Only deliver data from `nsidic_v01.1_delivery/`.

---

## 🔧 Troubleshooting

### Common Issues
- **"No data found"**: Check `VELDIR` and `IMGDIR` paths in `lib/config.py`
- **Environment errors**: Ensure `glacier_velocity` conda env is active
- **Job fails**: Verify HPC access and paths exist on cluster
- **Some glaciers fail**: Expected (~7% fail due to data limitations)

### Quick Fixes
```bash

# Check data exists
ls ${VELDIR}/049_jakobshavn/

# Verify environment
conda activate glacier_velocity
python -c "import xarray; print('OK')"
```

### Expected Failure Rates
- **Success**: ~93% glaciers produce complete outputs
- **Partial**: ~2% Sentinel-2 only (no Landsat)
- **Failure**: ~5% cannot process (architectural limits)

---

## 📚 More Information

- **[docs/](docs/)**: Detailed documentation and troubleshooting
- **Legacy codes**: Moved to `legacy/` subfolder - retained for reference during streamlining

**For help**: Check logs first, then consult detailed docs.

---

*Step 3 - Greenland Glacier Velocity Processing | OSU Unity HPC*
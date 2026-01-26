# Greenland Glacier Flow Processing - Quick Start Guide

## Overview

Automated satellite imagery processing for glacier velocity analysis. This is **Step 1 of a 3-step workflow** for processing 192 Greenland glaciers using Sentinel-2 and Landsat data.

**Workflow Pipeline:**
1. **Step 1 (This Repository)**: Download, merge, clip, and organize satellite imagery → `1_download_merge_and_clip/`
2. **Step 2 (Downstream)**: Calculate surface displacement maps for velocity estimation → Requires Step 1 outputs
3. **Step 3 (Downstream)**: Orthocorrect and package results into NetCDF files → Requires Steps 1 & 2 outputs

**Data Sources:**
- **Sentinel-2**: High-resolution optical imagery (10m resolution) from ESA Copernicus program
- **Landsat**: Long-term archive (15m resolution) from USGS/NASA
- **Storage**: All data accessed from AWS Open Data Registry (no costs for data transfer)

**Processing Overview:**
- Downloads raw satellite tiles covering glacier regions
- Merges overlapping tiles into seamless mosaics
- Clips to glacier boundaries using predefined region masks
- Organizes outputs by satellite type and region for downstream analysis

**Last Updated: January 26, 2026**

## Installation

### Install Miniforge

This workflow requires a conda environment for dependency management. We recommend using Miniforge (a minimal conda installer) for the best experience.

1. **Download and install Miniforge:**
   ```bash
   # Download the installer
   wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
   
   # Run the installer
   bash Miniforge3-Linux-x86_64.sh
   
   # Follow the prompts, accept defaults
   ```

2. **Clone the repository and set up the environment:**
   ```bash
   git clone https://github.com/bidhya/greenland-glacier-flow.git
   cd greenland-glacier-flow
   
   # Create the conda environment
   conda env create -f environment.yml
   
   # Activate the environment
   conda activate glacier_velocity
   ```

3. **Verify installation:**
   ```bash
   # Check that key packages are available
   python -c "import rasterio, geopandas, boto3; print('Dependencies OK')"
   ```

4. **Configure config.ini:**
   ```bash
   # Create config.ini by copying the template
   cp config.template.ini config.ini
   
   # Edit critical paths and settings for your environment
   # Update: base_dir, local_base_dir, email, runtime, memory, etc.
   # Most settings are optimized for Sentinel-2 (works for Landsat too)
   # Override satellite type and Landsat runtime via command line
   ```

5. **AWS IAM & Requester-Pays S3**
- **Why:** Landsat data is hosted in requester-pays S3 buckets on AWS; downloads will fail if AWS credentials are not correctly configured.
- **Quick setup:** Run `aws configure` or set environment variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `us-west-2` Oregon region for the account that will run the workflow.
- **Permissions:** Ensure the IAM user has S3 permissions (e.g., `s3:GetObject`, `s3:ListBucket`).
- **Boto3 behavior:** The workflow uses `boto3`; when accessing requester-pays buckets you may need to pass `RequestPayer='requester'` (the code handles this in the Landsat download functions, but verify access with a short dry-run).
- **Verify access:** From bash, `aws s3 ls --request-payer requester s3://usgs-landsat/collection02/landsat-c2l1/`.

## Core Commands

**All commands run from repository root.**

**Note:** All commands import default settings from `config.ini`. Command-line arguments override config values where specified.

### HPC Production (Primary Workflow)

**Batch Strategy:** Sentinel-2 uses 3 batches of 65 regions each due to AWS download limits (4 concurrent downloads). Landsat processes all 192 regions in a single batch since it has faster processing and fewer download operations per region.

```bash
# Sentinel-2: Process all 192 regions in 3 batches
./submit_job.sh --satellite sentinel2 --start-end-index 0:65
./submit_job.sh --satellite sentinel2 --start-end-index 65:130
./submit_job.sh --satellite sentinel2 --start-end-index 130:195

# Landsat: Single batch (all 192 regions, faster processing)
./submit_job.sh --satellite landsat --start-end-index 0:192 --runtime 125:00:00
```

### Testing & Development
```bash
# Dry-run test (recommended first)
./submit_job.sh --satellite sentinel2 --start-end-index 0:3 --dry-run true

# Small production test
./submit_job.sh --satellite sentinel2 --start-end-index 0:3

# Local execution for debugging
./submit_job.sh --satellite sentinel2 --regions 134_Arsuk --execution-mode local
```

## Production Workflow

### Job Monitoring (HPC)

```bash
# View log output (real-time)
tail -f /path/to/greenland_glacier_flow/slurm_jobs/sentinel2/logs/satellite_glacier_0-65.log

# Check SLURM output files
ls -lh OUT/sentinel2_*.out
```

### Validation Checklist

Before running full production:

- [ ] Updated `date1` and `date2` in config.ini
- [ ] Verified `base_dir` path exists and has space
- [ ] Confirmed email address is correct
- [ ] Pulled latest code: `git pull origin main`
- [ ] Tested with small batch (e.g., `--start-end-index 0:3`)
- [ ] Verified log files are being created with unique names
- [ ] Checked output directories are populating

## Custom Parameters

**Note:** The `--regions` and `--start-end-index` parameters are mutually exclusive. Use `--regions` for specific region selection, or `--start-end-index` for batch processing ranges.

**Region Naming:** Regions are identified by 3-digit codes (e.g., 134_Arsuk) corresponding to Greenland glacier IDs. Use `--regions` with comma-separated values for multiple regions.

```bash
# Single region, custom dates
./submit_job.sh --satellite sentinel2 --regions 134_Arsuk --date1 2025-01-01 --date2 2025-12-31

# Multiple regions
./submit_job.sh --satellite landsat --regions "134_Arsuk,191_Hagen_Brae"

# Force local execution
./submit_job.sh --satellite sentinel2 --execution-mode local

# Override memory/runtime (HPC only)
./submit_job.sh --satellite sentinel2 --start-end-index 0:65 --memory 128G --runtime 24:00:00
```

## Resource Requirements

### Expected Runtime & Storage
- **Single Region (Sentinel-2)**: 2-4 hours processing time
- **Batch of 65 Regions (Sentinel-2)**: ~50 hours processing time
- **Full Landsat Dataset (192 regions)**: ~125 hours processing time

**Note:** If a job times out, re-running the same SLURM command will process remaining uncompleted regions. However, it's better to set higher time limits initially to avoid timeout errors.

### HPC Resource Defaults
- **Memory**: Configurable (default: 60GB)
- **Runtime**: Configurable (default: 50 hours)
- **Cores**: 4 (configurable)

### Production Resource Requirements

| Satellite | Glaciers/Batch | Memory | Runtime | Output Size |
|-----------|----------------|--------|---------|-------------|
| Sentinel-2 | 65 | 60 GB | ~50 hours | ~50-100 GB/glacier |
| Landsat | 192 | 60 GB | ~125 hours | ~1-5 GB/glacier |

**Storage Planning**: 
- 192 Sentinel-2 glaciers × 75 GB avg = **~14 TB**
- 192 Landsat glaciers × 5 GB avg = **~960 GB**

## Configuration

**⚠️ CRITICAL:** The workflow imports all settings from `config.ini`. This file is the single source of truth for paths, memory, runtime, dates, and other parameters. Configure it properly before running any commands.

### config.ini Structure

```ini
[REGIONS]
regions = 134_Arsuk,191_Hagen_Brae

[DATES]
date1 = 2025-10-01
date2 = 2025-10-05

[PATHS]
base_dir = /path/to/save/processed/data

[FLAGS]
download_flag = 1
post_processing_flag = 1

[SETTINGS]
satellite = sentinel2
execution_mode = auto  # auto-detects HPC vs local
dry_run = False
```

### Satellite-Specific Configuration Notes

**Sentinel-2 (Default):**
- Optimized for high-resolution processing (10m bands)
- Default runtime: 24:00:00 (24 hours)
- Default memory: 60G
- Use 3 batches for full processing: 0:65, 65:130, 130:195

**Landsat:**
- Lower resolution processing (15m bands)
- Requires longer runtime: override with `--runtime 125:00:00`
- Same memory allocation (60G) works
- Single batch processing: 0:192 regions
- Command: `./submit_job.sh --satellite landsat --start-end-index 0:192 --runtime 125:00:00`

**Configuration Priority:**
1. Command-line arguments (highest priority)
2. config.ini values
3. Script defaults (lowest priority)

## Troubleshooting

### Environment Issues

```bash
# Check conda environment
conda info --envs
conda activate glacier_velocity

```

### Configuration Issues

```bash
# Validate config.ini syntax
python -c "import configparser; c=configparser.ConfigParser(); c.read('config.ini'); print('Config OK')"

# Check paths exist
ls -la /path/to/your/base_dir
```

## Output Structure

```
base_dir/
├── 1_download_merge_and_clip/
│   ├── sentinel2/
│   │   └── <region_name>/      # Region-specific processing directory
│   │       ├── download/        # Raw MGRS tiles (intermediate)
│   │       ├── clipped/         # Clipped scenes
│   │       ├── metadata/        # Processing metadata
│   │       └── template/        # Reference templates
│   └── landsat/
│       ├── <region_name>/       # Clipped Landsat scenes
│       └── _reference/          # STAC metadata and templates
```

## Key Files Reference

- `config.ini` - **CRITICAL configuration file** imported by the workflow. Contains all default settings for paths, memory, runtime, dates, and processing parameters. Must be configured before running any commands.
- `submit_job.sh` - **Master entry point** that automatically activates the `glacier_velocity` conda environment and calls `submit_satellite_job.py` with all provided arguments. This wrapper ensures consistent environment setup across HPC and local execution modes.
- `submit_satellite_job.py` - Core processing script that handles satellite data download, processing, and job submission


---

*For detailed documentation, see other .md files*
*Last Updated: January 26, 2026*
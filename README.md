# Greenland Glacier Flow Velocity Processing

This workflow is used download and subset Landsat and Sentinel-2 imagery for 192 glaciers over Greenland, calculate velocity using SDM algorithms, and finally orthocorrect and packages the results into NetCDF files for distribution through NSIDC DAAC.  

The workflow contains a mix of modern and legacy codes developed over many years by multiple people. This is it important to run the production workflow on HPC exactly as outlined here. 

## Workflow Pipeline

**Complete 3-Step Workflow**: End-to-end processing from satellite imagery to final NetCDF velocity products.

1. **Step 1 (This Repository)**: Download, merge, clip, and organize satellite imagery → `1_download_merge_and_clip/`
2. **Step 2 (Downstream)**: Calculate surface displacement maps for velocity estimation → Requires Step 1 data and orchestrated with `matlab` 
3. **Step 3 (This Repository)**: Orthocorrect and package results into NetCDF files → `3_orthocorrect_and_netcdf-package/`

## 🚀 Operational Workflow

**All commands run from repository root.**

### One-Time Setup
Read Step1 [QUICKSTART.md](docs/QUICKSTART.md) for detailed setup instructions. The same setup is used for Step3 as well.  

```bash
# Create conda environment (includes all dependencies)
conda env create -f environment.yml

# ⚠️ CRITICAL: Configure config.ini for your environment
# Copy config.template.ini to config.ini and edit paths/settings
cp config.template.ini config.ini
# Edit base_dir, local_base_dir, email, and other settings
```

**⚠️ Important:** The workflow imports settings from `config.ini`. All production commands rely on this configuration file for paths, memory, runtime, and other critical parameters.

**HPC Setup Note:** After cloning/pulling on HPC, make shell scripts executable:
```bash
chmod +x submit_job.sh
# Add execute permissions to any other .sh files as needed, else call with bash ... command.
```

**Note (Landsat data):** Landsat downloads rely on AWS "requester-pays" S3 buckets. Ensure you have AWS IAM credentials configured locally (e.g., via `aws configure` or environment variables) and that your IAM user/account has S3 access permissions. Workflow uses `boto3` .

### Production Commands
```bash
# Sentinel-2: Process all 192 regions in 3 batches
./submit_job.sh --satellite sentinel2 --start_end_index 0:65
./submit_job.sh --satellite sentinel2 --start_end_index 65:130
./submit_job.sh --satellite sentinel2 --start_end_index 130:195

# Landsat: Single batch
./submit_job.sh --satellite landsat --start_end_index 0:192 --runtime 125:00:00
```

**How It Works**: The `submit_job.sh` script calls the Python script (`submit_satellite_job.py`), which creates and submits SLURM jobs to the HPC cluster. All SLURM job files, logs, and processing outputs will be created in the `base_dir` specified in `config.ini`.  

Command line argument overwrites provided for many of the args. However, it is strongly recommended to setup these args in `config.ini`. Do overwrite only for `satellite, start_end_index and runtime` as you see in production-level copy/past commands above.  

## 📖 Documentation

- **[QUICKSTART.md](docs/QUICKSTART.md)** - Step1 detailed setup, operational commands, and troubleshooting
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design decisions
- **[SENTINEL2_WORKFLOW_DOCUMENTATION.md](docs/SENTINEL2_WORKFLOW_DOCUMENTATION.md)** - Sentinel-2 processing details
- **[LANDSAT_WORKFLOW_DOCUMENTATION.md](docs/LANDSAT_WORKFLOW_DOCUMENTATION.md)** - Landsat processing details

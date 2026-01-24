# Greenland Glacier Flow Processing

**Automated satellite data acquisition for glacier velocity analysis.**

## What It Does

This repository processes satellite imagery to prepare data for glacier velocity analysis across Greenland's 192 major glaciers. It downloads, merges, and clips Sentinel-2 and Landsat satellite data, organizing it for downstream velocity estimation workflows.

## Workflow Pipeline

**Step 1 of 3-Step Workflow**: Download, process, and organize satellite imagery for glacier velocity analysis.

1. **Step 1 (This Repository)**: Download, merge, clip, and organize satellite imagery → `1_download_merge_and_clip/`
2. **Step 2 (Downstream)**: Calculate surface displacement maps for velocity estimation → Requires Step 1 outputs
3. **Step 3 (Downstream)**: Orthocorrect and package results into NetCDF files → Requires Steps 1 & 2 outputs

## 🎯 Project Status (January 23, 2026)

**Production Ready**: Batch processing infrastructure complete and validated for HPC deployment.

- ✅ **192 Glacier Regions**: Full Greenland coverage with predictable batch slicing
- ✅ **Dual Satellite Support**: Unified workflow for Sentinel-2 and Landsat
- ✅ **HPC Production**: SLURM-based batch processing operational
- ✅ **Batch Processing**: `--start-end-index` parameter for systematic region batching

## 🚀 Operational Workflow

**All commands run from repository root.**

### One-Time Setup
```bash
# Create conda environment (includes all dependencies)
conda env create -f environment.yml

# ⚠️ CRITICAL: Configure config.ini for your environment
# Copy config.template.ini to config.ini and edit paths/settings
cp config.template.ini config.ini
# Edit base_dir, local_base_dir, email, and other settings
```

**⚠️ Important:** The workflow imports settings from `config.ini`. All production commands rely on this configuration file for paths, memory, runtime, and other critical parameters.

**Note (Landsat data):** Landsat downloads rely on AWS "requester-pays" S3 buckets. Ensure you have AWS IAM credentials configured locally (e.g., via `aws configure` or environment variables) and that your IAM user/account has S3 access permissions. Workflow uses `boto3` .

### Production Commands
```bash
# Sentinel-2: Process all 192 regions in 3 batches
./submit_job.sh --satellite sentinel2 --start-end-index 0:65
./submit_job.sh --satellite sentinel2 --start-end-index 65:130
./submit_job.sh --satellite sentinel2 --start-end-index 130:195

# Landsat: Single batch
./submit_job.sh --satellite landsat --start-end-index 0:192 --runtime 125:00:00
```

**How It Works**: The `submit_job.sh` script activates the conda environment and calls the Python script (`submit_satellite_job.py`), which creates and submits SLURM jobs to the HPC cluster. All SLURM job files, logs, and processing outputs will be created in the `base_dir` specified in `config.ini`.

### Testing Commands
```bash
# Dry-run test (recommended first)
./submit_job.sh --satellite sentinel2 --start-end-index 0:3 --dry-run true

# Small production test
./submit_job.sh --satellite sentinel2 --start-end-index 0:3
```

## 📖 Documentation

- **[QUICKSTART.md](docs/QUICKSTART.md)** - Detailed setup and troubleshooting

## 🏗️ Overview

- **Satellite Data**: Sentinel-2 and Landsat from AWS Open Data
- **Regions**: 192 Greenland glaciers
- **Batch Strategy**: 3 batches of 65 regions (AWS download limits)
- **Environment**: HPC SLURM jobs with automatic conda activation

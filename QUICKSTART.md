# Greenland Glacier Flow Processing - Quick Start Guide

## Overview

Automated satellite imagery processing for glacier velocity analysis. Supports Sentinel-2 and Landsat across HPC (SLURM), local (WSL/Ubuntu), and AWS Lambda environments.

## Quick Setup

```bash
# Clone repository
git clone <repository-url>
cd greenland-glacier-flow

# Copy and edit configuration
cp config.ini.example config.ini
# Edit config.ini with your paths and settings
```

```bash
# Install Miniforge
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh

# Create environment
conda env create -f environment.yml
conda activate glacier_velocity
```

```bash
# Configure AWS
aws configure

# Deploy Lambda container
cd aws/scripts
./deploy_lambda_container.sh
```

## Core Commands

```bash
# Auto-detect environment, use config.ini settings
python submit_satellite_job.py

# Process Sentinel-2 data
python submit_satellite_job.py --satellite sentinel2

# Process Landsat data
python submit_satellite_job.py --satellite landsat

# Test without submitting jobs
python submit_satellite_job.py --dry-run true
```

## Custom Parameters

```bash
# Single region, custom dates
python submit_satellite_job.py --regions 134_Arsuk --date1 2024-10-01 --date2 2024-10-05 --satellite sentinel2

# Multiple regions
python submit_satellite_job.py --regions "134_Arsuk,191_Hagen_Brae" --satellite landsat

# Force execution mode
python submit_satellite_job.py --execution-mode local --satellite sentinel2

# Override config paths
python submit_satellite_job.py --base-dir /path/to/your/data --satellite sentinel2
```

## AWS Processing

```bash
# Lambda processing
python aws/scripts/submit_aws_job.py --service lambda --satellite sentinel2 --regions 134_Arsuk

# Batch processing
python aws/scripts/submit_aws_job.py --service batch --satellite landsat --regions 191_Hagen_Brae
```

## Data Synchronization (AWS Users)

```bash
# Sync results from S3 to local/HPC
./sync_from_s3.sh --exclude-downloads

# Preview sync without downloading
./sync_from_s3.sh --dry-run

# Force overwrite existing files
./sync_from_s3.sh --exclude-downloads --force-overwrite
```

## Configuration

### config.ini Structure

```ini
[REGIONS]
regions = 134_Arsuk,191_Hagen_Brae

[DATES]
date1 = 2024-10-01
date2 = 2024-10-05

[PATHS]
base_dir = /path/to/your/data

[FLAGS]
download_flag = 1
post_processing_flag = 1

[SETTINGS]
satellite = sentinel2
execution_mode = auto
dry_run = False
```

### AWS Configuration (aws/config/aws_config.ini)

```ini
[LAMBDA]
function_name = glacier-processor
memory_size = 5120
timeout = 900
ephemeral_storage = 10240

[S3]
bucket_name = your-glacier-data-bucket
base_path = 1_download_merge_and_clip
```

## Testing Commands

```bash
# Dry run (recommended first step)
python submit_satellite_job.py --satellite sentinel2 --dry-run true

# Test single region, short date range
python submit_satellite_job.py --regions 134_Arsuk --date1 2024-10-01 --date2 2024-10-05 --satellite sentinel2 --dry-run true

# Test Landsat (longer revisit time)
python submit_satellite_job.py --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-08 --satellite landsat --dry-run true
```

## Troubleshooting

### Environment Issues

```bash
# Check SLURM availability (HPC)
which sbatch

# Check conda environment
conda info --envs
conda activate glacier_velocity

# Force local mode if auto-detection fails
python submit_satellite_job.py --execution-mode local
```

### Configuration Issues

```bash
# Validate config.ini syntax
python -c "import configparser; c=configparser.ConfigParser(); c.read('config.ini'); print('Config OK')"

# Check paths exist
ls -la /path/to/your/base_dir
```

### AWS Issues

```bash
# Check AWS credentials
aws sts get-caller-identity

# Check Lambda function
aws lambda get-function --function-name your-function-name

# Check S3 bucket access
aws s3 ls s3://your-bucket-name/
```

## Output Structure

```
base_dir/
├── 1_download_merge_and_clip/
│   ├── sentinel2/
│   │   ├── download/          # Shared tile pool
│   │   ├── clipped/           # Region-specific outputs
│   │   │   ├── 134_Arsuk/
│   │   │   └── 191_Hagen_Brae/
│   │   ├── metadata/          # Processing logs
│   │   └── template/          # Reference files
│   └── landsat/
│       ├── 134_Arsuk/         # Direct outputs
│       └── _reference/        # Reference data
```

## Key Files Reference

- `submit_satellite_job.py` - Main processing script
- `config.ini` - Configuration file
- `aws/scripts/submit_aws_job.py` - AWS processing
- `sync_from_s3.sh` - Data synchronization tool

---

*For detailed documentation, see other .md files*
*Last Updated: October 2025*

### Basic Processing

```bash
# Auto-detect environment, use config.ini settings
python submit_satellite_job.py

# Process Sentinel-2 data
python submit_satellite_job.py --satellite sentinel2

# Process Landsat data
python submit_satellite_job.py --satellite landsat

# Test without submitting jobs
python submit_satellite_job.py --dry-run true
```

### Custom Parameters

```bash
# Single region, custom dates
python submit_satellite_job.py --regions 134_Arsuk --date1 2024-10-01 --date2 2024-10-05 --satellite sentinel2

# Multiple regions
python submit_satellite_job.py --regions "134_Arsuk,191_Hagen_Brae" --satellite landsat

# Force execution mode
python submit_satellite_job.py --execution-mode local --satellite sentinel2

# Override config paths
python submit_satellite_job.py --base-dir /path/to/your/data --satellite sentinel2
```

### AWS Processing

```bash
# Lambda processing
python aws/scripts/submit_aws_job.py --service lambda --satellite sentinel2 --regions 134_Arsuk

# Batch processing
python aws/scripts/submit_aws_job.py --service batch --satellite landsat --regions 191_Hagen_Brae
```

### Data Synchronization (AWS Users)

```bash
# Sync results from S3 to local/HPC
./sync_from_s3.sh --exclude-downloads

# Preview sync without downloading
./sync_from_s3.sh --dry-run

# Force overwrite existing files
./sync_from_s3.sh --exclude-downloads --force-overwrite
```

### AWS Processing

```bash
# Lambda processing
python aws/scripts/submit_aws_job.py \
  --service lambda \
  --satellite sentinel2 \
  --regions 134_Arsuk

# Batch processing
python aws/scripts/submit_aws_job.py \
  --service batch \
  --satellite landsat \
  --regions 191_Hagen_Brae
```

### Data Synchronization (AWS Users)

```bash
# Sync results from S3 to local/HPC
./sync_from_s3.sh --exclude-downloads

# Preview sync without downloading
./sync_from_s3.sh --dry-run

# Force overwrite existing files
./sync_from_s3.sh --exclude-downloads --force-overwrite
```

## Configuration

### config.ini Structure

```ini
[REGIONS]
regions = 134_Arsuk,191_Hagen_Brae

[DATES]
date1 = 2024-10-01
date2 = 2024-10-05

[PATHS]
base_dir = /path/to/your/data

[FLAGS]
download_flag = 1
post_processing_flag = 1

[SETTINGS]
satellite = sentinel2
execution_mode = auto
dry_run = False
```

### AWS Configuration (aws/config/aws_config.ini)

```ini
[LAMBDA]
function_name = glacier-processor
memory_size = 5120
timeout = 900
ephemeral_storage = 10240

[S3]
bucket_name = your-glacier-data-bucket
base_path = 1_download_merge_and_clip
```

## Testing Commands

```bash
# Dry run (recommended first step)
python submit_satellite_job.py --satellite sentinel2 --dry-run true

# Test single region, short date range
python submit_satellite_job.py --regions 134_Arsuk --date1 2024-10-01 --date2 2024-10-05 --satellite sentinel2 --dry-run true

# Test Landsat (longer revisit time)
python submit_satellite_job.py --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-08 --satellite landsat --dry-run true
```

## Troubleshooting

### Environment Issues

```bash
# Check SLURM availability (HPC)
which sbatch

# Check conda environment
conda info --envs
conda activate glacier_velocity

# Force local mode if auto-detection fails
python submit_satellite_job.py --execution-mode local
```

### Configuration Issues

```bash
# Validate config.ini syntax
python -c "import configparser; c=configparser.ConfigParser(); c.read('config.ini'); print('Config OK')"

# Check paths exist
ls -la /path/to/your/base_dir
```

### AWS Issues

```bash
# Check AWS credentials
aws sts get-caller-identity

# Check Lambda function
aws lambda get-function --function-name your-function-name

# Check S3 bucket access
aws s3 ls s3://your-bucket-name/
```

## Output Structure

After processing, your data will be organized as:

```
base_dir/
├── 1_download_merge_and_clip/
│   ├── sentinel2/
│   │   ├── download/          # Shared tiles (Sentinel-2 only)
│   │   ├── clipped/134_Arsuk/ # Processed outputs
│   │   ├── metadata/          # Processing logs
│   │   └── template/          # Reference files
│   └── landsat/
│       ├── 134_Arsuk/         # Direct outputs
│       └── _reference/        # Reference data
```

## Key Files Reference

- `submit_satellite_job.py` - Main processing script
- `config.ini` - Configuration file
- `aws/scripts/submit_aws_job.py` - AWS processing
- `sync_from_s3.sh` - Data synchronization tool

---

*For detailed documentation, see other .md files*
*Last Updated: October 2025*
#!/bin/bash

# Wrapper script to run submit_satellite_job.py with automatic conda environment activation
# Handles environment setup for both HPC (SLURM) and local execution modes
# Edit the environment name below to match your setup

ENV_NAME="glacier_velocity"  # <-- CHANGE THIS TO YOUR ENVIRONMENT NAME

# Usage examples:
# ./submit_job.sh --satellite sentinel2
# ./submit_job.sh --satellite landsat --regions 134_Arsuk,101_sermiligarssuk
# ./submit_job.sh --satellite landsat --date1 2024-01-01 --date2 2024-12-31 --dry-run true
# ./submit_job.sh --satellite sentinel2 --execution-mode local --date1 2024-10-01 --date2 2024-10-05
# ./submit_job.sh --satellite sentinel2 --memory 64G --runtime 12:00:00 --cores 4
# ./submit_job.sh --config custom_config.ini --satellite sentinel2 --memory 64G --runtime 02:00:00

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Initialize conda and activate environment
eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME"

# Run the Python script with all arguments
python "${SCRIPT_DIR}/submit_satellite_job.py" "$@"
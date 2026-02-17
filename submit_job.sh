#!/bin/bash

# Wrapper script to run submit_satellite_job.py with automatic conda environment activation
# Handles environment setup for both HPC (SLURM) and local execution modes
# Edit the environment name below to match your setup

# Conda Environment Activation
# Note: The following conda activation is optional if your default Python environment
# contains all required workflow packages. If `python` runs without errors, these lines
# can be removed. However, the glacier_velocity environment is required for the full
# workflow anyway, so this setup ensures compatibility across all user environments.
ENV_NAME="glacier_velocity"  # <-- CHANGE THIS TO YOUR ENVIRONMENT NAME
eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME"

# Usage examples:
# ./submit_job.sh --satellite sentinel2
# ./submit_job.sh --satellite landsat --regions 134_Arsuk,101_sermiligarssuk
# ./submit_job.sh --satellite landsat --date1 2024-01-01 --date2 2024-12-31 --dry-run true
# ./submit_job.sh --satellite sentinel2 --execution-mode local --date1 2024-10-01 --date2 2024-10-05
# ./submit_job.sh --satellite sentinel2 --memory 64G --runtime 12:00:00 --cores 4
# ./submit_job.sh --config custom_config.ini --satellite sentinel2 --memory 64G --runtime 02:00:00

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the Python script with all arguments
python "${SCRIPT_DIR}/submit_satellite_job.py" "$@"
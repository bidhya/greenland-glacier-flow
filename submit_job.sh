#!/bin/bash

# Simple wrapper to run submit_satellite_job.py
# Edit the environment name below to match your setup

ENV_NAME="glacier_velocity"  # <-- CHANGE THIS TO YOUR ENVIRONMENT NAME

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Initialize conda and activate environment
eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME"

# Run the Python script with all arguments
python "${SCRIPT_DIR}/submit_satellite_job.py" "$@"
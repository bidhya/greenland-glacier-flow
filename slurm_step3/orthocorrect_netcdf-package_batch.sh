#!/usr/bin/env bash

#SBATCH --time=03:00:00  # 4 hours to process ~192 glaciers with 40 cpus
#SBATCH --cpus-per-task=4  # 90
## with 48 cores and 120Gb, got following: "slurmstepd: error: Detected 1 oom_kill event in StepId=9347559.batch. Some of the step tasks have been OOM Killed"
#SBATCH --mem=28G  # 140G (for 48 cpus), 280G for 90 cpus etc.
#SBATCH --job-name=ortho_nc_pkg.job
#SBATCH --mail-type=ALL
#SBATCH --mail-user=yadav.111@osu.edu
#SBATCH --output=runs_output/ortho_nc_pkg_%j.out
#SBATCH --partition=howat,batch
#SBATCH --begin=now+0minutes

# Activate appropriate conda environment. 
eval "$(conda shell.bash hook)"
# source activate greenland_glacier_flow_3
# conda activate greenland_glacier_flow_3
conda activate glacier_velocity
# Report to terminal.
date; hostname; pwd
python --version; which python
echo $SLURM_SUBMIT_DIR
echo "===================================================================================================="
echo "Step 3: Orthocorrect and NetCDF package for Greenland"

# Parse command line arguments (optional)
# Usage: sbatch orthocorrect_netcdf-package_batch.sh [--glaciers "name1,name2"]
# Examples:
#   sbatch orthocorrect_netcdf-package_batch.sh                    # Process ALL available glaciers

#   Test specific glaciers (by name, comma-separated, no spaces)
#   sbatch orthocorrect_netcdf-package_batch.sh --glaciers 138_SermiitsiaqInTasermiut
#   sbatch orthocorrect_netcdf-package_batch.sh --glaciers "138_SermiitsiaqInTasermiut,184_Usugdlup,137_SermeqSondreSermilik,104_sorgenfri"
#   sbatch orthocorrect_netcdf-package_batch.sh --glaciers "049_jakobshavn,001_alison"  

#   sbatch orthocorrect_netcdf-package_batch.sh --glaciers "134_Arsuk,140_CentralLindenow"  # Problematic glaciers (triggered errors for 2024)

# Check for optional --glaciers argument
GLACIERS=""
if [ $# -ge 1 ] && [ "$1" = "--glaciers" ]; then
    GLACIERS="$2"
fi

# ================================================================================
# DYNAMIC PATH DETECTION FOR STEP 3 FOLDER
# ================================================================================
# This section automatically determines the location of the Step 3 processing folder
# regardless of where the repository is cloned or where sbatch is executed from.
#
# IMPORTANT: If repository structure changes (e.g., folder names or locations),
# update the STEP3_DIR path construction below accordingly.
#
# Current assumption: Step 3 folder is at repository root level
# Repository structure: repo_root/3_orthocorrect_and_netcdf-package/
# SLURM script location: repo_root/slurm_step3/orthocorrect_netcdf-package_batch.sh
# ================================================================================

# Use SLURM_SUBMIT_DIR to determine repository path
# SLURM_SUBMIT_DIR points to where sbatch was run (likely slurm_step3/ or repo root)
# Go up one level from submit directory to get repository root, then to Step 3 folder
REPO_DIR="$(dirname "$SLURM_SUBMIT_DIR")"
STEP3_DIR="$REPO_DIR/3_orthocorrect_and_netcdf-package"

# Debug output: Show path detection for troubleshooting
echo "Dynamic path detection:"
echo "  SLURM_SUBMIT_DIR: $SLURM_SUBMIT_DIR"
echo "  REPO_DIR: $REPO_DIR"
echo "  STEP3_DIR: $STEP3_DIR"
echo ""

# ================================================================================
# COPY STEP 3 CODE TO COMPUTE NODE
# ================================================================================
# SLURM jobs run on compute nodes with access to $TMPDIR
# Copy the entire Step 3 processing folder to the node's temporary directory
cd $TMPDIR
# cp -r /home/yadav.111/Github/greenland-glacier-flow/3_orthocorrect_and_netcdf-package .
cp -r "$STEP3_DIR" .
cd 3_orthocorrect_and_netcdf-package


# Run the main script.
if [ -n "$GLACIERS" ]; then
    echo "Running: python batch_glacier_processor.py --glaciers \"$GLACIERS\""
    python batch_glacier_processor.py --glaciers "$GLACIERS"
else
    echo "Running: python batch_glacier_processor.py  # Process ALL available glaciers for current IMGDIR"
    python batch_glacier_processor.py
fi

# # Updated examples for simplified interface:
# # sbatch orthocorrect_netcdf-package_batch.sh                           # Process ALL available glaciers
# # sbatch orthocorrect_netcdf-package_batch.sh --glaciers "049_jakobshavn,001_alison"  # Process specific glaciers

squeue --job $SLURM_JOBID

echo "================================================END================================================="
echo ""

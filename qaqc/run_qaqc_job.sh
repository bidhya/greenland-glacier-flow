#!/usr/bin/env bash
# =============================================================================
# Unified SLURM wrapper for all QAQC Python scripts.
#
# Usage (submit from inside qaqc/):
#   cd ~/Github/greenland-glacier-flow/qaqc
#
#   STEP 1 — run all four at once (finish in seconds):
#   sbatch run_qaqc_job.sh --step Step1 --script count_step1_files.py --year 2024
#   sbatch run_qaqc_job.sh --step Step1 --script count_step1_files.py --year 2025
#   sbatch run_qaqc_job.sh --step Step1 --script analyze_s2_satellites.py --year 2024
#   sbatch run_qaqc_job.sh --step Step1 --script analyze_s2_satellites.py --year 2025
#
#   STEP 3 — extract metadata (run all three at once; takes a few minutes each):
#   sbatch --cpus-per-task=16 --mem-per-cpu=20G run_qaqc_job.sh --step Step3 --script extract_metadata.py --year 2024
#   sbatch --cpus-per-task=16 --mem-per-cpu=20G run_qaqc_job.sh --step Step3 --script extract_metadata.py --year 2025
#   sbatch --cpus-per-task=16 --mem-per-cpu=20G run_qaqc_job.sh --step Step3 --script extract_metadata.py --year 2025_old
#
#   STEP 3 — comparisons (run after extract jobs finish):
#   sbatch --output=logs/csv_compare_2024_2025.out run_qaqc_job.sh --step Step3 --script compare_step3_metadata.py --year1 2024 --year2 2025
#   sbatch --output=logs/csv_compare_25old_25.out run_qaqc_job.sh --step Step3 --script compare_step3_metadata.py --year1 2025_old --year2 2025
# 
#   STEP 3 — compare netCDFs:
#   sbatch --output=logs/netcdf_compare_2024_2025.out run_qaqc_job.sh --step Step3 --script compare_netcdf.py --year1 2025 --year2 2024
#   sbatch --output=logs/netcdf_compare_25old_2025.out run_qaqc_job.sh --step Step3 --script compare_netcdf.py --year1 2025 --year2 2025_old
#
#   STEP 3 — NSIDC absolute compliance validation:
#   sbatch --output=logs/validate_2025.out run_qaqc_job.sh --step Step3 --script validate_netcdf.py --year 2025
#   sbatch --output=logs/validate_custom.out run_qaqc_job.sh --step Step3 --script validate_netcdf.py --base /fs/project/howat.4-3/greenland_glacier_flow/3_orthocorrect_and_netcdf-package/nsidic_v01.1_delivery
#
#   SLURM OVERRIDES — pass before the script name to override #SBATCH defaults:
#   sbatch --mem-per-cpu=20G run_qaqc_job.sh --step Step3 --script compare_netcdf.py --year1 2025 --year2 2025_old
#   sbatch --cpus-per-task=8 --mem-per-cpu=20G run_qaqc_job.sh --step Step3 --script extract_metadata.py --year 2025
#   sbatch --time=04:00:00 run_qaqc_job.sh --step Step3 --script extract_metadata.py --year 2024
#   sbatch --output=logs/netcdf_compare_%j.out run_qaqc_job.sh --step Step3 --script compare_netcdf.py --year1 2025 --year2 2024 --mode pixel-perfect  # pixel-perfect (e.g. after env change)
#
#   AFTER ALL JOBS — rsync results back to local:
#   rsync -avz yadav.111@unity.asc.ohio-state.edu:/home/yadav.111/QAQC_Results/ /home/bny/QAQC_Results/
#
# --step   : subfolder inside qaqc/ to run from (Step1 or Step3 — case-sensitive)
# --script : Python script filename inside that subfolder
# --year   : processing year (2024 or 2025); paths are resolved from data_paths.yml
#            For Step3: resolves the delivery directory automatically.
#            For Step1: passed through as --year to the Python script.
# All remaining args are forwarded to the Python script unchanged.
#
# CPU usage notes:
#   Step1 scripts (count_step1_files.py, analyze_s2_satellites.py) — single-core only;
#     extra CPUs allocated by SBATCH are unused but harmless (jobs finish in seconds).
#   Step3 extract_metadata.py — parallel by default (ProcessPoolExecutor); uses all
#     allocated CPUs. Pass --no-parallel to force serial execution.
#
# Output: CSVs written to ~/QAQC_Results/{step}/
#         No TMPDIR staging — scripts run in-place from SLURM_SUBMIT_DIR.
# =============================================================================

#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4G  # override: 20G for netcdf compare; cpus=16 for extract_metadata.py
#SBATCH --job-name=qaqc.job
#SBATCH --mail-type=ALL
#SBATCH --mail-user=yadav.111@osu.edu
#SBATCH --output=logs/qaqc_%j.out
#SBATCH --partition=howat,batch
#SBATCH --begin=now+0minutes

# SLURM_SUBMIT_DIR = qaqc/ (submitted from there)
QAQC_DIR="$SLURM_SUBMIT_DIR"

# Ensure logs directory exists (must be after all #SBATCH directives)
mkdir -p "$QAQC_DIR/logs"

# Activate conda environment
eval "$(conda shell.bash hook)"
conda activate glacier_velocity

# Report
date; hostname; pwd
python --version; which python
echo "SLURM_SUBMIT_DIR: $SLURM_SUBMIT_DIR"
echo "===================================================================================================="

# -----------------------------------------------------------------------
# Parse --step and --script; collect remaining args for the Python script
# -----------------------------------------------------------------------
STEP=""
SCRIPT=""
PYTHON_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --step)   STEP="$2";   shift 2 ;;
        --script) SCRIPT="$2"; shift 2 ;;
        *)        PYTHON_ARGS+=("$1"); shift ;;
    esac
done

if [[ -z "$STEP" || -z "$SCRIPT" ]]; then
    echo "ERROR: --step and --script are required."
    echo "Usage: sbatch run_qaqc_job.sh --step Step1 --script count_step1_files.py --year 2025"
    exit 1
fi

# Output directory — read from data_paths.yml hpc.results_root
OUT_DIR=$(python - <<EOF
import yaml; from pathlib import Path
with open("$QAQC_DIR/data_paths.yml") as f: p = yaml.safe_load(f)
print(Path(p["hpc"]["results_root"]) / "$STEP")
EOF
)
mkdir -p "$OUT_DIR"

echo "Step  : $STEP"
echo "Script: $SCRIPT"
echo "Args  : ${PYTHON_ARGS[*]}"
echo "OutDir: $OUT_DIR"
echo ""

# -----------------------------------------------------------------------
# Run the script directly from its location in the repo.
# Only inject --out-dir if the target script actually declares it.
# -----------------------------------------------------------------------
cd "$QAQC_DIR/$STEP"

# decide whether to append --out-dir
INJECT_OUT=
if grep -q -- "--out-dir" "$QAQC_DIR/$STEP/$SCRIPT"; then
    INJECT_OUT=yes
fi

if [[ -n "$INJECT_OUT" ]]; then
    echo "Running: python $SCRIPT --out-dir $OUT_DIR ${PYTHON_ARGS[*]}"
    echo "===================================================================================================="
    python "$SCRIPT" --out-dir "$OUT_DIR" "${PYTHON_ARGS[@]}"
else
    echo "Running: python $SCRIPT ${PYTHON_ARGS[*]}"
    echo "===================================================================================================="
    python "$SCRIPT" "${PYTHON_ARGS[@]}"
fi

squeue --job "$SLURM_JOBID"
echo "================================================END================================================="

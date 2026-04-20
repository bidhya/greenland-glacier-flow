#!/usr/bin/env bash


#SBATCH --time=03:00:00  # 72:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --job-name=ortho_nc_pkg.job
#SBATCH --mail-type=ALL
#SBATCH --mail-user=yadav.111@osu.edu
#SBATCH --output=runs_output/ortho_nc_pkg_%j.out
#SBATCH --partition=howat



# Change to the folder 1 level up from this shell script.
if [ -n "${SLURM_JOB_ID:-}" ]; then
    bash_file_path=$(scontrol show job "$SLURM_JOB_ID" | awk -F= '/Command=/{print $2}')
else
    bash_file_path=$(realpath $0)
fi
cd $(dirname $bash_file_path)
cd ..

# Activate appropriate conda environment. (For some reason have to activate geopy twice, once using "source".)
eval "$(conda shell.bash hook)"
# source activate greenland_glacier_flow_3
# conda activate greenland_glacier_flow_3
conda activate glacier_velocity


# Report to terminal.
date; hostname; pwd
echo "===================================================================================================="
echo "Orthocorrect and NetCDF package for Greenland"


# Set up parameters from command-line arguments or defaults.
if [[ -z "$1" ]]; then
	regions=''
else
	regions=$1
fi
if [[ -z "$2" ]]; then
	start_date='2023-01-01'
else
	start_date=$2
fi
if [[ -z "$3" ]]; then
	end_date='2023-12-31'
else
	end_date=$3
fi
if [[ -z "$4" ]]; then
	base_dir=/fs/project/howat.4-3/howat-data/glacier_flow/sentinel2
else
	base_dir=$4
fi
if [[ -z "$5" ]]; then
	log_name=slurm_jobs/runs_output/download_clip_landsat.log
else
	log_name=$5
fi
# BNY: Next 6 lines customized log name to include regions as prefix
log_prefix=${regions//,/_} # BNY: replace commas with underscores when multiple regions specified
log_prefix="${log_prefix:0:30}"  # Limit to first 30 chars when multiple regions specified
log_name=$5
dir="${log_name%/*}"
file="${log_name##*/}"
log_name="${dir}/${log_prefix}_${file}"

# Create the log file if it doesn't yet exist.
if [[ ! -e $log_name ]]; then
	touch $log_name
fi


# Run the main script.
python orthocorrect_netcdf-package.py --glaciers $regions --start_date $start_date --end_date $end_date --base_dir $base_dir --log_name $log_name


# Report to terminal.
squeue --job $SLURM_JOBID
tree -L 2 $base_dir
echo "================================================END================================================="
echo ""

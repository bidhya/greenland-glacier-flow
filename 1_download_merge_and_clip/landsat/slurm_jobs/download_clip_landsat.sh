#!/usr/bin/env bash


#SBATCH --time=2:00:00  # use 200 hours for all 192 regions.
#SBATCH --cpus-per-task=1
#SBATCH --mem=48gb
#SBATCH --job-name=landsat_download_clip
#SBATCH --mail-type=ALL
#SBATCH --mail-user=yadav.111@osu.edu
#SBATCH --output=runs_output/%x_%j.out
#SBATCH --partition=howat,batch


# Change to the folder 1 level up from this shell script.
if [ -n "${SLURM_JOB_ID:-}" ]; then
    bash_file_path=$(scontrol show job "$SLURM_JOB_ID" | awk -F= '/Command=/{print $2}')
else
    bash_file_path=$(realpath $0)
fi
cd $(dirname $bash_file_path)
cd ..

# Activate appropriate conda environment.
eval "$(conda shell.bash hook)"
conda activate glacier_velocity


# Report to terminal.
date; hostname; pwd
echo "===================================================================================================="
echo "Downloading/merging/clipping AWS Landsat data for Greenland"


# Set up parameters from command-line arguments or defaults.
if [[ -z "$1" ]]; then  # Checks if the first command-line argument ($1) is empty (-z means "zero length").
	regions=''
else
	regions=$1
fi
if [[ -z "$2" ]]; then
	start_date='2016-01-01'
else
	start_date=$2
fi
if [[ -z "$3" ]]; then
	end_date='2024-01-01'
else
	end_date=$3
fi
if [[ -z "$4" ]]; then
	base_dir=/fs/project/howat.4-3/howat-data/
else
	base_dir=$4
fi
if [[ -z "$5" ]]; then
	log_name=slurm_jobs/runs_output/download_clip_landsat.log
else
	log_name=$5
fi


# Create the log file if it doesn't yet exist.
if [[ ! -e $log_name ]]; then
	touch $log_name  # TODO: error if logs subfolder doesn't exist
fi


# Run the main script.
python download_clip_landsat.py --regions $regions --date1 $start_date --date2 $end_date --base_dir $base_dir --log_name $log_name



# Report to terminal.
echo "================================================END================================================="
echo ""

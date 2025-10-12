#!/usr/bin/env bash


#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=5
#SBATCH --mem=48gb
#SBATCH --job-name=sentinel2_download_clip_2025
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
#conda activate greenland_glacier_flow_1b
conda activate glacier_velocity

# Report to terminal.
date; hostname; pwd
echo "===================================================================================================="
echo "Download S2 data for Greenland"


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
download_flag=1
post_processing_flag=1
clear_downloads=0
if [[ -z "$4" ]]; then
	base_dir=/fs/project/howat.4-3/howat-data/glacier_flow/sentinel2
else
	base_dir=$4
fi
if [[ -z "$5" ]]; then
	log_name=slurm_jobs/runs_output/download_clip_sentinel2.log
else
	log_name=$5
fi

# # Aside: BNY to download by start and end index of regions
# # start_end_index=151:160
# start_end_index=40:45  # 100 less because inside code we are only selecting from 101 to 192
# log_name="../../control/logs/${start_end_index/:/_}_download_clip_sentinel2.log"  # temporary overwrite log name using start_end_index
# log_name="../../control/logs/download_clip_sentinel2_2025.log"  # temporary overwrite log name for region(s)

# Create the log file if it doesn't yet exist.
if [[ ! -e $log_name ]]; then
	touch $log_name
fi


# Run the main script.
python download_merge_clip_sentinel2.py --regions $regions --date1 $start_date --date2 $end_date --download_flag $download_flag --post_processing_flag $post_processing_flag --clear_downloads $clear_downloads --base_dir $base_dir --log_name $log_name
# python download_merge_clip_sentinel2.py --date1 $start_date --date2 $end_date --download_flag $download_flag --post_processing_flag $post_processing_flag --clear_downloads $clear_downloads --base_dir $base_dir --log_name $log_name --start_end_index $start_end_index

squeue --job $SLURM_JOBID
# Report to terminal.
echo "================================================END================================================="
echo ""

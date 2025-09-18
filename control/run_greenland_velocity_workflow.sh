#!/usr/bin/env bash


# Change to the folder 1 level up from this shell script.
cd $(dirname "$(realpath $0)")
cd ..



# Load the config.
source control/config.sh


# Load in default parameters, then override any that were passed in as arguments.
regions=$REGIONS
start_date=$START_DATE
end_date=$END_DATE
base_dir=$BASE_DIR
which_steps_to_run=$WHICH_STEPS_TO_RUN

while getopts ":r:s:e:b:w:" flag
do
    case "${flag}" in
        r) regions=${OPTARG};;
        s) start_date=${OPTARG};;
	e) end_date=${OPTARG};;
        b) base_dir=${OPTARG};;
	w) which_steps_to_run=${OPTARG};;
    esac
done

# Calculate other date variables.
# run_date=$(date +'%Y%m%d')
run_date=$(date +'%Y%m%d%HH%MM')  # BNY
run_date_no_hyphens="${run_date//-}"
start_date_no_hyphens="${start_date//-}"
end_date_no_hyphens="${end_date//-}"

# Determine the log name.
# log_name=../../control/logs/${run_date_no_hyphens}_greenland_glacier_flow.log
landsat_log=../../control/logs/landsat_download_clip_${run_date_no_hyphens}.log
sentinel2_log=../../control/logs/sentinel_download_clip_${run_date_no_hyphens}.log


# Report to terminal.
date; hostname; pwd
echo "============================ START GREENLAND VELOCITY WORKFLOW ============================="




if [[ " ${which_steps_to_run[*]} " == *" 1a "* ]]; then
    # 1a. Run Landsat download/clip sub-workflow.
	greenland_download_merge_and_clip_landsat_job_id=$(sbatch --parsable 1_download_merge_and_clip/landsat/slurm_jobs/download_clip_landsat.sh $regions $start_date $end_date "${base_dir}/1_download_merge_and_clip/landsat" "$landsat_log")
	current_time=$(date)
	echo "Run Landsat download/clip sub-workflow, job ID: ${greenland_download_merge_and_clip_landsat_job_id}, time: ${current_time}"
fi

if [[ " ${which_steps_to_run[*]} " == *" 1b "* ]]; then
    # 1b. Run Sentinel-2 download/merge/clip sub-workflow.
	greenland_download_merge_and_clip_sentinel2_job_id=$(sbatch --parsable 1_download_merge_and_clip/sentinel2/slurm_jobs/download_merge_clip_sentinel2.sh $regions $start_date $end_date "${base_dir}/1_download_merge_and_clip/sentinel2" "$sentinel2_log")
	current_time=$(date)
	echo "Run Sentinel-2 download/clip sub-workflow, job ID: ${greenland_download_merge_and_clip_sentinel2_job_id}, time: ${current_time}"
fi


# 2. Run SETSM-SDM sub-workflow. (Currently non-functional; this is placeholder logic.)
if [[ " ${which_steps_to_run[*]} " == *" 2 "* ]]; then
	echo "SETSM-SDM sub-workflow not yet automated. Run this step manually. If this step was run in automation by accident, discard any products from downstream steps."
#    if [[ " ${which_steps_to_run[*]} " == *" 1 "* ]]; then
#	    greenland_velocity_job_id=(sbatch --dependency=afterok:${greenland_download_merge_and_clip_landsat_job_id}:${greenland_download_merge_and_clip_sentinel2_job_id} --parsable SLURMFILE_NAME_PLACEHOLDER.sh)
#	else
#	    greenland_velocity_job_id=(sbatch --parsable SLURMFILE_NAME_PLACEHOLDER.sh)
#	fi
#	current_time=$(date)
#	echo "Queue SETSM-SDM sub-workflow, job ID: ${greenland_velocity_job_id}, time: ${current_time}"
fi


# 3. Run orthocorrection/NetCDF-packaging sub-workflow.
if [[ " ${which_steps_to_run[*]} " == *" 3 "* ]]; then
    if [[ " ${which_steps_to_run[*]} " == *" 2 "* ]]; then
	    greenland_orthocorrect_and_netcdf_package_job_id=$(sbatch --dependency=afterok:${greenland_velocity_job_id} --parsable 3_orthocorrect_and_netcdf-package/slurm_jobs/orthocorrect_netcdf-package.sh $regions $start_date_no_hyphens $end_date_no_hyphens "${base_dir}/3_orthocorrect_and_netcdf-package" "../control/logs/${run_date}_slurm_orthocorrect_netcdf-package.log")
	else
	    greenland_orthocorrect_and_netcdf_package_job_id=$(sbatch --parsable 3_orthocorrect_and_netcdf-package/slurm_jobs/orthocorrect_netcdf-package.sh $regions $start_date_no_hyphens $end_date_no_hyphens "${base_dir}/3_orthocorrect_and_netcdf-package" "../control/logs/${run_date}_slurm_orthocorrect_netcdf-package.log")
	fi
	current_time=$(date)
	echo "Queue orthocorrection/NetCDF-packaging sub-workflow, job ID: ${greenland_orthocorrect_and_netcdf_package_job_id}, time: ${current_time}"
fi




# Report to terminal.
echo "======================================END WORKFLOW======================================"
echo ""

#!usr/bin/env python

""" Generate and submit Slurm job for satellite data processing (Sentinel-2 or Landsat)
    - Must run from command line; this script will thus submit the slurm jobs
    - Supports both HPC (SLURM) and local execution modes
    - Can override config.ini values using command line arguments

    Usage examples:
    - python submit_satellite_job.py --satellite sentinel2
    - python submit_satellite_job.py --satellite landsat --regions 134_Arsuk,101_sermiligarssuk
    - python submit_satellite_job.py --satellite landsat --date1 2024-01-01 --date2 2024-12-31 --dry-run true
    - python submit_satellite_job.py --satellite sentinel2 --execution-mode local --date1 2024-10-01 --date2 2024-10-05
    - python submit_satellite_job.py --satellite sentinel2 --memory 64G --runtime 12:00:00 --cores 4
    - python submit_satellite_job.py --config custom_config.ini --satellite sentinel2 --memory 64G --runtime 02:00:00

    Note: For local development, use submit_job.sh wrapper script which handles conda environment activation automatically.
    Direct Python calls require manual environment activation: conda activate glacier_velocity

    Author: B. Yadav. Aug 18, 2025
"""
import os
import logging
import argparse
import subprocess
import configparser
import time
from pathlib import Path
import shutil


# Set up command line argument parser
parser = argparse.ArgumentParser(description='Create and submit SLURM job for satellite data processing (Sentinel-2 or Landsat)')
parser.add_argument('--config', help='Path to configuration file', type=str, default='config.ini')
parser.add_argument('--satellite', help='Satellite type (sentinel2 or landsat)', type=str, choices=['sentinel2', 'landsat'])
parser.add_argument('--regions', help='Regions to process (comma-separated, no spaces)', type=str)
parser.add_argument('--start-end-index', help='Start and end index for batch processing (e.g., 0:48)', type=str)
parser.add_argument('--date1', help='Start date in YYYY-MM-DD format', type=str)
parser.add_argument('--date2', help='End date in YYYY-MM-DD format', type=str)
parser.add_argument('--base-dir', help='Base output directory', type=str)
parser.add_argument('--cores', help='Number of cores to use', type=int)
parser.add_argument('--memory', help='Memory allocation (e.g., 48G)', type=str)
parser.add_argument('--runtime', help='Runtime for the job (e.g., 01:00:00)', type=str)
parser.add_argument('--dry-run', help='Generate job file but do not submit (true/false)', type=str, choices=['true', 'false'], default=None)
parser.add_argument('--email', help='Email for job notifications', type=str)
parser.add_argument('--execution-mode', help='Execution mode: hpc (SLURM), local (direct), auto (detect)', type=str, choices=['hpc', 'local', 'auto'], default='auto')

args = parser.parse_args()

# Get absolute path to current script directory (global variable). We use this to copy script files to Node's $TMPDIR
# Alternatively, could use script_dir to run the python script directly from this location (say on Windows, WSL etc.)
script_dir = Path(__file__).resolve().parent
print(f"Script directory: {script_dir}")


def mkdir_p(folder):
    '''make a (sub) directory (folder) if it doesn't exist'''
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)


def detect_execution_mode():
    """Auto-detect whether we're on HPC or local machine"""
    # Check if we're already in a SLURM job
    if os.getenv('SLURM_JOB_ID'):
        return 'hpc'
    
    # Check if sbatch command is available
    if shutil.which('sbatch'):
        return 'hpc'
    
    # Default to local execution
    return 'local'


def create_bash_job(jobname, regions, start_end_index, date1, date2, base_dir, download_flag, post_processing_flag, clear_downloads, cores, memory, runtime, dry_run, email, log_name, satellite):
    """ Generate and call bash script for either Sentinel-2 or Landsat
        This part is mostly for prototyping and testing on local machine
    """
    logging.info(f'jobname = {jobname}    base_dir = {base_dir}   date1 = {date1}   date2 = {date2}   regions = {regions}   start_end_index = {start_end_index}   satellite = {satellite}\n') 
    job_file = os.path.join(os.getcwd(), f"{jobname}.job")
    print(f"Jobfile: {job_file}")
    with open(job_file, 'w') as fh:
        fh.writelines("#!/usr/bin/env bash\n\n")
        fh.writelines("# Activate appropriate conda environment.\n")
        fh.writelines("eval \"$(conda shell.bash hook)\"\n")
        fh.writelines("conda activate glacier_velocity\n")
        fh.writelines("date; hostname; pwd\n")         # Add host, time, and directory name for later troubleshooting
        fh.writelines("python --version; which python\n")  # Check python version
        fh.writelines("python -c \"for p in ['rioxarray','rasterio','osgeo','geopandas','xarray']: print(f'\\t{p}: {__import__(p).__version__}')\"\n")  # Check key package versions
        fh.writelines("echo ========================================================\n")
        fh.writelines("\n")
        # fh.writelines("cd $TMPDIR\n")
        # upto this point, it can be common to other jobs as well
        # fh.writelines(f"mkdir -p $out_folder\n")  # creating directly here using python code.  

        fh.writelines(f"cp -r {script_dir}/1_download_merge_and_clip .\n")
        fh.writelines("cd 1_download_merge_and_clip\n")  # required because ancillary folder located here
        
        # Determine region selection method (mutually exclusive: either specific regions OR batch index range)
        region_param = f"--start_end_index {start_end_index}" if start_end_index else f"--regions {regions}"
        
        # Choose the appropriate script and parameters based on satellite type
        if satellite.lower() == "sentinel2":
            fh.writelines(f"python sentinel2/download_merge_clip_sentinel2.py {region_param} --date1 {date1} --date2 {date2} --download_flag {download_flag} --post_processing_flag {post_processing_flag} --clear_downloads {clear_downloads} --base_dir {base_dir} --log_name {log_name}\n")
        elif satellite.lower() == "landsat":
            fh.writelines(f"python landsat/download_clip_landsat.py {region_param} --date1 {date1} --date2 {date2} --base_dir {base_dir} --log_name {log_name}\n")
        else:
            raise ValueError(f"Unsupported satellite type: {satellite}. Supported types are 'sentinel2' and 'landsat'.")
            
        # fh.writelines("tree -L 2 \n")  # $out_folder
        fh.writelines(f"echo Check outputs at base_dir = {base_dir}\n")
        fh.writelines("echo Finished Slurm job \n")
    
    # Submit the job (unless dry_run is enabled)
    if dry_run:
        print(f"DRY RUN: Job file created at {job_file} but not submitted to SLURM")
        logging.info(f"DRY RUN: Job file created but not submitted")
    else:
        print(f"Submitting job: {job_file}")
        subprocess.run(['bash', job_file], check=True)  # TODO: check best practice


def create_slurm_job(jobname, regions, start_end_index, date1, date2, base_dir, download_flag, post_processing_flag, clear_downloads, cores, memory, runtime, dry_run, email, log_name, satellite):
    """ Generate SLURM job file and submit it for either Sentinel-2 or Landsat """
    logging.info(f'jobname = {jobname}    base_dir = {base_dir}   date1 = {date1}   date2 = {date2}   regions = {regions}   start_end_index = {start_end_index}   satellite = {satellite}\n') 
    job_file = os.path.join(os.getcwd(), f"{jobname}.job")
    print(f"Jobfile: {job_file}")

    # lizard_data = os.path.join(data_dir, lizard)
    # Create lizard directories
    # mkdir_p(lizard_data)
    with open(job_file, 'w') as fh:
        fh.writelines("#!/usr/bin/env bash\n\n")
        # fh.writelines(f"#SBATCH --partition=howat-ice\n")  # for Unity  eg: howat-ice
        fh.writelines(f"#SBATCH --job-name={jobname}\n")
        fh.writelines("#SBATCH --output=OUT/%x_%j.out\n")  # On Unity, OUT directory will be created if it doesn't exist 
        fh.writelines(f"#SBATCH --time={runtime}\n")
        fh.writelines(f"#SBATCH --nodes=1 --ntasks={cores}\n")        
        # fh.writelines(f"#SBATCH --mem-per-cpu={memory}\n")
        fh.writelines(f"#SBATCH --mem={memory}\n")
        fh.writelines("#SBATCH --mail-type=ALL\n")
        fh.writelines(f"#SBATCH --mail-user={email}\n")
        fh.writelines("#SBATCH --partition=howat,batch\n")
        # fh.writelines("#SBATCH --exclude=u060,u061,u062,u063\n")
        # fh.writelines("#SBATCH --begin=now+0minutes\n")
        fh.writelines("\n")
        fh.writelines("# Activate appropriate conda environment.\n")
        fh.writelines("eval \"$(conda shell.bash hook)\"\n")
        fh.writelines("conda activate glacier_velocity\n")
        fh.writelines("date; hostname; pwd\n")         # Add host, time, and directory name for later troubleshooting
        fh.writelines("python --version; which python\n")  # Check python version
        fh.writelines("python -c \"for p in ['rioxarray','rasterio','osgeo','geopandas','xarray']: print(f'\\t{p}: {__import__(p).__version__}')\"\n")  # Check key package versions
        # # first thing we do when the job starts is to "change directory to the place where the job was submitted from".
        fh.writelines("echo $SLURM_SUBMIT_DIR\n")
        fh.writelines("echo ========================================================\n")
        fh.writelines("\n")
        fh.writelines("cd $TMPDIR\n")
        # upto this point, it can be common to other jobs as well
        # fh.writelines(f"mkdir -p $out_folder\n")  # creating directly here using python code.  

        fh.writelines(f"cp -r {script_dir}/1_download_merge_and_clip .\n")
        fh.writelines("cd 1_download_merge_and_clip\n")
        
        # Determine region selection method (mutually exclusive: either specific regions OR batch index range)
        region_param = f"--start_end_index {start_end_index}" if start_end_index else f"--regions {regions}"
        
        # Choose the appropriate script and parameters based on satellite type
        if satellite.lower() == "sentinel2":
            fh.writelines(f"python sentinel2/download_merge_clip_sentinel2.py {region_param} --date1 {date1} --date2 {date2} --download_flag {download_flag} --post_processing_flag {post_processing_flag} --clear_downloads {clear_downloads} --base_dir {base_dir} --log_name {log_name}\n")
        elif satellite.lower() == "landsat":
            fh.writelines(f"python landsat/download_clip_landsat.py {region_param} --date1 {date1} --date2 {date2} --base_dir {base_dir} --log_name {log_name}\n")
        else:
            raise ValueError(f"Unsupported satellite type: {satellite}. Supported types are 'sentinel2' and 'landsat'.")
            
        # fh.writelines("tree -L 2 $TMPDIR\n")  # $out_folder
        fh.writelines(f"echo Check outputs at base_dir = {base_dir}\n")
        fh.writelines("echo Finished Slurm job \n")
    
    # Submit the job (unless dry_run is enabled)
    if dry_run:
        print(f"DRY RUN: Job file created at {job_file} but not submitted to SLURM")
        logging.info(f"DRY RUN: Job file created but not submitted")
    else:
        print(f"Submitting job: {job_file}")
        subprocess.run(['sbatch', job_file], check=True)  # This is more robust and recommended


def load_config(config_file="config.ini", cli_args=None):
    """Load and parse configuration from INI file with optional CLI overrides.
    
    Args:
        config_file: Path to the INI configuration file
        cli_args: Parsed command line arguments to override config values
    
    Returns:
        dict: Dictionary containing all configuration values
    """
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # Parse configuration values from sections
    config_dict = {
        # Region settings
        'regions': config.get("REGIONS", "regions"),
        'start_end_index': config.get("REGIONS", "start_end_index"),
        
        # Date settings
        'date1': config.get("DATES", "date1"),
        'date2': config.get("DATES", "date2"),
        
        # Path settings
        'base_dir': config.get("PATHS", "base_dir"),
        'local_base_dir': config.get("PATHS", "local_base_dir", fallback=None),

        # Processing flags
        'download_flag': config.getint("FLAGS", "download_flag", fallback=1),
        'post_processing_flag': config.getint("FLAGS", "post_processing_flag", fallback=1),
        'clear_downloads': config.getint("FLAGS", "clear_downloads", fallback=0),
        
        # General settings
        'cores': config.getint("SETTINGS", "cores", fallback=1),
        'memory': config.get("SETTINGS", "memory", fallback="48G"),
        'runtime': config.get("SETTINGS", "runtime", fallback="01:00:00"),
        'log_name': config.get("SETTINGS", "log_name"),
        'email': config.get("SETTINGS", "email"),
        'satellite': config.get("SETTINGS", "satellite"),
        # 'which_steps_to_run': config.get("SETTINGS", "which_steps_to_run"),
        'dry_run': config.getboolean("SETTINGS", "dry_run", fallback=False),
        'execution_mode': config.get("SETTINGS", "execution_mode", fallback="auto")
    }
    
    # Override with command line arguments if provided
    if cli_args:
        if cli_args.satellite:
            config_dict['satellite'] = cli_args.satellite
        if cli_args.regions:
            config_dict['regions'] = cli_args.regions
        if cli_args.start_end_index:
            config_dict['start_end_index'] = cli_args.start_end_index
        if cli_args.date1:
            config_dict['date1'] = cli_args.date1
        if cli_args.date2:
            config_dict['date2'] = cli_args.date2
        if cli_args.base_dir:
            config_dict['base_dir'] = cli_args.base_dir
        if cli_args.cores:
            config_dict['cores'] = cli_args.cores
        if cli_args.memory:
            config_dict['memory'] = cli_args.memory
        if cli_args.runtime:
            config_dict['runtime'] = cli_args.runtime
        if cli_args.email:
            config_dict['email'] = cli_args.email
        if cli_args.dry_run is not None:
            config_dict['dry_run'] = cli_args.dry_run.lower() == 'true'
        if cli_args.execution_mode:
            config_dict['execution_mode'] = cli_args.execution_mode
    
    return config_dict


def main():
    """ Main script to parameterize, generate, and dispatch slurm jobs
        Make this suite self-sufficient so everything can be controled from 
        here rather than submitting from the command line
        ie, this script needs to be updated everything the job is run 
        --cores 1 --memory 16gb --runtime 36:00:00 --jobname s2_download

        NB: 4 nodes (48 cores/192GB (187 max allowed)); 2 nodes (40 cores/192GB); and 4 nodes (26 cores/96GB)
        In the new workflow, ~2.5GB per core seems enough; check further

    """
    # Load configuration
    # Give path to config file relative to script location or from CLI args
    config_file = args.config if args.config != 'config.ini' else script_dir / args.config
    cfg = load_config(config_file, args)
    # Extract commonly used values
    regions = cfg['regions']
    date1 = cfg['date1']
    date2 = cfg['date2']
    root_dir = cfg['base_dir']
    satellite = cfg['satellite']
    start_end_index = cfg['start_end_index']
    download_flag = cfg['download_flag']
    post_processing_flag = cfg['post_processing_flag']
    clear_downloads = cfg['clear_downloads']
    cores = cfg['cores']
    log_name = cfg['log_name']
    email = cfg['email']
    memory = cfg['memory']
    runtime = cfg['runtime']
    dry_run = cfg['dry_run']
    execution_mode = cfg['execution_mode']
    
    # Auto-append batch range to log name if using start_end_index
    if start_end_index:
        base_log = log_name.rsplit('.', 1)[0]
        ext = log_name.rsplit('.', 1)[1] if '.' in log_name else 'log'
        log_name = f"{base_log}_{start_end_index.replace(':', '_')}.{ext}"

    # Determine execution mode (ie running on HPC or local machine)
    if execution_mode == 'auto':
        execution_mode = detect_execution_mode()
    if execution_mode == 'local' and cfg['local_base_dir']:
        root_dir = cfg['local_base_dir']  # Use local_base_dir from config if available


    base_dir = f"{root_dir}/1_download_merge_and_clip/{satellite}"  # This is where files will be downloaded, merged, clipped, and saved
    mkdir_p(f"{base_dir}")  # Create base directory if it doesn't exist

    # mkdir_p(f"{root_dir}")  # Create parent base directory if it doesn't exist to hold all outputs
    slurm_dir = f"{root_dir}/slurm_jobs/{satellite}"  # Path(root_dir) / "slurm_jobs"
    mkdir_p(slurm_dir)  # Create slurm_jobs directory if it doesn't exist to hold all slurm related job, outputs, logs
    log_dir = Path(slurm_dir) / "logs"
    mkdir_p(log_dir)  # Create log directory if it doesn't exist
    os.chdir(slurm_dir)  # Change to slurm_jobs directory to hold all slurm related job, outputs, logs
    # Path(log_name).touch()

    # Create job name using date strings from config
    jobname = f"{satellite.lower()}_{date1.replace('-', '')}"  # _{date2.replace('-', '')}
    
    # Auto-append batch range to job name if using start_end_index
    if start_end_index:
        jobname = f"{jobname}_{start_end_index.replace(':', '_')}"
    
    if len(jobname) > 50:
        jobname = jobname[:50]  # Truncate to first 50 characters to avoid overly long job names

    
    # Set up logging using current YMDHM format.
    # logfile_prefix = datetime.now().strftime("%Y%m%d")  # ("%Y%m%d_%H")
    # logging.basicConfig(filename=f'slurm_job_submission_{logfile_prefix}.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')
    logging.basicConfig(filename=f'slurm_job_submission.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')
    logging.info('--------------------------------------Job Creation/Submission info----------------------------------------------')
    if execution_mode == 'hpc':
        logging.info("Execution mode: HPC (SLURM detected)")
        create_slurm_job(jobname=jobname, regions=regions, start_end_index=start_end_index, date1=date1, date2=date2,
                         base_dir=base_dir, download_flag=download_flag, post_processing_flag=post_processing_flag, clear_downloads=clear_downloads,
                         cores=cores, memory=memory, runtime=runtime, dry_run=dry_run, email=email, log_name=f"{log_dir}/{log_name}", satellite=satellite)
    elif execution_mode == 'local':
        create_bash_job(jobname=jobname, regions=regions, start_end_index=start_end_index, date1=date1, date2=date2,
                        base_dir=base_dir, download_flag=download_flag, post_processing_flag=post_processing_flag, clear_downloads=clear_downloads,
                        cores=cores, memory=memory, runtime=runtime, dry_run=dry_run, email=email, log_name=f"{log_dir}/{log_name}", satellite=satellite)
        logging.info("Execution mode: Local (direct execution)")
    else:
        raise ValueError(f"Unsupported execution mode: {execution_mode}. Supported modes are 'auto', 'hpc', and 'local'.")

    # For landsat,
    # python download_clip_landsat.py --regions $regions --date1 $date1 --date2 $date2 --base_dir $base_dir --log_name $log_name

    
    time.sleep(1)  # sleep for a second to avoid job submission too fast
    logging.info("Job submission complete\n")


if __name__ == "__main__":
    """ Call the main function """
    main()

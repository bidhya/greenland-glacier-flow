#!usr/bin/env python


###################################################################################################
# Imports.
###################################################################################################

# Import basic python resources.
import argparse, os, sys, multiprocessing

# Import config values.
sys.path.append(".")
from lib.config import VELDIR, OUTDIRNAME, WD, START_DATE, END_DATE
from lib.utility import try_command_with_log_and_discontinue_on_error, try_command_with_log_and_continue_on_error
from lib.log import setUpBasicLoggingConfig, log_to_stdout_and_file




###################################################################################################
# Parse command-line arguments.
###################################################################################################

# Parse command-line arguments.
parser = argparse.ArgumentParser(description='Orthocorrect and NetCDF-package glacier velocity data.')
parser.add_argument(
    '--glaciers',
    help='List of glacier regions to process, separated by commas (no spaces)',
    type=str,
    default=""
)
parser.add_argument(
    '--start_date',
    help='First day of data to process, in YYYYMMDD format',
    type=str
)
parser.add_argument(
    '--end_date',
    help='Last day of data to process, in YYYYMMDD format',
    type=str
)
parser.add_argument(
    '--base_dir',
    help='Base folder for processing',
    type=str
)
parser.add_argument(
    '--log_name',
    help='Name of log file',
    type=str,
    default='sentinel_glacier.log'
)
args = parser.parse_args()
glaciers = args.glaciers.split(",")
if not glaciers:
    glaciers = os.listdir(VELDIR) # By default, glaciers list is everything in velocities directory.
    glaciers = [x for x in glaciers if "." not in x]
start_date = args.start_date
if not start_date:
    start_date = START_DATE
end_date = args.end_date
if not end_date:
    end_date = END_DATE  # changed from start_date to end_date. also done by Gravina (see Nov 24, 2025 commit).
base_dir = args.base_dir
if not base_dir:
    base_dir = WD
log_name = args.log_name


###################################################################################################
# Set up logging.
###################################################################################################

# Set up basic logging configuration.
setUpBasicLoggingConfig(log_name, f"Attempting orthocorrection and NetCDF packaging of Greenland data.")



###################################################################################################
# Run the workflow.
###################################################################################################

# Log info about the glacier regions list.
log_to_stdout_and_file(f"Glaciers list to process: {glaciers}")


# Define the workflow.
def correct_glacier_velocity(glacier):
    """
    Run processing chain scripts for a given glacier ID.
    """

    script_infos = [
        {
            "filename": "1_match_to_orbits.py",
            "description": f"MATCHING ORBITS",
            "graceful_failure": False
        },
        {
            "filename": "2_get_orbital_average_offset.py",
            "description": f"GENERATING OFFSETS",
            "graceful_failure": False
        },
        {
            "filename": "3_correct_fields.py",
            "description": f"CORRECTING FIELDS",
            "graceful_failure": False
        },
        {
            "filename": "4a_netcdf_stack_sentinel.py",
            "description": f"PRODUCING SENTINEL-2 NETCDF DATACUBES",
            "graceful_failure": True
        },
        {
            "filename": "4b_netcdf_stack_landsat.py",
            "description": f"PRODUCING LANDSAT NETCDF DATACUBES",
            "graceful_failure": True
        },
        {
            "filename": "4c_netcdf_stack_landsat_sentinel_combined.py",
            "description": f"COMBINING SENTINEL-2 AND LANDSAT NETCDF DATACUBES",
            "graceful_failure": False
        }
    ]

    # Don't rerun if glacier's directory already exists.
    # FIXED 2025-11-26: Changed from WD to base_dir to match actual output location
    # Previous bug: WD was overridden by CLI --base_dir, causing existence check to use wrong path
    # This caused inconsistent behavior where script would sometimes skip, sometimes not    
    # outdir_container = os.path.join(WD, OUTDIRNAME, glacier)  # Old code (commented for reference)
    outdir_container = os.path.join(base_dir, OUTDIRNAME, glacier)  # BNY's fix on Nov 26, 2025
    if not os.path.exists(outdir_container):

        # Determine if processing needs to be done in two parts (splitting around the 2021 DEM
        # switch).
        split_processing_around_dem_switch = True if (
            int(start_date) < 20210823
            and int(end_date) >= 20210823
        ) else False
        if (split_processing_around_dem_switch):
            log_to_stdout_and_file("Dates span 23 Aug 2021, when the DEM used to generate input files was switched. Splitting processing in two around this date.")


        log_to_stdout_and_file(f"\n\n\n\nPROCESSING FIELDS FOR {glacier}\n\n")
        
        # For each script in the workflow, run it for this glacier region.
        error_while_running_scripts = False
        for script_info in script_infos:

            # Get date bounds and base directories to use (this is usually just start_date,
            # end_date, and base_dir, but runs that span the 23 Aug 2021 DEM switch in the input
            # imagery must be run separately for the parts of 2021 before and starting with that
            # date).
            date_bounds_and_base_dirs_to_use_for_this_script = (
                # If the supplied date bounds span the DEM-switch date, split into two sets of
                # date-bounds divided by that date, with appropriately labeled base directories.
                [
                    {"start_date": start_date, "end_date": "20210822", "base_dir": f"{base_dir}_pre_dem_switch"},
                    {"start_date": "20210823", "end_date": end_date, "base_dir": f"{base_dir}_post_dem_switch"}
                ] if (split_processing_around_dem_switch)

                # Otherwise just use the supplied date bounds and base directory.
                else [
                    {"start_date": start_date, "end_date": end_date, "base_dir": base_dir}
                ]
            )

            # For each set of date bounds,
            for date_bounds_and_base_dirs in date_bounds_and_base_dirs_to_use_for_this_script:
                log_to_stdout_and_file(f"\n\n\n\n{script_info['description']} FOR {glacier} FROM {date_bounds_and_base_dirs['start_date']} TO {date_bounds_and_base_dirs['end_date']}\n\n")

                # Run this script.
                if script_info.get("graceful_failure", False):
                    exit_code = try_command_with_log_and_continue_on_error(
                        glacier,
                        date_bounds_and_base_dirs["start_date"],
                        date_bounds_and_base_dirs["end_date"],
                        date_bounds_and_base_dirs["base_dir"],
                        log_name,
                        f"python processing_chain/{script_info['filename']}"
                    )
                    # For graceful failures, don't stop the workflow
                    if exit_code != 0:
                        log_to_stdout_and_file(f"Step {script_info['filename']} failed but continuing with available data sources.")
                else:
                    exit_code = try_command_with_log_and_discontinue_on_error(
                        glacier,
                        date_bounds_and_base_dirs["start_date"],
                        date_bounds_and_base_dirs["end_date"],
                        date_bounds_and_base_dirs["base_dir"],
                        log_name,
                        f"python processing_chain/{script_info['filename']}"
                    )
                    if exit_code != 0:
                        error_while_running_scripts = True
                        break

            if error_while_running_scripts:
                log_to_stdout_and_file(f"Error encountered on one of the scripts in the sequence. Stopping sequence. Inspect logs for details.")
                break
            
        # If the date bounds span the DEM-switch date,
        if (split_processing_around_dem_switch and not error_while_running_scripts ):
            log_to_stdout_and_file(f"\n\n\n\nCOMBINING PRE- AND POST-DEM-SWITCH NETCDF DATACUBES FOR {glacier} FROM {start_date} TO {end_date}\n\n")

            # Run the final script to combine the separate pre- and post-switch 2021 NetCDFs
            # into a single output NetCDF.
            try_command_with_log_and_discontinue_on_error(
                glacier,
                start_date,
                end_date,
                base_dir,
                log_name,
                f"python processing_chain/4d_netcdf_stack_pre_post_dem_switch.py"
            )


# Create a processing pool with 4 parallel workers, refreshing each worker after 1 task, and run
# the workflow for all glaciers in the list.
# nprocs = 4
# pool = multiprocessing.Pool(nprocs, maxtasksperchild=1)
# results = pool.map(correct_glacier_velocity, glaciers, 1)
# pool.close()

# Process glaciers sequentially instead of in parallel
# for glacier in glaciers:
glacier = glaciers[0]  # because glaciers is currently a list
correct_glacier_velocity(glacier)


log_to_stdout_and_file("\n\n-----------------------END LOG-----------------------\n")
log_to_stdout_and_file("Finished.")

#!/usr/bin/env bash



# List of glacier regions to process. Should be comma-separated with no spaces.
REGIONS='001_alison'

# Start and end dates.
START_DATE='2021-01-01'
END_DATE='2021-12-31' # $(date +'%Y-%m-%d') # To use current date.

# Base directory for output data.
BASE_DIR='/fs/project/howat.4/gravina.2/greenland_glacier_flow'

# Which steps to run. For example, "1 2 3" will run all 3 steps.
WHICH_STEPS_TO_RUN='3'
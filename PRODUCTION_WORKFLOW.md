# Production Workflow Guide - HPC Batch Processing

**Last Updated**: December 21, 2025  
**Status**: ✅ Validated in production with 75 Sentinel-2 + 100 Landsat glaciers (2025-01-01 to 2025-12-31)

## Quick Start - Running Batch Jobs on HPC

### 1. Update Configuration (config.ini)

```ini
[DATES]
date1 = 2025-01-01    # Update to desired start date
date2 = 2025-12-31    # Update to desired end date

[PATHS]
base_dir = /fs/project/howat.4-3/greenland_glacier_flow  # Verify path

[SETTINGS]
email = yadav.111@osu.edu  # Update if needed
```

**Note**: Leave `regions =` and `start_end_index =` empty in config.ini - specify on command line for batch processing.

### 2. Adjust Resource Allocation (Optional)

Edit `submit_satellite_job.py` default values if needed:

```python
# Line 334: Default runtime
runtime = args.runtime if args.runtime else "25:00:00"  # Adjust hours

# Line 335: Default memory  
memory = args.memory if args.memory else "60G"  # Adjust GB
```

Or override via command line: `--runtime 12:00:00 --memory 48G`

### 3. Run Batch Jobs

**Sync latest code to HPC first:**
```bash
cd ~/Github/greenland-glacier-flow
git pull origin develop
```

**Execute batch processing:**

#### Sentinel-2 (3 batches × 25 glaciers = 75 total)
```bash
./submit_job.sh --satellite sentinel2 --start-end-index 0:25
./submit_job.sh --satellite sentinel2 --start-end-index 25:50
./submit_job.sh --satellite sentinel2 --start-end-index 50:75
```

#### Landsat (faster, can process more per batch)
```bash
./submit_job.sh --satellite landsat --start-end-index 0:100
```

#### Process All 192 Glaciers (4 batches)
```bash
# Sentinel-2
./submit_job.sh --satellite sentinel2 --start-end-index 0:48
./submit_job.sh --satellite sentinel2 --start-end-index 48:96
./submit_job.sh --satellite sentinel2 --start-end-index 96:144
./submit_job.sh --satellite sentinel2 --start-end-index 144:192

# Landsat
./submit_job.sh --satellite landsat --start-end-index 0:48
./submit_job.sh --satellite landsat --start-end-index 48:96
./submit_job.sh --satellite landsat --start-end-index 96:144
./submit_job.sh --satellite landsat --start-end-index 144:192
```

## Key Features

### Automatic Log File Naming
- Each batch gets unique log: `satellite_glacier_0-25.log`, `satellite_glacier_25-50.log`, etc.
- No manual log naming needed - automatically appended based on `--start-end-index`
- Prevents concurrent job log conflicts

### Alphabetical Region Sorting
- Both Sentinel-2 and Landsat use identical alphabetical sorting
- Same index range = same glaciers across both satellites
- Predictable, reproducible batching

### Batch Size Guidelines (Full Year Processing)
- **Sentinel-2**: 25-50 glaciers per batch (more resource intensive)
- **Landsat**: 50-100 glaciers per batch (more efficient)
- **Test runs**: Use 3-5 glaciers with 5-10 day date range first

## Output Structure

```
/fs/project/howat.4-3/greenland_glacier_flow/
└── 1_download_merge_and_clip/
    ├── sentinel2/
    │   └── <region_name>/      # Region-specific processing directory
    │       ├── download/        # Raw MGRS tiles (intermediate)
    │       ├── clipped/         # Clipped scenes → Used by Step 2
    │       ├── metadata/        # Processing metadata → Used by Step 3
    │       └── template/        # Reference templates → Used by Steps 2 & 3
    └── landsat/
        ├── <region_name>/       # Clipped Landsat scenes → Used by Step 2
        └── _reference/          # STAC metadata and templates → Used by Steps 2 & 3
```

## Monitoring Jobs

```bash
# Check job status
squeue -u $USER

# View log output (real-time)
tail -f /path/to/greenland_glacier_flow/slurm_jobs/sentinel2/logs/satellite_glacier_0-25.log

# Check SLURM output files
ls -lh OUT/sentinel2_*.out
```

## Validation Checklist

Before running full production:

- [ ] Updated `date1` and `date2` in config.ini
- [ ] Verified `base_dir` path exists and has space
- [ ] Confirmed email address is correct
- [ ] Pulled latest code: `git pull origin develop`
- [ ] Tested with small batch (e.g., `--start-end-index 0:3`)
- [ ] Verified log files are being created with unique names
- [ ] Checked output directories are populating

## December 21, 2025 Production Run

**Successfully Executed:**
- 3 Sentinel-2 batches: 0:25, 25:50, 50:75 (75 glaciers total)
- 1 Landsat batch: 0:100 (100 glaciers total)
- Date range: 2025-01-01 to 2025-12-31 (full year)
- Runtime: 25 hours
- Memory: 60 GB
- Status: All jobs running successfully with data being generated

**Log files created:**
- `satellite_glacier_0-25.log`
- `satellite_glacier_25-50.log`
- `satellite_glacier_50-75.log`
- `satellite_glacier_0-100.log`

## Troubleshooting

### Error: "No option 'regions' in section: 'REGIONS'"
**Solution**: Ensure `regions =` line exists in config.ini (can be empty)

### Jobs not submitting
- Verify on HPC: `which sbatch` should show path
- Check SLURM partition availability
- Confirm conda environment: `conda activate glacier_velocity`

### Out of memory errors
- Increase memory: `--memory 80G` or `--memory 120G`
- Reduce batch size (fewer glaciers per job)
- Adjust default in line 335 of submit_satellite_job.py

### Jobs timing out
- Increase runtime: `--runtime 36:00:00`
- Adjust default in line 334 of submit_satellite_job.py
- Consider splitting into smaller batches

## Resource Requirements (Full Year 2025)

| Satellite | Glaciers/Batch | Memory | Runtime | Output Size |
|-----------|----------------|--------|---------|-------------|
| Sentinel-2 | 25 | 60 GB | 25 hours | ~50-100 GB/glacier |
| Landsat | 100 | 60 GB | 25 hours | ~1-5 GB/glacier |

**Storage Planning**: 
- 192 Sentinel-2 glaciers × 75 GB avg = **~14 TB**
- 192 Landsat glaciers × 3 GB avg = **~576 GB**

## Quick Reference

```bash
# Minimal command (uses config.ini for everything)
./submit_job.sh --satellite sentinel2 --start-end-index 0:25

# Override dates (ignore config.ini dates)
./submit_job.sh --satellite landsat --start-end-index 0:100 \
  --date1 2024-01-01 --date2 2024-12-31

# Override resources
./submit_job.sh --satellite sentinel2 --start-end-index 0:25 \
  --memory 80G --runtime 36:00:00

# Dry-run (test without submitting)
./submit_job.sh --satellite sentinel2 --start-end-index 0:5 --dry-run true
```

## Related Documentation

- [README.md](README.md) - Project overview and Step 1 workflow details
- [AGENTS.md](AGENTS.md) - Development notes and architecture decisions
- [CHANGELOG.md](CHANGELOG.md) - All notable changes and feature additions
- [config.ini](config.ini) - Configuration file (single source of truth)

## Future Improvements

- [ ] Dynamic resource allocation based on region size
- [ ] Automated retry logic for failed regions
- [ ] Post-processing data quality checks
- [ ] Automated sync to backup/archive storage
- [ ] Email summary reports with statistics

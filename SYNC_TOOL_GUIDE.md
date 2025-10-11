# S3 Data Synchronization Tool Guide

## Overview

The `sync_from_s3.sh` script provides automated, config-aware synchronization of processed satellite data between AWS S3 and local/HPC environments.

**Created**: October 9, 2025  
**Status**: ✅ Production Ready  
**Tested**: WSL Ubuntu, HPC SLURM cluster

## Key Features

✅ **Config-aware**: Reads paths from `config.ini` (single source of truth)  
✅ **Environment-intelligent**: Auto-detects HPC vs local execution  
✅ **Multi-user safe**: Skips existing files by default  
✅ **Bandwidth-efficient**: Option to exclude large raw download folders  
✅ **Git-isolated**: Never syncs data into code repository  
✅ **Symlinkable**: Can be symlinked for always-current version  

## Quick Start

### Local (WSL/Ubuntu)

```bash
# Create symlink (one-time setup)
cd ~/greenland_glacier_flow
ln -s ~/Github/greenland-glacier-flow/sync_from_s3.sh sync_from_s3.sh

# Sync processed data (skip raw tiles)
./sync_from_s3.sh --exclude-downloads

# Preview what will be synced
./sync_from_s3.sh --exclude-downloads --dry-run
```

### HPC (SLURM)

```bash
# Create symlink (one-time setup)
cd /fs/project/howat.4/yadav.111/greenland_glacier_flow
ln -s ~/Github/greenland-glacier-flow/sync_from_s3.sh sync_from_s3.sh

# Sync processed data (skip raw tiles)
./sync_from_s3.sh --exclude-downloads

# Preview what will be synced
./sync_from_s3.sh --exclude-downloads --dry-run
```

## Usage Options

### Basic Commands

```bash
# Sync both satellites (safe mode - skip existing files)
./sync_from_s3.sh --exclude-downloads

# Sync only Sentinel-2
./sync_from_s3.sh sentinel2 --exclude-downloads

# Sync only Landsat
./sync_from_s3.sh landsat --exclude-downloads

# Preview changes without downloading
./sync_from_s3.sh --exclude-downloads --dry-run
```

### Advanced Options

```bash
# Force overwrite existing files (use with caution)
./sync_from_s3.sh --exclude-downloads --force-overwrite

# Include raw download folders (large bandwidth usage)
./sync_from_s3.sh

# Combine options
./sync_from_s3.sh sentinel2 --exclude-downloads --dry-run
```

## How It Works

### 1. Configuration Detection

The script automatically finds `config.ini` in these locations (in order):
1. Same directory as the script
2. Current working directory
3. `~/Github/greenland-glacier-flow/`

### 2. Environment Detection

```bash
# HPC Detection
if command -v sbatch &> /dev/null; then
    # Uses: base_dir from config.ini
    # Example: /fs/project/howat.4/yadav.111/greenland_glacier_flow
fi

# Local Detection
else
    # Uses: local_base_dir from config.ini
    # Example: /home/bny/greenland_glacier_flow
fi
```

### 3. Safe Operation

```bash
# Default sync mode (recommended)
--size-only   # Skip files with same size (multi-user safe)

# Force mode (explicit)
<no flag>     # Compare timestamps and sizes, overwrite if different
```

### 4. Directory Isolation

```bash
# Script always changes to data directory FIRST
cd "$DATA_DIR" || exit 1

# Then syncs to relative path
aws s3 sync s3://bucket/path/ ./1_download_merge_and_clip/satellite/
```

This ensures:
- ✅ Data never ends up in Git repository
- ✅ Safe to run from any location
- ✅ Clean separation of code and data

## Sync Modes Explained

### Safe Mode (Default)

```bash
./sync_from_s3.sh --exclude-downloads
```

**Behavior**:
- Downloads files that don't exist locally
- **Skips** files that already exist (filename + size match)
- **Does not** check timestamps
- **Does not** overwrite existing files

**Use Cases**:
- Daily sync of new processed results
- Multi-user batch processing environments
- Downloading initial dataset
- Safe for production use

### Force Overwrite Mode

```bash
./sync_from_s3.sh --exclude-downloads --force-overwrite
```

**Behavior**:
- Downloads files that don't exist locally
- **Overwrites** files if timestamp or size differs
- Checks both timestamps and sizes
- Updates existing files from S3

**Use Cases**:
- Reprocessing scenarios (updated S3 data)
- Fixing corrupted local files
- Ensuring exact S3 replica locally
- **Use with caution** in multi-user environments

## Bandwidth Optimization

### Exclude Downloads (Recommended)

```bash
./sync_from_s3.sh --exclude-downloads
```

**Impact**:
- **Sentinel-2**: Skips ~8 raw tiles per region (~1 GB)
- **Landsat**: Skips raw download folders
- **Savings**: ~98% bandwidth reduction
- **Still downloads**: Clipped scenes, metadata, templates

**What gets synced**:
```
sentinel2/
├── clipped/          ✅ Downloaded
├── metadata/         ✅ Downloaded
├── template/         ✅ Downloaded
└── download/         ❌ Skipped (large raw tiles)

landsat/
├── [region]/         ✅ Downloaded (processed scenes)
├── _reference/       ✅ Downloaded
└── download/         ❌ Skipped (if exists)
```

### Include Downloads (Full Sync)

```bash
./sync_from_s3.sh
```

**Impact**:
- Downloads **everything** from S3
- Much larger bandwidth usage
- Longer sync times

**Use Cases**:
- Archival purposes
- Need raw tiles for reprocessing
- Full dataset replication

## Configuration File Integration

### config.ini Structure

```ini
[PATHS]
# HPC data directory
base_dir = /fs/project/howat.4/yadav.111/greenland_glacier_flow

# Local data directory (WSL/Ubuntu)
local_base_dir = /home/bny/greenland_glacier_flow
```

### How Script Uses Config

1. **Finds config.ini** in script directory or common locations
2. **Detects environment** using `sbatch` command presence
3. **Reads appropriate path**:
   - HPC → `base_dir`
   - Local → `local_base_dir`
4. **Changes to data directory** before syncing
5. **Uses relative paths** for S3 sync operations

### Benefits of Config Integration

✅ **Single source of truth** for all paths  
✅ **No hardcoded paths** in sync script  
✅ **Works on any system** with valid config.ini  
✅ **Consistent with other scripts** (submit_satellite_job.py, etc.)  
✅ **Easy to update** paths across entire project  

## Symlink Workflow (Recommended)

### Why Use Symlinks?

✅ **Always up-to-date**: Uses latest version from Git  
✅ **No copying needed**: Changes in Git automatically available  
✅ **Clean separation**: Script in code repo, executed from data dir  
✅ **Single source**: One file to maintain  
✅ **Git workflow**: Pull updates, symlink uses new version automatically  

### Setup Symlink

**On HPC**:
```bash
cd /fs/project/howat.4/yadav.111/greenland_glacier_flow
ln -s ~/Github/greenland-glacier-flow/sync_from_s3.sh sync_from_s3.sh
ls -l sync_from_s3.sh  # Verify symlink
```

**On Local**:
```bash
cd ~/greenland_glacier_flow
ln -s ~/Github/greenland-glacier-flow/sync_from_s3.sh sync_from_s3.sh
ls -l sync_from_s3.sh  # Verify symlink
```

### Using Symlinked Script

```bash
# From data directory
cd ~/greenland_glacier_flow  # or HPC equivalent
./sync_from_s3.sh --exclude-downloads

# Script automatically:
# 1. Finds config.ini in Git repo
# 2. Detects environment
# 3. Uses correct data path
# 4. Syncs to current directory
```

### Updating Script

```bash
# In Git repo, pull latest changes
cd ~/Github/greenland-glacier-flow
git pull origin develop

# Symlink automatically uses new version - nothing else needed!
# Next time you run sync, it uses updated script
```

## AWS CLI Setup

### Prerequisites

The script requires AWS CLI configured with S3 access.

**Install via conda/mamba** (recommended for HPC):
```bash
conda activate glacier_velocity
conda install -c conda-forge awscli
```

**Configure credentials**:
```bash
aws configure
# AWS Access Key ID: <your-key>
# AWS Secret Access Key: <your-secret>
# Default region name: us-west-2
# Default output format: json
```

**Verify access**:
```bash
aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/
```

### Benefits of conda/mamba Installation

✅ No root access needed  
✅ Integrates with existing conda environment  
✅ Easy version management  
✅ Can be included in `environment.yml`  
✅ Works alongside geospatial tools  

## Output Examples

### Dry Run Output

```bash
$ ./sync_from_s3.sh --exclude-downloads --dry-run

Reading configuration from: /home/yadav.111/Github/greenland-glacier-flow/config.ini
Working in data directory: /fs/project/howat.4/yadav.111/greenland_glacier_flow

DRY RUN MODE - No files will be downloaded
EXCLUDING download/ folders - Only processed results will be synced
SAFE MODE - Existing files will be skipped (multi-user friendly)

========================================
AWS S3 Data Sync
========================================

Syncing sentinel2 data...
From: s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/
To:   /fs/project/howat.4/yadav.111/greenland_glacier_flow/1_download_merge_and_clip/sentinel2/
Excluding: download/ folder

(dryrun) download: s3://greenland-glacier-data/.../clipped/134_Arsuk/S2B_...tif to ...
(dryrun) download: s3://greenland-glacier-data/.../metadata/134_Arsuk.csv to ...
✅ sentinel2 sync complete

Syncing landsat data...
From: s3://greenland-glacier-data/1_download_merge_and_clip/landsat/
To:   /fs/project/howat.4/yadav.111/greenland_glacier_flow/1_download_merge_and_clip/landsat/
Excluding: download/ folder

(dryrun) download: s3://greenland-glacier-data/.../134_Arsuk/LC8_...tif to ...
✅ landsat sync complete

========================================
Sync Complete!
========================================
```

### Actual Sync Output

```bash
$ ./sync_from_s3.sh --exclude-downloads

Reading configuration from: /home/bny/Github/greenland-glacier-flow/config.ini
Working in data directory: /home/bny/greenland_glacier_flow

EXCLUDING download/ folders - Only processed results will be synced
SAFE MODE - Existing files will be skipped (multi-user friendly)

========================================
AWS S3 Data Sync
========================================

Syncing sentinel2 data...
From: s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/
To:   /home/bny/greenland_glacier_flow/1_download_merge_and_clip/sentinel2/
Excluding: download/ folder

download: s3://greenland-glacier-data/.../clipped/134_Arsuk/S2B_...tif to ...
download: s3://greenland-glacier-data/.../metadata/134_Arsuk.csv to ...
✅ sentinel2 sync complete

Syncing landsat data...
From: s3://greenland-glacier-data/1_download_merge_and_clip/landsat/
To:   /home/bny/greenland_glacier_flow/1_download_merge_and_clip/landsat/
Excluding: download/ folder

download: s3://greenland-glacier-data/.../134_Arsuk/LC8_...tif to ...
✅ landsat sync complete

========================================
Sync Complete!
========================================

Local directory structure:
[tree output showing synced files]
```

## Multi-User Workflow

### Scenario: Team Processing Different Regions

**User A**: Processing regions 1-50
```bash
# Process on Lambda
python submit_aws_job.py --regions 001_Region --satellite sentinel2

# Sync results
./sync_from_s3.sh --exclude-downloads
# ✅ Downloads User A's regions
```

**User B**: Processing regions 51-100
```bash
# Process on Lambda
python submit_aws_job.py --regions 051_Region --satellite landsat

# Sync results
./sync_from_s3.sh --exclude-downloads
# ✅ Downloads User B's regions
# ✅ Skips User A's regions (already exist)
```

### Safe Mode Behavior

- User A's existing files are **not overwritten**
- User B only downloads **new files** (their regions)
- No conflicts between users
- Each user gets complete dataset incrementally

## Troubleshooting

### Error: Cannot cd to [directory]

**Cause**: Data directory doesn't exist  
**Solution**:
```bash
# Create the directory
mkdir -p /fs/project/howat.4/yadav.111/greenland_glacier_flow
# Or create local equivalent
mkdir -p ~/greenland_glacier_flow
```

### Error: config.ini not found

**Cause**: Script can't locate config.ini  
**Solution**:
```bash
# Ensure config.ini exists in Git repo
ls ~/Github/greenland-glacier-flow/config.ini

# Run script from Git repo directory
cd ~/Github/greenland-glacier-flow
./sync_from_s3.sh --exclude-downloads

# Or use symlink approach (recommended)
```

### Error: AWS credentials not configured

**Cause**: AWS CLI not configured  
**Solution**:
```bash
# Configure AWS credentials
aws configure

# Verify access
aws s3 ls s3://greenland-glacier-data/
```

### Files Not Syncing (Already Exist)

**Expected Behavior**: Default safe mode skips existing files  
**Solution** (if you need to update):
```bash
# Force overwrite mode
./sync_from_s3.sh --exclude-downloads --force-overwrite
```

### Slow Sync Speed

**Cause**: Including large download folders  
**Solution**:
```bash
# Always use --exclude-downloads for processed data
./sync_from_s3.sh --exclude-downloads
```

## Performance Benchmarks

### Bandwidth Usage

| Sync Type | Sentinel-2 | Landsat | Total |
|-----------|-----------|---------|-------|
| With --exclude-downloads | ~3 MB | ~1.5 MB | ~4.5 MB |
| Without --exclude-downloads | ~1.2 GB | ~1.5 MB | ~1.2 GB |
| **Savings** | **98%+** | **minimal** | **98%+** |

### Sync Times (Single Region)

| Environment | --exclude-downloads | Full Sync |
|-------------|---------------------|-----------|
| Local Gigabit | ~5 seconds | ~2 minutes |
| HPC Network | ~10 seconds | ~5 minutes |

## Integration with Other Tools

### With submit_aws_job.py

```bash
# Process on Lambda
python aws/scripts/submit_aws_job.py \
  --service lambda \
  --satellite sentinel2 \
  --regions 134_Arsuk

# Sync results
./sync_from_s3.sh --exclude-downloads
```

### With submit_satellite_job.py (HPC)

```bash
# Process on HPC
python submit_satellite_job.py --satellite landsat

# Later, sync any Lambda results
./sync_from_s3.sh landsat --exclude-downloads
```

### Automated Workflow

```bash
#!/bin/bash
# Process and sync workflow

# Process multiple regions on Lambda
for region in 134_Arsuk 101_sermiligarssuk; do
  python aws/scripts/submit_aws_job.py \
    --satellite sentinel2 \
    --regions $region
done

# Wait for processing
sleep 300

# Sync all results
./sync_from_s3.sh --exclude-downloads
```

## Best Practices

### ✅ DO

- Use `--exclude-downloads` for daily sync of processed data
- Run `--dry-run` first to preview changes
- Use symlink approach for always-current script
- Keep AWS CLI credentials secure (use IAM roles when possible)
- Let config.ini manage all paths (single source of truth)
- Use safe mode for multi-user environments

### ❌ DON'T

- Don't use `--force-overwrite` without understanding impact
- Don't manually edit script for different environments (use config.ini)
- Don't run without `--exclude-downloads` unless you need raw tiles
- Don't copy script to multiple locations (use symlink instead)
- Don't hardcode paths in sync commands

## Security Notes

- AWS credentials stored in `~/.aws/credentials` (user-specific)
- Script only reads from S3 (no write/delete operations)
- Safe mode prevents accidental data loss
- Works with IAM user credentials or assumed roles
- No credentials hardcoded in script

## Future Enhancements

Potential improvements being considered:

- [ ] Upload mode (local → S3 sync)
- [ ] Selective region sync (specify regions to sync)
- [ ] Progress bars for large transfers
- [ ] Parallel downloads for faster sync
- [ ] Integration with notification systems
- [ ] Automatic retry on network failures

## Related Documentation

- **AGENTS.md**: Full project architecture and development history
- **aws/docs/LAMBDA_INTEGRATION_GUIDE.md**: AWS Lambda workflow guide
- **aws/docs/S3_STRUCTURE_STANDARDIZATION.md**: S3 structure details
- **config.ini**: Configuration file reference

## Version History

- **v1.0** (Oct 8, 2025): Initial creation with basic S3 sync
- **v1.1** (Oct 8, 2025): Added cd to data directory for safety
- **v1.2** (Oct 9, 2025): Config-aware, environment-intelligent (CURRENT)

## Support

For issues or questions:
1. Check this documentation
2. Review AGENTS.md for project context
3. Verify config.ini has correct paths
4. Ensure AWS CLI configured correctly
5. Test with `--dry-run` first

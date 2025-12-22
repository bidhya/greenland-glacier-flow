# AWS Operations Guide - Greenland Glacier Flow Processing

**Purpose**: Comprehensive AWS operations reference for the Greenland glacier flow processing system.

**Last Updated**: October 17, 2025 - Reorganized document structure, moved reference sections to end, updated future additions list, and improved logical flow from cleanup to deployment to operations to monitoring.
**Scope**: Complete AWS workflow including cleanup, deployment, Lambda operations, data processing, and monitoring.
**Learning Objective**: Enable independent AWS operations for satellite data processing workflows.

---

## 📋 Working Directory Assumption

**Important**: All commands in this guide assume you are running them from the project root directory `/home/bny/Github/greenland-glacier-flow`.

**For Other Systems**: On different systems, this path will vary (e.g., `~/projects/greenland-glacier-flow` or `/workspace/greenland-glacier-flow`), but all scripts and relative paths are designed to work from within the `greenland-glacier-flow` project folder. Adjust any initial `cd` commands as needed for your local setup.

---

## 🎯 Overview

This guide provides complete AWS operations for the Greenland glacier flow processing system:

### **Current Sections:**
- **Environment Cleanup**: Complete AWS environment reset for fresh testing
- **Deployment Operations**: Lambda container deployment and configuration
- **Lambda Function Testing**: Sentinel-2 and Landsat data processing with AWS Lambda
- **Data Processing Workflows**: Satellite data download and processing commands for both satellites
- **Data Synchronization**: S3-to-local sync with bandwidth optimization
- **Monitoring & Cost Management**: Performance monitoring and cost optimization
- **Basic AWS Commands Reference**: Essential CLI commands for all AWS services

### **Future Additions:**
- Automated deployment pipelines
- Advanced cost optimization strategies

---

## 📋 Prerequisites

Before running any AWS commands, ensure you have:

```bash
# Check AWS CLI installation and configuration
aws --version
aws sts get-caller-identity

# Verify you're in the project directory
pwd  # Should show: /home/bny/Github/greenland-glacier-flow
```

---

## 🗑️ Section 1: Environment Cleanup

**Purpose**: Complete AWS environment reset for fresh testing. Removes all previous deployments while preserving the parent S3 bucket.

**⚠️ Important**: The parent S3 bucket `greenland-glacier-data` is PRESERVED as requested.

### Step 1: Remove Project Scripts from S3

**Command:**
```bash
aws s3 rm s3://greenland-glacier-data/scripts/ --recursive
```

**What it does:**
- Removes the entire `scripts/` folder from S3 bucket
- This folder contains the uploaded project code and dependencies

**Context/Rationale:**
- During AWS testing, the entire project gets uploaded to S3 for Lambda container access
- Removing this ensures fresh code deployment without old cached versions
- `--recursive` flag deletes all files and subfolders within the scripts directory

**Expected Output:**
- Lists all files being deleted (100+ files including Python scripts, configs, docs)
- No errors if successful

---

### Step 2: Remove Processed Data from S3

**Command:**
```bash
aws s3 rm s3://greenland-glacier-data/1_download_merge_and_clip/ --recursive
```

**What it does:**
- Removes all processed satellite imagery and metadata from S3
- Cleans the main data processing output directory

**Context/Rationale:**
- This folder contains Sentinel-2 and Landsat processed results from previous tests
- Includes downloaded tiles, clipped scenes, metadata CSVs, and template files
- Removing ensures clean slate for new test runs without data conflicts
- Preserves the parent bucket `greenland-glacier-data` as requested

**Expected Output:**
- Lists satellite data files being deleted (TIF images, CSV metadata files)
- Shows file sizes and deletion confirmations

---

### Step 3: Verify S3 Cleanup

**Command:**
```bash
aws s3 ls s3://greenland-glacier-data/ --recursive
```

**What it does:**
- Lists all remaining files in the S3 bucket

**Context/Rationale:**
- Verification step to confirm cleanup was successful
- Should return empty (no output) if cleanup completed properly
- Ensures parent bucket still exists but is completely clean

**Expected Output:**
- No output (empty bucket)
- If files remain, cleanup was incomplete

---

## ☁️ Section 2: Lambda Function Cleanup

### Step 4: Delete Lambda Function

**Command:**
```bash
aws lambda delete-function --function-name glacier-sentinel2-processor --region us-west-2
```

**What it does:**
- Permanently deletes the Lambda function from AWS

**Context/Rationale:**
- Lambda functions persist between deployments and can cause conflicts
- Fresh deployment requires clean slate without old function versions
- Function contains cached code and configurations from previous tests
- `us-west-2` region is used for optimal satellite data access

**Expected Output:**
- No output if successful (quiet deletion)
- Error if function doesn't exist (acceptable for clean environments)

---

### Step 5: Verify Lambda Deletion

**Command:**
```bash
aws lambda list-functions --region us-west-2 --query 'Functions[?FunctionName==`glacier-sentinel2-processor`].FunctionName'
```

**What it does:**
- Queries for the specific Lambda function to confirm deletion

**Context/Rationale:**
- Verification that Lambda function was successfully removed
- Uses JMESPath query to filter results specifically for our function
- Empty array `[]` confirms successful deletion

**Expected Output:**
```json
[]
```

---

## 🐳 Section 3: ECR (Container Registry) Cleanup

### Step 6: List ECR Images Before Deletion

**Command:**
```bash
aws ecr list-images --repository-name glacier-sentinel2-processor --region us-west-2
```

**What it does:**
- Lists all container images in the ECR repository

**Context/Rationale:**
- ECR repositories can contain multiple image versions
- Need to identify all images before deletion
- Shows image digests and tags for targeted removal
- Helps understand what will be deleted

**Expected Output:**
```json
{
    "imageIds": [
        {
            "imageDigest": "sha256:xxxxx...",
            "imageTag": "latest"
        }
    ]
}
```

---

### Step 7: Delete ECR Images (Run for Each Image)

**Command:**
```bash
# Replace SHA256_DIGEST with actual digest from Step 6
aws ecr batch-delete-image --repository-name glacier-sentinel2-processor --image-ids imageDigest=sha256:YOUR_ACTUAL_DIGEST_HERE --region us-west-2
```

**What it does:**
- Deletes individual container images from ECR repository

**Context/Rationale:**
- ECR requires images to be deleted before repository deletion
- Must be done one image at a time using their SHA256 digest
- `batch-delete-image` can handle multiple images but we use single for safety
- Images contain cached Lambda container environments

**Expected Output:**
```json
{
    "imageIds": [
        {
            "imageDigest": "sha256:xxxxx..."
        }
    ],
    "failures": []
}
```

---

### Step 8: Delete ECR Repository

**Command:**
```bash
aws ecr delete-repository --repository-name glacier-sentinel2-processor --region us-west-2 --force
```

**What it does:**
- Permanently deletes the ECR repository

**Context/Rationale:**
- Repository must be empty before deletion (hence previous step)
- `--force` flag ensures deletion even if repository has dependencies
- Removes all repository metadata and settings
- Required for truly fresh container deployments

**Expected Output:**
```json
{
    "repository": {
        "repositoryArn": "arn:aws:ecr:us-west-2:YOUR_ACCOUNT:repository/glacier-sentinel2-processor",
        "repositoryName": "glacier-sentinel2-processor",
        ...
    }
}
```

---

### Step 9: Verify ECR Cleanup

**Command:**
```bash
aws ecr describe-repositories --region us-west-2 --query 'repositories[?repositoryName==`glacier-sentinel2-processor`].repositoryName'
```

**What it does:**
- Checks if the ECR repository still exists

**Context/Rationale:**
- Final verification that ECR cleanup is complete
- Empty array confirms successful deletion
- Ensures no leftover container resources

**Expected Output:**
```json
[]
```

---

## 🧹 Section 4: Local Environment Cleanup

### Step 10: Remove Log Files

**Command:**
```bash
rm -f ./aws/logs/aws_job_submission.log ./logs/sentinel2_20240701.log ./1_download_merge_and_clip/sentinel2/test.log ./1_download_merge_and_clip/sentinel2/sentinel_glacier.log ./1_download_merge_and_clip/landsat/test.log
```

**What it does:**
- Deletes all local log files from previous runs

**Context/Rationale:**
- Log files accumulate during testing and can cause confusion
- Contains old error messages, timestamps, and debug information
- Fresh logs provide cleaner debugging experience
- `-f` flag prevents errors if files don't exist

**Expected Output:**
- No output (silent deletion)
- Command completes without errors

---

### Step 11: Remove Python Cache Directories

**Command:**
```bash
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
```

**What it does:**
- Finds and removes all `__pycache__` directories recursively

**Context/Rationale:**
- Python creates cache directories containing compiled bytecode
- Old cache can cause import issues or use outdated code
- Fresh cache ensures clean Python execution
- `2>/dev/null` suppresses permission errors, `|| true` ensures script continues

**Expected Output:**
- No output (silent deletion)
- Command completes successfully

---

## ✅ Section 5: Final Verification

### Step 12: Complete Environment Check

**Commands:**
```bash
# Check S3 bucket is clean but exists
aws s3 ls s3://greenland-glacier-data/

# Verify no Lambda functions
aws lambda list-functions --region us-west-2 --query 'Functions[?FunctionName==`glacier-sentinel2-processor`].FunctionName'

# Verify no ECR repositories
aws ecr describe-repositories --region us-west-2 --query 'repositories[?repositoryName==`glacier-sentinel2-processor`].repositoryName'

# Check local directory is clean
find . -name "*.log" -o -name "__pycache__" | wc -l  # Should return 0
```

**What they do:**
- Comprehensive verification that all cleanup was successful
- Checks all AWS services and local environment

**Context/Rationale:**
- Ensures clean slate for fresh testing
- Prevents conflicts from leftover resources
- Confirms all commands executed successfully

**Expected Output:**
- All commands should return empty results or zero counts
- Indicates completely clean environment

---

## 🚀 Section 6: Deployment Operations

**Purpose**: Deploy Lambda container and prepare for satellite data processing.

### Step 1: Deploy Lambda Container

**Command:**
```bash
cd aws/scripts && chmod +x deploy_lambda_container.sh && ./deploy_lambda_container.sh
```

**What it does:**
- Builds Docker container with geospatial libraries (GDAL, rasterio, geopandas, etc.)
- Creates ECR repository if it doesn't exist
- Pushes container image to Amazon ECR
- Creates/updates Lambda function with container image
- Configures function with 5GB memory and 10GB ephemeral storage

**Expected Output:**
- Docker build progress with layer caching
- ECR repository creation confirmation
- Lambda function creation/update with container image
- Final confirmation: "Lambda container image deployed successfully!"

**Context/Rationale:**
- Container-based Lambda provides full Python environment with scientific libraries
- 5GB memory optimal for small glaciers (1-2 Sentinel-2 tiles)
- 10GB ephemeral storage handles intermediate processing files
- 15-minute timeout sufficient for typical processing jobs

---

### Step 2: Update Lambda Configuration (if needed)

**Command:**
```bash
aws lambda update-function-configuration \
  --function-name glacier-sentinel2-processor \
  --memory-size 5120 \
  --ephemeral-storage '{"Size": 10240}' \
  --region us-west-2
```

**What it does:**
- Updates Lambda function memory to 5GB (5120 MB)
- Sets ephemeral storage to 10GB for processing large satellite files
- Maintains 15-minute timeout for complex geospatial operations

**Context/Rationale:**
- Memory sizing based on extensive testing (October 2025)
- 5GB sufficient for small glaciers (1-2 tiles) - proven successful
- Large glaciers (4+ tiles) exceed Lambda 10GB limit - use HPC instead

---

### Step 3: Upload Project Files to S3

**Command:**
```bash
aws s3 sync . s3://greenland-glacier-data/scripts/greenland-glacier-flow/ --exclude ".git/*" --exclude "*.log" --exclude "__pycache__/*" --exclude ".pytest_cache/*"
```

**What it does:**
- Uploads entire project codebase to S3 for Lambda container access
- Excludes development artifacts (.git, logs, cache files)
- Creates `scripts/greenland-glacier-flow/` folder in S3 bucket

**Expected Output:**
- Lists 100+ files being uploaded (Python scripts, configs, documentation)
- Shows upload progress and completion confirmation

**Context/Rationale:**
- Lambda container downloads project files at runtime from S3
- Ensures Lambda has access to all processing scripts and configurations
- Bandwidth-efficient sync only uploads changed files

---

## 📊 Section 7: Lambda Function Testing

**Purpose**: Test Lambda function with Sentinel-2 data processing.

### Step 4: Test Satellite Processing (Sentinel-2 or Landsat)

**Command for Sentinel-2:**
```bash
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-02 --dry-run false
```

**Command for Landsat:**
```bash
python aws/scripts/submit_aws_job.py --satellite landsat --service lambda --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-05 --dry-run false
```

**What it does:**
- Invokes Lambda function with satellite processing parameters
- Downloads satellite data for the specified region and date range
- Processes data: download → merge tiles → clip to region → upload results
- Returns processing results and S3 upload confirmation

**Expected Output:**
```
✅ Lambda invocation successful!
   Status Code: 200
   Request ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

✅ Processing completed successfully!

Results:
   Uploaded Files: 5 (Sentinel-2) or 4 (Landsat)
   S3 Location: s3://greenland-glacier-data/1_download_merge_and_clip/{satellite}/
   Message: Sentinel-2/Landsat processing completed successfully with geospatial libraries
```

**Processing Details:**
- **Sentinel-2**: Downloads tiles covering the region, merges overlapping tiles into mosaics, clips to glacier boundary
- **Landsat**: Downloads individual scenes, processes and clips to region boundary
- Uploads processed scenes + metadata + template files to S3

**Context/Rationale:**
- **Sentinel-2**: Small test region (1 tile), 1-2 day range minimizes processing time
- **Landsat**: 5-day range increases chance of finding available scenes (16-day revisit cycle)
- Both proven successful configurations from October 2025 testing
- Avoid Lambda timeout (15 minutes) with appropriate date ranges

---

### Step 5: Verify Processing Results

**Command:**
```bash
aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/ --recursive
# OR for Landsat:
aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/landsat/ --recursive
```

**What it does:**
- Lists all files uploaded by the Lambda processing job
- Shows file sizes, timestamps, and S3 paths

**Expected Output for Sentinel-2:**
```
2025-10-13 14:28:48    1729933 1_download_merge_and_clip/sentinel2/clipped/134_Arsuk/S2A_MSIL2A_20240704T142751_N0510_R139.tif
2025-10-13 14:28:48    1729933 1_download_merge_and_clip/sentinel2/clipped/134_Arsuk/S2A_MSIL2A_20240707T144001_N0510_R039.tif
[2-3 more clipped scenes ~1.7 MB each]
[4 downloaded tiles in download/2024/ folder ~90-200 MB each]
[5 metadata CSV files in metadata/ folders]
[1 template file in template/ folder ~1.7 MB]
```

**Expected Output for Landsat:**
```
2025-10-13 14:43:45     769041 1_download_merge_and_clip/landsat/134_Arsuk/20240704142514_LC80030172024186LGN00_LC08_L1TP_003017_20240704_20240712_02_T1_ortho.tif
2025-10-13 14:43:45     769041 1_download_merge_and_clip/landsat/134_Arsuk/20240705141901_LC90020172024187LGN00_LC09_L1GT_002017_20240705_20240705_02_T2_ortho.tif
2025-10-13 14:43:46      66892 1_download_merge_and_clip/landsat/_reference/134_Arsuk.tif
2025-10-13 14:43:45       3196 1_download_merge_and_clip/landsat/_reference/134_Arsuk_stac_query_results.csv
```

**File Structure:**
- **Sentinel-2**: `clipped/` (processed scenes), `download/` (raw tiles), `metadata/` (CSVs), `template/` (reference)
- **Landsat**: `{region}/` (processed scenes), `_reference/` (template + STAC results)

---

### Step 6: Download Results Locally (Optional)

**Command:**
```bash
./sync_from_s3.sh --exclude-downloads
```

**What it does:**
- Downloads processed results from S3 to local filesystem
- Skips raw download tiles (saves bandwidth)
- Uses config-aware paths matching local directory structure

**Context/Rationale:**
- Enables local analysis of Lambda-processed data
- `--exclude-downloads` saves 98% bandwidth by skipping raw tiles
- Maintains consistent directory structure across environments

---

## 📥 Section 8: Data Processing Workflows

**Purpose**: Process satellite data using AWS Lambda for different scenarios.

### Satellite Processing Examples

**Sentinel-2 (5-day revisit, tile-based):**
```bash
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-02
```

**Landsat (16-day revisit, scene-based):**
```bash
python aws/scripts/submit_aws_job.py --satellite landsat --service lambda --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-05
```

**Multiple Regions (both satellites):**
```bash
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda --regions "134_Arsuk,191_Hagen_Brae" --date1 2024-07-01 --date2 2024-07-02
```

**Longer Date Ranges:**
```bash
# Sentinel-2: 1 week (more tiles, longer processing)
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-08

# Landsat: 2 weeks (better chance of finding scenes)
python aws/scripts/submit_aws_job.py --satellite landsat --service lambda --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-15
```

**Dry Run (Test Configuration):**
```bash
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-02 --dry-run true
```

### Satellite Differences

| Aspect | Sentinel-2 | Landsat |
|--------|------------|---------|
| **Revisit Time** | 5 days | 16 days |
| **Data Structure** | Tiles (overlapping) | Scenes (individual) |
| **Processing** | Merge tiles → clip | Direct clip |
| **Typical Files** | 4-6 tiles → 4 scenes | 1-2 scenes |
| **Date Range** | 1-3 days | 5-14 days |
| **File Size** | ~1.7 MB scenes | ~769 KB scenes |
| **Lambda Memory** | 5 GB | 5 GB |

**Note**: Both satellites use the same Lambda function and processing pipeline, with satellite-specific parameters handled automatically.

### Command Style Preference

**Recommended**: `python aws/scripts/submit_aws_job.py` (direct path)

**Why better than `cd aws/scripts && python submit_aws_job.py`:**
- ✅ **No directory changes**: Doesn't modify your current shell location
- ✅ **Explicit paths**: Clear where the script is located
- ✅ **Automation-friendly**: Works in scripts and CI/CD pipelines
- ✅ **Error-resistant**: Script handles its own path resolution correctly
- ✅ **Project root context**: Can run from anywhere in the project

**Note**: The script uses `Path(__file__).resolve().parent` for path resolution, so it works correctly regardless of where it's called from.

---

## 🔄 Section 9: Data Synchronization (S3 to Local)

**Purpose**: Download processed satellite data from AWS S3 to your local machine or HPC for analysis.

### Overview

The `sync_from_s3.sh` script provides intelligent, config-aware synchronization of processed satellite data from AWS S3 to your local filesystem. It automatically detects your environment (HPC vs local) and uses the appropriate data directory from `config.ini`.

### Key Features

- **Environment-Aware**: Auto-detects HPC (SLURM) vs local (WSL/Ubuntu) and uses correct data directory
- **Config-Driven**: Reads `base_dir` (HPC) or `local_base_dir` (local) from `config.ini`
- **Multi-User Safe**: Default behavior skips existing files to prevent overwriting work
- **Bandwidth-Efficient**: `--exclude-downloads` option skips raw satellite tiles (98% bandwidth savings)
- **Flexible Options**: Sync specific satellites, dry-run mode, force overwrite capability
- **Git-Safe**: Changes to data directory, keeping Git repository separate from large data files

### Basic Usage

**Safe Sync (Recommended - skips existing files):**
```bash
./sync_from_s3.sh --exclude-downloads
```

**What it does:**
- Downloads processed Sentinel-2 and Landsat results from S3
- Skips raw download tiles (saves 98% bandwidth)
- Only downloads files that don't exist locally
- Uses config-aware paths matching your environment

**Expected Output:**
```
Reading configuration from: /home/bny/Github/greenland-glacier-flow/config.ini
Working in data directory: /home/bny/greenland_glacier_flow

========================================
AWS S3 Data Sync
========================================

Syncing sentinel2 data...
From: s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/
To:   /home/bny/greenland_glacier_flow/1_download_merge_and_clip/sentinel2/
Excluding: download/ folder

✅ sentinel2 sync complete

Syncing landsat data...
From: s3://greenland-glacier-data/1_download_merge_and_clip/landsat/
To:   /home/bny/greenland_glacier_flow/1_download_merge_and_clip/landsat/
Excluding: download/ folder

✅ landsat sync complete

========================================
Sync Complete!
========================================
```

**Actual Results (October 14, 2025):**
- **Sentinel-2**: Downloaded 9 files (4 clipped scenes @ 1.7 MB each + 5 metadata files)
- **Landsat**: Downloaded 4 files (2 processed scenes @ 752 KB each + 2 reference files)
- **Total Size**: ~8.2 MB (vs ~1.2 GB if raw tiles were included)
- **Bandwidth Saved**: 98% by excluding download folders

### Advanced Options

**Sync Specific Satellite:**
```bash
# Only Sentinel-2
./sync_from_s3.sh sentinel2 --exclude-downloads

# Only Landsat
./sync_from_s3.sh landsat --exclude-downloads
```

**Dry Run (Preview what would be downloaded):**
```bash
./sync_from_s3.sh --exclude-downloads --dry-run
```

**Force Overwrite Existing Files:**
```bash
./sync_from_s3.sh --exclude-downloads --force-overwrite
```

**⚠️ Warning**: `--force-overwrite` will replace local files if they differ from S3. Use with caution in multi-user environments.

### Configuration Details

**Environment Detection:**
- **HPC**: Detects `sbatch` command → uses `base_dir` from config.ini
- **Local**: No `sbatch` command → uses `local_base_dir` from config.ini

**Config File Locations (searched in order):**
1. Script directory (`/home/bny/Github/greenland-glacier-flow/config.ini`)
2. Current directory (`./config.ini`)
3. Home directory (`~/Github/greenland-glacier-flow/config.ini`)

**Directory Structure:**
```
Local Data Directory (from config.ini):
├── 1_download_merge_and_clip/
│   ├── sentinel2/
│   │   ├── clipped/          # Processed scenes (~1.7 MB each)
│   │   │   └── 134_Arsuk/
│   │   │       ├── S2A_MSIL2A_20240704T142751_N0510_R139.tif (1.7M)
│   │   │       ├── S2A_MSIL2A_20240707T144001_N0510_R039.tif (1.7M)
│   │   │       ├── S2B_MSIL2A_20240702T143749_N0510_R039.tif (1.7M)
│   │   │       └── S2B_MSIL2A_20240705T144749_N0510_R082.tif (1.7M)
│   │   ├── metadata/         # CSV files with scene info
│   │   │   ├── combined_csv/134_Arsuk.csv
│   │   │   └── individual_csv/134_Arsuk/[4 scene CSVs]
│   │   └── template/         # Reference template files
│   │       └── 134_Arsuk.tif (1.6M)
│   └── landsat/
│       ├── {region}/         # Processed scenes (~752 KB each)
│       │   └── 134_Arsuk/
│       │       ├── 20240704142514_LC80030172024186LGN00_LC08_L1TP_003017_20240704_20240712_02_T1_ortho.tif (752K)
│       │       └── 20240705141901_LC90020172024187LGN00_LC09_L1GT_002017_20240705_20240705_02_T2_ortho.tif (752K)
│       └── _reference/        # Template and STAC results
│           ├── 134_Arsuk.tif (65K)
│           └── 134_Arsuk_stac_query_results.csv (3.1K)
```

### Bandwidth Optimization

**Without `--exclude-downloads`:**
- Downloads everything including raw satellite tiles
- Sentinel-2: ~1.2 GB per region (8 tiles × 150 MB each)
- Landsat: ~1.6 MB per region (2 scenes × 800 KB each)

**With `--exclude-downloads` (recommended):**
- Skips raw download tiles, only gets processed results
- Sentinel-2: ~7 MB per region (4 scenes @ 1.7 MB + 5 metadata files)
- Landsat: ~1.6 MB per region (2 scenes @ 752 KB + 2 reference files)
- **Savings**: 98% bandwidth reduction for Sentinel-2

**Actual Test Results (October 14, 2025):**
- **Downloaded**: 13 files total (9 Sentinel-2 + 4 Landsat)
- **Total Size**: 8.2 MB
- **Time**: ~30 seconds
- **Bandwidth Saved**: 1.2 GB (raw tiles would have been ~1.2 GB)

### Multi-User Considerations

**Safe Mode (Default):**
- Uses `--size-only` flag to skip existing files
- Perfect for team environments where multiple users process different regions
- Prevents accidental overwriting of local work

**When to Use Force Overwrite:**
- When you need updated versions of processed files
- When local files are corrupted or incomplete
- When you want to ensure local data matches S3 exactly

### Troubleshooting

**Config File Not Found:**
```
Warning: config.ini not found in common locations
Searched: /path/to/script, current dir, ~/Github/greenland-glacier-flow/
```
**Solution**: Ensure `config.ini` exists and contains `[PATHS]` section with `base_dir` or `local_base_dir`.

**Cannot Change to Data Directory:**
```
Error: Cannot cd to /path/to/data/dir
```
**Solution**: Check that the data directory exists and you have write permissions.

**AWS Credentials Issues:**
```
Unable to locate credentials
```
**Solution**: Run `aws configure` to set up AWS credentials.

### Integration with Processing Workflow

**Complete Workflow Example:**
```bash
# 1. Process data on AWS Lambda
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --date1 2024-07-01 --date2 2024-07-02

# 2. Verify results on S3
aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/ --recursive

# 3. Sync to local machine
./sync_from_s3.sh --exclude-downloads

# 4. Analyze locally
ls -lh ~/greenland_glacier_flow/1_download_merge_and_clip/sentinel2/clipped/
```

**Actual Workflow Results (October 14, 2025):**
```bash
# Files downloaded to local machine:
# Sentinel-2 (9 files, 7 MB):
#   - 4 clipped scenes: 1.7 MB each (S2A/S2B satellites)
#   - 1 combined CSV metadata
#   - 4 individual scene CSVs
#   - 1 template file: 1.6 MB
#
# Landsat (4 files, 1.6 MB):
#   - 2 processed scenes: 752 KB each (LC8/LC9 satellites)
#   - 1 reference template: 65 KB
#   - 1 STAC query results: 3.1 KB
#
# Total: 13 files, 8.2 MB, ~30 seconds download time
```

### Performance Notes

- **Network Speed**: S3 downloads are typically 10-50 MB/s depending on your internet connection
- **File Count**: Sentinel-2 regions typically have 8-14 files, Landsat regions have 4 files
- **Resume Capability**: Script can be interrupted and restarted - it will skip already downloaded files
- **Parallel Downloads**: AWS CLI automatically uses multiple connections for faster transfers

---

## 📈 Section 10: Monitoring & Cost Management

**Purpose**: Monitor Lambda performance and manage AWS costs.

### Monitor Lambda Invocations

**Command:**
```bash
aws lambda get-function --function-name glacier-sentinel2-processor --region us-west-2 --query 'Configuration.{State:State, LastModified:LastModified, MemorySize:MemorySize}'
```

**What it does:**
- Shows Lambda function status and configuration
- Confirms function is active and properly configured

---

### Check CloudWatch Logs

**Command:**
```bash
aws logs filter-log-events --log-group-name /aws/lambda/glacier-sentinel2-processor --region us-west-2 --start-time $(date -d '1 hour ago' +%s000) --query 'events[*].message' --output text
```

**What it does:**
- Shows recent Lambda execution logs
- Helps troubleshoot processing issues
- Displays processing progress and errors

---

### Monitor Costs (Current Month)

**Command:**
```bash
aws ce get-cost-and-usage --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) --granularity MONTHLY --metrics BlendedCost --query 'ResultsByTime[*].Groups[?Keys[0]==`AWS Lambda`].Metrics.BlendedCost.Amount' --output text
```

**What it does:**
- Shows current month Lambda costs
- Helps track processing expenses
- Enables cost optimization decisions

**Cost Estimates:**
- **Sentinel-2**: Lambda compute ~$0.007 (5GB × 84s), S3 storage ~$0.023/GB/month
- **Landsat**: Lambda compute ~$0.007 (5GB × 60s), S3 storage ~$0.023/GB/month
- Data transfer: Minimal for processing within same region

---

## ⚠️ Important Notes

1. **Memory Limits**: Lambda maximum is 10GB - large glaciers (4+ Sentinel-2 tiles) will fail
2. **Timeout Limits**: 15-minute maximum - use shorter date ranges for complex processing
3. **Storage Limits**: 10GB ephemeral storage - monitor disk usage for large datasets
4. **Satellite Differences**: Sentinel-2 uses 1-3 day ranges, Landsat needs 5-14 days for data availability
5. **Cost Monitoring**: Track Lambda invocations and S3 storage costs regularly
6. **Region Selection**: Use us-west-2 for optimal satellite data access
7. **Testing First**: Always test with small regions and appropriate date ranges
8. **Backup Strategy**: Large glaciers should use HPC instead of Lambda

---

## 🔧 Section 11: Basic AWS Commands Reference

**Purpose**: Essential AWS CLI commands for getting started and troubleshooting.

### Account & Configuration

```bash
# Check AWS CLI version
aws --version

# Verify AWS credentials and account
aws sts get-caller-identity

# List configured profiles
aws configure list-profiles

# Show current configuration
aws configure list

# Configure AWS credentials (interactive)
aws configure

# Configure specific profile
aws configure --profile myprofile
```

### S3 (Storage) Commands

```bash
# List all buckets
aws s3 ls

# List contents of a bucket
aws s3 ls s3://my-bucket-name/

# List contents recursively (shows all files)
aws s3 ls s3://my-bucket-name/ --recursive

# Copy file to S3
aws s3 cp myfile.txt s3://my-bucket-name/myfile.txt

# Copy directory to S3
aws s3 cp myfolder s3://my-bucket-name/myfolder --recursive

# Sync local directory to S3 (upload changes only)
aws s3 sync myfolder s3://my-bucket-name/myfolder

# Download file from S3
aws s3 cp s3://my-bucket-name/myfile.txt myfile.txt

# Download directory from S3
aws s3 cp s3://my-bucket-name/myfolder myfolder --recursive

# Delete file from S3
aws s3 rm s3://my-bucket-name/myfile.txt

# Delete directory from S3
aws s3 rm s3://my-bucket-name/myfolder --recursive

# Create bucket
aws s3 mb s3://my-new-bucket-name

# Delete bucket (must be empty)
aws s3 rb s3://my-bucket-name
```

### Lambda Commands

```bash
# List all Lambda functions
aws lambda list-functions

# List functions in specific region
aws lambda list-functions --region us-west-2

# Get function details
aws lambda get-function --function-name my-function

# Invoke function
aws lambda invoke --function-name my-function response.json

# Update function code
aws lambda update-function-code --function-name my-function --zip-file fileb://function.zip

# Update function configuration
aws lambda update-function-configuration --function-name my-function --memory-size 512

# Delete function
aws lambda delete-function --function-name my-function
```

### ECR (Container Registry) Commands

```bash
# List repositories
aws ecr describe-repositories

# Create repository
aws ecr create-repository --repository-name my-repo

# List images in repository
aws ecr list-images --repository-name my-repo

# Delete image
aws ecr batch-delete-image --repository-name my-repo --image-ids imageDigest=sha256:xxxxx

# Delete repository
aws ecr delete-repository --repository-name my-repo --force

# Login to ECR (for Docker)
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-west-2.amazonaws.com
```

### IAM Commands

```bash
# List users
aws iam list-users

# Get current user details
aws iam get-user

# List policies attached to user
aws iam list-attached-user-policies --user-name myuser

# List user access keys
aws iam list-access-keys --user-name myuser
```

### General AWS Commands

```bash
# List all regions
aws ec2 describe-regions

# Get account information
aws sts get-account-summary

# Check service limits
aws service-quotas get-service-quota --service-code lambda --quota-code L-2ACBD22F

# Get billing information (requires billing permissions)
aws ce get-cost-and-usage --time-period Start=2025-01-01,End=2025-01-31 --granularity MONTHLY --metrics BlendedCost
```

### Troubleshooting Commands

```bash
# Check AWS CLI configuration
aws configure list

# Test S3 access
aws s3 ls s3://my-bucket-name/

# Test Lambda permissions
aws lambda list-functions --max-items 1

# Check CloudWatch logs for Lambda
aws logs tail /aws/lambda/my-function --follow

# Get Lambda function logs
aws logs filter-log-events --log-group-name /aws/lambda/my-function
```

### Cost Monitoring

```bash
# Get current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost

# List services with costs
aws ce get-dimension-values \
  --dimension SERVICE \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d)
```

---

## ⚠️ Important Notes

1. **S3 Bucket Preservation**: The parent bucket `greenland-glacier-data` is intentionally preserved
2. **Region Consistency**: All commands use `us-west-2` for satellite data optimization
3. **Order Matters**: Follow the exact sequence to avoid dependency conflicts
4. **Verification Steps**: Always verify deletions were successful
5. **Cost Awareness**: ECR storage and Lambda invocations incur charges
6. **IAM Permissions**: Ensure your user has necessary AWS permissions

---

## 📚 AWS Concepts Learned

### S3 (Simple Storage Service)
- **Buckets**: Containers for storing objects (files)
- **Objects**: Files stored in buckets with unique keys
- **Recursive operations**: `--recursive` flag for entire directory trees

### Lambda Functions
- **Serverless compute**: Run code without managing servers
- **Functions**: Deployed code units with specific handlers
- **Regions**: Services are region-specific for latency optimization

### ECR (Elastic Container Registry)
- **Container registry**: Store Docker container images
- **Repositories**: Named collections of images
- **Images**: Tagged versions of containerized applications

### AWS CLI Patterns
- **JMESPath queries**: `--query` parameter for filtering JSON output
- **Region specification**: `--region` parameter for service location
- **Force operations**: `--force` flag for non-interactive deletions

---

## 📚 AWS Learning Resources

- **AWS CLI Documentation**: https://docs.aws.amazon.com/cli/
- **AWS Free Tier**: https://aws.amazon.com/free/
- **AWS Console**: https://console.aws.amazon.com/
- **AWS Pricing Calculator**: https://calculator.aws/

---

*This comprehensive guide enables independent AWS operations for the Greenland glacier flow processing system, from cleanup to production deployment and monitoring.*
# Landsat Lambda Processing - Troubleshooting Guide

**Status**: 🔄 In Progress  
**Last Updated**: October 2, 2025

## Overview

This document tracks the implementation and troubleshooting of Landsat satellite data processing on AWS Lambda. While Sentinel-2 processing is fully functional, Landsat processing encounters an early exit issue that requires further investigation.

## Current Status

### ✅ What's Working

1. **Lambda Handler Integration**
   - Landsat processing function implemented in `lambda_handler.py`
   - Correct satellite type routing (`if satellite.lower() == "landsat"`)
   - Proper argument mapping for Landsat-specific parameters

2. **Credential Handling** 
   - Successfully fixed AWS credentials fallback mechanism
   - Code now uses Lambda execution role when CSV file doesn't exist
   - Requester-pays bucket configuration in place

3. **Infrastructure**
   - Docker container builds successfully with Landsat dependencies
   - ECR push and Lambda deployment working correctly
   - 5GB RAM, 10GB ephemeral storage allocated

### ❌ What's Not Working

**Issue**: Landsat script exits early with return code 1

**Symptoms:**
- Script starts successfully (prints initial message)
- Exits immediately after startup message
- No stderr output
- Minimal stdout (only initialization message)
- Return code: 1

**Current Output:**
```
-----------------------BEGIN-----------------------

Attempting download/merge/clip of Landsat imagery for regions in greenland 
between 2024-08-01 and 2024-08-01, with intersect fraction threshold 0.05, 
outputting to /tmp/glacier_processing/output.

[Script exits]
```

## Implementation Details

### Argument Differences: Sentinel-2 vs Landsat

**Sentinel-2 Arguments:**
```python
cmd = [
    "download_merge_clip_sentinel2.py",
    "--regions", regions,
    "--start_date", start_date,      # Sentinel-2 specific
    "--end_date", end_date,            # Sentinel-2 specific
    "--download_flag", "1",            # Sentinel-2 specific
    "--post_processing_flag", "1",    # Sentinel-2 specific
    "--cores", "1",                    # Sentinel-2 specific
    "--base_dir", base_dir
]
```

**Landsat Arguments:**
```python
cmd = [
    "download_clip_landsat.py",
    "--regions", regions,
    "--date1", start_date,             # Landsat uses date1
    "--date2", end_date,               # Landsat uses date2
    "--base_dir", base_dir,
    "--log_name", "lambda_processing.log"
]
# Note: NO download_flag, post_processing_flag, or cores
```

### Credential Fix Implementation

**Location**: `/1_download_merge_and_clip/landsat/lib/functions.py` (lines 143-156)

```python
# Get AWS access credentials.
# Try to read from CSV file, but fall back to default credentials (e.g., Lambda execution role)
import os
credentials_path = os.path.expanduser(AWS_CREDENTIALS_FPATH)
if os.path.exists(credentials_path):
    aws_creds = pd.read_csv(credentials_path)
    access_key = aws_creds["Access key ID"].values[0]
    secret_access_key = aws_creds["Secret access key"].values[0]
    aws_session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_access_key,
    )
else:
    # Use default credential chain (environment variables, IAM role, etc.)
    aws_session = boto3.Session()
```

**Rasterio Session Update** (lines 167-171):
```python
with rs.Env(
    AWSSession(
        aws_session,  # Uses the session created above
        requester_pays=True,
    )
) as env:
```

## Troubleshooting Steps Taken

### ✅ Completed
1. Fixed argument parsing (removed incompatible flags)
2. Implemented credential fallback mechanism
3. Verified Docker build includes all dependencies
4. Confirmed Lambda has sufficient resources (5GB RAM, 10GB storage)
5. Tested with multiple date ranges (2024-08-01, 2023-07-01 to 2023-07-31)
6. Verified Sentinel-2 still works after changes

### 🔄 To Investigate

1. **STAC API Access**
   - Verify USGS Landsat STAC API accessible from Lambda
   - Check for API authentication requirements
   - Test connectivity: `https://landsatlook.usgs.gov/stac-server`

2. **Logging & Error Capture**
   - Add verbose logging to identify exact failure point
   - Capture Python exceptions that might be silently failing
   - Add try-catch blocks around critical sections

3. **Environment Differences**
   - Compare HPC vs Lambda environment variables
   - Check for missing dependencies specific to Landsat workflow
   - Verify GDAL configuration in Lambda

4. **File System Issues**
   - Verify `/tmp/glacier_processing/output` directory creation
   - Check write permissions in Lambda environment
   - Confirm sufficient ephemeral storage

5. **Timeout Considerations**
   - Current timeout: 800 seconds (13+ minutes)
   - STAC search might be timing out silently
   - Consider adding progress indicators

## Diagnostic Commands

### Test Landsat Processing
```bash
cd /mnt/c/Github/greenland-glacier-flow/aws/scripts

# Create test payload
cat > test_landsat.json << 'EOF'
{
  "satellite": "landsat",
  "regions": "134_Arsuk",
  "start_date": "2024-08-01",
  "end_date": "2024-08-01",
  "s3_bucket": "greenland-glacier-data"
}
EOF

# Invoke Lambda
aws lambda invoke --function-name glacier-sentinel2-processor \
  --payload file://test_landsat.json result.json

# Check results
cat result.json | jq '.'
```

### Check CloudWatch Logs
```bash
# Get recent logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/glacier-sentinel2-processor \
  --start-time $(($(date +%s) * 1000 - 300000)) \
  --query 'events[-20:].message' --output text
```

### Verify Container Contents
```bash
# Check if script exists in container
docker run --rm glacier-sentinel2-processor:latest \
  ls -la /tmp/greenland-glacier-flow/1_download_merge_and_clip/landsat/

# Test credentials fallback locally
docker run --rm glacier-sentinel2-processor:latest \
  python -c "import os; print(os.path.exists(os.path.expanduser('~/AWS_user_credentials.csv')))"
```

## Comparison with Working Sentinel-2

### Sentinel-2 (Working)
- ✅ Processes 8 files successfully
- ✅ Uploads to S3 without issues
- ✅ Complete logs in CloudWatch
- ✅ Returns statusCode 200

### Landsat (Not Working)
- ❌ Exits early (return code 1)
- ❌ No files processed
- ❌ Minimal logs (only startup message)
- ❌ Returns statusCode 500

### Key Differences to Investigate
1. Sentinel-2 uses pystac-client differently
2. Landsat requires requester-pays configuration
3. Different STAC API endpoints
4. Landsat uses AWS S3 hrefs directly

## Potential Root Causes

### Most Likely
1. **STAC API Connectivity**: USGS Landsat STAC API might be blocked or require authentication
2. **Silent Exception**: Python exception occurring but not being captured in stderr
3. **Directory Creation**: Output directory creation failing in `/tmp`

### Less Likely (but possible)
4. **Library Version Mismatch**: Specific rasterio/GDAL version incompatibility with Landsat
5. **Network Timeout**: STAC search timing out without proper error handling
6. **Memory Issue**: Early OOM not being reported properly

## Next Development Steps

### Priority 1: Add Verbose Logging
```python
# Add to download_clip_landsat.py
import sys
import traceback

try:
    # Existing code
    print("DEBUG: Starting STAC search...", file=sys.stderr)
    stac_gdf = stac_search_aoi(...)
    print(f"DEBUG: STAC returned {len(stac_gdf)} results", file=sys.stderr)
except Exception as e:
    print(f"ERROR: {str(e)}", file=sys.stderr)
    print(f"TRACEBACK: {traceback.format_exc()}", file=sys.stderr)
    raise
```

### Priority 2: Test STAC API Access
Create minimal test script to verify STAC connectivity from Lambda:
```python
from pystac_client import Client

stac = Client.open("https://landsatlook.usgs.gov/stac-server")
print("STAC connection successful")
```

### Priority 3: Local Lambda-like Testing
Run Landsat script locally with Lambda-like environment:
```bash
# Simulate Lambda environment
export AWS_EXECUTION_ENV=AWS_Lambda_python3.12
export LAMBDA_TASK_ROOT=/var/task
export HOME=/tmp

# Run script
python download_clip_landsat.py --regions 134_Arsuk \
  --date1 2024-08-01 --date2 2024-08-01 \
  --base_dir /tmp/glacier_processing/output
```

## Success Criteria

Landsat processing will be considered successful when:
- [ ] Script completes without early exit
- [ ] STAC search returns results
- [ ] Files are downloaded and clipped
- [ ] Files are uploaded to S3
- [ ] Lambda returns statusCode 200
- [ ] CloudWatch shows complete processing logs

## Related Files

- `aws/lambda/lambda_handler.py` - Lambda handler with Landsat function
- `1_download_merge_and_clip/landsat/download_clip_landsat.py` - Main Landsat script
- `1_download_merge_and_clip/landsat/lib/functions.py` - Credential handling (lines 143-171)
- `1_download_merge_and_clip/landsat/lib/defaults.py` - Configuration defaults
- `aws/docs/LAMBDA_DEPLOYMENT_GUIDE.md` - Deployment procedures

## Lessons Learned

1. **Credential Handling**: Always implement fallback for credential loading in cloud environments
2. **Argument Compatibility**: Document satellite-specific argument differences clearly
3. **Docker Caching**: Always use `--no-cache` for fresh builds when debugging
4. **Error Visibility**: Ensure stderr and stdout are properly captured in containerized environments
5. **Environment Parity**: Test in environments as close to production as possible

---

**Note**: This is an active debugging document. Update as new findings emerge.

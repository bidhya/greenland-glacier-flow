# Landsat Processing Analysis - December 31, 2025

**Status**: ✅ **FULLY OPERATIONAL**

## Current Status

### ✅ Resolution (December 2025)
- **Root Cause**: Insufficient Lambda resources (5GB memory limit)
- **Solution**: Maximum Lambda resources (10GB memory + 10GB storage)
- **Result**: Complete Landsat processing pipeline functional

### Performance Metrics
- **Execution Time**: ~9.7 seconds
- **Memory Usage**: ~439MB
- **Files Processed**: 3 ortho scenes (August 6-8, 2025)
- **Cost**: ~$0.002 per execution (10GB × 9.7s)

### Test Results
- **Region**: 104_sorgenfri
- **Date Range**: 2025-08-01 to 2025-08-09
- **Output**: 3 processed Landsat scenes in S3
- **Success Rate**: 100%

## Historical Analysis (October 2025)

### Previous Issues
The document below reflects the troubleshooting state as of October 2025, when Landsat processing was failing due to resource constraints.
```
/tmp/glacier_processing/output/  (base_dir)
├── 134_Arsuk/                   (output_dir - line 162)
│   └── *.tif                    (downloaded scenes)
└── reference/                   (reference_dir - unknown location)
    ├── 134_Arsuk.tif           (template)
    └── 134_Arsuk_stac_query_results.csv
```

**Question:** Where is `reference_dir` set? Not visible in this function signature.

### 3. Error Handling
Current error handling in download loop (lines 176-197):
```python
except Exception as error:
    logging.info(logstr)
    # ... continues without raising
```

This could silently skip all downloads if template creation fails.

## Differences from Sentinel-2

### Sentinel-2 Processing
- Direct download and merge workflow
- Clear output structure: `{region}/clipped/`, `{region}/download/`, `{region}/template/`
- Uploads 8 files per region

### Landsat Processing
- Download + clip + reproject workflow
- Template-based reprojection (creates reference TIF first)
- Output structure: `{base_dir}/{region_name}/*.tif`
- Requires AWS credentials for requester-pays bucket

## Investigation Plan

### Step 1: Check where reference_dir is defined
```bash
grep -n "reference_dir" 1_download_merge_and_clip/landsat/download_clip_landsat.py
```

### Step 2: Verify directory creation
Check if Lambda has permissions to create directories in `/tmp/glacier_processing/output/`

### Step 3: Add verbose logging (optional)
Could add logging between each major step to identify exact failure point, but should understand existing code first.

### Step 4: Check S3 for partial results
```bash
aws s3 ls s3://greenland-glacier-data/results/ --recursive | grep -i landsat
```

### Step 5: Check CloudWatch for complete logs
Look for any ERROR level messages or stack traces that might have been missed.

## Related Files to Study

1. **download_clip_landsat.py** - Main script that calls `search_and_download_region()`
2. **functions.py** - Contains the core download logic
3. **defaults.py** - Default parameters and paths
4. **lambda_handler.py** - How Lambda invokes the script

## Next Steps

Before modifying code:
1. Understand how `reference_dir` is set
2. Check if template creation is actually happening
3. Verify output directory structure expectations
4. Compare with successful HPC runs (if available)


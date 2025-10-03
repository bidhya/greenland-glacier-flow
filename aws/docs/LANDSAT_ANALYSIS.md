# Landsat Processing Analysis - October 3, 2025

## Current Behavior

### Test Parameters
- Region: 134_Arsuk
- Date range: 2024-07-01 to 2024-07-08 (1 week)
- Result: statusCode 200, 0 files uploaded

### Script Output
```
STAC query returned 2 scenes.
After removing already downloaded, 2 scenes remain to download.
Finished.
```

## Code Flow Analysis

### Expected Flow (from functions.py)

1. **STAC Search** (lines 73-87)
   - ✅ Working: Found 2 scenes

2. **Filter Downloaded** (lines 93-104)
   - ✅ Working: 2 scenes remained after filtering

3. **Export CSV** (line 107-108)
   - ❓ Unknown: Should create `{reference_dir}/{region_name}_stac_query_results.csv`

4. **Create Template TIF** (lines 115-127)
   - ❓ Missing: Should print "Creating reference image to resample to..."
   - Creates: `{reference_dir}/{region_name}.tif`

5. **Open Template** (line 130)
   - ❓ Missing: Uses `rxr.open_rasterio(sample_fpath)`

6. **Download Scenes** (lines 143-197)
   - ❌ Missing: Should print "Downloading 2 scenes."
   - Should download to: `{base_dir}/{region_name}/*.tif`

## Key Questions

### 1. Where is the script exiting?
The script completes successfully but skips steps 4-6. Possible causes:
- Silent exception in template creation/opening
- Early return statement triggered
- Missing directory causing os.mkdir() to fail

### 2. Directory Structure
**Expected structure:**
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


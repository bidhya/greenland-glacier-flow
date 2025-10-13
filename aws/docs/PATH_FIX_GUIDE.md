# Path Resolution Fix for AWS Lambda Glacier Processing

## Problem Encountered (October 2, 2025)

When running Sentinel-2 processing on AWS Lambda, the script failed to find the glacier regions file even though it was successfully downloaded from S3.

### Error Symptoms
```
FileNotFoundError: [Errno 2] No such file or directory: 
'/tmp/greenland-glacier-flow/1_download_merge_and_clip/sentinel2/ancillary/glacier_roi_v2/glaciers_roi_proj_v3_300m.gpkg'
```

### Root Cause Analysis

**Directory Structure:**
```
/tmp/greenland-glacier-flow/
├── 1_download_merge_and_clip/
│   ├── sentinel2/              # Script location
│   │   └── download_merge_clip_sentinel2.py
│   └── ancillary/              # Sibling directory (NOT child)
│       └── glacier_roi_v2/
│           └── glaciers_roi_proj_v3_300m.gpkg
```

**Incorrect Path Logic:**
```python
script_dir = Path(__file__).resolve().parent
# Results in: /tmp/greenland-glacier-flow/1_download_merge_and_clip/sentinel2

glacier_regions_path = script_dir / 'ancillary' / 'glacier_roi_v2' / 'glaciers_roi_proj_v3_300m.gpkg'
# Results in: /tmp/greenland-glacier-flow/1_download_merge_and_clip/sentinel2/ancillary/...
# ❌ WRONG: ancillary is NOT inside sentinel2 folder
```

**The Issue:** 
- `ancillary/` is a **sibling** directory to `sentinel2/`, not a child
- Both are under `1_download_merge_and_clip/`
- Need to go up one level (`.parent`) to access the sibling

## Solution

**Corrected Path Logic:**
```python
script_dir = Path(__file__).resolve().parent
# Results in: /tmp/greenland-glacier-flow/1_download_merge_and_clip/sentinel2

glacier_regions_path = script_dir.parent / 'ancillary' / 'glacier_roi_v2' / 'glaciers_roi_proj_v3_300m.gpkg'
# Results in: /tmp/greenland-glacier-flow/1_download_merge_and_clip/ancillary/...
# ✅ CORRECT: Uses .parent to go up to 1_download_merge_and_clip, then accesses ancillary
```

## Files Modified

### `/1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py`
**Line 145 changed from:**
```python
glacier_regions_path = script_dir / 'ancillary' / 'glacier_roi_v2' / 'glaciers_roi_proj_v3_300m.gpkg'
```

**To:**
```python
glacier_regions_path = script_dir.parent / 'ancillary' / 'glacier_roi_v2' / 'glaciers_roi_proj_v3_300m.gpkg'
```

## Deployment Steps After Fix

1. **Upload fixed script to S3:**
   ```bash
   cd /mnt/c/Github/greenland-glacier-flow
   aws s3 cp 1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py \
     s3://greenland-glacier-data/scripts/greenland-glacier-flow/1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py
   ```

2. **No Docker rebuild needed:** Lambda downloads scripts from S3 at runtime

3. **Test immediately:**
   ```bash
   aws lambda invoke --function-name glacier-sentinel2-processor \
     --payload '{"satellite": "sentinel2", "regions": "134_Arsuk", "date1": "2024-08-01", "date2": "2024-08-01", "s3_bucket": "greenland-glacier-data"}' \
     result.json
   ```

## Verification

**Success Indicators:**
```json
{
  "statusCode": 200,
  "uploaded_files": 8,
  "message": "Sentinel-2 processing completed successfully"
}
```

**Files in S3:**
```
results/lambda-sentinel2-134_Arsuk/
├── 134_Arsuk/
│   ├── clipped/
│   │   └── S2B_MSIL2A_20240801T143749_N0511_R039.tif (1.7 MB)
│   ├── template/
│   │   └── 134_Arsuk.tif (1.7 MB)
│   ├── download/2024/
│   │   ├── S2B_..._T22VFN_..._B08.tif (172 MB)
│   │   ├── S2B_..._T22VFP_..._B08.tif (201 MB)
│   │   ├── S2B_..._T23VLH_..._B08.tif (178 MB)
│   │   └── S2B_..._T23VLJ_..._B08.tif (191 MB)
│   └── metadata/
│       ├── individual_csv/
│       │   └── S2B_MSIL2A_20240801T143749_N0511_R039.csv
│       └── combined_csv/
│           └── 134_Arsuk.csv
```

## Lessons Learned

1. **Path Resolution Pitfalls:**
   - Always consider directory structure carefully
   - Don't assume relative paths without testing across environments
   - Use `.parent` to navigate up directory tree when needed

2. **Lambda-Specific Considerations:**
   - Scripts downloaded to `/tmp/greenland-glacier-flow/` maintain original structure
   - Path logic must work with this structure
   - Test with actual Lambda environment, not just local

3. **Debugging Tips:**
   - Check CloudWatch logs for FileNotFoundError messages
   - Verify S3 sync uploaded all necessary files
   - Confirm directory structure matches expectations

4. **Prevention:**
   - Document directory structure assumptions
   - Add path validation/logging in critical scripts
   - Test with clean S3 bucket to verify full workflow

## Related Documentation
- Main guide: `/AGENTS.md` (Path Handling Simplification section)
- Lambda deployment: `/aws/docs/LAMBDA_DEPLOYMENT_GUIDE.md`
- Session summary: `/aws/docs/SESSION_SUMMARY_2025-10-02.md`

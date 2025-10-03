# OBSOLETE FILE - Historical Reference Only

This file has been superseded by the complete project upload approach used in the current Lambda container system.

## Why This File is Obsolete

### Original Purpose (Deprecated)
- Uploaded individual Sentinel-2 processing scripts to S3
- Limited to specific script files only
- Missing complete project context

### Current Approach (Active) 
- Lambda downloads complete `greenland-glacier-flow` project from S3
- Full project context available in Lambda execution
- Complete dependency and configuration access

### Evidence of Obsolescence
```bash
# Old approach files (this script created these):
s3://greenland-glacier-data/scripts/1_download_merge_and_clip/sentinel2/

# Current approach (what Lambda actually uses):
s3://greenland-glacier-data/scripts/greenland-glacier-flow/
```

### Replacement
The complete project upload is now handled by:
- `../../upload_scripts_to_s3.sh` (main project directory)
- Lambda handler automatically downloads complete project via boto3

## File Status: ❌ OBSOLETE - Safe to Delete

This file is kept for historical reference only. The Lambda container system uses complete project download for full functionality.

Date Obsoleted: October 2, 2025
Reason: Replaced by complete project upload approach
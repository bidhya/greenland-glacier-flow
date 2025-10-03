# Fresh Download Workflow - AWS Lambda Sentinel-2 Processing

## Quick Start: Fresh S3 Download

This guide documents the successful workflow for deleting old data and running a fresh Sentinel-2 download on AWS Lambda (tested October 2, 2025).

## Prerequisites

- AWS CLI configured with appropriate credentials
- Access to `greenland-glacier-data` S3 bucket
- Lambda function `glacier-sentinel2-processor` deployed
- Project files synced to S3 (if not, follow sync steps below)

## Step-by-Step Workflow

### 1. Clean S3 Bucket (Optional)

Delete old results and scripts:

```bash
# Delete results folder
aws s3 rm s3://greenland-glacier-data/results/ --recursive

# Delete scripts folder
aws s3 rm s3://greenland-glacier-data/scripts/ --recursive

# Verify bucket is clean
aws s3 ls s3://greenland-glacier-data/
```

### 2. Sync Project Files to S3

Upload complete project to S3 for Lambda to download:

```bash
cd /mnt/c/Github/greenland-glacier-flow

# Sync project files (excluding unnecessary files)
aws s3 sync . s3://greenland-glacier-data/scripts/greenland-glacier-flow/ \
  --exclude ".git/*" \
  --exclude "*.pyc" \
  --exclude "__pycache__/*" \
  --exclude ".vscode/*" \
  --exclude "*.log" \
  --exclude "test_*.json" \
  --exclude "result*.json" \
  --exclude "fresh_*.json" \
  --delete
```

**Verify sync:**
```bash
# Check sentinel2 scripts
aws s3 ls s3://greenland-glacier-data/scripts/greenland-glacier-flow/1_download_merge_and_clip/sentinel2/ --recursive

# Check ancillary data
aws s3 ls s3://greenland-glacier-data/scripts/greenland-glacier-flow/1_download_merge_and_clip/ancillary/glacier_roi_v2/
```

### 3. Ensure Path Fix is Applied

**Critical:** Verify the sentinel2 script uses correct path for ancillary folder:

```bash
# Check local file has the fix
grep -A 2 "glacier_regions_path" 1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py
# Should show: script_dir.parent / 'ancillary' / ...

# If fix is missing, apply it:
# Change: script_dir / 'ancillary' / ...
# To:     script_dir.parent / 'ancillary' / ...
```

**Upload fixed script (if needed):**
```bash
aws s3 cp 1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py \
  s3://greenland-glacier-data/scripts/greenland-glacier-flow/1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py
```

### 4. Run Fresh Sentinel-2 Download

```bash
cd /mnt/c/Github/greenland-glacier-flow/aws/scripts

# Create test payload (or use existing)
cat > fresh_sentinel2.json << 'EOF'
{
  "satellite": "sentinel2",
  "regions": "134_Arsuk",
  "start_date": "2024-08-01",
  "end_date": "2024-08-01",
  "s3_bucket": "greenland-glacier-data"
}
EOF

# Invoke Lambda
aws lambda invoke \
  --function-name glacier-sentinel2-processor \
  --payload file://fresh_sentinel2.json \
  fresh_sentinel2_result.json

# Check result
cat fresh_sentinel2_result.json | jq '.'
```

### 5. Verify Results

**Check Lambda response:**
```bash
# Should show statusCode: 200
cat fresh_sentinel2_result.json | jq '{statusCode, uploaded_files: (.body | fromjson | .uploaded_files)}'
```

**Expected output:**
```json
{
  "statusCode": 200,
  "uploaded_files": 8
}
```

**Check S3 results:**
```bash
# List uploaded files
aws s3 ls s3://greenland-glacier-data/results/ --recursive

# Count files for region
aws s3 ls s3://greenland-glacier-data/results/lambda-sentinel2-134_Arsuk/ --recursive | wc -l
# Should show: 8
```

**Expected files structure:**
```
results/lambda-sentinel2-134_Arsuk/
├── 134_Arsuk/
│   ├── clipped/
│   │   └── S2B_MSIL2A_20240801T143749_N0511_R039.tif (1.7 MB)
│   ├── template/
│   │   └── 134_Arsuk.tif (1.7 MB)
│   ├── download/2024/
│   │   ├── S2B_..._T22VFN_..._B08.tif (~172 MB)
│   │   ├── S2B_..._T22VFP_..._B08.tif (~201 MB)
│   │   ├── S2B_..._T23VLH_..._B08.tif (~178 MB)
│   │   └── S2B_..._T23VLJ_..._B08.tif (~191 MB)
│   └── metadata/
│       ├── individual_csv/
│       │   └── S2B_MSIL2A_20240801T143749_N0511_R039.csv
│       └── combined_csv/
│           └── 134_Arsuk.csv
```

### 6. Check CloudWatch Logs (Optional)

```bash
# Get recent logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/glacier-sentinel2-processor \
  --start-time $(($(date +%s) * 1000 - 300000)) \
  --max-items 50 | jq -r '.events[].message' | tail -40
```

## Troubleshooting

### Issue: FileNotFoundError for glacier_regions_path

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: 
'/tmp/greenland-glacier-flow/1_download_merge_and_clip/sentinel2/ancillary/glacier_roi_v2/glaciers_roi_proj_v3_300m.gpkg'
```

**Solution:** Apply path fix (see Step 3) - use `script_dir.parent / 'ancillary'`

### Issue: No logger output in CloudWatch

**Symptom:** Only see START/END/REPORT messages, no INFO logs

**Cause:** Logger configuration in Lambda
**Solution:** Check lambda_handler.py has logging configured

### Issue: Processing fails with return code 1

**Symptom:** Script starts but exits immediately

**Troubleshooting steps:**
1. Check stdout/stderr in Lambda response
2. Verify all required files synced to S3
3. Check glacier regions file path is correct
4. Ensure ancillary folder uploaded to S3

### Issue: Scripts not downloading from S3

**Symptom:** Error about missing /tmp/greenland-glacier-flow directory

**Solution:** 
1. Verify S3 prefix: `scripts/greenland-glacier-flow/`
2. Check S3 bucket permissions
3. Confirm Lambda has S3 read permissions

## Performance Metrics

**Typical Processing Time (Sentinel-2):**
- Region: 134_Arsuk
- Date range: Single day (2024-08-01)
- Processing time: ~55 seconds
- Files uploaded: 8
- Total data: ~750 MB

**Lambda Resources Used:**
- Memory allocated: 5120 MB (5 GB)
- Max memory used: ~345 MB
- Ephemeral storage: 10 GB
- Timeout: 900s (15 minutes)

## Success Criteria

✅ **Fresh download successful when:**
1. Lambda returns statusCode: 200
2. 8 files uploaded to S3 results folder
3. Processing stdout shows "Finished."
4. CloudWatch logs show no errors
5. S3 files have correct timestamps
6. File sizes match expected ranges

## Related Documentation

- Path fix details: `/aws/docs/PATH_FIX_GUIDE.md`
- Lambda deployment: `/aws/docs/LAMBDA_DEPLOYMENT_GUIDE.md`
- Main architecture: `/AGENTS.md`
- Troubleshooting: `/aws/docs/LANDSAT_LAMBDA_TROUBLESHOOTING.md`

## Testing with Different Regions/Dates

**Different region:**
```json
{
  "satellite": "sentinel2",
  "regions": "101_sermiligarssuk",
  "start_date": "2024-08-01",
  "end_date": "2024-08-01",
  "s3_bucket": "greenland-glacier-data"
}
```

**Different date range:**
```json
{
  "satellite": "sentinel2",
  "regions": "134_Arsuk",
  "start_date": "2024-07-01",
  "end_date": "2024-07-31",
  "s3_bucket": "greenland-glacier-data"
}
```

**Multiple regions (if supported):**
```json
{
  "satellite": "sentinel2",
  "regions": "134_Arsuk,101_sermiligarssuk",
  "start_date": "2024-08-01",
  "end_date": "2024-08-01",
  "s3_bucket": "greenland-glacier-data"
}
```

## Automation Potential

This workflow can be automated with:
- AWS Step Functions for orchestration
- EventBridge for scheduled processing
- SNS for notifications on completion
- DynamoDB for tracking processing history

---

**Last Updated:** October 2, 2025  
**Tested Environment:** AWS Lambda (Python 3.12), us-west-2 region  
**Success Rate:** 100% after path fix applied

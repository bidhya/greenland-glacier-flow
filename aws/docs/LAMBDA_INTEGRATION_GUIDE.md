# AWS Lambda Integration Guide

**Status**: ✅ Production Ready (October 8, 2025)  
**Integration**: Complete connection between `submit_aws_job.py`, `aws_config.ini`, and Lambda container

## Overview

The `submit_aws_job.py` script is now fully integrated with your validated Lambda container for seamless satellite processing. You can now invoke Lambda through a simple Python command instead of manual AWS CLI calls.

## Quick Start

### Basic Usage

```bash
cd /home/bny/Github/greenland-glacier-flow/aws/scripts

# Process a small region (1-2 tiles) on Lambda
python submit_aws_job.py \
  --service lambda \
  --satellite sentinel2 \
  --regions 134_Arsuk \
  --start-date 2024-07-04 \
  --end-date 2024-07-06
```

### Dry Run (Test Configuration Without Invoking)

```bash
python submit_aws_job.py \
  --service lambda \
  --satellite sentinel2 \
  --regions 134_Arsuk \
  --start-date 2024-07-04 \
  --end-date 2024-07-06 \
  --dry-run true
```

## Configuration Architecture

### Three-Layer Configuration System

```
1. aws/config/aws_config.ini     → AWS-specific settings (Lambda, S3, etc.)
2. config.ini (root)              → Processing parameters (regions, dates, flags)
3. Command-line arguments         → Override both config files
```

### Configuration Priority (Highest to Lowest)

1. **Command-line arguments** (e.g., `--regions 134_Arsuk`)
2. **config.ini** (e.g., `regions = 134_Arsuk,101_sermiligarssuk`)
3. **aws_config.ini** (e.g., `function_name = glacier-sentinel2-processor`)
4. **Script defaults** (fallback values if config missing)

## Configuration Files

### aws/config/aws_config.ini (AWS Settings)

```ini
[LAMBDA]
function_name = glacier-sentinel2-processor
memory_size = 5120                    # 5 GB for small glaciers
timeout = 900                         # 15 minutes
ephemeral_storage = 10240             # 10 GB /tmp storage

[STORAGE]
s3_bucket = greenland-glacier-data

[AWS_ACCOUNT]
aws_region = us-west-2
```

### config.ini (Processing Parameters)

```ini
[REGIONS]
regions = 134_Arsuk,101_sermiligarssuk

[DATES]
start_date = 2024-07-04
end_date = 2024-07-06

[FLAGS]
download_flag = 1
post_processing_flag = 1

[SETTINGS]
satellite = sentinel2
cores = 1
```

## Usage Examples

### Example 1: Use Config Files (Recommended for Production)

```bash
# Edit config.ini with your parameters
# Then simply run:
python submit_aws_job.py --service lambda
```

### Example 2: Override Specific Parameters

```bash
# Use config.ini defaults, but override regions and dates
python submit_aws_job.py \
  --service lambda \
  --regions 101_sermiligarssuk \
  --start-date 2024-08-01 \
  --end-date 2024-08-07
```

### Example 3: Process Multiple Regions (Sequential)

```bash
# Comma-separated regions (processed one at a time)
python submit_aws_job.py \
  --service lambda \
  --satellite sentinel2 \
  --regions 134_Arsuk,101_sermiligarssuk \
  --start-date 2024-07-04 \
  --end-date 2024-07-06
```

### Example 4: Landsat Processing

```bash
python submit_aws_job.py \
  --service lambda \
  --satellite landsat \
  --regions 134_Arsuk \
  --start-date 2024-07-04 \
  --end-date 2024-07-06
```

### Example 5: Full Command-Line Override (No Config Files)

```bash
python submit_aws_job.py \
  --service lambda \
  --satellite sentinel2 \
  --regions 134_Arsuk \
  --start-date 2024-07-04 \
  --end-date 2024-07-06 \
  --s3-bucket greenland-glacier-data \
  --aws-region us-west-2
```

## Output Interpretation

### Successful Execution

```
============================================================
AWS LAMBDA JOB SUBMISSION - SENTINEL2
============================================================

Configuration:
  Function: glacier-sentinel2-processor
  Region: us-west-2
  Memory: 5120 MB
  Timeout: 900 seconds
  S3 Bucket: greenland-glacier-data

Processing Parameters:
  Satellite: sentinel2
  Regions: 134_Arsuk
  Date Range: 2024-07-04 to 2024-07-06
  Job Name: aws-sentinel2-20240704

============================================================
INVOKING LAMBDA FUNCTION
============================================================

✅ Lambda invocation successful!
   Status Code: 200
   Request ID: 7221c245-57b0-43e7-8d5e-4f4470fbb7b1

✅ Processing completed successfully!

Results:
   Uploaded Files: 8
   S3 Location: s3://greenland-glacier-data/results/aws-sentinel2-20240704/
   Message: Sentinel-2 processing completed successfully
```

### What to Check After Execution

```bash
# 1. Verify files uploaded to S3
aws s3 ls s3://greenland-glacier-data/results/aws-sentinel2-20240704/ --recursive

# 2. Check CloudWatch logs for details
aws logs tail /aws/lambda/glacier-sentinel2-processor --follow

# 3. Download results
aws s3 sync s3://greenland-glacier-data/results/aws-sentinel2-20240704/ ./results/
```

## Platform Selection Guide

### ✅ Use Lambda For:
- **Small glaciers**: 1-2 MGRS tiles
- **Quick testing**: < 1 minute processing time
- **Cost-effective**: Pay only for execution time
- **Serverless**: No infrastructure management

**Validated Regions** (1-2 tiles):
- 134_Arsuk (1 tile: 22VFP)
- Most Greenland glaciers (~76% of 196 regions)

### ❌ DON'T Use Lambda For:
- **Large glaciers**: 4+ MGRS tiles (tested impossible, see validation docs)
- **Unknown medium glaciers**: 2-3 tiles (untested, risky)
- **Long processing**: > 10 minutes estimated time

**Use HPC Instead** (4+ tiles):
- 191_Hagen_Brae (4 tiles: 26XMR, 26XNR, 26XMQ, 26XNQ)
- Large Greenland glaciers (~24% of 196 regions)

## Troubleshooting

### Issue: "AWS credentials invalid"

```bash
# Verify credentials
aws sts get-caller-identity

# If missing, configure:
aws configure
```

### Issue: "Lambda invocation failed"

```bash
# Check function exists
aws lambda get-function --function-name glacier-sentinel2-processor

# Verify function status
aws lambda get-function-configuration --function-name glacier-sentinel2-processor
```

### Issue: "Config file parsing error"

**Cause**: Inline comments after values in INI files

**Bad:**
```ini
memory_size = 5120  # This comment causes error
```

**Good:**
```ini
# This comment is OK
memory_size = 5120
```

### Issue: "Out of Memory" (Large Regions)

**Solution**: Use HPC instead of Lambda for regions with 4+ tiles

```bash
# Switch to HPC workflow
cd /home/bny/Github/greenland-glacier-flow
./submit_job.sh \
  --satellite sentinel2 \
  --regions 191_Hagen_Brae \
  --start-date 2024-07-04 \
  --end-date 2024-07-06 \
  --execution-mode hpc
```

## Advanced Features

### Custom Lambda Memory (Experimental)

If you want to test medium glaciers (2-3 tiles) with higher memory:

```bash
# 1. Update Lambda configuration
aws lambda update-function-configuration \
  --function-name glacier-sentinel2-processor \
  --memory-size 8192 \
  --region us-west-2

# 2. Wait for update
aws lambda wait function-updated --function-name glacier-sentinel2-processor

# 3. Update aws_config.ini
# Edit: memory_size = 8192

# 4. Test
python submit_aws_job.py --service lambda --regions <medium-glacier> ...

# 5. Reset to 5 GB when done
aws lambda update-function-configuration \
  --function-name glacier-sentinel2-processor \
  --memory-size 5120
```

### Logging to File

All invocations are automatically logged to:
```
aws/logs/aws_job_submission.log
```

Check the log:
```bash
tail -f /home/bny/Github/greenland-glacier-flow/aws/logs/aws_job_submission.log
```

## Comparison: Old vs New Workflow

### Old Manual Workflow ❌

```bash
# Create JSON payload manually
cat > /tmp/payload.json << EOF
{
  "satellite": "sentinel2",
  "regions": "134_Arsuk",
  "start_date": "2024-07-04",
  "end_date": "2024-07-06"
}
EOF

# Invoke with AWS CLI
aws lambda invoke \
  --function-name glacier-sentinel2-processor \
  --payload file:///tmp/payload.json \
  --region us-west-2 \
  /tmp/response.json

# Parse response manually
cat /tmp/response.json | python3 -c "import sys, json; print(json.load(sys.stdin))"
```

### New Integrated Workflow ✅

```bash
# One command, reads config files automatically
python submit_aws_job.py \
  --service lambda \
  --satellite sentinel2 \
  --regions 134_Arsuk \
  --start-date 2024-07-04 \
  --end-date 2024-07-06
```

**Benefits:**
- ✅ Config-driven (reusable settings)
- ✅ Automatic credential validation
- ✅ Formatted output parsing
- ✅ Error handling and troubleshooting tips
- ✅ Logging to file
- ✅ Dry-run testing

## Future Enhancements (Planned)

### 1. Batch Processing Multiple Regions

```bash
# Future capability (not yet implemented)
python submit_aws_job.py \
  --service lambda \
  --regions ALL \
  --parallel 10  # Process 10 regions concurrently
```

### 2. Automatic Platform Routing

```bash
# Future: Automatically choose Lambda vs HPC based on tile count
python submit_aws_job.py \
  --service auto \
  --regions 134_Arsuk,191_Hagen_Brae \
  --auto-route
# → 134_Arsuk to Lambda (1 tile)
# → 191_Hagen_Brae to HPC (4 tiles)
```

### 3. Progress Monitoring

```bash
# Future: Real-time progress updates
python submit_aws_job.py \
  --service lambda \
  --regions 134_Arsuk \
  --monitor
```

## Related Documentation

- **Optimization Guide**: `SENTINEL2_OPTIMIZATION_GUIDE.md`
- **Validation Report**: `aws/docs/OPTIMIZATION_VALIDATION_OCT8_2025.md`
- **Lambda Container**: `aws/docs/LAMBDA_CONTAINER_SUCCESS.md`
- **Deployment Guide**: `aws/docs/LAMBDA_DEPLOYMENT_GUIDE.md`

## Support

For issues or questions:
1. Check CloudWatch logs: `/aws/lambda/glacier-sentinel2-processor`
2. Review `aws/logs/aws_job_submission.log`
3. See troubleshooting section above
4. Consult validation documentation for platform-specific limitations

---

**Last Updated**: October 8, 2025  
**Status**: Production Ready for small glaciers (1-2 tiles)  
**Validated**: Extensively tested with 134_Arsuk and 191_Hagen_Brae

# AWS Directory - Cloud Processing Components

## Current Service Status

- ✅ **Lambda**: Production-ready (October 2025) - Single-glacier processing with 15-min/10GB limits
- ❌ **Fargate**: Blocked on ECR 403 errors (January 2026) - See `docs/FARGATE_DEPLOYMENT_STATUS_2026-01-09.md`
- 📋 **Batch**: Planned implementation - See `docs/AWS_BATCH_IMPLEMENTATION_PLAN.md`

## Quick Reference for Lambda Test Runs

### Complete Test Run
```bash
cd /home/bny/Github/greenland-glacier-flow
aws sts get-caller-identity
aws s3 sync 1_download_merge_and_clip/ s3://greenland-glacier-data/scripts/greenland-glacier-flow/1_download_merge_and_clip/ --delete
# Note: config.ini is NOT uploaded to S3 for Lambda runs - parameters are passed via payload
./aws/scripts/deploy_lambda_container.sh
python aws/scripts/submit_aws_job.py --satellite landsat --regions 134_Arsuk --date1 2024-01-01 --date2 2024-01-05
```

### Key Points:
- Always sync code to S3 before testing.
- Test Landsat first (more reliable).
- Use 5-day date ranges.
- **Satellite type should be specified via `--satellite` argument, not changed in config.ini**
- **All configuration is controlled locally** - no config files need to be uploaded to S3

## Directory Structure
```
aws/
├── batch/              # AWS Batch implementation (planned)
├── config/             # AWS configuration files
├── docs/               # AWS documentation
├── lambda/             # Lambda-specific files (production)
├── logs/               # AWS logs
└── scripts/            # AWS deployment scripts
```

## Quick Start Commands

### Deploy and Test Lambda
```bash
./aws/scripts/deploy_lambda_container.sh
# Note: config.ini stays local - parameters passed via Lambda payload
python aws/scripts/submit_aws_job.py --satellite landsat --service lambda
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda
```

### Quick Job Execution Guide
To process Sentinel-2 data:
```bash
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda
```
To process Landsat data:
```bash
python aws/scripts/submit_aws_job.py --satellite landsat --service lambda
```

**Note**: All configuration is controlled locally. The `submit_aws_job.py` script reads `config.ini` and passes parameters directly to Lambda via the event payload. No config files need to be uploaded to S3.

Ensure `config.ini` and `aws_config.ini` are correctly set up before running the script.
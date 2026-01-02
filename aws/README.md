# AWS Directory - Cloud Processing Components

## Quick Reference for AWS Test Runs

### **Complete Test Run**
```bash
cd /home/bny/Github/greenland-glacier-flow
aws sts get-caller-identity
aws s3 sync 1_download_merge_and_clip/ s3://greenland-glacier-data/scripts/greenland-glacier-flow/1_download_merge_and_clip/ --delete
aws s3 cp config.ini s3://greenland-glacier-data/scripts/greenland-glacier-flow/config.ini
./aws/scripts/deploy_lambda_container.sh
python aws/scripts/submit_aws_job.py --satellite landsat --regions 134_Arsuk --date1 2024-01-01 --date2 2024-01-05
aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/landsat/134_Arsuk/ --recursive | wc -l
```

### **Key Points:**
- Always sync code to S3 before testing
- Test Landsat first (more reliable)
- Use 5-day date ranges
- Check S3 results (~5 files for Landsat)

## Directory Structure

```
aws/
├── config/             # AWS configuration files
├── docs/               # AWS documentation
├── lambda/             # Lambda-specific files
├── logs/               # AWS logs
└── scripts/            # AWS deployment scripts
```

## Key Components

### 1. Main AWS Job Submission (`scripts/submit_aws_job.py`)
- Unified interface for AWS services (Batch, ECS, Lambda)

### 2. Lambda Container System (`lambda/`)
- Production Lambda handler with geospatial libraries
- Containerized Python 3.12 environment

### 3. Deployment Automation (`scripts/`)
- Container deployment and testing scripts

### 4. Configuration Management (`config/`)
- AWS settings and IAM policies

## AWS File Organization and Syncing

### S3 Bucket Structure
```
greenland-glacier-data/
├── scripts/greenland-glacier-flow/     # Project codebase for Lambda
│   ├── config.ini                      # Active config file
│   └── 1_download_merge_and_clip/      # Processing scripts
└── 1_download_merge_and_clip/          # Processing results
    ├── landsat/                        # Landsat data
    └── sentinel2/                      # Sentinel-2 data
```

### File Synchronization
```bash
# Sync processing scripts
aws s3 sync 1_download_merge_and_clip/ s3://greenland-glacier-data/scripts/greenland-glacier-flow/1_download_merge_and_clip/ --delete

# Sync config file
aws s3 cp config.ini s3://greenland-glacier-data/scripts/greenland-glacier-flow/config.ini
```

## AWS Test Run Workflow

### Prerequisites
- [ ] AWS CLI configured
- [ ] S3 bucket `greenland-glacier-data` exists
- [ ] Lambda function `glacier-sentinel2-processor` deployed

### Step-by-Step Test
1. **Verify AWS access**: `aws sts get-caller-identity`
2. **Sync code to S3**: Run sync commands above
3. **Deploy container**: `./aws/scripts/deploy_lambda_container.sh`
4. **Execute test**: `python aws/scripts/submit_aws_job.py --satellite landsat --regions 134_Arsuk --date1 2024-01-01 --date2 2024-01-05`
5. **Verify results**: Check S3 for output files

## S3 Bucket Structure

**Bucket:** `greenland-glacier-data`

```
greenland-glacier-data/
├── 1_download_merge_and_clip/          # Processed satellite data
│   ├── landsat/                        # Landsat orthorectified imagery
│   │   ├── {region_name}/              # Individual glacier regions
│   │   └── _reference/                 # STAC metadata and templates
│   └── sentinel2/                      # Sentinel-2 processed data
│       ├── {region_name}/              # Individual glacier regions
│       └── _reference/                 # STAC metadata and templates
└── scripts/greenland-glacier-flow/     # Project codebase for Lambda
    ├── config.ini                      # ⚠️ ACTIVE CONFIG FILE LOCATION
    └── [all project files...]          # Complete repository backup
```

**⚠️ Critical:** Config file must be synced to S3 for Lambda functions to access updated settings.

## Quick Start Commands

### Deploy and Test Lambda
```bash
# Deploy updated Lambda container
./aws/scripts/deploy_lambda_container.sh

# Sync config to S3 (required for Lambda)
aws s3 cp config.ini s3://greenland-glacier-data/scripts/greenland-glacier-flow/config.ini

# Test Landsat processing
python aws/scripts/submit_aws_job.py --satellite landsat --service lambda

# Test Sentinel-2 processing
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda
```

## Support and Troubleshooting

### Processing Status
- **Landsat**: ✅ Production ready - reliable processing
- **Sentinel-2**: ✅ Working but may timeout on large regions

### Common Issues
1. **IAM Permissions**: Ensure Lambda has S3 access
2. **Container Size**: Monitor 1.4GB image size limits
3. **Timeout Settings**: Lambda may need 15+ minute timeouts
4. **Sync Required**: Always sync code to S3 before testing

### Debug Resources
- **CloudWatch Logs**: `/aws/lambda/glacier-sentinel2-processor`
- **ECR Repository**: `glacier-sentinel2-processor`
- **S3 Bucket**: `greenland-glacier-data`

### Documentation Quick Reference
- **Setup Status**: `docs/AWS_SETUP_STATUS.md`
- **Deployment**: `docs/LAMBDA_DEPLOYMENT_GUIDE.md`
- **Troubleshooting**: `docs/LANDSAT_LAMBDA_TROUBLESHOOTING.md`
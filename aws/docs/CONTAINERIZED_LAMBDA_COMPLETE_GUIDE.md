# Complete Containerized Lambda Deployment Guide
## Greenland Glacier Flow Processing - Production Ready (January 23, 2026)

**Purpose**: Complete, copy-paste guide to recreate containerized AWS Lambda for satellite processing after all resources are deleted.

**Status**: ✅ **PRODUCTION VALIDATED** - Both Sentinel-2 (102s) and Landsat (4s) processing confirmed working
**Architecture**: Self-contained Docker container with all code and dependencies baked in
**Requirements**: No S3 code sync required - container includes complete processing pipeline

---

## 📋 Prerequisites

### Required Tools & Accounts
```bash
# Verify installations
aws --version                    # AWS CLI
docker --version                 # Docker
python --version                 # Python 3.13+
pip install boto3                # AWS Python SDK

# Verify AWS access
aws sts get-caller-identity      # Should show YOUR actual AWS account ID (not 123456789012)
aws configure list               # Verify us-west-2 region

> **⚠️ IMPORTANT**: The account ID `123456789012` shown in examples is a placeholder.
> Replace it with your actual AWS account ID in all configuration files and commands.
```

### Required Permissions
Your IAM user needs these permissions (attach `aws/config/minimal-lambda-policy.json`):
- Lambda function management (create/update/delete/invoke)
- IAM role management (create roles, attach policies)
- ECR repository management
- S3 bucket access (for results storage)

### ⚠️ Important: Placeholder Values
This guide contains placeholder AWS account IDs for security reasons:
- `123456789012` - Replace with your actual AWS account ID
- `123456789012` - Replace with your actual AWS account ID in IAM role ARNs

**Before running any commands:**
1. Edit `aws/config/aws_config.ini` and replace placeholder account IDs
2. Update any hardcoded account IDs in scripts you plan to use
3. Verify `aws sts get-caller-identity` shows your actual account ID

---

## 🚀 Complete Deployment Workflow

### Phase 1: Environment Setup

#### Step 1: Create S3 Bucket (if needed)
```bash
# Create bucket for processing results
aws s3 mb s3://greenland-glacier-data --region us-west-2

# Verify bucket creation
aws s3 ls s3://greenland-glacier-data/
```

#### Step 2: Create Lambda Execution Role
```bash
# Create the IAM role for Lambda execution
aws iam create-role \
  --role-name lambda-glacier-execution-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "lambda.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }'

# Attach required policies
aws iam attach-role-policy \
  --role-name lambda-glacier-execution-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Wait for role propagation (important!)
sleep 30

# Verify role creation
aws iam get-role --role-name lambda-glacier-execution-role
```

#### Step 3: Update VPC Endpoint Policy (if using VPC)
If you're using a VPC with S3 endpoints, update the VPC endpoint policy to allow ECR image pulls:

```bash
# Find your S3 VPC endpoint ID
aws ec2 describe-vpc-endpoints --filters Name=service-name,Values=com.amazonaws.us-west-2.s3

# Update the policy (replace vpce-xxxxx with your endpoint ID)
aws ec2 modify-vpc-endpoint \
  --vpc-endpoint-id vpce-0466ad77a879d944a \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "AllowS3AccessToBucketFromVpc",
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:*",
        "Resource": [
          "arn:aws:s3:::greenland-glacier-data",
          "arn:aws:s3:::greenland-glacier-data/*"
        ],
        "Condition": {
          "StringEquals": {
            "aws:SourceVpc": "vpc-0f32ee3ff3b0f4542"
          }
        }
      },
      {
        "Sid": "AllowECRImagePull",
        "Effect": "Allow",
        "Principal": "*",
        "Action": ["s3:GetObject"],
        "Resource": "arn:aws:s3:::prod-us-west-2-starport-layer-bucket/*"
      }
    ]
  }'
```

### Phase 2: Container Build & Deployment

**RECOMMENDED: Complete Cleanup and Rebuild** (January 23, 2026 - Production Validated):
```bash
cd /home/bny/Github/greenland-glacier-flow

# Single-command complete environment cleanup and rebuild
./aws/scripts/cleanup_and_rebuild.sh
```

**What this does:**
1. Deletes existing Lambda function and ECR repository
2. Builds fresh Docker container with Python 3.13 and geospatial libraries
3. Creates new ECR repository and pushes container image
4. Creates/updates Lambda function with maximum resources (10GB memory, 10GB storage, 15min timeout)
5. Validates complete deployment

**Alternative: Individual Deployment** (shown below): Step-by-step container deployment after manual cleanup.

#### Step 1: Build and Push Docker Container
```bash
cd /home/bny/Github/greenland-glacier-flow

# Make deployment script executable
chmod +x aws/scripts/deploy_lambda_container.sh

# Run automated deployment (builds, pushes, creates/updates Lambda)
./aws/scripts/deploy_lambda_container.sh
```

**What this script does:**
1. Builds Docker container with all geospatial libraries
2. Creates ECR repository if needed
3. Pushes container image to ECR
4. Creates/updates Lambda function with container
5. Configures maximum resources (10GB memory, 10GB storage, 15min timeout)
6. Validates deployment

#### Step 2: Verify Deployment
```bash
# Check Lambda function
aws lambda get-function --function-name glacier-processing

# Check ECR repository
aws ecr describe-repositories --repository-names glacier-lambda

# Check container image
aws ecr list-images --repository-name glacier-lambda
```

### Phase 3: Testing & Validation

#### Step 1: Test Sentinel-2 Processing
```bash
cd /home/bny/Github/greenland-glacier-flow

# Test with validated parameters
python aws/scripts/submit_aws_job.py \
  --service lambda \
  --satellite sentinel2 \
  --regions 140_CentralLindenow \
  --date1 2025-08-01 \
  --date2 2025-08-02 \
  --dry-run false
```

**Expected Results:**
- Processing time: ~102 seconds
- Memory usage: ~4.4 GB
- Status: SUCCESS
- S3 output: `s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/134_Arsuk/`

#### Step 2: Test Landsat Processing
```bash
python aws/scripts/submit_aws_job.py \
  --service lambda \
  --satellite landsat \
  --regions 140_CentralLindenow \
  --date1 2025-08-01 \
  --date2 2025-08-05 \
  --dry-run false
```

**Expected Results:**
- Processing time: ~4 seconds
- Memory usage: ~415 MB
- Status: SUCCESS
- S3 output: `s3://greenland-glacier-data/1_download_merge_and_clip/landsat/134_Arsuk/`

#### Step 3: Verify Results in S3
```bash
# Check Sentinel-2 results
aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/134_Arsuk/ --recursive

# Check Landsat results
aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/landsat/134_Arsuk/ --recursive
```

#### Step 4: Download Results Locally (Optional)
```bash
# Download processed results to your local machine
# This syncs only processed files (skips raw satellite downloads for bandwidth savings)
./sync_from_s3.sh --exclude-downloads

# Or sync only specific satellites
./sync_from_s3.sh sentinel2 --exclude-downloads
./sync_from_s3.sh landsat --exclude-downloads

# Preview what would be downloaded (dry run)
./sync_from_s3.sh --exclude-downloads --dry-run
```

**What this does:**
- Downloads processed satellite data from S3 to your local data directory
- Automatically detects HPC vs local environment from `config.ini`
- Skips raw satellite tiles (98% bandwidth savings)
- Safe for multi-user environments (skips existing files by default)

---

## 🔧 Troubleshooting

### Common Issues & Solutions

#### Issue: ECR Image Pull Fails (403 Forbidden)
**Cause**: VPC endpoint policy blocking ECR S3 access
**Solution**: Update VPC endpoint policy (see Phase 1, Step 3)

#### Issue: Lambda Function Creation Fails
**Cause**: IAM role not propagated yet
**Solution**: Wait 30+ seconds after role creation, then retry

#### Issue: Processing Times Out
**Cause**: Insufficient resources configured
**Solution**: Verify Lambda has 10GB memory, 10GB storage, 15min timeout

#### Issue: S3 Access Denied
**Cause**: Missing AmazonS3FullAccess policy on execution role
**Solution**: Attach policy to lambda-glacier-execution-role

### Logs & Debugging
```bash
# Check CloudWatch logs
aws logs tail /aws/lambda/glacier-processing --follow

# Check function configuration
aws lambda get-function-configuration --function-name glacier-processing

# Test with minimal parameters
python aws/scripts/submit_aws_job.py \
  --service lambda \
  --satellite sentinel2 \
  --regions 134_Arsuk \
  --date1 2024-07-01 \
  --date2 2024-07-01 \
  --dry-run false
```

---

## 📁 Required Files Reference

### Core Files (must preserve)
- `aws/Dockerfile.lambda` - Container definition
- `aws/lambda_handler_container.py` - Lambda handler
- `aws/scripts/deploy_lambda_container.sh` - Deployment automation
- `aws/scripts/submit_aws_job.py` - Job submission script
- `aws/config/minimal-lambda-policy.json` - IAM management policy
- `config.ini` - Processing configuration
- `1_download_merge_and_clip/` - Core processing code

### Documentation Files (preserve for reference)
- `aws/docs/VPC_ENDPOINT_FIX.md` - VPC policy updates
- `aws/README.md` - Quick reference
- `aws/docs/LAMBDA_QUICK_REFERENCE.md` - Troubleshooting

---

## 💰 Cost Optimization

### Lambda Pricing (us-west-2)
- **Request**: $0.0000000021 per request
- **Duration**: $0.0000166667 per GB-second
- **Sentinel-2**: ~$0.25 per processing job
- **Landsat**: ~$0.05 per processing job

### Cleanup When Not Using
```bash
# Delete Lambda function
aws lambda delete-function --function-name glacier-processing

# Delete ECR repository
aws ecr delete-repository --repository-name glacier-lambda --force

# Delete IAM role (optional)
aws iam detach-role-policy \
  --role-name lambda-glacier-execution-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam delete-role --role-name lambda-glacier-execution-role
```

---

## 🔄 Alternative: Non-Containerized Lambda (Historical Notes)

**Status**: Not recommended - containerized approach is superior
**Issues**: Requires S3 code sync, dependency management challenges, conda licensing restrictions

### Historical ZIP Deployment (for reference only)
```bash
# This approach is deprecated - kept for historical reference
# NOTE: Replace 123456789012 with your actual AWS account ID

# Upload code to S3
aws s3 sync . s3://greenland-glacier-data/scripts/greenland-glacier-flow/ \
  --exclude ".git/*" --exclude "*.log" --exclude "__pycache__/*"

# Create ZIP-based Lambda function
aws lambda create-function \
  --function-name glacier-processing \
  --runtime python3.13 \
  --role arn:aws:iam::123456789012:role/lambda-glacier-execution-role \
  --handler lambda_handler.lambda_handler \
  --code S3Bucket=greenland-glacier-data,S3Key=scripts/greenland-glacier-flow/lambda-deployment.zip \
  --timeout 900 \
  --memory-size 10240
```

**Why containerized is better:**
- No runtime S3 downloads (faster cold starts)
- Self-contained dependencies (no conda licensing issues)
- Consistent environment across dev/test/prod
- Easier deployment and maintenance

---

## ✅ Success Checklist

- [ ] AWS CLI configured with proper permissions
- [ ] S3 bucket `greenland-glacier-data` exists
- [ ] IAM role `lambda-glacier-execution-role` created with S3FullAccess
- [ ] VPC endpoint policy updated (if using VPC)
- [ ] Docker container built and pushed to ECR
- [ ] Lambda function `glacier-processing` created with container
- [ ] Sentinel-2 test processing successful (~102s)
- [ ] Landsat test processing successful (~4s)
- [ ] Results visible in S3 bucket

**🎉 Deployment Complete!** Your containerized Lambda is ready for production satellite processing.</content>
<parameter name="filePath">/home/bny/Github/greenland-glacier-flow/aws/docs/CONTAINERIZED_LAMBDA_COMPLETE_GUIDE.md
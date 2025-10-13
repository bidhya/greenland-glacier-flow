# AWS Fresh Start Quickstart Guide

**Last Updated**: October 12, 2025  
**Purpose**: Complete AWS Lambda container environment management

---

## 🎯 Overview

This comprehensive guide covers all AWS Lambda operations for the glacier processing project:

- **Fresh Start**: Complete cleanup and redeployment (when you want everything clean)
- **Incremental Updates**: Code changes and container rebuilds
- **Testing & Monitoring**: Run tests and check system status
- **Troubleshooting**: Common issues and solutions

**Time Required**: 15-20 minutes (fresh start) | 5-10 minutes (updates)  
**Prerequisites**: AWS CLI configured, Docker installed, project cloned

---

## 🗑️ Phase 1: Complete AWS Cleanup (Fresh Start Only)

### Step 1: Delete S3 Scripts Folder
```bash
# Remove old project files from S3
aws s3 rm s3://greenland-glacier-data/scripts/ --recursive
```

### Step 2: Delete Lambda Function
```bash
# Delete existing Lambda function
aws lambda delete-function --function-name glacier-sentinel2-processor --region us-west-2
```

### Step 3: Delete ECR Repository & Images
```bash
# Check what repositories exist
aws ecr describe-repositories --region us-west-2

# Delete all images in the repository
aws ecr batch-delete-image --repository-name glacier-sentinel2-processor \
  --image-ids $(aws ecr list-images --repository-name glacier-sentinel2-processor --region us-west-2 --query 'imageIds[*]' --output json) \
  --region us-west-2

# Delete the repository itself
aws ecr delete-repository --repository-name glacier-sentinel2-processor --region us-west-2 --force
```

---

## 📤 Phase 2: Upload Fresh Project Files (Fresh Start Only)

### Step 1: Sync Project to S3
```bash
# From project root directory
cd /home/bny/Github/greenland-glacier-flow

# Upload entire project (excluding git and temp files)
aws s3 sync . s3://greenland-glacier-data/scripts/greenland-glacier-flow/ --exclude ".git/*"
```

### Step 2: Verify Upload
```bash
# Check that files were uploaded
aws s3 ls s3://greenland-glacier-data/scripts/greenland-glacier-flow/ --recursive | head -10
```

---

## 🚀 Phase 3: Deploy Fresh Lambda Container (Fresh Start Only)

### Step 1: Run Deployment Script
```bash
# Make script executable and run
cd aws/scripts
chmod +x deploy_lambda_container.sh
./deploy_lambda_container.sh
```

### Step 2: Configure Lambda Resources
```bash
# Update memory to 5 GB
aws lambda update-function-configuration \
  --function-name glacier-sentinel2-processor \
  --memory-size 5120 \
  --region us-west-2

# Update ephemeral storage to 10 GB
aws lambda update-function-configuration \
  --function-name glacier-sentinel2-processor \
  --ephemeral-storage Size=10240 \
  --region us-west-2
```

### Step 3: Verify Function Status
```bash
# Check function configuration
aws lambda get-function --function-name glacier-sentinel2-processor --region us-west-2
```

---

## 🔄 Phase 4: Incremental Updates (Code Changes)

### Force Fresh Container Build
```bash
cd /home/bny/Github/greenland-glacier-flow

# Force rebuild without cache (use when code changes)
docker build --no-cache -t glacier-sentinel2-processor:latest \
  -f aws/lambda/Dockerfile.lambda .
```

### Complete Update Pipeline
```bash
# 1. Build fresh container
docker build --no-cache -t glacier-sentinel2-processor:latest \
  -f aws/lambda/Dockerfile.lambda .

# 2. Tag for ECR
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="us-west-2"
docker tag glacier-sentinel2-processor:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/glacier-sentinel2-processor:latest

# 3. Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# 4. Push to ECR
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/glacier-sentinel2-processor:latest

# 5. Update Lambda function
aws lambda update-function-code \
  --function-name glacier-sentinel2-processor \
  --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/glacier-sentinel2-processor:latest

# 6. Wait for update completion
aws lambda get-function --function-name glacier-sentinel2-processor \
  --query 'Configuration.LastUpdateStatus' --output text
```

### Automated Update (Recommended)
```bash
cd /home/bny/Github/greenland-glacier-flow/aws/scripts
./deploy_lambda_container.sh
```

---

## 🧪 Phase 5: Testing & Monitoring

### Dry Run Test
```bash
# Test configuration without actual processing
cd /home/bny/Github/greenland-glacier-flow
python aws/scripts/submit_aws_job.py \
  --satellite sentinel2 \
  --service lambda \
  --regions 134_Arsuk \
  --dry-run true
```

### Live Processing Test
```bash
# Run actual processing
python aws/scripts/submit_aws_job.py \
  --satellite sentinel2 \
  --service lambda \
  --regions 134_Arsuk \
  --dry-run false
```

### Verify Results
```bash
# Check uploaded files
aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/ --recursive
```

### Lambda Function Status
```bash
aws lambda get-function --function-name glacier-sentinel2-processor \
  --query 'Configuration.LastUpdateStatus' --output text
```

### CloudWatch Logs (Recent)
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/glacier-sentinel2-processor \
  --start-time $(($(date +%s) * 1000 - 300000)) \
  --query 'events[-20:].message' --output text
```

### ECR Latest Image
```bash
aws ecr describe-images \
  --repository-name glacier-sentinel2-processor \
  --query 'sort_by(imageDetails,& imagePushedAt)[-1]' --output json
```

---

## 📋 Complete Command Sequences

### Fresh Start (Complete Cleanup + Redeploy)
```bash
# Phase 1: Cleanup
aws s3 rm s3://greenland-glacier-data/scripts/ --recursive
aws lambda delete-function --function-name glacier-sentinel2-processor --region us-west-2
aws ecr batch-delete-image --repository-name glacier-sentinel2-processor --image-ids $(aws ecr list-images --repository-name glacier-sentinel2-processor --region us-west-2 --query 'imageIds[*]' --output json) --region us-west-2
aws ecr delete-repository --repository-name glacier-sentinel2-processor --region us-west-2 --force

# Phase 2: Upload
cd /home/bny/Github/greenland-glacier-flow
aws s3 sync . s3://greenland-glacier-data/scripts/greenland-glacier-flow/ --exclude ".git/*"

# Phase 3: Deploy
cd aws/scripts
chmod +x deploy_lambda_container.sh
./deploy_lambda_container.sh
aws lambda update-function-configuration --function-name glacier-sentinel2-processor --memory-size 5120 --region us-west-2
aws lambda update-function-configuration --function-name glacier-sentinel2-processor --ephemeral-storage Size=10240 --region us-west-2

# Phase 4: Test
cd /home/bny/Github/greenland-glacier-flow
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --dry-run false
```

### Quick Update (Code Changes Only)
```bash
cd /home/bny/Github/greenland-glacier-flow
docker build --no-cache -t glacier-sentinel2-processor:latest -f aws/lambda/Dockerfile.lambda .
cd aws/scripts && ./deploy_lambda_container.sh
python ../aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --dry-run false
```

---

## ✅ Success Indicators

- **S3 Upload**: Files appear under `scripts/greenland-glacier-flow/`
- **Lambda Function**: Status shows "Active" with 5 GB memory, 10 GB storage
- **Test Run**: Returns "Processing completed successfully" with uploaded file count
- **S3 Results**: Files appear under `1_download_merge_and_clip/sentinel2/`

---

## � Key Differences: Sentinel-2 vs Landsat

### Arguments
**Sentinel-2**:
```python
--regions --date1 --date2 --download_flag --post_processing_flag --cores
```

**Landsat**:
```python
--regions --date1 --date2 --base_dir --log_name
# NO: download_flag, post_processing_flag, cores
```

### Credentials
**Both satellites support**:
- CSV file (HPC/local): `~/AWS_user_credentials.csv`
- Lambda execution role (fallback when CSV missing)

---

## �🔧 Troubleshooting

### Lambda Out of Memory
```bash
# Increase memory allocation
aws lambda update-function-configuration \
  --function-name glacier-sentinel2-processor \
  --memory-size 8192 \
  --region us-west-2
```

### ECR Repository Already Exists
```bash
# Force delete existing repository
aws ecr delete-repository --repository-name glacier-sentinel2-processor --region us-west-2 --force
```

### S3 Sync Fails
```bash
# Check AWS credentials
aws sts get-caller-identity

# Check bucket permissions
aws s3 ls s3://greenland-glacier-data/
```

### Lambda Shows Old Code After Update
**Cause**: Docker layer caching  
**Solution**:
```bash
docker build --no-cache -t glacier-sentinel2-processor:latest \
  -f aws/lambda/Dockerfile.lambda .
```

### Build Context Error
**Cause**: Building from wrong directory  
**Solution**: Always build from project root:
```bash
cd /home/bny/Github/greenland-glacier-flow  # Project root
docker build -f aws/lambda/Dockerfile.lambda .  # Correct
```

### Landsat Exits Early
**Status**: Under investigation  
**See**: `aws/docs/LANDSAT_LAMBDA_TROUBLESHOOTING.md`

---

## 📝 Important File Locations

### Lambda Handler
- `aws/lambda/lambda_handler.py` - Main Lambda handler with multi-satellite support

### Processing Scripts
- `1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py`
- `1_download_merge_and_clip/landsat/download_clip_landsat.py`

### Credential Handling
- `1_download_merge_and_clip/landsat/lib/functions.py` (lines 143-171) - Fallback logic

### Documentation
- `AGENTS.md` - Architecture and lessons learned
- `aws/README.md` - AWS overview and quick links
- `aws/docs/LAMBDA_DEPLOYMENT_GUIDE.md` - Deployment procedures
- `aws/docs/LANDSAT_LAMBDA_TROUBLESHOOTING.md` - Landsat debugging

---

## 🎯 Current Status Summary

### ✅ Sentinel-2 - PRODUCTION READY
- End-to-end processing working
- 11 files per region successfully processed
- ~56 seconds processing time
- 5GB RAM, 10GB storage

### ✅ Landsat - PRODUCTION READY
- End-to-end processing working
- 4 files per region successfully processed
- ~11 seconds processing time
- 5GB RAM, 10GB storage
- Satellite isolation working correctly

---

## 📚 Related Documentation

- `AGENTS.md` - Architecture and lessons learned
- `aws/README.md` - AWS overview and quick links
- `aws/docs/LAMBDA_DEPLOYMENT_GUIDE.md` - Manual console deployment
- `aws/docs/AWS_GETTING_STARTED.md` - Initial AWS setup guide
- `aws/docs/LANDSAT_LAMBDA_TROUBLESHOOTING.md` - Landsat debugging
- `aws_config.ini` - AWS configuration settings</content>
<parameter name="filePath">/home/bny/Github/greenland-glacier-flow/aws/docs/AWS_FRESH_START_QUICKSTART.md
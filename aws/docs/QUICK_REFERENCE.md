# Quick Reference - AWS Lambda Multi-Satellite Processing

**Last Updated**: October 2, 2025  
**Status**: Sentinel-2 ✅ Production | Landsat 🔄 In Progress

---

## 🧹 Fresh Download Workflow

### 1. Clean S3 Bucket
```bash
# Delete old results and scripts
aws s3 rm s3://greenland-glacier-data/results/ --recursive
aws s3 rm s3://greenland-glacier-data/scripts/ --recursive
```

### 2. Sync Project Files to S3
```bash
cd /mnt/c/Github/greenland-glacier-flow
aws s3 sync . s3://greenland-glacier-data/scripts/greenland-glacier-flow/ \
  --exclude ".git/*" --exclude "*.pyc" --exclude "__pycache__/*" \
  --exclude ".vscode/*" --exclude "*.log" --exclude "*test*.json" --delete
```

### 3. Test Fresh Processing
```bash
cd aws/scripts
aws lambda invoke --function-name glacier-sentinel2-processor \
  --payload '{"satellite": "sentinel2", "regions": "134_Arsuk", "start_date": "2024-08-01", "end_date": "2024-08-01", "s3_bucket": "greenland-glacier-data"}' \
  fresh_result.json && cat fresh_result.json | jq '.'
```

---

## 🚀 Quick Test Commands

### Test Sentinel-2 (Working)
```bash
cd /mnt/c/Github/greenland-glacier-flow/aws/scripts

aws lambda invoke --function-name glacier-sentinel2-processor \
  --payload '{"satellite": "sentinel2", "regions": "134_Arsuk", "start_date": "2024-08-01", "end_date": "2024-08-01", "s3_bucket": "greenland-glacier-data"}' \
  result.json && cat result.json | jq '.'
```

### Test Landsat (Debugging)
```bash
aws lambda invoke --function-name glacier-sentinel2-processor \
  --payload '{"satellite": "landsat", "regions": "134_Arsuk", "start_date": "2024-08-01", "end_date": "2024-08-01", "s3_bucket": "greenland-glacier-data"}' \
  result.json && cat result.json | jq '.'
```

---

## 🐳 Docker Rebuild & Deploy

### Force Fresh Build (Use when code changes)
```bash
cd /mnt/c/Github/greenland-glacier-flow

# Force rebuild without cache
docker build --no-cache -t glacier-sentinel2-processor:latest \
  -f aws/lambda/Dockerfile.lambda .
```

### Complete Deployment Pipeline
```bash
# 1. Build
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

# 5. Update Lambda
aws lambda update-function-code \
  --function-name glacier-sentinel2-processor \
  --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/glacier-sentinel2-processor:latest

# 6. Wait for update
aws lambda get-function --function-name glacier-sentinel2-processor \
  --query 'Configuration.LastUpdateStatus' --output text
```

### Automated Deployment (Recommended)
```bash
cd /mnt/c/Github/greenland-glacier-flow/aws/scripts
./deploy_lambda_container.sh
```

---

## 📊 Check Status

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
  --query 'sort_by(imageDetails,& imagePushedAt)[-1]' --output json | jq
```

---

## 🔑 Key Differences: Sentinel-2 vs Landsat

### Arguments
**Sentinel-2**:
```python
--regions --start_date --end_date --download_flag --post_processing_flag --cores
```

**Landsat**:
```python
--regions --date1 --date2 --base_dir --log_name
# NO: download_flag, post_processing_flag, cores
```

### Credentials
**Both satellites now support**:
- CSV file (HPC/local): `~/AWS_user_credentials.csv`
- Lambda execution role (fallback when CSV missing)

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
- `aws/docs/SESSION_SUMMARY_2025-10-02.md` - Today's session summary

---

## ⚠️ Common Issues & Solutions

### Issue: Lambda Shows Old Code After Update
**Cause**: Docker layer caching  
**Solution**: 
```bash
docker build --no-cache -t glacier-sentinel2-processor:latest \
  -f aws/lambda/Dockerfile.lambda .
```

### Issue: Build Context Error
**Cause**: Building from wrong directory  
**Solution**: Always build from project root:
```bash
cd /mnt/c/Github/greenland-glacier-flow  # Project root
docker build -f aws/lambda/Dockerfile.lambda .  # Correct
```

### Issue: Landsat Exits Early
**Status**: Under investigation  
**See**: `aws/docs/LANDSAT_LAMBDA_TROUBLESHOOTING.md`

---

## 🎯 Current Status Summary

### ✅ Sentinel-2 - PRODUCTION READY
- End-to-end processing working
- 8 files per region successfully processed
- ~56 seconds processing time
- 5GB RAM, 10GB storage

### 🔄 Landsat - DEBUGGING
- Infrastructure complete
- Credentials fallback working
- Early exit issue (return code 1)
- STAC API connectivity investigation needed

---

## 📚 Next Steps

### Immediate (Landsat)
1. Add verbose logging to Landsat script
2. Test STAC API from Lambda
3. Verify `/tmp` permissions
4. Local Lambda-environment testing

### Short-term
1. Complete Landsat implementation
2. Add monitoring and metrics
3. Performance optimization
4. Automated testing

---

**Quick Help**: For detailed information, see documentation in `aws/docs/` or main `AGENTS.md`

# AWS Lambda Manual Deployment Guide for Sentinel-2 Processing

## 🎯 Step-by-Step Lambda Deployment

Since we don't have IAM/Lambda permissions via AWS CLI, we'll deploy manually through the AWS Console.

### 📋 What You Need
- ✅ AWS Console access
- ✅ Lambda deployment package (lambda-deployment.zip)
- ✅ S3 bucket ready (greenland-glacier-data)

### 🚀 Manual Deployment Steps

#### 1. Create Lambda Function in AWS Console
1. Go to **AWS Console** → **Lambda** service
2. Click **"Create function"**
3. Choose **"Author from scratch"**
4. Configure:
   - **Function name**: `glacier-sentinel2-processor`
   - **Runtime**: `Python 3.9`
   - **Architecture**: `x86_64`

#### 2. Set Execution Role
1. In **"Permissions"** section:
   - Choose **"Create a new role with basic Lambda permissions"**
   - AWS will create: `glacier-sentinel2-processor-role-xxxxx`

#### 3. Upload Function Code
1. In **"Code"** section:
   - Click **"Upload from"** → **".zip file"**
   - Upload the `lambda-deployment.zip` (created below)
   - Handler should be: `lambda_handler.lambda_handler`

#### 4. Configure Function Settings
1. **General configuration**:
   - **Timeout**: `15 minutes 0 seconds` (900 seconds - maximum)
   - **Memory**: `10240 MB` (10 GB - maximum)
   - **Ephemeral storage**: `10240 MB` (10 GB - maximum)

2. **Environment variables** (optional):
   - `S3_BUCKET`: `greenland-glacier-data`
   - `AWS_REGION`: `us-west-2`

#### ⚠️ Critical Resource Note (December 2025)
**Always use maximum resources** for Sentinel-2 processing:
- **Memory**: 10GB required for geospatial processing
- **Storage**: 10GB required for tile downloads (~100MB each)
- **Timeout**: 15 minutes required for complete workflow

**Reason**: Default resources (512MB storage) limit processing to 3-4 tiles. Maximum resources enable full workflow completion.

See: `LAMBDA_RESOURCE_TROUBLESHOOTING.md` for complete analysis.

#### 5. Set S3 Permissions
1. Go to **Configuration** → **Permissions**
2. Click on the execution role name
3. In IAM console, click **"Attach policies"**
4. Attach: **AmazonS3FullAccess**

### 📦 Create Deployment Package

Run this locally to create the deployment package:

```bash
cd /mnt/c/Github/greenland-glacier-flow
zip lambda-deployment.zip lambda_handler.py
```

### 🧪 Test the Function

#### Manual Test in AWS Console
1. Go to your Lambda function
2. Click **"Test"**
3. Create new test event with this JSON:

```json
{
  "satellite": "sentinel2",
  "regions": "134_Arsuk",
  "date1": "2025-05-04",
  "date2": "2025-05-07",
  "s3_bucket": "greenland-glacier-data",
  "download_flag": 1,
  "post_processing_flag": 1
}
```

4. Click **"Test"** - should return success!

#### Test via Our Script
Once deployed, test with:
```bash
python submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --dry-run false
```

### 🎉 Expected Results

**Success Response:**
```json
{
  "statusCode": 200,
  "body": {
    "message": "Sentinel-2 processing completed successfully",
    "satellite": "sentinel2", 
    "regions": "134_Arsuk",
    "date1": "2025-05-04",
    "date2": "2025-05-07",
    "s3_bucket": "greenland-glacier-data"
  }
}
```

### 🔧 Troubleshooting

**Common Issues:**
1. **Timeout errors**: Increase timeout to 15 minutes
2. **Memory errors**: Increase memory to 1024 MB or higher  
3. **S3 access denied**: Ensure AmazonS3FullAccess is attached to execution role
4. **Handler errors**: Verify handler is set to `lambda_handler.lambda_handler`

### 📈 Next Steps

Once basic Lambda is working:
1. **Add real processing code** to lambda_handler.py
2. **Package dependencies** (boto3, numpy, etc.)
3. **Implement S3 data processing**
4. **Add error handling and logging**

---

## 🐳 Docker Container Deployment (Production Method)

**Note:** The above manual deployment is for initial setup. For production, we use Docker containers with full geospatial libraries.

### Container Architecture
- **Base Image**: `public.ecr.aws/lambda/python:3.12`
- **Package Manager**: `dnf` (Amazon Linux 2023)
- **Libraries**: 30+ geospatial packages (geopandas, rasterio, GDAL, etc.)
- **Size**: ~1.4GB container image

### 🔄 Automated Deployment Script

Use the automated deployment script for complete rebuild and deployment:

```bash
cd /mnt/c/Github/greenland-glacier-flow/aws/scripts
./deploy_lambda_container.sh
```

This script handles:
1. ✅ Docker image build from `aws/lambda/Dockerfile.lambda`
2. ✅ ECR repository creation (if needed)
3. ✅ Image tagging and push to ECR
4. ✅ Lambda function update with new image
5. ✅ Verification and status checks

### 🔨 Manual Docker Rebuild (When Needed)

**When to rebuild:**
- After updating `lambda_handler.py` code
- After modifying processing scripts
- After changing dependencies in Dockerfile
- When Docker cache causes stale code issues

#### Step 1: Force Fresh Build (No Cache)

```bash
cd /mnt/c/Github/greenland-glacier-flow

# Force complete rebuild without Docker cache
docker build --no-cache -t glacier-sentinel2-processor:latest \
  -f aws/lambda/Dockerfile.lambda .
```

**Important:** Build from project root, not from `aws/lambda/` directory!

#### Step 2: Tag for ECR

```bash
# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="us-west-2"

# Tag image for ECR
docker tag glacier-sentinel2-processor:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/glacier-sentinel2-processor:latest
```

#### Step 3: Push to ECR

```bash
# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Push image
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/glacier-sentinel2-processor:latest
```

#### Step 4: Update Lambda Function

```bash
# Update Lambda to use new image
aws lambda update-function-code \
  --function-name glacier-sentinel2-processor \
  --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/glacier-sentinel2-processor:latest
```

#### Step 5: Wait for Update to Complete

```bash
# Check update status
aws lambda get-function --function-name glacier-sentinel2-processor \
  --query 'Configuration.LastUpdateStatus' --output text

# Wait until it shows "Successful"
```

### 🐛 Troubleshooting Docker Builds

#### Problem: Docker Using Cached Layers (Stale Code)

**Symptom:** Code changes in `lambda_handler.py` not reflected in deployed Lambda

**Solution:**
```bash
# Force rebuild without cache
docker build --no-cache -t glacier-sentinel2-processor:latest \
  -f aws/lambda/Dockerfile.lambda .

# OR update file timestamp to bust cache
touch aws/lambda/lambda_handler.py
docker build -t glacier-sentinel2-processor:latest \
  -f aws/lambda/Dockerfile.lambda .
```

#### Problem: Build Context Issues

**Symptom:** `COPY failed: file not found`

**Solution:** Always build from project root:
```bash
# ❌ Wrong - building from lambda directory
cd aws/lambda && docker build -f Dockerfile.lambda .

# ✅ Correct - build from project root
cd /mnt/c/Github/greenland-glacier-flow
docker build -f aws/lambda/Dockerfile.lambda .
```

#### Problem: Lambda Still Using Old Code

**Symptom:** Deployed Lambda shows old behavior after rebuild

**Checklist:**
1. ✅ Verify local file has correct code: `cat aws/lambda/lambda_handler.py | grep -A 5 "run_landsat"`
2. ✅ Force Docker rebuild without cache: `--no-cache` flag
3. ✅ Verify image pushed to ECR: Check ECR console for latest timestamp
4. ✅ Confirm Lambda updated: `aws lambda get-function` shows recent update time
5. ✅ Wait for update completion: Status must be "Successful" before testing

### 📊 Satellite-Specific Argument Handling

The Lambda handler supports both Sentinel-2 and Landsat with different arguments:

**Sentinel-2:**
```python
cmd = [
    "download_merge_clip_sentinel2.py",
    "--regions", regions,
    "--date1", date1,
    "--date2", date2,
    "--download_flag", "1",
    "--post_processing_flag", "1",
    "--cores", "1",
    "--base_dir", base_dir
]
```

**Landsat:**
```python
cmd = [
    "download_clip_landsat.py",
    "--regions", regions,
    "--date1", date1,
    "--date2", date2,
    "--base_dir", base_dir
]
# Note: NO download_flag, post_processing_flag, or cores for Landsat
```

### 🧪 Testing After Deployment

#### Test Sentinel-2 Processing:
```bash
cd /mnt/c/Github/greenland-glacier-flow/aws/scripts

cat > test_sentinel2.json << 'EOF'
{
  "satellite": "sentinel2",
  "regions": "134_Arsuk",
  "date1": "2024-08-01",
  "date2": "2024-08-01",
  "s3_bucket": "greenland-glacier-data"
}
EOF

aws lambda invoke --function-name glacier-sentinel2-processor \
  --payload file://test_sentinel2.json result.json

cat result.json | jq '.'
```

#### Test Landsat Processing:
```bash
cat > test_landsat.json << 'EOF'
{
  "satellite": "landsat",
  "regions": "134_Arsuk",
  "date1": "2024-08-01",
  "date2": "2024-08-01",
  "s3_bucket": "greenland-glacier-data"
}
EOF

aws lambda invoke --function-name glacier-sentinel2-processor \
  --payload file://test_landsat.json result.json

cat result.json | jq '.'
```

### 📝 Deployment Checklist

Before deploying updates:
- [ ] Update `lambda_handler.py` with changes
- [ ] Test locally if possible
- [ ] Force rebuild Docker image with `--no-cache`
- [ ] Push to ECR
- [ ] Update Lambda function
- [ ] Wait for "Successful" update status
- [ ] Test with both Sentinel-2 and Landsat payloads
- [ ] Check CloudWatch logs for any errors
- [ ] Verify S3 outputs uploaded correctly

---

**Ready to deploy!** 🚀 Follow these steps and your Sentinel-2/Landsat Lambda will be running in minutes!
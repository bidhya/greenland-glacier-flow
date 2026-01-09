# AWS Getting Started Guide for Glacier Processing

## Service Overview (January 9, 2026)

**Production Service**: AWS Lambda (operational since October 2025)
- Single-glacier processing with 15-min/10GB limits
- Validated for both Sentinel-2 and Landsat
- See `AWS_OPERATIONS_GUIDE.md` for usage

**Attempted Service**: AWS Fargate (January 2026)
- Blocked on ECR 403 authentication errors
- Complete troubleshooting documented in `FARGATE_DEPLOYMENT_STATUS_2026-01-09.md`

**Planned Service**: AWS Batch (planning phase)
- Production-scale processing with unlimited runtime
- Incremental implementation plan in `AWS_BATCH_IMPLEMENTATION_PLAN.md`

---

## Phase 1: Basic AWS Setup (Start Here)

### Step 1: Install Required Tools

```bash
# Install boto3 for Python AWS integration
pip install boto3

# Install AWS CLI (if not already installed)
pip install awscli
```

### Step 2: AWS Account Setup

1. **Create AWS Account** (if you don't have one)
   - Go to https://aws.amazon.com/
   - Sign up for a free tier account
   - Note: You'll need a credit card, but many services have free tiers

2. **Create IAM User** (recommended for security)
   - Go to AWS Console → IAM → Users → Create User
   - Attach policies: `AmazonS3FullAccess`, `AWSBatchFullAccess` (for now)
   - Create access keys for programmatic access

3. **Configure AWS CLI**
   ```bash
   aws configure
   # Enter your Access Key ID
   # Enter your Secret Access Key  
   # Enter default region: us-east-1
   # Enter default output format: json
   ```

4. **Test Basic Connection**
   ```bash
   aws sts get-caller-identity
   # Should show your account info
   ```

### Step 3: Create Your First S3 Bucket

```bash
# Create bucket (replace 'your-name' with something unique)
aws s3 mb s3://your-name-glacier-test-bucket

# Test basic operations
echo "Hello AWS from glacier processing!" > test.txt
aws s3 cp test.txt s3://your-name-glacier-test-bucket/
aws s3 ls s3://your-name-glacier-test-bucket/

# Clean up test file
aws s3 rm s3://your-name-glacier-test-bucket/test.txt
rm test.txt
```

### Step 4: Test Your AWS Script

```bash
# Test the script framework (should work now)
python submit_aws_job.py --satellite sentinel2 --service batch --dry-run true

# Test with your actual S3 bucket
python submit_aws_job.py --satellite sentinel2 --service batch --s3-bucket your-name-glacier-test-bucket --dry-run true
```

## Phase 2: Simple AWS Batch Experiment

### Step 5: AWS Batch Console Setup (Manual - Learning Exercise)

1. **Go to AWS Batch Console**
   - Navigate to AWS Console → Batch

2. **Create Compute Environment**
   - Name: `glacier-test-compute-env`
   - Type: Managed
   - Instance types: `optimal` (let AWS choose)
   - Min vCPUs: 0, Max vCPUs: 10
   - Instance role: Create new (AWS will create)

3. **Create Job Queue**
   - Name: `glacier-test-queue`
   - Priority: 1
   - Compute environment: Select the one you just created

4. **Create Job Definition**
   - Name: `glacier-hello-world`
   - Type: Container
   - Container image: `busybox:latest`
   - Command: `echo,"Hello from AWS Batch!"` 
   - vCPUs: 1, Memory: 128

### Step 6: Test Simple Job Submission

Once you have the Batch setup, we can implement real job submission in the Python script.

## Phase 3: Next Steps (After Phase 1 & 2 Work)

- Upload processing scripts to S3
- Create Docker container with your processing environment
- Implement real satellite data processing jobs
- Add monitoring and cost optimization

## Quick Reference

### Useful AWS CLI Commands
```bash
# List S3 buckets
aws s3 ls

# Check AWS account
aws sts get-caller-identity

# List Batch compute environments
aws batch describe-compute-environments

# List Batch job queues  
aws batch describe-job-queues
```

### Important Notes

- **Free Tier**: AWS offers free tier services, but monitor usage
- **Costs**: S3 storage and compute time will incur costs after free tier
- **Security**: Use IAM users/roles, not root account credentials
- **Regions**: Keep everything in the same region (us-east-1) to start

## Troubleshooting

### Common Issues

1. **"Credentials not found"**
   - Run `aws configure` and enter your access keys

2. **"Bucket already exists"**
   - Bucket names are globally unique, try a different name

3. **"Access Denied"**
   - Check IAM permissions for your user

4. **boto3 import error**
   - Run `pip install boto3`

### Getting Help

- AWS Documentation: https://docs.aws.amazon.com/
- AWS Free Tier: https://aws.amazon.com/free/
- Batch Getting Started: https://docs.aws.amazon.com/batch/latest/userguide/getting-started.html
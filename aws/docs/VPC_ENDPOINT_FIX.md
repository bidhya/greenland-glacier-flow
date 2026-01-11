# VPC Endpoint Fix for ECR Image Pull

## Problem Summary
AWS Batch and Fargate jobs fail with `CannotPullContainerError` when trying to pull ECR images. 

**Root Cause**: S3 VPC endpoint policy only allows access to `greenland-glacier-data` bucket, but ECR stores container image layers in AWS-managed S3 buckets (`prod-us-west-2-starport-layer-bucket`).

**Error Message**:
```
User: arn:aws:sts::812812325446:assumed-role/storage-access-role-prod-us-west-2/...
is not authorized to perform: s3:GetObject on resource: 
"arn:aws:s3:::prod-us-west-2-starport-layer-bucket/..." 
because no VPC endpoint policy allows the s3:GetObject action
```

## AWS Console Fix (5 minutes)

### Step 1: Navigate to VPC Endpoints
1. Go to AWS Console → **VPC** service
2. Left sidebar → **Endpoints**
3. Find endpoint: **vpce-0466ad77a879d944a** (Service: `com.amazonaws.us-west-2.s3`)

### Step 2: View Current Policy
Current policy (restrictive):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
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
  }]
}
```

### Step 3: Update Policy
1. Select the S3 endpoint (vpce-0466ad77a879d944a)
2. **Actions** → **Manage policy**
3. Replace with this policy:

```json
{
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
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::prod-us-west-2-starport-layer-bucket/*"
    }
  ]
}
```

4. Click **Save**

### Step 4: Test the Fix
After updating the policy, resubmit the Batch job:

```bash
aws batch submit-job \
  --job-name hello-world-test-002 \
  --job-queue glacier-batch-hello-queue \
  --job-definition hello-world-test:1
```

Wait 2-3 minutes for Spot instance provisioning, then check status:
```bash
aws batch describe-jobs --jobs <JOB_ID> --query 'jobs[0].status'
```

## Alternative: Full Access Policy (Less Restrictive)

If you want to allow all S3 access through VPC endpoint:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": "*",
    "Action": "*",
    "Resource": "*"
  }]
}
```

This removes all restrictions - simpler but less secure.

## Why This Happens

**AWS Best Practice**: When using ECR with VPC endpoints, the S3 endpoint policy must allow:
1. Your application buckets (greenland-glacier-data)
2. AWS ECR service buckets (prod-*-starport-layer-bucket)

**Reference**: [AWS ECR VPC Endpoints Documentation](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html)

## Current Status (January 9, 2026)

- **VPC ID**: vpc-0f32ee3ff3b0f4542
- **S3 Endpoint ID**: vpce-0466ad77a879d944a
- **ECR API Endpoint**: vpce-0ceb903b9aee79843 ✅ (policy correct)
- **ECR DKR Endpoint**: vpce-0fc47277ac6ca4ca9 ✅ (policy correct)
- **S3 Endpoint**: vpce-0466ad77a879d944a ❌ (needs policy update)

## After Fix

Once fixed, both AWS Batch and Fargate will be able to pull ECR images without issues.

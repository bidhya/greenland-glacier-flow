#!/bin/bash

# AWS Lambda Deployment Script for Sentinel-2 Processing
# This script packages and deploys the Lambda function

set -e

# Configuration
FUNCTION_NAME="glacier-sentinel2-processor"
REGION="us-west-2"
RUNTIME="python3.9"
TIMEOUT=900  # 15 minutes
MEMORY=1024  # 1GB

echo "🚀 Deploying Lambda function: $FUNCTION_NAME"
echo "Region: $REGION"
echo "Runtime: $RUNTIME"

# Create deployment package
echo "📦 Creating deployment package..."
zip -r lambda-deployment.zip lambda_handler.py

# Check if function exists
echo "🔍 Checking if function exists..."
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION >/dev/null 2>&1; then
    echo "📝 Function exists, updating code..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://lambda-deployment.zip \
        --region $REGION
    
    echo "⚙️ Updating function configuration..."
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --timeout $TIMEOUT \
        --memory-size $MEMORY \
        --region $REGION
else
    echo "🆕 Function doesn't exist, creating new function..."
    
    # Create execution role first (if needed)
    ROLE_NAME="lambda-glacier-execution-role"
    ROLE_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/$ROLE_NAME"
    
    echo "🔐 Creating IAM role: $ROLE_NAME"
    cat > trust-policy.json << EOF
{
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
}
EOF

    # Create role (ignore error if exists)
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file://trust-policy.json || true
    
    # Attach basic Lambda execution policy
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole || true
    
    # Attach S3 full access policy  
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess || true
    
    echo "⏳ Waiting for role to be ready..."
    sleep 10
    
    # Create Lambda function
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role $ROLE_ARN \
        --handler lambda_handler.lambda_handler \
        --zip-file fileb://lambda-deployment.zip \
        --timeout $TIMEOUT \
        --memory-size $MEMORY \
        --region $REGION
fi

# Clean up
rm -f lambda-deployment.zip trust-policy.json

echo "✅ Lambda function deployed successfully!"
echo "Function name: $FUNCTION_NAME"
echo "Region: $REGION"
echo ""
echo "🧪 Test with:"
echo "python submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --dry-run false"
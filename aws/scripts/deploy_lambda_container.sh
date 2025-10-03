#!/bin/bash

# Deploy Lambda Container Image for Sentinel-2 Processing
# This script builds and deploys a containerized Lambda with conda environment

set -e

# Configuration
AWS_REGION="us-west-2"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPOSITORY_NAME="glacier-sentinel2-processor"
FUNCTION_NAME="glacier-sentinel2-processor"
IMAGE_TAG="latest"

echo "🐳 Deploying Lambda Container Image"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "Repository: $REPOSITORY_NAME"
echo "Function: $FUNCTION_NAME"

# Step 1: Create ECR repository if it doesn't exist
echo "📦 Creating ECR repository..."
aws ecr describe-repositories --repository-names $REPOSITORY_NAME --region $AWS_REGION > /dev/null 2>&1 || \
aws ecr create-repository --repository-name $REPOSITORY_NAME --region $AWS_REGION

# Step 2: Get ECR login token
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Step 3: Build Docker image
echo "🏗️  Building Docker image..."
docker build -f ../lambda/Dockerfile.lambda -t $REPOSITORY_NAME:$IMAGE_TAG ../..

# Step 4: Tag image for ECR
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPOSITORY_NAME:$IMAGE_TAG"
echo "🏷️  Tagging image: $ECR_URI"
docker tag $REPOSITORY_NAME:$IMAGE_TAG $ECR_URI

# Step 5: Push image to ECR
echo "☁️  Pushing image to ECR..."
docker push $ECR_URI

# Step 6: Update Lambda function to use container image
echo "🔄 Updating Lambda function..."

# Check if function exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION > /dev/null 2>&1; then
    echo "📝 Function exists. Checking package type..."
    
    # Get current package type
    PACKAGE_TYPE=$(aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION --query 'Configuration.PackageType' --output text)
    
    if [ "$PACKAGE_TYPE" = "Zip" ]; then
        echo "🔄 Converting from ZIP to container image - deleting and recreating..."
        
        aws lambda delete-function \
            --function-name $FUNCTION_NAME \
            --region $AWS_REGION
        
        echo "⏳ Waiting for function deletion..."
        sleep 10
        
        echo "🆕 Creating new container-based function..."
        ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/lambda-glacier-execution-role"
        
        aws lambda create-function \
            --function-name $FUNCTION_NAME \
            --package-type Image \
            --code ImageUri=$ECR_URI \
            --role $ROLE_ARN \
            --timeout 900 \
            --memory-size 2048 \
            --region $AWS_REGION
    else
        echo "📝 Updating container image..."
        aws lambda update-function-code \
            --function-name $FUNCTION_NAME \
            --image-uri $ECR_URI \
            --region $AWS_REGION
            
        echo "⚙️  Updating function configuration..."
        aws lambda update-function-configuration \
            --function-name $FUNCTION_NAME \
            --timeout 900 \
            --memory-size 2048 \
            --region $AWS_REGION
    fi
else
    echo "🆕 Function doesn't exist, creating new container-based function..."
    
    # Get existing execution role ARN (from previous deployment)
    ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/lambda-glacier-execution-role"
    
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$ECR_URI \
        --role $ROLE_ARN \
        --timeout 900 \
        --memory-size 2048 \
        --region $AWS_REGION
fi

echo "✅ Lambda container image deployed successfully!"
echo "Function: $FUNCTION_NAME"
echo "Image: $ECR_URI"
echo "Memory: 2048 MB"
echo "Timeout: 15 minutes"
echo ""
echo "🧪 Test with:"
echo "python submit_aws_job.py --satellite sentinel2 --service lambda --regions 134_Arsuk --dry-run false"
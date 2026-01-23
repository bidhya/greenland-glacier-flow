#!/bin/bash
# Deploy Lambda Container to AWS
# Self-contained Lambda based on Fargate's proven architecture
# Date: January 11, 2026

set -e

echo "=================================="
echo "Lambda Container AWS Deployment"
echo "=================================="

# Configuration
AWS_REGION="us-west-2"
# Get AWS account ID dynamically from credentials
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_NAME="glacier-lambda"
LAMBDA_FUNCTION_NAME="glacier-processing"
IMAGE_TAG="latest"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${IMAGE_TAG}"

echo ""
echo "Configuration:"
echo "  Region: ${AWS_REGION}"
echo "  Account: ${AWS_ACCOUNT_ID}"
echo "  ECR Repo: ${ECR_REPO_NAME}"
echo "  Lambda Function: ${LAMBDA_FUNCTION_NAME}"
echo "  Image Tag: ${IMAGE_TAG}"
echo ""

# Step 1: Create ECR repository if it doesn't exist
echo "Step 1: Checking ECR repository..."
if aws ecr describe-repositories --repository-names ${ECR_REPO_NAME} --region ${AWS_REGION} 2>/dev/null; then
    echo "✓ ECR repository exists"
else
    echo "Creating ECR repository..."
    aws ecr create-repository \
        --repository-name ${ECR_REPO_NAME} \
        --region ${AWS_REGION} \
        --image-scanning-configuration scanOnPush=true
    echo "✓ ECR repository created"
fi

# Step 2: Login to ECR
echo ""
echo "Step 2: Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
echo "✓ Logged into ECR"

# Step 3: Build the image
echo ""
echo "Step 3: Building Lambda container..."
docker build -t ${ECR_REPO_NAME}:${IMAGE_TAG} -f aws/Dockerfile.lambda .
echo "✓ Build complete"

# Step 4: Tag the image
echo ""
echo "Step 4: Tagging image for ECR..."
docker tag ${ECR_REPO_NAME}:${IMAGE_TAG} ${ECR_URI}
echo "✓ Image tagged"

# Step 5: Push to ECR
echo ""
echo "Step 5: Pushing to ECR..."
docker push ${ECR_URI}
echo "✓ Image pushed to ECR"

# Step 6: Update Lambda function
echo ""
echo "Step 6: Updating Lambda function..."

# Check current package type
PACKAGE_TYPE=$(aws lambda get-function-configuration \
    --function-name ${LAMBDA_FUNCTION_NAME} \
    --region ${AWS_REGION} \
    --query 'PackageType' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$PACKAGE_TYPE" = "Zip" ]; then
    echo "Converting from ZIP to container (requires function recreation)..."
    echo "Deleting existing ZIP-based function..."
    
    aws lambda delete-function \
        --function-name ${LAMBDA_FUNCTION_NAME} \
        --region ${AWS_REGION}
    
    echo "Waiting for deletion to complete..."
    sleep 10
    
    echo "Creating new container-based function..."
    ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/lambda-glacier-execution-role"
    
    aws lambda create-function \
        --function-name ${LAMBDA_FUNCTION_NAME} \
        --package-type Image \
        --code ImageUri=${ECR_URI} \
        --role ${ROLE_ARN} \
        --timeout 900 \
        --memory-size 10240 \
        --ephemeral-storage Size=10240 \
        --region ${AWS_REGION}
    
    echo "✓ Function created with container image"
    
elif [ "$PACKAGE_TYPE" = "Image" ]; then
    echo "Updating existing container-based function..."
    
    aws lambda update-function-code \
        --function-name ${LAMBDA_FUNCTION_NAME} \
        --image-uri ${ECR_URI} \
        --region ${AWS_REGION}
    
    echo "✓ Function code updated"
    
else
    echo "Function not found, creating new container-based function..."
    ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/lambda-glacier-execution-role"
    
    aws lambda create-function \
        --function-name ${LAMBDA_FUNCTION_NAME} \
        --package-type Image \
        --code ImageUri=${ECR_URI} \
        --role ${ROLE_ARN} \
        --timeout 900 \
        --memory-size 10240 \
        --ephemeral-storage Size=10240 \
        --region ${AWS_REGION}
    
    echo "✓ Function created"
fi

echo ""
echo "Waiting for Lambda function update to complete..."
aws lambda wait function-updated-v2 \
    --function-name ${LAMBDA_FUNCTION_NAME} \
    --region ${AWS_REGION}

echo "✓ Lambda function ready"

# Step 7: Verify deployment
echo ""
echo "Step 7: Verifying deployment..."
LAMBDA_SHA=$(aws lambda get-function-configuration \
    --function-name ${LAMBDA_FUNCTION_NAME} \
    --region ${AWS_REGION} \
    --query 'CodeSha256' \
    --output text)

echo "✓ Lambda function is using container: SHA256=${LAMBDA_SHA}"

echo ""
echo "=================================="
echo "Deployment Complete!"
echo "=================================="
echo ""
echo "Lambda function '${LAMBDA_FUNCTION_NAME}' is now using container:"
echo "  ${ECR_URI}"
echo ""

# Automatic configuration validation
echo "Validating Lambda configuration..."
if python aws/scripts/validate_lambda_config.py --function-name ${LAMBDA_FUNCTION_NAME}; then
    echo ""
    echo "Next Steps:"
    echo "1. Test Lambda function:"
    echo "   python aws/scripts/submit_aws_job.py --service lambda --satellite sentinel2 --regions 140_CentralLindenow"
    echo ""
    echo "2. Check CloudWatch logs:"
    echo "   aws logs tail /aws/lambda/${LAMBDA_FUNCTION_NAME} --follow"
    echo "=================================="
else
    echo ""
    echo "❌ Configuration validation failed!"
    echo "   Fix configuration issues above before testing."
    echo "=================================="
    exit 1
fi

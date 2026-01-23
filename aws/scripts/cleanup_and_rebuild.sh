#!/bin/bash
# Cleanup and Rebuild Lambda Container
# Removes all AWS resources, local containers, and rebuilds from scratch
# Date: January 11, 2026

set -e  # Exit on error

echo "=========================================="
echo "Lambda Container Cleanup and Rebuild"
echo "=========================================="

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-west-2"
ECR_REPO="glacier-lambda"
LAMBDA_FUNCTION="glacier-processing"

# 1. Cleanup AWS Lambda function
echo ""
echo "1. Cleaning up Lambda function..."
if aws lambda get-function --function-name $LAMBDA_FUNCTION &>/dev/null; then
    echo "   Deleting Lambda function: $LAMBDA_FUNCTION"
    aws lambda delete-function --function-name $LAMBDA_FUNCTION
    echo "   ✅ Lambda function deleted"
else
    echo "   ℹ️  Lambda function not found (already deleted)"
fi

# 2. Cleanup ECR images
echo ""
echo "2. Cleaning up ECR repository..."
if aws ecr describe-repositories --repository-names $ECR_REPO --region $REGION &>/dev/null; then
    echo "   Listing all images in $ECR_REPO..."
    IMAGE_IDS=$(aws ecr list-images --repository-name $ECR_REPO --region $REGION --query 'imageIds[*]' --output json)
    
    if [ "$IMAGE_IDS" != "[]" ]; then
        echo "   Deleting all images from ECR..."
        aws ecr batch-delete-image \
            --repository-name $ECR_REPO \
            --region $REGION \
            --image-ids "$IMAGE_IDS"
        echo "   ✅ ECR images deleted"
    else
        echo "   ℹ️  No images found in repository"
    fi
    
    echo "   Deleting ECR repository: $ECR_REPO"
    aws ecr delete-repository --repository-name $ECR_REPO --region $REGION --force
    echo "   ✅ ECR repository deleted"
else
    echo "   ℹ️  ECR repository not found (already deleted)"
fi

# 3. Cleanup S3 test data (optional - comment out if you want to keep data)
echo ""
echo "3. Cleaning up S3 test data..."
read -p "   Delete S3 test data? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   Deleting Sentinel-2 test data..."
    aws s3 rm s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/140_CentralLindenow/ --recursive
    echo "   Deleting Landsat test data..."
    aws s3 rm s3://greenland-glacier-data/1_download_merge_and_clip/landsat/140_CentralLindenow/ --recursive
    echo "   ✅ S3 test data deleted"
else
    echo "   ℹ️  Skipping S3 cleanup"
fi

# 4. Cleanup local Docker images
echo ""
echo "4. Cleaning up local Docker images..."
echo "   Removing glacier-lambda:latest..."
docker rmi glacier-lambda:latest 2>/dev/null || echo "   ℹ️  Local image not found"

echo "   Removing ECR-tagged images..."
docker images --format "{{.Repository}}:{{.Tag}}" | grep "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO" | xargs -r docker rmi 2>/dev/null || echo "   ℹ️  No ECR-tagged images found"

echo "   Cleaning up dangling images..."
docker image prune -f

echo "   ✅ Local Docker cleanup complete"

# 5. Rebuild from scratch
echo ""
echo "=========================================="
echo "Rebuilding Lambda Container"
echo "=========================================="

cd /home/bny/Github/greenland-glacier-flow

echo ""
echo "Building Docker container..."
docker build --no-cache -t glacier-lambda:latest -f aws/Dockerfile.lambda .

echo ""
echo "✅ Container built successfully"

# 6. Redeploy to AWS
echo ""
echo "=========================================="
echo "Deploying to AWS"
echo "=========================================="

# Use existing deployment script
bash aws/scripts/deploy_lambda_container.sh

echo ""
echo "=========================================="
echo "✅ Cleanup and Rebuild Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test Sentinel-2: aws lambda invoke --function-name glacier-processing --invocation-type Event --payload '{\"satellite\": \"sentinel2\", \"region\": \"140_CentralLindenow\", \"date1\": \"2024-10-01\", \"date2\": \"2024-10-05\", \"s3_bucket\": \"greenland-glacier-data\"}' /dev/null"
echo "2. Test Landsat: aws lambda invoke --function-name glacier-processing --invocation-type Event --payload '{\"satellite\": \"landsat\", \"region\": \"140_CentralLindenow\", \"date1\": \"2024-10-01\", \"date2\": \"2024-10-05\", \"s3_bucket\": \"greenland-glacier-data\"}' /dev/null"
echo "3. Check logs: aws logs tail /aws/lambda/glacier-processing --since 5m --follow"
echo "4. Check S3: aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/ --recursive"

#!/bin/bash

# Test Lambda Container Locally
# This script builds and tests the container without needing ECR

set -e

REPOSITORY_NAME="glacier-sentinel2-processor"
IMAGE_TAG="latest"

echo "🐳 Building and Testing Lambda Container Locally"

# Build Docker image
echo "🏗️  Building Docker image..."
docker build -f ../lambda/Dockerfile.lambda -t $REPOSITORY_NAME:$IMAGE_TAG ../..

echo "✅ Container built successfully!"
echo ""
echo "🧪 To test locally, you can run:"
echo "docker run --rm -p 9000:8080 $REPOSITORY_NAME:$IMAGE_TAG"
echo ""
echo "Then in another terminal:"
echo "curl -XPOST \"http://localhost:9000/2015-03-31/functions/function/invocations\" -d '{\"satellite\":\"sentinel2\",\"regions\":\"134_Arsuk\",\"date1\":\"2025-05-04\",\"date2\":\"2025-05-07\"}'"
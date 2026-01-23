#!/bin/bash
# Build and test Lambda container locally
# Date: January 11, 2026

set -e

echo "=================================="
echo "Lambda Container Build & Test"
echo "=================================="

# Build the container
echo ""
echo "Building Lambda container..."
docker build -t glacier-lambda:latest -f aws/Dockerfile.lambda .

if [ $? -eq 0 ]; then
    echo "✓ Build successful!"
else
    echo "✗ Build failed!"
    exit 1
fi

# Ask if user wants to run local test
echo ""
echo "Build complete. Would you like to run a local test? (y/n)"
read -p "> " run_test

if [ "$run_test" = "y" ] || [ "$run_test" = "Y" ]; then
    echo ""
    echo "Starting Lambda container on port 9000..."
    echo "Container will run in background. Use 'docker ps' to check status."
    echo ""
    
    # Run container in background
    docker run -d -p 9000:8080 --name glacier-lambda-test glacier-lambda:latest
    
    echo "Waiting 5 seconds for container to start..."
    sleep 5
    
    echo ""
    echo "Testing with Sentinel-2 payload..."
    echo ""
    
    # Test payload
    curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
        -H "Content-Type: application/json" \
        -d '{
            "satellite": "sentinel2",
            "region": "140_CentralLindenow",
            "date1": "2024-10-01",
            "date2": "2024-10-05",
            "s3_bucket": "greenland-glacier-data"
        }'
    
    echo ""
    echo ""
    echo "Test complete!"
    echo ""
    echo "To view logs: docker logs glacier-lambda-test"
    echo "To stop container: docker stop glacier-lambda-test"
    echo "To remove container: docker rm glacier-lambda-test"
else
    echo ""
    echo "Skipping local test."
    echo ""
    echo "To test manually:"
    echo "1. docker run -p 9000:8080 glacier-lambda:latest"
    echo "2. curl -XPOST \"http://localhost:9000/2015-03-31/functions/function/invocations\" -d '{...}'"
fi

echo ""
echo "=================================="
echo "Next Steps:"
echo "=================================="
echo "1. Test locally (if not done above)"
echo "2. Deploy to AWS:"
echo "   ./aws/scripts/deploy_lambda_container.sh"
echo "3. Test in AWS:"
echo "   python aws/scripts/submit_aws_job.py --service lambda --satellite sentinel2 --regions 140_CentralLindenow"
echo "=================================="

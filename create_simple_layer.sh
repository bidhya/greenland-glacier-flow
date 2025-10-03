#!/bin/bash

# Create Lambda Layer with Essential Geospatial Libraries
# Simplified approach without full conda environment

set -e

echo "📦 Creating Lambda Layer with Essential Libraries"

# Create working directory
WORK_DIR=$(mktemp -d)
LAYER_DIR="$WORK_DIR/python"
mkdir -p $LAYER_DIR

echo "📁 Working directory: $WORK_DIR"

# Install essential packages using pip (Lambda-compatible)
echo "📚 Installing essential packages..."
pip install --target $LAYER_DIR \
    boto3 \
    geopandas \
    rasterio \
    fiona \
    pyproj \
    shapely \
    pandas \
    numpy \
    requests

# Create layer zip
echo "🗜️  Creating layer zip..."
cd $WORK_DIR
zip -r essential-geospatial-layer.zip python/

# Upload to AWS Lambda as layer (if we have permissions)
LAYER_NAME="essential-geospatial-libs"
REGION="us-west-2"

echo "☁️  Uploading layer to AWS Lambda..."
aws lambda publish-layer-version \
    --layer-name $LAYER_NAME \
    --description "Essential geospatial libraries for glacier processing" \
    --zip-file fileb://essential-geospatial-layer.zip \
    --compatible-runtimes python3.9 \
    --region $REGION

# Copy layer to current directory for manual upload if needed
cp essential-geospatial-layer.zip /mnt/c/Github/greenland-glacier-flow/

echo "✅ Layer created successfully!"
echo "Layer name: $LAYER_NAME"
echo "Local copy: essential-geospatial-layer.zip"

# Clean up
cd /
rm -rf $WORK_DIR
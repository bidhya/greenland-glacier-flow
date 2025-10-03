#!/bin/bash

# Build Lambda Layer with Conda Dependencies for Sentinel-2 Processing
# This script creates a Lambda layer with the required geospatial libraries

set -e

echo "🐍 Building Lambda Layer with Conda Dependencies"

# Configuration
LAYER_NAME="glacier-processing-dependencies"
REGION="us-west-2"
PYTHON_VERSION="3.9"  # Lambda supports 3.9

# Create working directory
WORK_DIR=$(mktemp -d)
LAYER_DIR="$WORK_DIR/python"
echo "📁 Working directory: $WORK_DIR"

# Install miniconda in temp directory
echo "📦 Installing Miniconda..."
cd $WORK_DIR
wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $WORK_DIR/miniconda
export PATH="$WORK_DIR/miniconda/bin:$PATH"

# Create conda environment with required packages
echo "🌍 Creating conda environment..."
conda create -n lambda_env python=$PYTHON_VERSION -y

# Activate environment
source activate lambda_env

# Install packages from environment.yml (simplified for Lambda)
echo "📚 Installing essential packages..."
conda install -c conda-forge -y \
    geopandas \
    rioxarray \
    boto3 \
    pystac-client \
    gdal \
    tqdm \
    netcdf4

# Copy site-packages to layer directory
echo "📋 Copying packages to layer directory..."
mkdir -p $LAYER_DIR
cp -r $WORK_DIR/miniconda/envs/lambda_env/lib/python*/site-packages/* $LAYER_DIR/

# Create layer zip
echo "🗜️  Creating layer zip..."
cd $WORK_DIR
zip -r layer.zip python/

# Upload to AWS Lambda as layer
echo "☁️  Uploading layer to AWS Lambda..."
aws lambda publish-layer-version \
    --layer-name $LAYER_NAME \
    --description "Geospatial dependencies for glacier processing" \
    --zip-file fileb://layer.zip \
    --compatible-runtimes python3.9 \
    --region $REGION

# Clean up
cd /
rm -rf $WORK_DIR

echo "✅ Lambda layer created successfully!"
echo "Layer name: $LAYER_NAME"
echo "Region: $REGION"
echo ""
echo "🔗 Next: Add this layer to your Lambda function in AWS Console"
echo "   - Go to Lambda function configuration"
echo "   - Add layer: $LAYER_NAME"
echo "   - Use latest version"
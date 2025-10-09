#!/bin/bash
#
# Sync processed satellite data from AWS S3 to local directory
# 
# Usage:
#   ./sync_from_s3.sh                           # Sync both satellites (skip existing files)
#   ./sync_from_s3.sh sentinel2                 # Sync only Sentinel-2
#   ./sync_from_s3.sh landsat                   # Sync only Landsat
#   ./sync_from_s3.sh --dry-run                 # See what would be synced
#   ./sync_from_s3.sh --exclude-downloads       # Skip download/ folder (saves bandwidth)
#   ./sync_from_s3.sh --force-overwrite         # Overwrite existing files (use with caution)
#   ./sync_from_s3.sh sentinel2 --exclude-downloads  # Combine options
#
# Default Behavior:
#   - Downloads files that don't exist locally
#   - SKIPS files that already exist (safe for multi-user batch processing)
#   - Use --force-overwrite to update existing files
#
# Examples:
#   # Safe sync - only get new files
#   ./sync_from_s3.sh --exclude-downloads
#
#   # Force update all files from S3 (overwrites existing)
#   ./sync_from_s3.sh --exclude-downloads --force-overwrite
#
#   # Preview what would be downloaded
#   ./sync_from_s3.sh --exclude-downloads --dry-run
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
S3_BUCKET="greenland-glacier-data"
S3_BASE_PATH="1_download_merge_and_clip"
DATA_DIR="$HOME/greenland_glacier_flow"

# Change to data directory (keeps Git repo separate from data)
cd "$DATA_DIR" || { echo "Error: Cannot cd to $DATA_DIR"; exit 1; }
echo -e "${GREEN}Working in data directory: ${DATA_DIR}${NC}\n"

# Parse arguments
SATELLITE="all"
DRY_RUN=""
EXCLUDE_DOWNLOADS=""
SYNC_MODE="--size-only"  # DEFAULT: Skip existing files (filename match)

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN="--dryrun"
            ;;
        --exclude-downloads)
            EXCLUDE_DOWNLOADS="--exclude 'download/*'"
            ;;
        --force-overwrite)
            SYNC_MODE=""  # Remove --size-only to enable overwrite
            ;;
        sentinel2|landsat|all)
            SATELLITE="$arg"
            ;;
        *)
            echo -e "${YELLOW}Unknown argument: $arg${NC}"
            echo -e "${YELLOW}Usage: $0 [sentinel2|landsat|all] [--dry-run] [--exclude-downloads] [--force-overwrite]${NC}"
            exit 1
            ;;
    esac
done

if [[ -n "$DRY_RUN" ]]; then
    echo -e "${YELLOW}DRY RUN MODE - No files will be downloaded${NC}"
fi

if [[ -n "$EXCLUDE_DOWNLOADS" ]]; then
    echo -e "${YELLOW}EXCLUDING download/ folders - Only processed results will be synced${NC}"
fi

if [[ -z "$SYNC_MODE" ]]; then
    echo -e "${YELLOW}⚠️  FORCE OVERWRITE MODE - Existing files will be replaced if different${NC}"
else
    echo -e "${GREEN}SAFE MODE - Existing files will be skipped (multi-user friendly)${NC}"
fi

echo ""

# Function to sync a satellite
sync_satellite() {
    local satellite=$1
    local s3_path="s3://${S3_BUCKET}/${S3_BASE_PATH}/${satellite}/"
    local local_path="${S3_BASE_PATH}/${satellite}/"
    
    echo -e "${BLUE}Syncing ${satellite} data...${NC}"
    echo "From: ${s3_path}"
    echo "To:   ${PWD}/${local_path}"
    
    if [[ -n "$EXCLUDE_DOWNLOADS" ]]; then
        echo -e "${YELLOW}Excluding: download/ folder${NC}"
    fi
    echo ""
    
    # Create local directory if it doesn't exist
    mkdir -p "${local_path}"
    
    # Build sync command
    local sync_cmd="aws s3 sync \"${s3_path}\" \"${local_path}\" ${DRY_RUN} ${SYNC_MODE} --no-progress"
    
    if [[ -n "$EXCLUDE_DOWNLOADS" ]]; then
        sync_cmd="${sync_cmd} --exclude \"download/*\""
    fi
    
    # Execute sync
    eval ${sync_cmd}
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ ${satellite} sync complete${NC}\n"
    else
        echo -e "${YELLOW}⚠️  ${satellite} sync had issues${NC}\n"
    fi
}

# Main logic
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AWS S3 Data Sync${NC}"
echo -e "${GREEN}========================================${NC}\n"

case "$SATELLITE" in
    sentinel2)
        sync_satellite "sentinel2"
        ;;
    landsat)
        sync_satellite "landsat"
        ;;
    all)
        sync_satellite "sentinel2"
        sync_satellite "landsat"
        ;;
    *)
        echo -e "${YELLOW}Usage: $0 [sentinel2|landsat|all] [--dry-run] [--exclude-downloads]${NC}"
        exit 1
        ;;
esac

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Sync Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

# Show summary
echo ""
echo "Local directory structure:"
tree -L 3 -h "${S3_BASE_PATH}" 2>/dev/null || ls -lh "${S3_BASE_PATH}"

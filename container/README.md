# Container Quickstart Guide

**Run Greenland Glacier Flow processing in Docker containers**

## Prerequisites

- Docker installed and running
- AWS credentials configured (for Landsat processing)
- Root processing directory created with correct ownership

## Setup

### 1. Create Processing Directory

```bash
# Create the root processing directory
mkdir -p /home/bny/greenland_glacier_flow

# Ensure correct ownership (if created by user, this defaults correctly)
# If created by root/sudo, fix ownership:
# chown -R $USER:$USER /home/bny/greenland_glacier_flow
```

**Important**: The container requires `/home/bny/greenland_glacier_flow` to exist on the host. The container cannot create this root directory itself due to volume mounting constraints.

## Quick Start Commands

### Sentinel-2 Processing

```bash
docker run --rm --user $(id -u):$(id -g) -v /home/bny/greenland_glacier_flow:/app/processing -e satellite=sentinel2 -e regions=140_CentralLindenow -e date1=2025-08-01 -e date2=2025-08-05 glacier-container:latest
```

### Landsat Processing

```bash
docker run --rm --user $(id -u):$(id -g) -v /home/bny/greenland_glacier_flow:/app/processing -v ~/.aws:/home/ubuntu/.aws:ro -e satellite=landsat -e regions=140_CentralLindenow -e date1=2025-08-01 -e date2=2025-08-05 glacier-container:latest
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `satellite` | Satellite type | `sentinel2` or `landsat` |
| `regions` | Region name | `140_CentralLindenow` |
| `date1` | Start date | `2024-10-01` |
| `date2` | End date | `2024-10-05` |

## Output Structure

Processing creates the following directory structure:

```
/home/bny/greenland_glacier_flow/
├── 1_download_merge_and_clip/
│   ├── sentinel2/
│   │   └── {region}/
│   │       ├── clipped/
│   │       ├── download/
│   │       ├── metadata/
│   │       └── template/
│   └── landsat/
│       └── {region}/
│           └── {scene_files}.tif
└── slurm_jobs/
    ├── sentinel2/logs/
    └── landsat/logs/
```

## Building the Container

Build the container from the repository root:

```bash
docker build -f container/Dockerfile.glacier -t glacier-container:latest .
```

## Notes

- **File Ownership**: Output files are owned by the user running the container (not root)
- **AWS Credentials**: Required for Landsat processing via `~/.aws` volume mount
- **Processing Time**: Sentinel-2 (~5-10 minutes), Landsat (~2-5 minutes) for test regions
- **Disk Space**: Plan for ~500MB+ per region for Sentinel-2, ~3MB+ for Landsat

## Troubleshooting

### Permission Errors
- Ensure `/home/bny/greenland_glacier_flow` exists and is owned by your user
- Check that Docker is running with `--user $(id -u):$(id -g)`

### Missing AWS Credentials
- For Landsat: ensure `~/.aws/credentials` exists with valid AWS keys
- Sentinel-2 uses free public data, no credentials needed

### Container Not Found
- Build the container using the instructions in the "Building the Container" section above</content>
<parameter name="filePath">/home/bny/Github/greenland-glacier-flow/container/README.md
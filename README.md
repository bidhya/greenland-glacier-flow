# Greenland Glacier Flow Processing - Step 1: Data Acquisition

**Step 1 of 3-Step Workflow**: Download, process, and organize satellite imagery for glacier velocity analysis.

This is the **data acquisition and preprocessing stage** of the Greenland glacier flow velocity workflow. It downloads and processes Sentinel-2 and Landsat satellite imagery, organizing outputs for downstream velocity calculations (Step 2) and final data packaging (Step 3). All subsequent workflow steps depend on the file structure and data products generated here.

## Workflow Pipeline

1. **Step 1 (This Repository)**: Download, merge, clip, and organize satellite imagery → `1_download_merge_and_clip/`
2. **Step 2 (Downstream)**: Calculate surface displacement maps for velocity estimation → Requires Step 1 outputs
3. **Step 3 (Downstream)**: Orthocorrect and package results into NetCDF files → Requires Steps 1 & 2 outputs

## 🎯 Project Status (January 23, 2026)

**Production Ready**: Batch processing infrastructure complete and validated for HPC deployment.

- ✅ **192 Glacier Regions**: Full Greenland coverage with predictable batch slicing
- ✅ **Dual Satellite Support**: Unified workflow for Sentinel-2 and Landsat
- ✅ **Multi-Environment**: HPC (SLURM), local (WSL/Ubuntu), and AWS Lambda execution
- ✅ **Batch Processing**: `--start-end-index` parameter for systematic region batching
- ✅ **Configuration-Driven**: INI config with CLI override capability
- ✅ **Cloud Ready**: AWS Lambda containerized deployment available

## 🚀 Quick Start

### Process Specific Regions
```bash
# Single region
./submit_job.sh --satellite sentinel2 --regions 134_Arsuk --date1 2025-01-01 --date2 2025-12-31

# Multiple regions
./submit_job.sh --satellite landsat --regions 134_Arsuk,101_sermiligarssuk --date1 2025-01-01 --date2 2025-12-31
```

### Batch Processing (HPC Production)
```bash
# Sentinel-2: Process all 192 regions in 3 batches (65 regions each)
./submit_job.sh --satellite sentinel2 --start-end-index 0:65 --date1 2025-01-01 --date2 2025-12-31
./submit_job.sh --satellite sentinel2 --start-end-index 65:130 --date1 2025-01-01 --date2 2025-12-31
./submit_job.sh --satellite sentinel2 --start-end-index 130:195 --date1 2025-01-01 --date2 2025-12-31
# Note: 3 batches used due to AWS free account limit of 4 concurrent downloads

# Landsat: 1 batch of 100 regions (faster processing)
./submit_job.sh --satellite landsat --start-end-index 0:100 --date1 2025-01-01 --date2 2025-12-31
```

### Test Before Production
```bash
# Dry-run to verify job file generation
./submit_job.sh --satellite sentinel2 --start-end-index 0:3 --date1 2025-01-01 --date2 2025-01-31 --dry-run true

# Local execution for debugging
./submit_job.sh --satellite sentinel2 --regions 134_Arsuk --execution-mode local --date1 2025-01-01 --date2 2025-01-31
```

## 📖 Documentation

### Main Documentation
- **[AGENTS.md](AGENTS.md)** - Complete workflow guide, architecture decisions, and AI agent instructions
- **[CHANGELOG.md](CHANGELOG.md)** - Detailed change history and feature additions
- **[config.ini](config.ini)** - Configuration file (modify for your environment)

### AWS Cloud Processing
- **[aws/README.md](aws/README.md)** - AWS directory overview
- **[aws/docs/](aws/docs/)** - Complete AWS Lambda documentation and setup guides

### Historical Documentation
- **[Archive/legacy_README.md](Archive/legacy_README.md)** - Pre-2025 workflow documentation

## 🏗️ Architecture

### Core Scripts
- **`submit_satellite_job.py`** - Master job submission script (HPC/local)
- **`submit_job.sh`** - Wrapper script with conda environment activation
- **`config.ini`** - Central configuration with sectioned parameters

### Processing Workflows
- **Sentinel-2**: `1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py`
  - Downloads MGRS tiles, merges overlapping scenes, clips to glacier boundaries
  - Outputs: clipped imagery, metadata CSVs, reference templates
- **Landsat**: `1_download_merge_and_clip/landsat/download_clip_landsat.py`
  - Downloads Landsat scenes via STAC API, clips to glacier regions
  - Outputs: clipped imagery, STAC query results, reference templates

### Output Structure (Required by Downstream Steps)
```
1_download_merge_and_clip/
├── sentinel2/
│   └── <region_name>/      # Region-specific processing directory
│       ├── download/        # Raw MGRS tiles (intermediate)
│       ├── clipped/         # Clipped scenes → Used by Step 2
│       ├── metadata/        # Processing metadata → Used by Step 3
│       └── template/        # Reference templates → Used by Steps 2 & 3
└── landsat/
    ├── <region_name>/   # Clipped Landsat scenes → Used by Step 2
    └── _reference/      # STAC metadata and templates → Used by Steps 2 & 3
```

**⚠️ Critical**: Do not modify output folder structure - Steps 2 and 3 expect this exact organization.

### Key Features
- **Alphabetical Sorting**: Both satellites use identical glacier ordering (001→192)
- **Mutual Exclusivity**: `--regions` and `--start-end-index` cannot be used together
- **Package Logging**: Automatic version reporting for debugging (rioxarray, rasterio, GDAL, geopandas, xarray)
- **Environment Detection**: Automatic HPC vs local mode selection

## 🔧 Configuration

Edit `config.ini` for your environment, or use CLI overrides:

```ini
[REGIONS]
regions = 140_CentralLindenow
start_end_index = 0:65

[DATES]
date1 = 2025-01-01
date2 = 2025-12-31

[PATHS]
base_dir = /fs/project/howat.4/greenland_glacier_flow
local_base_dir = /home/bny/greenland_glacier_flow

[SETTINGS]
satellite = sentinel2
cores = 1
dry_run = False
execution_mode = auto
```

**⚠️ Important**: Use CLI overrides for testing. Never commit test values to `config.ini`.

## 🧪 Environment Setup

### Required Environment
```bash
# Activate conda environment (handled automatically by submit_job.sh)
conda activate glacier_velocity

# Key dependencies
# - Python 3.13+
# - rioxarray, rasterio, GDAL, geopandas, xarray
# - For HPC: SLURM scheduler
```

### HPC Requirements
- SLURM job scheduler
- Conda environment: `glacier_velocity`
- Network access to satellite data archives

### Local Requirements
- WSL/Ubuntu or Linux environment
- Conda/mamba with `glacier_velocity` environment
- Sufficient disk space for downloaded imagery

## 📊 Batch Processing Strategy

**192 Glaciers → 3 Batches** (optimized for AWS free account concurrent download limits):

| Batch | Index Range | Regions | Example Glaciers |
|-------|-------------|---------|------------------|
| 1 | 0:65 | 65 | 001_alison → 065_... |
| 2 | 65:130 | 65 | 066_... → 130_... |
| 3 | 130:195 | 62* | 131_... → 192_CH_Ostenfeld |

**Why 3 batches?** AWS free account allows maximum 4 concurrent downloads. Using 3 batches maximizes parallel processing capacity while staying within limits.

**Why this works**: Alphabetical sorting ensures consistent glacier assignment across both satellites. *Last batch contains remaining 62 regions (code stops at final glacier).

## 🎓 Usage Tips

1. **Test with dry-run first**: Verify job files before submission
2. **Start small**: Test 3-5 glaciers before full batch runs
3. **Monitor resources**: Check memory/runtime requirements with initial runs
4. **Use wrappers**: `./submit_job.sh` handles environment activation automatically
5. **Check logs**: SLURM output includes package versions for debugging

## 🚨 Troubleshooting

### Common Issues

**Package version errors**: Check job output for installed package versions
```
Python 3.13
    rioxarray: 0.15.0
    rasterio: 1.3.9
    osgeo: 3.6.2
```

**GDAL version warnings**: Environment uses GDAL 3.10.3 (fixed in [environment.yml](environment.yml)). Newer versions may trigger warnings and have not been thoroughly tested with this workflow.

**Wrong glaciers processed**: Verify region sorting is enabled in processing scripts

**Job fails immediately**: Check conda environment activation and SLURM configuration

## 🔬 Development

### Recent Achievements (January 2026)
- ✅ **January 23**: AWS Lambda containerization complete - Python 3.13 containerized deployment validated
- ✅ **January 23**: Lambda positioned as gap filling platform for targeted satellite data acquisition
- ✅ **January 23**: Unified Lambda infrastructure (single function, single ECR repository)
- ✅ **January 23**: Updated batch processing strategy (3 batches of 65 regions for AWS download limits)
- ✅ **January 23**: Comprehensive documentation updates across all guides

### Recent Achievements (December 2025)
- ✅ **December 22**: Fixed critical config hierarchy bug (runtime/memory now correctly read from config.ini)
- ✅ **December 22**: Enhanced config.ini with comprehensive batch processing documentation
- ✅ **December 22**: Streamlined AGENTS.md (83% reduction, optimized for AI agents)
- ✅ **December 22**: Updated documentation structure and AWS integration
- ✅ **December 21**: Batch processing infrastructure complete with automatic log/job naming
- ✅ **December 21**: Consistent region sorting across both satellites
- ✅ **December 21**: Package version logging added to all job outputs
- ✅ **December 21**: Code cleanup (removed legacy parameters)

### Future Enhancements
- [ ] Automated resource allocation based on region size
- [ ] Incremental processing (only new dates)
- [ ] Result validation pipeline
- [ ] Integration with downstream velocity analysis

## 📝 Citation

If you use this workflow in your research, please cite:

```
Yadav, B., et al. (2025). Greenland Glacier Flow Processing System.
GitHub: https://github.com/bidhya/greenland-glacier-flow
```

## 👥 Contributors

- B. Yadav - Sentinel-2 workflow developer, Current maintainer, HPC/AWS workflow development and deployment
- T. Chuddley - Landsat workflow developer
- M. Gravina - Code refactoring and re-organization

## 📧 Contact

For questions or issues, please open a GitHub issue or contact the maintainers.

## 🔗 Related Resources

- **AWS Data Source**: Satellite imagery accessed from AWS Open Data Registry (Sentinel-2, Landsat)
- **AWS Lambda**: See `aws/docs/` for cloud processing setup and deployment guides
- **Historical Workflow**: See `Archive/legacy_README.md` for pre-2025 refactoring documentation

---

**Current Focus**: HPC batch processing for 2025 production data delivery. AWS Lambda capability available for specialized use cases.
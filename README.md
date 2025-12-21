# Greenland Glacier Flow Processing - Step 1: Data Acquisition

**Step 1 of 3-Step Workflow**: Download, process, and organize satellite imagery for glacier velocity analysis.

This is the **data acquisition and preprocessing stage** of the Greenland glacier flow velocity workflow. It downloads and processes Sentinel-2 and Landsat satellite imagery, organizing outputs for downstream velocity calculations (Step 2) and final data packaging (Step 3). All subsequent workflow steps depend on the file structure and data products generated here.

## Workflow Pipeline

1. **Step 1 (This Repository)**: Download, merge, clip, and organize satellite imagery → `1_download_merge_and_clip/`
2. **Step 2 (Downstream)**: Calculate surface displacement maps for velocity estimation → Requires Step 1 outputs
3. **Step 3 (Downstream)**: Orthocorrect and package results into NetCDF files → Requires Steps 1 & 2 outputs

## 🎯 Project Status (December 2025)

**Production Ready**: Batch processing infrastructure complete and validated for HPC deployment.

- ✅ **192 Glacier Regions**: Full Greenland coverage with predictable batch slicing
- ✅ **Dual Satellite Support**: Unified workflow for Sentinel-2 and Landsat
- ✅ **Multi-Environment**: HPC (SLURM) and local (WSL/Ubuntu) execution
- ✅ **Batch Processing**: `--start-end-index` parameter for systematic region batching
- ✅ **Configuration-Driven**: INI config with CLI override capability

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
# Process first 48 glaciers (batch 1 of 4)
./submit_job.sh --satellite sentinel2 --start-end-index 0:48 --date1 2025-01-01 --date2 2025-12-31

# Process next 48 glaciers (batch 2 of 4)
./submit_job.sh --satellite sentinel2 --start-end-index 48:96 --date1 2025-01-01 --date2 2025-12-31

# Continue with remaining batches: 96:144, 144:192
```

### Test Before Production
```bash
# Dry-run to verify job file generation
./submit_job.sh --satellite sentinel2 --start-end-index 0:3 --date1 2025-01-01 --date2 2025-01-31 --dry-run true

# Local execution for debugging
./submit_job.sh --satellite sentinel2 --regions 134_Arsuk --execution-mode local --date1 2025-01-01 --date2 2025-01-31
```

## 📖 Documentation

- **[AGENTS.md](AGENTS.md)** - Complete workflow guide, architecture decisions, and AI agent instructions
- **[CHANGELOG.md](CHANGELOG.md)** - Detailed change history and feature additions
- **[config.ini](config.ini)** - Configuration file (modify for your environment)

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
start_end_index = 0:48

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
# - Python 3.11+
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

**192 Glaciers → 4 Batches** (optimal for HPC resource management):

| Batch | Index Range | Regions | Example Glaciers |
|-------|-------------|---------|------------------|
| 1 | 0:48 | 48 | 001_alison → 048_ingia |
| 2 | 48:96 | 48 | 049_jakobshavn → 096_... |
| 3 | 96:144 | 48 | 097_... → 144_... |
| 4 | 144:192 | 48 | 145_... → 192_CH_Ostenfeld |

**Why this works**: Alphabetical sorting ensures consistent glacier assignment across both satellites.

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
Python 3.11.5
    rioxarray: 0.15.0
    rasterio: 1.3.9
    osgeo: 3.6.2
```

**Wrong glaciers processed**: Verify region sorting is enabled in processing scripts

**Job fails immediately**: Check conda environment activation and SLURM configuration

## 🔬 Development

### Recent Achievements (December 2025)
- ✅ Batch processing infrastructure complete
- ✅ Consistent region sorting across both satellites
- ✅ Package version logging added to all job outputs
- ✅ Code cleanup (removed legacy parameters)

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

- B. Yadav - Original Sentinel-2 workflow developer, Current maintainer, HPC/AWS workflow development
- T. Chuddley - Original Landsat workflow developer
- M. Gravina -  Code refactoring and re-organization

## 📧 Contact

For questions or issues, please open a GitHub issue or contact the maintainers.

---

**Legacy Documentation**: See `legacy_README.md` for historical workflow information (pre-2025 refactoring).
# QAQC - Quality Assurance & Quality Control

This directory contains Python scripts for quality assurance, quality control, and data accounting for the Greenland glacier flow processing system.

## Purpose

These scripts provide:
- **Data Accounting**: Count imagery per region, track processing status
- **Quality Validation**: Verify data integrity and processing results
- **Quicklook Generation**: Create preview images and summaries
- **Analysis Tools**: Statistical analysis and reporting

## Scripts

### Data Accounting
- `count_imagery_per_region.py` - Count satellite imagery files per glacier region
- `processing_status.py` - Track processing completion status across regions

### Quality Validation
- `validate_data_integrity.py` - Check file integrity and metadata consistency
- `compare_results.py` - Compare processing results across different runs

### Quicklook & Visualization
- `generate_quicklooks.py` - Create thumbnail/preview images
- `create_summary_reports.py` - Generate statistical summaries and reports

## Usage

All scripts are designed to be cross-platform and work on Linux, Windows, and macOS.

### Prerequisites
```bash
pip install -r requirements.txt
```

### Example Usage
```bash
# Count imagery for all regions
python count_imagery_per_region.py --data-dir /path/to/processed/data

# Generate quicklooks for specific region
python generate_quicklooks.py --region 134_Arsuk --output-dir ./quicklooks
```

## Dependencies

- `pandas` - Data manipulation
- `geopandas` - Geospatial data handling
- `rasterio` - Raster data processing
- `matplotlib` - Plotting and visualization
- `numpy` - Numerical operations

## Contributing

When adding new QAQC scripts:
1. Follow the existing naming conventions
2. Include docstrings and type hints
3. Add command-line argument parsing
4. Include example usage in docstrings
5. Update this README with the new script description</content>
<parameter name="filePath">/home/bny/Github/greenland-glacier-flow/qaqc/README.md
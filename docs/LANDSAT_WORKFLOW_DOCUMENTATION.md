# Landsat Workflow Documentation

This document provides comprehensive specifications and processing details for the Landsat satellite data workflow in the Greenland Glacier Flow project. It covers data sources, naming conventions, download processes, clip operations, and known technical considerations.

## Data Source & Naming Conventions

**Data Provider**: USGS Landsat Collection 2 Level-1 via AWS Earth Search STAC API
- **STAC URL**: `https://earth-search.aws.element84.com/v1`
- **Collection**: `landsat-c2l1` (Level-1 orthorectified products)
- **Processing Level**: Level-1 (orthorectified, not atmospherically corrected)

### Landsat Scene Naming Convention
Landsat scenes use WRS-2 (Worldwide Reference System) path/row identifiers.

**Scene ID Format**: `LC08_L1GT_044034_20130330_20200913_02_T2`
- **LC08**: Landsat 8
- **L1GT**: Level-1, Geometric Terrain correction
- **044034**: Path 044, Row 034
- **20130330**: Acquisition date (YYYYMMDD)
- **20200913**: Processing date
- **02**: Collection number
- **T2**: Tier (T1 = highest quality, T2 = acceptable)

### Workflow Implementation
Subset ID creation for unique file naming:
```python
gdf["subset_id"] = (
    pd.to_datetime(gdf["datetime"], format="mixed").dt.strftime("%Y%m%d%H%M%S")
    + "_"
    + gdf["landsat:scene_id"]
    + "_"
    + gdf["id"]
    + "_ortho"
)
```

**Result**: `{timestamp}_{scene_id}_{stac_id}_ortho.tif`

## Key Specifications
- **Spatial Resolution**: 30m (NIR band used for velocity calculations)
- **Scene Size**: ~185km × 180km (varies by latitude)
- **Data Type**: Surface Reflectance (not atmospherically corrected)
- **Format**: Cloud-Optimized GeoTIFF via AWS S3
- **Temporal Resolution**: 16 days (Landsat 8 revisit cycle)

## Workflow Overview and Processing Logic

### Core Processing Steps
The Landsat workflow consists of two main phases: search/download and clip/reproject.

#### 1. Search and Download Phase (`search_and_download_region()` function)
- **STAC Query**: Searches for Landsat scenes intersecting glacier AOIs within date ranges, filtered by minimum intersection threshold.
  ```python
  search = stac.search(
      intersects=geometry_wgs84,
      datetime=daterange,
      collections=["landsat-c2l1"],
      limit=500,
      max_items=1e9,
  )
  ```
- **Filtering**: Removes already downloaded scenes and those below intersection threshold.
- **AWS Download**: Uses boto3 session for authenticated S3 access (requester pays).
- **Output**: Saves STAC query results to CSV for reference.

#### 2. Clip and Reproject Phase (`download_clip_and_squeeze_one_stac_result()`)
- **Download**: Streams scene from AWS S3 using Rasterio.
- **Clip**: Clips to glacier bounds in source CRS.
- **Squeeze**: Reduces to single NIR band.
- **Reproject**: Matches template raster (NSIDC Polar Stereographic, 30m resolution).
- **Save**: Exports as `{subset_id}.tif`.

### Subset ID Logic
- **Components**: Timestamp (YYYYMMDDHHMMSS) + Landsat scene ID + STAC item ID + "_ortho"
- **Purpose**: Unique identifier for each processed scene
- **Example**: `20130330150000_LC08_L1GT_044034_20130330_20200913_02_T2_LC80440342013060LGN00_ortho.tif`

### Key Differences from Sentinel-2
- **No Merging**: Each Landsat scene is processed individually (no tile grouping like Sentinel-2's 37-char truncation).
- **Resolution**: 30m vs 10m (coarser, fewer scenes needed per region).
- **Metadata**: Only STAC query CSV; no per-file lineage CSVs like Sentinel-2.
- **Coverage Check**: Commented out (all qualifying scenes saved).
- **Download Method**: Direct S3 access vs STAC asset URLs.

### Reference Folder Structure
- **Location**: `{base_dir}/reference/` (common to all regions)
- **Contents per Region**:
  - **STAC Query Results CSV**: `{region_name}_stac_query_results.csv` - Contains the filtered STAC search results for that region, used for error-checking and auditing.
  - **Template TIF**: `{region_name}.tif` - A master reference raster created once per region, ensuring all processed scenes match in projection, grid size, resolution, and spatial bounds. Persists throughout the workflow for consistency.

### CSV File Handling
- **Creation**: Exported each time a region is processed.
- **Behavior on Reprocessing**: Completely overwritten (no merging or appending) with new STAC query results.
- **Purpose**: Provides a snapshot of the most recent query/filter results for auditing; does not preserve historical data across runs.
- **Creation**: Exported each time a region is processed.
- **Behavior on Reprocessing**: Completely overwritten (no merging or appending) with new STAC query results.
- **Purpose**: Provides a snapshot of the most recent query/filter results for auditing; does not preserve historical data across runs.

## Function Reference

This section provides detailed breakdowns of key functions in the Landsat processing workflow.

### search_and_download_region()
**Purpose**: Orchestrates STAC search and download for a single glacier region.

**Parameters**:
- `region_name`: Region identifier (e.g., `049_jakobshavn`).
- `aoi_gdf`: Full AOI geodataframe.
- `daterange`: Date range string (`YYYY-MM-DD/YYYY-MM-DD`).
- `intersect_frac_thresh`: Minimum AOI coverage to retain scenes.
- `base_dir`: Root output directory.
- `reference_dir`: Directory for reference files (CSVs, templates).
- `errored_downloads_log_name`: Log file for failed downloads.

**Logic**:
1. Extract region geometry from AOI.
2. Run STAC search and filter results.
3. Remove already downloaded scenes.
4. Create reprojection template if needed.
5. Download and process each remaining scene.

**Returns**: None.

**Rationale**: Handles per-region processing, ensuring efficient downloads and error logging.

### stac_search_aoi()
**Purpose**: Queries STAC API for Landsat scenes intersecting a region.

**Parameters**:
- `region_aoi_gdf`: Single-region geodataframe.
- `daterange`: Date range string.
- `intersect_threshold`: Minimum coverage fraction.

**Logic**:
1. Convert geometry to WGS84 for STAC query.
2. Search Landsat C2L1 collection.
3. Create geodataframe from results.
4. Filter by content and intersection.

**Returns**: Filtered geodataframe with scene metadata.

**Rationale**: Retrieves relevant Landsat scenes with quality filtering.

### download_clip_and_squeeze_one_stac_result()
**Purpose**: Downloads, clips, and reprojects a single Landsat scene.

**Parameters**:
- `output_dir`: Directory for output .tif.
- `subset_id`: Unique scene identifier.
- `aws_href`: S3 URL for scene data.
- `region_name`: Region identifier.
- `region_aoi_gdf`: Region geometry.
- `sample_raster`: Template for reprojection.
- `errored_downloads_log_name`: Error log file.

**Logic**:
1. Check if output exists (skip if so).
2. Open remote file with Rasterio.
3. Clip to region bounds in source CRS.
4. Squeeze to single NIR band.
5. Reproject to match template.
6. Save as .tif.

**Returns**: None.

**Rationale**: Processes individual scenes into analysis-ready format.

## Technical Debts and Known Issues

### Commented-Out Coverage Check
- **Issue**: Coverage quality check is disabled in `download_clip_and_squeeze_one_stac_result()`.
- **Code**: Lines calculating coverage fraction and rejecting <50% scenes are commented.
- **Impact**: All downloaded scenes are saved, potentially including low-coverage data.
- **Status**: Technical debt; uncomment and test for production use.

### No Data Lineage Tracking
- **Issue**: Unlike Sentinel-2, no CSV metadata tracking source files per output.
- **Impact**: Harder to audit data provenance for velocity calculations.
- **Status**: Could be added if needed for consistency.

### AWS Credentials Handling
- **Issue**: Falls back to default credentials if CSV file missing.
- **Risk**: Potential authentication failures in different environments.
- **Status**: Works for current setup; document credential requirements.

### Template Persistence Across Years
- **Issue**: Templates are created per region but may be recreated if processing different years separately, potentially leading to mismatches in spatial parameters (projection, grid, resolution) across years.
- **Risk**: Inconsistent data alignment if templates differ between yearly runs.
- **Proposed Solution**: Use a single persistent template per region across all years to ensure uniformity.
- **Status**: Technical debt; investigate if mismatches exist and implement shared templates if needed.

## Future Improvements

### Documentation Enhancements
- Add comprehensive docstrings to all Landsat functions.
- Document parameter behaviors and error handling.
- Include workflow diagrams and Landsat vs Sentinel-2 comparisons.

### Code Refactoring
- Enable and test coverage quality checks.
- Add data lineage CSV creation for consistency with Sentinel-2.
- Improve error handling and logging for production reliability.

### Workflow Validation
- Compare Landsat and Sentinel-2 outputs for data quality.
- Assess resolution differences on velocity calculation accuracy.
- Evaluate scene density requirements for Greenland coverage.

## References</content>
<parameter name="filePath">/home/bny/Github/greenland-glacier-flow/docs/LANDSAT_WORKFLOW_DOCUMENTATION.md
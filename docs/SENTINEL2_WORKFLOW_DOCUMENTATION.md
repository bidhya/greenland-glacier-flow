# Sentinel-2 Workflow Documentation

This document provides comprehensive specifications and processing details for the Sentinel-2 satellite data workflow in the Greenland Glacier Flow project. It covers data sources, naming conventions, download processes, merge/clip operations, metadata creation, and known technical considerations.

## Data Source & Naming Conventions

**Data Provider**: Copernicus Data Space Ecosystem via AWS Earth Search STAC API
- **STAC URL**: `https://earth-search.aws.element84.com/v1`
- **Collection**: `sentinel-2-l2a` (Level-2A atmospherically corrected products)
- **Processing Level**: Level-2A (Surface Reflectance) - optimal for quantitative analysis

### Official Sentinel-2 Product Naming Convention
```
MMM_MSIXXX_YYYYMMDDHHMMSS_Nxxyy_ROOO_Txxxxx_<Product Discriminator>.SAFE
```

**Components**:
- **MMM**: Mission ID (`S2A`/`S2B`)
- **MSIXXX**: `MSIL2A` (Level-2A products used in workflow)
- **YYYYMMDDHHMMSS**: Datatake sensing start time
- **Nxxyy**: Processing Baseline number (e.g., `N0500` for baseline 05.00)
- **Importance**: ESA updates algorithms over time to improve product quality and correct errors
- **Higher numbers**: Generally indicate better quality data
- **Example baselines**: N0204 (older), N0400 (current), N0500 (latest)
- **ROOO**: Relative Orbit number (`R001`-`R143`)
- **Txxxxx**: MGRS Tile identifier (e.g., `T22WEB`)
- **<Product Discriminator>**: 15-character timestamp for product distinction
- **.SAFE**: Standard Archive Format for Europe

**Example**: `S2A_MSIL2A_20240101T000000_N0500_R001_T22WEB_20240101T000000.SAFE`

### Workflow Implementation
```python
# Filename construction in download_region() function
download_filename = f'{item.properties["s2:product_uri"][:-5]}_B08.tif'
```

**Process**:
1. Takes full product URI from STAC metadata
2. Removes last 5 characters (`.SAFE`)
3. Appends `_B08.tif` for Band 8 (near-infrared, 10m resolution)

**Result**: `{product_stem}_B08.tif` (e.g., `S2A_MSIL2A_20240101T000000_N0500_R001_T22WEB_20240101T000000_B08.tif`)

## Key Specifications
- **Spatial Resolution**: 10m (Band 8 NIR used for velocity calculations)
- **Tile Size**: 110km × 110km (UTM/WGS84 projection)
- **Data Type**: Surface Reflectance (atmospherically corrected)
- **Format**: Cloud-Optimized GeoTIFF via STAC API
- **Temporal Resolution**: 5 days (Sentinel-2A + Sentinel-2B combined)

## Tile Filtering Strategy
```python
# Filter to glacier-relevant tiles only
tile_ids = aoi['utm_grid'].values[0].split(',')
items = [item for item in items if item.id.split("_")[1] in tile_ids]
```

**Benefits**:
- Reduces download volume by ~90%
- Focuses processing on Greenland glacier regions only
- Uses pre-selected UTM tile IDs from geopackage

## Landsat vs Sentinel-2 Processing Differences

### Sentinel-2 Advantages (observed in HPC results)
- ✅ Successful processing of all 75 glacier regions (3 batches × 25)
- ✅ Consistent 10m resolution across all bands
- ✅ Atmospheric correction (Level-2A) ready for analysis
- ✅ Smaller tile footprint reduces memory requirements

### Potential Landsat Challenges
- 🔄 Timeout on large glaciers (100 regions in single batch)
- ❓ Different resolution combinations (15m/30m bands)
- ❓ Additional processing steps for atmospheric correction
- ❓ Larger data volumes per scene

## Clipped File Naming and Processing Logic

### Post-Processing Workflow

After downloading individual Sentinel-2 tiles, the workflow performs **merge and clip operations** to create final glacier-specific datasets.

### Tile Grouping Strategy

Multiple Sentinel-2 tiles covering the same glacier region are intelligently grouped for processing:

```python
# Get a unique version of this list that includes relative orbit number and truncates
# the filename string after hour of acquisition.
tifs_set = set([x[:37] for x in aoi_tifs])  # Truncate to 37 characters
```

### 37-Character Truncation Logic

The **37-character truncation** captures the common prefix shared by tiles from the **same satellite acquisition**:

**Original naming convention**:
```
S2A_MSIL2A_YYYYMMDDHHMMSS_Nxxyy_ROOO_Txxxxx_<Product Discriminator>.SAFE
```

**37-character truncation** includes:
- `S2A_MSIL2A_YYYYMMDDHHMMSS_Nxxyy_ROOO` (37 characters total)

This groups tiles that share:
- **Satellite** (S2A/S2B)
- **Date and time** (YYYYMMDDHHMMSS)
- **Processing baseline** (Nxxyy)
- **Relative orbit** (ROOO)

### Why 37-Character Truncation Works

The 37-character truncation **preserves acquisition uniqueness** while enabling tile merging:

**Preserved (ensures same acquisition + processing quality)**:
- Satellite ID (S2A/S2B)
- Acquisition date/time (YYYYMMDDHHMMSS) 
- Processing baseline (Nxxyy) - ensures consistent algorithm version
- Relative orbit (ROOO)

**Dropped (tile-specific, safe to merge)**:
- Tile identifier (Txxxxx) - different tiles from same acquisition can be merged
- Product discriminator - not needed for merged product uniqueness

**Rationale**: Sentinel-2 data is distributed in 110km × 110km tiles for easier data distribution. Tiles from the same satellite acquisition (same date/time/orbit/baseline) provide seamless coverage and can be safely merged. Processing baseline ensures consistent algorithm versions across merged tiles. If acquisition times or baselines differed, the data wouldn't be mergeable for velocity analysis.

This ensures **temporal consistency** - only data acquired at the exact same moment gets combined into glacier velocity datasets.

### Clipped File Naming Convention

**Final clipped filename**: `{truncated_prefix}.tif`

**Example**:
- **Input tiles** (different MGRS tiles, same acquisition):
  - `S2A_MSIL2A_20240101T000000_N0500_R001_T22WEB_20240101T000000_B08.tif`
  - `S2A_MSIL2A_20240101T000000_N0500_R001_T22WEA_20240101T000000_B08.tif`
- **Truncated prefix**: `S2A_MSIL2A_20240101T000000_N0500_R001`
- **Clipped output**: `S2A_MSIL2A_20240101T000000_N0500_R001.tif`

### Processing Benefits

1. **Efficient Merging**: Tiles from the same satellite pass are merged seamlessly
2. **Glacier Coverage**: Large glaciers spanning multiple tiles get complete coverage
3. **Unique Identifiers**: Each clipped file represents one unique satellite acquisition
4. **Predictable Naming**: Filename reflects the acquisition parameters
5. **Processing Units**: Creates optimal processing chunks regardless of tile count

### Why This Matters

- **Large Glaciers**: Can span 2-3+ Sentinel-2 tiles (110km × 110km each)
- **Seamless Coverage**: Merged tiles provide continuous glacier coverage
- **Memory Efficiency**: Single clipped file per acquisition vs. multiple tile files
- **Analysis Ready**: Clipped to exact glacier boundaries for velocity calculations

## Processing Baselines

ESA periodically updates Sentinel-2 processing algorithms to improve data quality:

- **N0200-N0299**: Early operational baselines
- **N0300-N0399**: Improved geolocation and radiometry  
- **N0400**: Major update (Jan 2022) - improved cloud/snow detection, terrain correction
- **N0500**: Latest baseline (2023+) - enhanced atmospheric correction, better cirrus detection

**Key improvements over time**:
- Better cloud and snow/ice discrimination
- Improved atmospheric correction (aerosol, water vapor)
- Enhanced terrain shadow handling
- More accurate geolocation
- Better handling of bright surfaces and water bodies

Higher baseline numbers generally provide better quality data for quantitative analysis like glacier velocity measurements.

## Potential Data Integrity Issues

### Duplicate Files with Different Processing Baselines

**Issue**: Occasionally, download directories may contain duplicate files with different processing baselines (e.g., N0400 vs N0500) for the same acquisition.

**Possible Causes**:
- Older files not yet deleted from data archive
- Permanent persistence due to data management oversight
- Files not yet processed with latest algorithm
- Data provider keeping multiple versions for validation

**Current Status**: No explicit guards against such duplicates in the workflow.

**Risk Assessment**:
- **Low Risk**: Mixed baselines in downloads are sometimes acceptable
- **Potential Issue**: Could lead to inconsistent processing if wrong version selected
- **May Not Be Current Problem**: Could have been resolved in recent data management

**Investigation Needed**:
- Check for duplicate detection logic in download/merge process
- Verify which baseline version gets selected when duplicates exist
- Assess if this affects data quality or processing consistency

**Proposed Solution**: Compare files by removing processing baseline and product discriminator + file extension to identify true duplicates:

```
# Remove: Nxxxx_<Product_Discriminator>.tif
# Keep: S2A_MSIL2A_YYYYMMDDHHMMSS_ROOO_Txxxxx
# This identifies files from same acquisition regardless of processing version
```

**Priority**: Low - investigate when time permits, likely not affecting current production runs.

## Workflow Overview and Processing Logic

### Core Processing Steps
The Sentinel-2 workflow consists of three main phases: download, merge/clip, and metadata creation. This section details how files are downloaded, processed, and named.

#### 1. Download Phase (`download_region()` function)
- **STAC API Query**: Searches Copernicus Data Space Ecosystem for Sentinel-2 Level-2A products intersecting glacier AOIs within specified date ranges.
- **Tile Filtering**: Reduces downloads by ~90% by filtering to pre-selected UTM tiles from the AOI geopackage.
  ```python
  tile_ids = aoi['utm_grid'].values[0].split(',')
  items = [item for item in items if item.id.split("_")[1] in tile_ids]
  ```
- **File Download**: Downloads Band 8 (NIR, 10m resolution) as Cloud-Optimized GeoTIFFs.
- **Naming**: Constructs filename from product URI: `{product_stem}_B08.tif`
  ```python
  download_filename = f'{item.properties["s2:product_uri"][:-5]}_B08.tif'
  ```
- **Storage**: Saves to year-specific folders (e.g., `downloads/2024/`).

#### 2. Merge and Clip Phase (`post_process_region()` → `merge_and_clip_tifs()`)
- **Tile Grouping**: Groups downloaded tiles by truncating filenames to 37 characters to identify same-acquisition data.
  ```python
  tifs_set = set([x[:37] for x in aoi_tifs])
  ```
- **Why Truncate?**: Preserves satellite, date/time, processing baseline, and orbit (ensuring temporal consistency) while dropping tile-specific identifiers (safe for merging).
- **Merging**: Combines multiple tiles from the same acquisition into seamless coverage using rioxarray.
- **Clipping**: Reprojects and clips merged data to glacier boundaries using a template raster.
- **Coverage Check**: Saves clipped `.tif` only if glacier coverage > 50%.
- **Output Naming**: `{truncated_prefix}.tif` (e.g., `S2A_MSIL2A_20240101T000000_N0500_R001.tif`)

#### 3. Metadata Creation Phase (`concat_csv_files()`)
- **Individual CSVs**: Created per clipped `.tif` to track source files merged into it.
  ```python
  # In merge_and_clip_tifs()
  with open(metadata_file, 'w') as outfile:
      for key in tif_dict.keys():
          vals = ",".join(tif_dict[key])
          outfile.write(f'{key},{vals}')
  ```
- **Combined CSVs**: Regional manifests concatenating all individual CSVs for a region.
- **Recreation**: Both types are recreated if clipped files are reprocessed (no persistence checks).

### 37-Character Truncation Logic
- **Full Convention**: `S2A_MSIL2A_YYYYMMDDHHMMSS_Nxxyy_ROOO_Txxxxx_<Product_Discriminator>.SAFE`
- **Truncated**: `S2A_MSIL2A_YYYYMMDDHHMMSS_Nxxyy_ROOO` (37 chars)
- **Preserved Elements**: Satellite ID, acquisition time, processing baseline, relative orbit
- **Dropped Elements**: Tile ID, product discriminator (these vary per tile but not per acquisition)
- **Benefit**: Groups tiles from the same satellite pass for merging, creating unique processing units

### CSV Metadata System
- **Purpose**: Provides data lineage audit trail from source downloads to final products
- **Individual CSVs**: One per clipped `.tif`, lists constituent source files
- **Combined CSVs**: Regional summaries, potentially for NSIDC metadata in step 3
- **Storage**: `metadata/individual_csv/{region}/` and `metadata/combined_csv/`
- **Recreation Behavior**: Automatically regenerated during reprocessing

## Function Reference

This section provides detailed breakdowns of key functions in the Sentinel-2 processing workflow, including purpose, parameters, logic, returns, and rationale.

### download_region()
**Purpose**: Downloads Sentinel-2 Level-2A Band 8 (NIR) tiles from the Copernicus Data Space Ecosystem via STAC API, filtered to glacier-relevant UTM tiles.

**Parameters**:
- `download_folder`: Path to store downloaded .tif files.
- `geom`: Shapely geometry of the AOI.
- `aoi`: Geopandas DataFrame with region details, including UTM tile IDs.
- `start_date`, `end_date`: Date range for data search.
- `collection_name`: STAC collection (default: sentinel-2-l2a).

**Logic**:
1. Initialize STAC client and search for intersecting items.
2. Filter items to AOI's UTM tiles (reduces downloads by ~90%).
3. For each item, construct Band 8 filename and download via URL.

**Returns**: None (downloads files to disk).

**Rationale**: Efficiently acquires only relevant NIR data for glacier velocity analysis, minimizing storage and processing overhead.

### post_process_region()
**Purpose**: Orchestrates the merge, clip, and metadata creation for a region's downloaded Sentinel-2 tiles.

**Parameters**:
- `aoi`: Geopandas DataFrame of the region.
- `start_date`, `end_date`: Processing date range.
- `download_folder`, `clip_folder`: Paths for input/output.
- `template_folder`: Path for clipping template.
- `region`: Region name.
- `cores`: Number of CPU cores for parallel processing.
- `metadata_folder`: Path for CSV metadata.

**Logic**:
1. Extract UTM tile IDs from AOI.
2. For each year, collect downloaded .tifs and group by 37-character truncation.
3. Create clipping template if needed.
4. Parallel process each group: merge tiles, clip to AOI, save .tif and CSV.

**Returns**: None.

**Rationale**: Handles large-scale processing of multiple tiles per region, ensuring seamless coverage and data lineage tracking.

### merge_and_clip_tifs()
**Purpose**: Merges multiple Sentinel-2 tiles from the same acquisition, clips to glacier boundaries, and creates metadata.

**Parameters**:
- `clip_folder`: Output path for clipped .tif.
- `metadata_folder`: Output path for CSV.
- `download_folder`: Input path for downloaded tiles.
- `aoi_tifs`: List of all .tif filenames in AOI.
- `tif_prefix`: 37-character truncated prefix for grouping.
- `aoi`: Geopandas DataFrame of the region.
- `template_tif`: Path to clipping template.
- `tile_ids`: List of UTM tile IDs.

**Logic**:
1. Check if output .tif exists (skip if so).
2. Subset .tifs to those matching prefix.
3. Sort by tile order and merge arrays.
4. Reproject and clip to template.
5. Calculate coverage; save .tif if >50%.
6. Create individual CSV with source files.

**Returns**: `tif_prefix`, `subset` (intended for NSIDC metadata, currently unused).

**Rationale**: Produces analysis-ready datasets by combining tiles into single acquisitions, ensuring temporal consistency for velocity calculations.

### concat_csv_files()
**Purpose**: Combines individual CSVs into a regional manifest for data lineage tracking.

**Parameters**:
- `base_metadata_folder`: Base path for metadata.
- `region`: Region name.
- `folder_structure`: 'old' or 'new' (affects subfolder paths).

**Logic**:
1. Locate individual CSV folder.
2. Read and concatenate all CSVs into a single DataFrame.
3. Save combined CSV to `combined_csv/{region}.csv`.

**Returns**: None.

**Rationale**: Creates audit trails for downstream use (e.g., NSIDC metadata), aggregating per-acquisition lineage into regional summaries.

## Technical Debts and Known Issues

### Unused Return Values
- **Function**: `merge_and_clip_tifs()` returns `tif_prefix` and `subset` (for NSIDC metadata)
- **Issue**: Return values are ignored in calling code (`post_process_region()`)
- **Impact**: Intended metadata not captured; potential data lineage gap
- **Status**: Technical debt; may need implementation or removal

### Potentially Unused Combined CSVs
- **Creation**: `concat_csv_files()` creates regional combined CSV manifests
- **Usage**: No downstream consumption found in current codebase
- **Intended Purpose**: NSIDC metadata and step 3 processing
- **Status**: Created but unused; verify against step 3 requirements

### Data Integrity Concerns
- **Duplicate Files**: Occasional duplicates with different processing baselines
- **Detection**: No explicit guards; relies on filename uniqueness
- **Risk**: Low; may not affect current production
- **Mitigation**: Proposed duplicate detection by comparing core acquisition identifiers

## Future Improvements

### Documentation Enhancements
- Add comprehensive docstrings to all Sentinel-2 functions
- Document parameter behaviors, return value purposes, and edge cases
- Include workflow diagrams and data flow explanations

### Code Refactoring
- Implement or remove unused return values based on step 3 analysis
- Add duplicate file detection logic if needed
- Improve error handling and logging for production reliability

### Workflow Validation
- Investigate combined CSV usage in step 3 processing
- Verify data lineage completeness for NSIDC metadata requirements
- Assess impact of technical debts on downstream analysis

## References
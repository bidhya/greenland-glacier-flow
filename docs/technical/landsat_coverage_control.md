# Landsat Coverage Quality Control (December 2025)

### Status: Implemented but Currently Disabled

**Current State**: The coverage quality control feature is fully implemented in the code but commented out as an optional enhancement. This allows easy activation after research validation of Landsat data patterns.

**Why Disabled**: Landsat data characteristics may differ from Sentinel-2, requiring validation that the 50% coverage threshold is appropriate for Landsat scenes before activation.

### Why We Filter Landsat Scenes

**Problem**: Landsat scenes often only partially cover our glacier regions of interest. Processing and storing scenes with minimal glacier coverage wastes storage space and computational resources, while providing insufficient data for reliable glacier velocity calculations.

**Solution**: Automatically reject Landsat scenes that cover less than 50% of the glacier area of interest (AOI).

### How It Works

1. **Area of Interest (AOI)**: Each glacier region is defined by a polygon or bounding box representing the glacier boundary
2. **Coverage Calculation**: For each Landsat scene, we count pixels that contain valid data within the AOI
3. **Quality Threshold**: Only scenes covering ≥50% of the glacier area are saved for further processing
4. **Data Reduction**: Scenes with <50% coverage are logged and discarded

### Practical Benefits

- **Storage Savings**: Eliminates processing of partial/inadequate scenes
- **Computational Efficiency**: Reduces processing time by skipping low-value data
- **Velocity Accuracy**: Ensures sufficient spatial coverage for reliable flow calculations
- **Data Quality**: Maintains consistent quality standards across all processed scenes

### Technical Implementation

**Location**: `1_download_merge_and_clip/landsat/lib/functions.py` - `download_clip_and_squeeze_one_stac_result()`

**Current Status**: Code is implemented but commented out for research validation

**Pixel Size**: Landsat uses 15m × 15m resolution = 225 m² per pixel

**Coverage Formula**:
```python
covered_pixels = xr.where(rxr_ds > 0, 1, 0).sum().item()
covered_area_km2 = covered_pixels * 225 / 1e6  # Convert m² to km²
coverage_fraction = covered_area_km2 / glacier_area_km2
```

**Decision Logic**:
```python
if coverage_fraction >= 0.5:  # 50% threshold
    # Save scene for velocity processing
    rxr_ds.rio.to_raster(output_fpath)
else:
    # Reject and log
    logstr = f"Scene {scene_id} rejected: {coverage_fraction:.1%} coverage"
    logging.info(logstr)
    print(logstr)
```

### Activation Instructions

**To Enable Coverage Quality Control:**

1. **Uncomment the import** in `1_download_merge_and_clip/landsat/lib/functions.py`:
   ```python
   # Uncomment for coverage quality control
   # import xarray as xr
   ```

2. **Uncomment the coverage check block** (lines ~449-468):
   ```python
   # Uncomment for coverage quality control
   # coverage_check_code_here
   ```

3. **Test with sample data** to validate the 50% threshold works appropriately for Landsat scenes

**To Disable (Current State):**
- Keep the import and coverage check code commented out
- All intersecting Landsat scenes will be processed regardless of coverage

### Key Differences from Sentinel-2

- **Sentinel-2**: Merges multiple tiles first, then checks total coverage
- **Landsat**: Evaluates each individual scene before saving
- **Processing**: Landsat processes scenes sequentially vs Sentinel-2's tile merging approach

### Validation Results

- ✅ **Code Implementation**: Successfully integrated coverage filtering logic
- ✅ **Local Testing**: Code functions correctly when activated
- ✅ **AWS Lambda**: Ready for cloud processing pipeline
- ✅ **Data Quality**: Consistent 50% threshold across both satellites (when activated)
- ✅ **Performance**: Minimal overhead, only processes qualifying scenes (when activated)

### Example Impact

**Before Filtering** (Current Behavior):
- Process all intersecting Landsat scenes regardless of coverage
- Store partial data that may not be usable for velocity analysis
- May waste computational resources on inadequate scenes

**After Filtering** (When Activated):
- Only process scenes with ≥50% glacier coverage
- Ensure sufficient spatial data for accurate velocity calculations
- Reduce storage and processing costs significantly

### Research Needed

**Before activating this feature, research should validate:**
- Whether 50% coverage threshold is appropriate for Landsat scenes
- How Landsat scene footprints compare to Sentinel-2 tile coverage
- Impact on data availability for different glacier regions
- Whether partial scenes still provide value for some analysis types
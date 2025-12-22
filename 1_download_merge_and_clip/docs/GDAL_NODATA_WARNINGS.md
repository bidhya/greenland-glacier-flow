# GDAL NoData Warnings - Known Issue Documentation

**Status**: 🟡 **Cosmetic Issue - Low Priority**  
**Date Identified**: December 19, 2025  
**Impact**: Verbose log output only - no data quality issues

## Problem Description

GDAL 3.10.4+ produces NoData warnings during rasterio operations:
```
WARNING:CPLE_AppDefined:Value 0 in the source dataset has been changed to 1 in the destination dataset 
to avoid being treated as NoData. To avoid this, select a different NoData value for the destination dataset.
```

**Frequency**: ~5 warnings per scene × 3 scenes × 2 regions = ~30 warnings per typical local test run

## Root Cause Analysis

**File**: `1_download_merge_and_clip/sentinel2/lib/functions.py`

**Triggering Operations** (in order of execution):

### 1. UTM Zone Reprojections (Lines 373, 384)
```python
merged = merged.rio.reproject(EPSG_CODE_STRING, resolution=10, resampling=Resampling.cubic)
merged2 = merged2.rio.reproject(EPSG_CODE_STRING, resolution=10, resampling=Resampling.cubic)
```
- **Triggers**: 1-2 warnings per scene (depends on single/multiple UTM zones)

### 2. Template Matching (Line 396)
```python
clipped = merged.rio.reproject_match(dst10m)
```
- **Triggers**: 1 warning per scene

### 3. Clipped Scene Write (Line 410)
```python
clipped.rio.to_raster(clipped_tif)
```
- **Triggers**: 1 warning per scene

### 4. Template Clipping (Line 525)
```python
clipped = merged.rio.clip(aoi.geometry.apply(mapping), aoi.crs)
```
- **Triggers**: 1 warning per template creation

### 5. Template Write (Line 552)
```python
clipped.rio.to_raster(template_tif)
```
- **Triggers**: 1 warning per template creation

**Why This Happens**: GDAL prevents confusion between "real zero pixel values" and "missing data" by adjusting NoData metadata during reprojection/clipping operations.

## Version Information

- **Last Clean Version**: GDAL 3.10.3 (no NoData warnings)
- **Current Version**: GDAL 3.10.4+ (warnings introduced)
- **Environment**: Python 3.13, rioxarray, conda glacier_velocity environment

## Impact Assessment

### Data Quality: ✅ **No Impact**
- Actual raster data is **NOT affected**
- Metadata adjustment only
- Output imagery is scientifically valid

### Operational Impact: ⚠️ **Minor Annoyance**
- Log files become verbose (30+ warnings per run)
- Harder to spot real errors among warnings
- Production runs with 196 regions will generate ~3,000+ warnings

## Potential Solutions (Not Yet Implemented)

### Option 1: Explicit NoData Value (Recommended)
```python
# Add nodata parameter to rasterio operations
clipped.rio.to_raster(clipped_tif, nodata=-9999)
```
- **Pros**: Clean solution, proper metadata handling
- **Cons**: Requires testing to ensure -9999 doesn't conflict with valid data range

### Option 2: Suppress GDAL Warnings (Quick Fix)
```python
# Add at top of processing script
import warnings
warnings.filterwarnings('ignore', category=rasterio.errors.NotGeoreferencedWarning)
```
- **Pros**: Immediate log cleanup
- **Cons**: Might hide legitimate GDAL errors

### Option 3: Environment Variable (Global Suppression)
```bash
# Add to job submission scripts
export CPL_LOG=/dev/null
```
- **Pros**: No code changes needed
- **Cons**: Suppresses ALL GDAL messages including errors

### Option 4: Downgrade GDAL (Not Recommended)
```bash
conda install gdal=3.10.3
```
- **Pros**: Eliminates warnings completely
- **Cons**: Loses bug fixes, potential compatibility issues

## Decision & Next Steps

**Current Decision**: **Leave as-is for now**
- Production focus is on 2025 data delivery
- Warnings don't affect data quality
- Can be addressed post-delivery

**When to Revisit**:
1. After 2025 production runs complete
2. During next major refactoring cycle
3. If log file sizes become problematic on HPC
4. If team members report confusion from verbose logs

**Recommended Approach**: Test Option 1 (explicit NoData) on development branch with validation that output TIFFs are identical before/after change.

## Related GDAL Issues

### 1. Coverage Warning (Working as Designed)
```
INFO:Coverage is less than minimum of 95% for S2B_MSIL2A_20250505T142749_N0511_R139. 
Did not create template.
```
- **File**: Same file, line 535
- **Purpose**: Quality control - rejects partial scenes for template creation
- **Action**: None needed - this is correct behavior

### 2. BLOCKXSIZE/TILED Warning (Step 3 Workflow)

**Warning Message**:
```
WARNING:CPLE_IllegalArg in 101_sermiligarssuk_median_orbitmatch_dmag.tif: 
BLOCKXSIZE can only be used with TILED=YES
```

**Source**: Step 3 of workflow (velocity processing)  
**Environment**: Same conda glacier_velocity environment  
**Date Identified**: December 19, 2025

#### Problem Description
GDAL complains when GeoTIFF creation options specify `BLOCKXSIZE` without also setting `TILED=YES`. This occurs during the velocity field processing step when writing output rasters.

#### Impact Assessment
**Data Quality**: ✅ **No Impact**
- GDAL ignores the invalid option and continues
- Output files are created correctly
- Processing completes successfully

**Operational Impact**: ⚠️ **Minor Annoyance**
- Adds noise to log files
- One warning per output GeoTIFF file

#### Root Cause
GeoTIFF creation options are inconsistent - specifying block size without enabling tiled format:
```python
# Problematic pattern (likely in step 3 code)
profile.update({
    'BLOCKXSIZE': 256,  # Block size specified
    # Missing: 'TILED': 'YES'
})
```

#### Solution
Add `TILED=YES` when using `BLOCKXSIZE` or `BLOCKYSIZE`:
```python
# Correct pattern
profile.update({
    'TILED': 'YES',
    'BLOCKXSIZE': 256,
    'BLOCKYSIZE': 256
})
```

**Decision**: Defer until step 3 workflow refactoring. Does not affect data quality.

## Test Results

**May 4-7, 2025 Test Run (Step 1)**:
- Regions: 134_Arsuk, 101_sermiligarssuk
- Total warnings: ~30 NoData warnings + 1 coverage warning
- Processing: Successful
- Data quality: Validated ✅

**December 19, 2025 (Step 3)**:
- Regions: 101_sermiligarssuk
- Warning: 1 BLOCKXSIZE/TILED warning
- Processing: Successful
- Data quality: Not affected

---

**Document Created**: December 19, 2025  
**Last Updated**: December 19, 2025  
**Author**: B. Yadav

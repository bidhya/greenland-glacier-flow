# Folder Structure Decision for 2025 Production

**Date**: December 19, 2025  
**Decision**: Revert to region-specific folder structure for 2025 production data

## Context

In October 2025, we developed and tested an optimized centralized folder structure that reduces duplicate downloads and saves 50-70% bandwidth. However, for the 2025 production run, we are **reverting to the old region-specific structure**.

## Folder Structure Comparison

### Current (2025 Production) - Region-Specific
```
sentinel2/
├── 134_Arsuk/
│   ├── download/2025/     # Region-specific downloads
│   ├── clipped/
│   ├── template/
│   └── metadata/
│       ├── combined_csv/
│       └── individual_csv/
├── 101_sermiligarssuk/
│   ├── download/2025/
│   ├── clipped/
│   ├── template/
│   └── metadata/
```

**Implementation**: Lines 54-59 in `download_and_post_process_region.py`

### Future (Post-2025) - Centralized Structure
```
sentinel2/
├── download/2025/         # Shared tile pool (no duplication)
├── clipped/
│   ├── 134_Arsuk/
│   └── 101_sermiligarssuk/
├── template/              # Shared templates
└── metadata/
    └── individual_csv/
        ├── 134_Arsuk/
        └── 101_sermiligarssuk/
```

**Implementation**: Lines 62-67 in `download_and_post_process_region.py` (commented out)

## Rationale for Reversion

### 1. Data Consistency
- **Historical Data**: Previous years (2015-2024) use region-specific structure
- **Compatibility**: Analysis pipelines expect consistent folder organization
- **Documentation**: Existing user guides reference region-specific paths

### 2. Risk Management
- **Production Deadline**: 2025 data delivery is time-sensitive
- **Proven Structure**: Old structure has 5+ years of production use
- **Testing Time**: New structure needs extensive validation with full dataset

### 3. Technical Debt vs Delivery
- **Immediate Need**: Deliver 2025 data with minimal risk
- **Future Optimization**: New structure ready for post-2025 runs
- **No Code Loss**: Both implementations preserved in codebase

## Code Implementation

**File**: `1_download_merge_and_clip/sentinel2/lib/download_and_post_process_region.py`

**Active Code** (2025 Production):
```python
# Lines 54-59 (ACTIVE)
download_folder = f'{base_dir}/{region}/download'
clip_folder = f'{base_dir}/{region}/clipped'
template_folder = f'{base_dir}/{region}/template'
base_metadata_folder = f'{base_dir}/{region}/metadata'
metadata_folder = f'{base_metadata_folder}/individual_csv/'
os.makedirs(metadata_folder, exist_ok=True)
```

**Commented Code** (Future Runs):
```python
# Lines 62-67 (COMMENTED OUT - Future use)
# download_folder = f'{base_dir}/download'
# clip_folder = f'{base_dir}/clipped/{region}'
# template_folder = f'{base_dir}/template'
# base_metadata_folder = f'{base_dir}/metadata'
# metadata_folder = f'{base_metadata_folder}/individual_csv/{region}'
# os.makedirs(metadata_folder, exist_ok=True)
```

**Comment in Code** (Line 61):
```python
# [New structure by BNY, Oct 2025]. Will not be used for 2025 processing, but for future runs.
```

## Trade-offs Accepted

### Disadvantages of Current Choice
- ❌ **Duplicate Downloads**: Same tile downloaded multiple times for overlapping regions
- ❌ **Storage Waste**: ~50-70% more disk space required
- ❌ **Longer Processing**: Re-downloading increases wall-clock time
- ❌ **Bandwidth Cost**: Higher network usage on HPC

### Advantages of Current Choice
- ✅ **Data Consistency**: Matches historical structure from 2015-2024
- ✅ **Zero Migration**: No need to restructure existing data
- ✅ **Minimal Risk**: Production-proven folder organization
- ✅ **User Familiarity**: Team knows existing structure
- ✅ **Documentation Alignment**: No need to update user guides

## Timeline

### October 2025
- New centralized structure developed
- Tested on local WSL environment
- Tested on AWS Lambda
- Validated with test regions (134_Arsuk, 191_Hagen_Brae)

### December 2025
- **Decision**: Revert to old structure for 2025 production
- **Reason**: Match historical data organization
- **Status**: Code commented but preserved

### Post-2025 (Future)
- Re-enable centralized structure
- Process 2026+ data with optimized folders
- Migrate historical data if needed
- Update user documentation

## How to Switch Back to Optimized Structure

When ready for future runs (2026+):

1. **Edit** `download_and_post_process_region.py`
2. **Comment out** lines 54-59 (old structure)
3. **Uncomment** lines 62-67 (new structure)
4. **Test** with 1-2 regions first
5. **Validate** output file locations
6. **Document** new structure for users

## Impact Assessment

### For 2025 Production
- **Timeline**: No delays introduced by folder migration
- **Quality**: Data quality unaffected
- **Storage**: Will use more disk space (acceptable on HPC)
- **Processing**: Longer download times (acceptable given deadline)

### For Future Runs
- **Optimization Ready**: New structure code maintained
- **Easy Switch**: Simple uncomment/comment swap
- **Validated**: Already tested in October 2025
- **Benefits Clear**: 50-70% savings documented

## Related Documentation

- **AGENTS.md**: Section "Sentinel-2 Processing Optimizations" updated
- **download_and_post_process_region.py**: Lines 52-67 with inline comments
- **GDAL_NODATA_WARNINGS.md**: Separate issue, not related to folder structure

---

**Decision Owner**: B. Yadav  
**Approved Date**: December 19, 2025  
**Review Date**: After 2025 production complete

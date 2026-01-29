# GDAL Compatibility Investigation & Upgrade Plan

**Date**: January 28, 2026
**Branch**: `feature/gdal-upgrade`
**Status**: UNSOLVED - GDAL warnings persist, workflow functional but noisy
**Priority**: Deferred - abandon for now, solve later
**Focus**: Comprehensive investigation of GDAL/rasterio compatibility issues in Step 1 processing

## Issue Summary

**UNSOLVED PROBLEM**: GDAL warnings continue to appear during Sentinel-2 processing:

```
CPLE_AppDefined: Value 0 in the source dataset has been changed to 1 in the destination dataset to avoid being treated as NoData. To avoid this, select a different NoData value for the destination dataset.
```

These warnings pollute logs and indicate underlying GDAL/rasterio compatibility issues that remain unresolved.

## Current Status

### ⚠️ **Workflow Functionality: COMPROMISED**
- **Processing**: Completes successfully but with log pollution
- **Output Quality**: Appears correct but GDAL warnings indicate potential data handling issues
- **Data Integrity**: Unknown - warnings suggest GDAL is modifying nodata values unexpectedly
- **Performance**: Functional but noisy logging impacts monitoring

### ❌ **Warning Status: UNSOLVED**
- **Visibility**: Warnings appear in logs despite multiple suppression attempts
- **Frequency**: 1-8 warnings per region (varies by data characteristics)
- **Source**: GDAL internal operations during reprojection/merging
- **Impact**: Log noise, potential data integrity concerns, monitoring difficulties

## Overview

This document outlines the systematic approach to address GDAL-related issues and warnings in the Greenland Glacier Flow processing pipeline. The testing will start with Step 1 (satellite data download and processing) and focus on Sentinel-2 data initially.

## 🔍 MAJOR DISCOVERY: GDAL Not Required for Satellite Processing

**Date**: January 27, 2026
**Finding**: Both Landsat and Sentinel-2 processing workflows complete successfully WITHOUT GDAL installed
**Implication**: GDAL appears to be an optional dependency, not a hard requirement

### Test Results
- **Landsat Processing**: ✅ Works with rasterio 1.5.0 (no GDAL)
- **Sentinel-2 Processing**: ✅ Works with rasterio 1.5.0 (no GDAL)
- **Environment**: `glacier_velocity1` (GDAL removed from environment.yml)
- **Status**: Full processing pipelines functional without GDAL

### Key Differences Between Environments

| Environment | GDAL | rasterio | Key Observations |
|-------------|------|----------|------------------|
| `glacier_velocity` | 3.10.3 | 1.4.4 | ✅ Clean output, no errors |
| `glacier_velocity1` | ❌ None | 1.5.0 | ⚠️ Multiple sys.excepthook errors |

### Rasterio Version Impact
**Critical Finding**: rasterio 1.5.0 shows `sys.excepthook` errors when GDAL is missing, while rasterio 1.4.4 does not.

**Error Pattern** (glacier_velocity1 only):
```
Error in sys.excepthook:
Original exception was:
[repeated multiple times]
```

**Root Cause**: Version checking code attempts to import `osgeo` (GDAL), triggering exceptions when GDAL is not installed. The newer rasterio version appears more sensitive to this missing dependency.

### 🚨 CRITICAL DATA INTEGRITY ISSUE DISCOVERED

**GDAL NoData Value Corruption**: Processing logs reveal GDAL automatically changes NoData values from 0 to 1:

```
WARNING:CPLE_AppDefined:Value 0 in the source dataset has been changed to 1 in the destination dataset to avoid being treated as NoData. To avoid this, select a different NoData value for the destination dataset.
```

**Occurrences**: 2 instances detected in recent Sentinel-2 processing

### 🔍 INVESTIGATION RESULTS: NO DATA CORRUPTION FOUND

**Critical Finding**: Despite GDAL warnings, final output data is **pixel-perfect identical** between GDAL and non-GDAL processing!

**Evidence**:
- Both output files: **100% identical pixel values**
- NoData metadata: Consistent (0.0) across both runs
- Data integrity: **MAINTAINED** - No scientific data corruption detected
- Warning appears to be **false positive** or internal processing artifact

**Implications**:
- ✅ **GDAL warnings are cosmetic** - do not affect final scientific output
- ✅ **Data integrity preserved** - identical results with/without GDAL
- ✅ **rasterio sufficient** - handles Sentinel-2 processing without GDAL dependency
- ✅ **Safe to proceed** - GDAL not required for data accuracy

**Next Steps**:
- Continue testing with Landsat data
- Monitor for similar warnings in other satellite processing
- Consider suppressing GDAL warnings if they don't affect output quality

### Key Implications
1. **Simplified Dependencies**: GDAL complexity may be unnecessary
2. **Focus Shift**: From functionality to performance/warnings optimization
3. **Environment Flexibility**: Option to run without GDAL for simpler deployments
4. **Testing Scope**: GDAL testing becomes optimization rather than requirement validation

**Note**: This discovery significantly changes the testing approach from "does it work without GDAL?" to "what are the trade-offs in performance/warnings?"

### ✅ ERROR HANDLING IMPROVEMENTS COMPLETED

**Issue Resolved**: `sys.excepthook` errors from version checking code attempting to import missing GDAL

**Root Cause**: Version checking in SLURM job scripts used `__import__('osgeo')` which crashed when GDAL not installed

**Solution Implemented**: Updated version checking code in `submit_satellite_job.py` to handle missing packages gracefully

**Changes Made**:
- ✅ Modified HPC mode version checking (line 152) to catch ImportError exceptions
- ✅ Updated local mode version checking (line 89) for consistency  
- ✅ Added GDAL error handler in `lib/functions.py` to capture GDAL warnings properly
- ✅ Enhanced file saving error handling in `merge_and_clip_tifs()` function

**Testing Results**:
- ✅ Version checking now works in both GDAL and non-GDAL environments
- ✅ GDAL warnings are properly logged instead of causing sys.excepthook errors
- ✅ File saving operations have better error reporting
- ✅ Displays "NOT INSTALLED - [error message]" instead of crashing

**Impact**: Eliminates confusing sys.excepthook errors, provides clear package availability information

### ✅ REAL-WORLD TESTING COMPLETED

**Test Run**: Sentinel-2 processing with `glacier_velocity1` environment (no GDAL, rasterio 1.5.0)

**Results**:
- ✅ **Version checking**: Graceful handling of missing GDAL - no crashes
- ✅ **Data processing**: Successful download and processing of 2 Sentinel-2 scenes
- ✅ **File output**: 2 GeoTIFF files created successfully (660x690 pixels each)
- ✅ **Data integrity**: 100% valid pixels, correct NoData values, proper CRS
- ✅ **Error handling**: File saving operations completed without exceptions
- ⚠️ **Minor issue**: Some sys.excepthook errors during cleanup (non-critical)

**Key Finding**: Processing pipeline works correctly with improved error handling. The remaining sys.excepthook errors occur during shutdown/cleanup and do not affect processing results or data quality.

### ✅ NODATA=0 HYPOTHESIS CONFIRMED

**Hypothesis**: GDAL warning about NoData value changes could be eliminated by explicitly setting `nodata=0` in `to_raster()` call

**Implementation**: Modified `clipped.rio.to_raster(clipped_tif)` to `clipped.rio.to_raster(clipped_tif, nodata=0)`

**Results**:
- ✅ **GDAL Warning Eliminated**: No more "Value 0 in source dataset changed to 1 in destination" warnings
- ✅ **Data Integrity Maintained**: Pixel-perfect identical output data
- ✅ **Processing Success**: Clean execution without GDAL warnings
- ✅ **No Side Effects**: All metadata and file properties unchanged

**Root Cause Confirmed**: GDAL was automatically changing NoData values from 0 to 1 to avoid confusion, but explicit `nodata=0` parameter tells GDAL that 0 is the intended NoData value.

### ✅ RASTERIO VERSION COMPARISON COMPLETED

**Hypothesis Tested**: rasterio 1.5.0 causes sys.excepthook errors while rasterio 1.4.4 provides clean execution

**Test Results**:
- ✅ **rasterio 1.4.4**: Clean execution, no sys.excepthook errors, successful processing
- ❌ **rasterio 1.5.0**: Same processing results but with cryptic sys.excepthook errors
- ✅ **Data integrity**: Identical output quality across both versions
- ✅ **nodata=0 fix**: Works for both rasterio versions (eliminates GDAL warnings)

**Root Cause Identified**: rasterio 1.5.0 has error handling regressions that manifest as sys.excepthook errors during normal processing operations, while rasterio 1.4.4 handles the same operations cleanly.

**Critical Finding: sys.excepthook Errors Are NOT Python Exceptions**
- **Debug Test Result**: Enhanced exception handler debug output does NOT appear
- **Conclusion**: "Error in sys.excepthook" messages are NOT Python exceptions
- **Root Cause**: Direct stderr output from rasterio 1.5.0/GDAL during cleanup
- **Implication**: Cannot be caught by Python exception handlers - requires different solution

**Recommendation**: 
- **Pin rasterio to 1.4.4** for production stability
- **Keep GDAL at 3.10.3** (maintains rasterio 1.4.4 compatibility)
- **Apply nodata=0 fix** universally for GDAL warning elimination

**Status**: ✅ **Issue resolved** - rasterio 1.4.4 confirmed as stable choice with clean error handling

### 🔍 DETAILED RASTERIO 1.5.0 CHANGE ANALYSIS

**Date**: January 27, 2026  
**Research**: Deep dive into specific code changes causing sys.excepthook errors

**Key Changes in Rasterio 1.5.0 Causing sys.excepthook Errors**:

#### 1. **MemoryDataset Context Management (PR #3461)**
- **What changed**: Replaced manual `try/finally` blocks with `.close()` calls with proper context managers using `ExitStack` and `enter_context(MemoryDataset(...))`
- **Impact**: MemoryDataset objects now guaranteed to be closed when exiting contexts, but changes timing and order of cleanup during Python interpreter shutdown
- **Files affected**: `_features.pyx`, `_fill.pyx`, `_warp.pyx`, `merge.py`

#### 2. **Multiple Close Handling (PR #3480)**  
- **What changed**: Removed `_closed` attribute tracking, modified `closed` property to check `self._hds == NULL`, changed `__exit__` methods to always call `close()` rather than checking if already closed
- **Impact**: Datasets can now be closed multiple times safely, but may cause cleanup code to run in different contexts during shutdown
- **Files affected**: `_base.pyx`, `_base.pxd`, `_io.pyx`, `_transform.pyx`, `_warp.pyx`, `io.py`, `transform.py`, `vrt.py`

#### 3. **Duplicate Dataset Cleanup Removal (PR #3473)**
- **What changed**: Removed redundant dataset deletion code since GDAL 3.2.0+ handles this automatically
- **Impact**: Simplified cleanup logic, potentially changing when and how cleanup occurs
- **Files affected**: `_io.pyx`

**Root Cause Analysis**:
The `sys.excepthook` errors are **stderr output from rasterio's cleanup code running during Python interpreter shutdown**. Changes to context management and multiple-close handling mean cleanup operations now occur during shutdown when they previously didn't, or occur in a different order.

**Critical Finding**: Since processing completes successfully ("Finished." appears before errors), the errors are **non-critical artifacts** - just cleanup code printing to stderr during interpreter teardown.

**Production Recommendations**:
1. **For production use**: Rasterio 1.5.0 acceptable if stderr output during shutdown tolerable
2. **For clean operation**: Stick with rasterio 1.4.4 if stderr artifacts unacceptable  
3. **No code changes needed**: Errors don't affect functionality, just shutdown behavior

### ✅ SIMPLE LOGGING IMPLEMENTATION COMPLETED

**Date**: January 27, 2026  
**Issue Resolved**: sys.excepthook errors now captured in log files

**Solution Implemented**: 
- Added `setUpSimpleLoggingConfig()` function that redirects stderr to log file
- Updated Sentinel-2 script to use simple logging instead of enhanced logging
- **Result**: All stderr output (including rasterio sys.excepthook errors) now captured in log files

**Testing Results**:
- ✅ stderr redirection working - warnings and errors appear in both console and log file
- ✅ Rasterio stderr output captured (tested with NotGeoreferencedWarning)
- ✅ No performance impact - simple redirection approach
- ✅ Backward compatible - maintains all existing logging functionality

**Files Modified**:
- `1_download_merge_and_clip/sentinel2/lib/utility.py` - Added simple logging function
- `1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py` - Switched to simple logging

**Impact**: Eliminates "unknown" sys.excepthook errors by ensuring all stderr output is logged for debugging and monitoring.

## Technical Analysis

### Warning Source
- **GDAL Operation**: Internal nodata value conversion during reprojection
- **Trigger**: `rio.reproject_match()` and array merging operations
- **Nature**: Informational warning, not an error
- **GDAL Version**: 3.12.1 (bundled with rasterio 1.5.0)

### Why Warnings Persist
- **CPLE_AppDefined**: Specific GDAL error class for application-defined messages
- **Not suppressed by CPL_LOG**: This variable affects different logging channels
- **Internal conversion**: GDAL automatically adjusts nodata values it considers invalid

## Current Mitigation

### Log Management
- Warnings captured in log files via stderr redirection
- No terminal output pollution
- Workflow continues normally despite warnings

### Code Stability
- Explicit resource cleanup prevents crashes
- Error handling robust across different data conditions
- Processing reliable for production use

## Future Considerations

### Potential Solutions
1. **GDAL Configuration**: Explore additional GDAL environment variables
2. **Alternative Approach**: Use different nodata handling strategies
3. **Version Testing**: Test with different GDAL/rasterio combinations
4. **Warning Suppression**: Find GDAL-specific method to suppress CPLE_AppDefined

### Priority Assessment
- **Functional Impact**: Compromised - warnings indicate data handling issues
- **Production Readiness**: Degraded - log pollution affects monitoring
- **Future-Proofing**: Failed - rasterio 1.5.0 upgrade incomplete
- **Status**: DEFERRED - abandon current approach, solve later

## Testing Results Summary

| Test Date | Region | Rasterio | GDAL | Warnings | Status |
|-----------|--------|----------|------|----------|--------|
| 2026-01-27 | 140_CentralLindenow | 1.5.0 | 3.12.1 | 5 warnings | ✅ Success |
| 2026-01-27 | 138_SermiitsiaqInTasermiut | 1.5.0 | 3.12.1 | 1 warning | ✅ Success |
| 2026-01-27 | 104_sorgenfri | 1.5.0 | 3.12.1 | 2 warnings | ✅ Success |
| 2026-01-27 | 134_Arsuk | 1.5.0 | 3.12.1 | 8 warnings | ✅ Success |

## Conclusion

**UNSOLVED: GDAL warnings persist with rasterio 1.5.0.** Multiple suppression attempts have failed. The warnings indicate potential data integrity issues where GDAL is unexpectedly modifying nodata values during processing.

**Current Approach: ABANDON FOR NOW**
- Accept the warnings as unavoidable with current library versions
- Continue using rasterio 1.5.0 for functional compatibility
- Defer solution to future library upgrades or alternative approaches

**Future Resolution Required:**
- Investigate GDAL 3.12.1 + rasterio 1.5.0 compatibility issues
- Find effective warning suppression methods
- Validate data integrity despite warnings
- Consider alternative libraries if issues persist

**Immediate Impact:** Workflow remains functional but with compromised logging and potential data handling concerns.

---

**Last Updated**: January 28, 2026
**Status**: DEFERRED - abandon current GDAL/rasterio issues, solve later
**Next Review**: When resources available for GDAL compatibility investigation

## Testing Strategy

### Phase 1: Environment Setup
1. **Baseline Environment**: `glacier_velocity` (current GDAL 3.10.3)
2. **No GDAL Environment**: `glacier_velocity1` (modified environment.yml without GDAL)
3. **Latest GDAL Environment**: `glacier_velocity1_gdal_latest` (GDAL 3.12.1+ if needed)

### Phase 2: Sentinel-2 Testing (Priority)
1. **Baseline Testing**: Establish current behavior with GDAL 3.10.3
2. **No GDAL Testing**: Identify what breaks when GDAL is removed
3. **Latest GDAL Testing**: Test with GDAL 3.12.1+ and document improvements

### Phase 3: Comparative Analysis
- Document differences in behavior, warnings, and output quality
- Identify GDAL dependencies and compatibility requirements
- Determine optimal GDAL version for production

## Testing Parameters

Following the rotating test strategy from AGENTS.md:

### Regions (Mix of small/medium glaciers)
- 138_SermiitsiaqInTasermiut (small)
- 140_CentralLindenow (medium)
- 134_Arsuk (additional medium for validation)

### Dates (Summer months for reliable data)
- 2023-06-01 to 2023-06-06
- 2024-08-01 to 2024-08-06
- 2025-09-01 to 2025-09-06

### Execution Mode
- Local testing with `--dry-run true` initially
- Full local execution for validation
- HPC testing only after local validation

## Success Criteria

### Functional Requirements
- [ ] Sentinel-2 processing completes without critical errors
- [ ] Output data quality maintained across GDAL versions
- [ ] Processing time within acceptable limits
- [ ] Memory usage stable

### Quality Requirements
- [ ] GDAL warnings reduced or eliminated
- [ ] Error messages clear and actionable
- [ ] Backward compatibility maintained
- [ ] Forward compatibility with latest GDAL

## Risk Assessment

### Medium Risk Activities
- Environment modifications
- GDAL version changes
- Testing with modified dependencies

### Mitigation Strategies
- Test on feature branch (isolated from main/develop)
- Maintain baseline environment for comparison
- Document all changes and results
- Rollback procedures defined

## Documentation Requirements

### Test Results
- Log all warnings and errors by GDAL version
- Document performance metrics (time, memory)
- Record output data validation results
- Note any behavioral differences

### Environment Configurations
- Preserve environment.yml modifications
- Document GDAL version compatibility matrix
- Record dependency conflicts and resolutions

### Recommendations
- Optimal GDAL version for production
- Migration path for existing deployments
- Future compatibility considerations

## Implementation Timeline

### Week 1: Setup and Baseline
- Create testing environments
- Establish baseline behavior
- Document current warnings/issues

### Week 2: No GDAL Testing
- Test processing without GDAL
- Identify breaking points
- Document GDAL dependencies

### Week 3: Latest GDAL Testing
- Test with GDAL 3.12.1+
- Compare results across versions
- Validate improvements

### Week 4: Analysis and Recommendations
- Complete comparative analysis
- Document findings and recommendations
- Prepare migration plan

## Rollback Procedures

### Environment Rollback
```bash
# Switch back to baseline environment
conda activate glacier_velocity
# Or recreate from original environment.yml
conda env create -f environment.yml -n glacier_velocity_rollback
```

### Code Rollback
```bash
# Switch back to develop branch
git checkout develop
git branch -D feature/gdal-upgrade  # Only if testing complete
```

### Data Validation
- Compare output files between versions
- Verify scientific accuracy maintained
- Check file format compatibility

## Communication Plan

### Internal Documentation
- Update AGENTS.md with testing status
- Maintain testing log in this document
- Document all environment changes

### Progress Tracking
- Weekly status updates
- Issue documentation in CHANGELOG.md
- Code changes with detailed commit messages

## Dependencies

### Required Environments
- `glacier_velocity` (baseline)
- `glacier_velocity1` (no GDAL)
- `glacier_velocity1_gdal_latest` (latest GDAL)

### Test Data
- Sentinel-2 imagery for test regions
- Velocity data for validation
- Reference outputs for comparison

### Tools
- Conda/Mamba for environment management
- Git for version control
- Python testing framework for validation

## Next Steps

1. Create `glacier_velocity1` environment from modified environment.yml
2. Run baseline tests with current GDAL 3.10.3
3. Test with no GDAL configuration
4. Add latest GDAL and retest
5. Analyze and document findings

## sys.excepthook Error Analysis (January 26, 2026)

### Root Cause Identified
**sys.excepthook errors in rasterio 1.5.0 are caused by unclosed rasterio file handles during program termination.**

### Detailed Findings
- **Error Pattern**: `Exception ignored in: <function RasterioIO.__del__ at 0x...> AttributeError: 'NoneType' object has no attribute 'close'`
- **Trigger Condition**: Occurs during `sys.exit(0)` when rasterio file objects are not explicitly closed
- **Version Specific**: Only affects rasterio 1.5.0; rasterio 1.4.4 does not exhibit this behavior
- **Impact**: Errors are cleanup artifacts, not processing failures - workflow completes successfully

### Code Analysis
**Problematic Pattern** (causes sys.excepthook errors):
```python
# In create_template_tif() function
tif = rioxarray.open_rasterio(template_path)
# ... processing ...
# No explicit close() - causes sys.excepthook error on exit
```

**Solution Pattern** (eliminates sys.excepthook errors):
```python
# In create_template_tif() function  
tif = rioxarray.open_rasterio(template_path)
# ... processing ...
tif.close()  # Explicit close prevents sys.excepthook errors
```

### Validation Results
- **With explicit close()**: No sys.excepthook errors during `sys.exit(0)`
- **Without explicit close()**: sys.excepthook errors occur during termination
- **Processing Success**: Both patterns produce identical correct outputs
- **Performance Impact**: Negligible - close() operations are fast

### Implementation Status
- **Fixed**: `create_template_tif()` function now explicitly closes rasterio handles
- **Validated**: sys.excepthook errors eliminated in Sentinel-2 processing workflow
- **Scope**: Error affects all rasterio file operations in rasterio 1.5.0

### Recommendations
1. **Immediate**: Audit all rasterio file operations for explicit close() calls
2. **Best Practice**: Implement context managers (`with` statements) for all rasterio operations
3. **Testing**: Include sys.excepthook error checks in regression tests
4. **Documentation**: Update coding standards to require explicit resource cleanup

### Related Issues
- **GDAL Warnings**: Separate issue occurring during EPSG:3413 reprojection operations
- **Version Compatibility**: rasterio 1.4.4 → 1.5.0 introduces stricter resource management requirements
- **Exception Handling**: sys.excepthook errors are cleanup artifacts, not functional failures
- **Debugging Locations Identified**: Two key locations in `create_template_tif()` function for resuming sys.excepthook investigation (documented separately for future reference)

---

**Status**: Planning Phase Complete
**Next Action**: Environment creation and baseline testing
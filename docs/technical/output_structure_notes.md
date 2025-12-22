# Output Structure Documentation - Critical Notes

**Date**: December 21, 2025  
**Issue**: Inconsistent documentation of Sentinel-2 output folder structure across files

## Current Production Structure ("Old" Structure)

**Source of Truth**: `README.md` lines 75-89

```
1_download_merge_and_clip/
├── sentinel2/
│   └── <region_name>/      # Region-specific processing directory
│       ├── download/        # Raw MGRS tiles (intermediate)
│       ├── clipped/         # Clipped scenes → Used by Step 2
│       ├── metadata/        # Processing metadata → Used by Step 3
│       └── template/        # Reference templates → Used by Steps 2 & 3
└── landsat/
    ├── <region_name>/       # Clipped Landsat scenes → Used by Step 2
    └── _reference/          # STAC metadata and templates → Used by Steps 2 & 3
```

**Key Point**: Region name is the PARENT directory, containing download/clipped/metadata/template subdirectories. This is the "old" structure and is currently in production due to legacy workflow dependencies (Steps 2 & 3).

## Experimental Structure ("New" Structure - Not Yet Implemented)

```
sentinel2/
├── download/          # WRONG - suggests shared download pool
├── clipped/           # WRONG - region as subdirectory of clipped
│   ├── 134_Arsuk/
│   └── 191_Hagen_Brae/
├── metadata/          # WRONG - missing region nesting
└── template/          # WRONG - missing region nesting
```

**Why This Was Wrong**: This represented an experimental "shared download pool" architecture ("new structure") that may be implemented in the future but is NOT currently in production. QUICKSTART.md incorrectly showed this experimental structure as if it were implemented.

## Structure Terminology Clarification

- **"Old" Structure** = Current production (region-specific, all subdirs nested inside region)
- **"New" Structure** = Experimental/future (shared download pool, region-specific only for clipped outputs)
- **Status**: Using "old" structure due to legacy workflow dependencies (Steps 2 & 3 expect this layout)
- **Future**: May migrate to "new" structure when downstream workflows are updated

## Historical Context

### Old vs New Folder Structure Discussion (December 2025)
- **"Old" Structure** (current production): Region-specific directories with all subdirectories nested inside - REQUIRED for Steps 2 & 3 compatibility
- **"New" Structure** (experimental): Shared download pool with region-specific clipped outputs - may be implemented in future
- **Current Decision**: Use "old" structure for all production work and documentation
- **Documentation Flag**: `docs/technical/folder_structure_automation.md` discusses --folder_structure flag (experimental, not recommended for production)

### Why Confusion Occurred
1. **QUICKSTART.md** had outdated "new structure" diagrams (lines 184-210 and 388-410)
2. **AI Assistant** read QUICKSTART.md first when creating PRODUCTION_WORKFLOW.md
3. **Result**: Incorrect structure propagated to new documentation

## Files Corrected (December 21, 2025)
- ✅ `PRODUCTION_WORKFLOW.md` - Fixed output structure diagram
- ✅ `QUICKSTART.md` - Fixed both instances (lines 184-210 and 388-410)

## Files Verified Correct
- ✅ `README.md` - Correct structure documented (lines 75-89)
- ✅ Actual code implementation matches README.md

## For Future Documentation

**When documenting Sentinel-2 output structure:**

1. ✅ **DO**: Copy structure from README.md lines 75-89 (current "old" structure)
2. ✅ **DO**: Show region_name as PARENT of download/clipped/metadata/template
3. ✅ **DO**: Note this is the "old" structure required for downstream workflow compatibility
4. ❌ **DON'T**: Use "new structure" (shared download pool) in production docs
5. ❌ **DON'T**: Show download/clipped/metadata/template at sentinel2 level (that's "new" structure)

**Template to Use:**
```
sentinel2/
└── <region_name>/
    ├── download/
    ├── clipped/
    ├── metadata/
    └── template/
```

## Verification Commands

```bash
# Check actual structure on HPC
tree -L 3 /fs/project/howat.4-3/greenland_glacier_flow/1_download_merge_and_clip/sentinel2/ | head -20

# Should show:
# sentinel2/
# ├── 134_Arsuk/
# │   ├── download/
# │   ├── clipped/
# │   ├── metadata/
# │   └── template/
# └── 191_Hagen_Brae/
#     ├── download/
#     ├── clipped/
#     ├── metadata/
#     └── template/
```

## Action Items for AI Agents

When creating new documentation mentioning Sentinel-2 output structure:
1. **Always** reference README.md lines 75-89 as source of truth
2. **Verify** structure shows region_name as parent directory
3. **Test** against actual filesystem if unsure
4. **Never** copy structure from QUICKSTART.md without verification (it had stale content)

---

**Lesson Learned**: Multiple documentation files can become inconsistent over time. Always verify against both:
1. Source of truth documentation (README.md)
2. Actual filesystem implementation (tree command on HPC)

# Sentinel-2 Folder Structure Automation (December 2025)

### Configuration Management Solution

**Status**: ✅ Implemented and production-ready

Eliminated manual comment/uncomment operations for folder structure switching between old (region-specific) and new (shared) folder layouts.

#### Problem Solved
- **Before**: Manual editing of 8+ lines across 2 files to switch folder structures
- **Risk**: Easy to forget uncommenting, version control pollution, human error
- **Maintenance**: Error-prone process for different processing runs

#### Solution: Parameterized Automation
- **Parameter**: `--folder_structure {old|new}` (defaults to 'old')
- **Function**: `folder_structure='old'` parameter in `download_and_post_process_region()`
- **Logic**: Conditional folder path generation instead of commented blocks

#### Folder Structure Comparison

**Old Structure (Region-specific)**:
```
{base_dir}/
├── {region}/
│   ├── download/      # Region-specific downloads
│   ├── clipped/
│   ├── template/
│   └── metadata/
```

**New Structure (Shared)**:
```
{base_dir}/
├── download/          # Shared across all regions
├── clipped/{region}/
├── template/
└── metadata/
```

#### Implementation Files
1. **`lib/download_and_post_process_region.py`**
   - Added `folder_structure='old'` parameter
   - Replaced commented blocks with conditional logic
   - Updated `concat_csv_files()` call

2. **`lib/functions.py`**
   - Modified `concat_csv_files()` to accept `folder_structure` parameter
   - Conditional metadata folder path logic

3. **`download_merge_clip_sentinel2.py`**
   - Added `--folder_structure` command-line argument
   - Validation: `choices=['old', 'new']`
   - Default: `'old'` (backward compatible)

#### Usage Examples
```bash
# Default (old structure) - backward compatible
python download_merge_clip_sentinel2.py [other args]

# Explicit old structure
python download_merge_clip_sentinel2.py --folder_structure old [other args]

# New structure for future processing
python download_merge_clip_sentinel2.py --folder_structure new [other args]
```

#### Benefits Achieved
- ✅ **Zero manual editing** - No more comment/uncomment operations
- ✅ **Version controlled** - Changes tracked in git
- ✅ **Error-proof** - No risk of forgetting to switch configurations
- ✅ **Future-proof** - Easy to add more folder structure variants
- ✅ **Backward compatible** - Existing scripts work unchanged

#### Validation
- ✅ Command-line argument parsing with validation
- ✅ Function parameter passing works correctly
- ✅ Folder paths generated correctly for both structures
- ✅ Code compiles and logic tested
- ✅ Default behavior unchanged (old structure)
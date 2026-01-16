#!/usr/bin/env python3
"""
Container Wrapper for Glacier Processing
Translates environment variables → CLI arguments → processing script
"""

import os
import subprocess
import sys
from pathlib import Path


def get_params():
    """Load parameters from environment variables with defaults
    
    Environment variable names match HPC workflow CLI argument names:
    - satellite (not SATELLITE)
    - regions (not REGION, matches --regions plural form)
    - date1, date2 (not DATE1, DATE2)
    - base_dir (not BASE_DIR)
    - log_name (not LOG_NAME)
    """
    params = {
        # Required parameters (match HPC CLI args)
        "satellite": os.getenv("satellite", "landsat"),  # Default to landsat
        "regions": os.getenv("regions", ""),  # Plural, matches HPC --regions
        "date1": os.getenv("date1", ""),
        "date2": os.getenv("date2", ""),
        
        # Optional parameters (match HPC CLI args)
        "base_dir": os.getenv("base_dir", "/app/processing"),
        "log_name": os.getenv("log_name", "processing.log"),
        
        # Sentinel-2 workflow flags (match HPC CLI args)
        "download_flag": os.getenv("download_flag", "1"),
        "post_processing_flag": os.getenv("post_processing_flag", "1"),
        "clear_downloads": os.getenv("clear_downloads", "0"),
        
        # AWS parameters (for future S3 sync) - keep uppercase for AWS convention
        "s3_bucket": os.getenv("S3_BUCKET", ""),
        "aws_region": os.getenv("AWS_REGION", "us-west-2"),
    }
    
    return params


def validate_params(params):
    """Validate required parameters"""
    required = ["regions", "date1", "date2"]
    missing = [k for k in required if not params[k]]
    
    if missing:
        print(f"ERROR: Missing required parameters: {', '.join(missing)}")
        print("\nRequired environment variables (match HPC CLI args):")
        print("  regions   - Glacier region name(s) (comma-separated)")
        print("  date1     - Start date (YYYY-MM-DD)")
        print("  date2     - End date (YYYY-MM-DD)")
        print("\nOptional environment variables:")
        print("  satellite  - 'landsat' or 'sentinel2' (default: landsat)")
        print("  base_dir   - Output directory (default: /app/processing)")
        print("  log_name   - Log filename (default: processing.log)")
        return False
    
    return True


def build_command(params, script_path, satellite):
    """Build CLI command for processing script
    
    CRITICAL: Match HPC workflow directory structure
    - Outputs: {base_dir}/1_download_merge_and_clip/{satellite}/{region}/...
    - Logs: {base_dir}/slurm_jobs/{satellite}/logs/{log_name}
    This keeps logs separate from outputs (can delete outputs without losing logs)
    """
    cmd = ["python", script_path]
    
    # Both scripts use these common parameters
    cmd.extend(["--regions", params["regions"]])
    cmd.extend(["--date1", params["date1"]])
    cmd.extend(["--date2", params["date2"]])
    
    # Match HPC/local workflow: base_dir points to 1_download_merge_and_clip/{satellite}
    # HPC: /fs/project/.../greenland_glacier_flow/1_download_merge_and_clip/{satellite}
    # Local: /home/bny/greenland_glacier_flow/1_download_merge_and_clip/{satellite}
    # Container: /app/processing/1_download_merge_and_clip/{satellite}
    processing_base = params["base_dir"]
    if not processing_base.endswith("/1_download_merge_and_clip"):
        processing_base = f"{processing_base}/1_download_merge_and_clip"
    
    # Satellite-specific output directory
    output_dir = f"{processing_base}/{satellite}"
    os.makedirs(output_dir, exist_ok=True)
    cmd.extend(["--base_dir", output_dir])
    
    # Logs: Match non-container workflow - create log directory structure
    # Local: logs go to base_dir/slurm_jobs/{satellite}/logs/{log_name}
    # Container: same structure, created by wrapper to match non-container behavior
    log_dir = f"{params['base_dir']}/slurm_jobs/{satellite}/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, params["log_name"])
    cmd.extend(["--log_name", log_path])
    
    # Sentinel-2 requires additional workflow flags
    if satellite == "sentinel2":
        cmd.extend(["--download_flag", params.get("download_flag", "1")])
        cmd.extend(["--post_processing_flag", params.get("post_processing_flag", "1")])
        cmd.extend(["--clear_downloads", params.get("clear_downloads", "0")])
    
    # Note: Scripts don't need --satellite parameter (they are satellite-specific)
    
    return cmd


def run_processing(params, script_path, satellite):
    """Execute processing script with CLI arguments"""
    cmd = build_command(params, script_path, satellite)
    
    print("=" * 60)
    print("WRAPPER: Launching processing script")
    print("=" * 60)
    print(f"Satellite: {satellite}")
    print(f"Script: {script_path}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    
    # DEBUG: Check directory structure
    print(f"\nDEBUG: Pre-flight checks...")
    print(f"  base_dir: {params['base_dir']}")
    print(f"  base_dir exists: {os.path.exists(params['base_dir'])}")
    processing_base = params["base_dir"]
    if not processing_base.endswith("/1_download_merge_and_clip"):
        processing_base = f"{processing_base}/1_download_merge_and_clip"
    output_dir = f"{processing_base}/{satellite}"
    print(f"  output_dir: {output_dir}")
    print(f"  output_dir exists: {os.path.exists(output_dir)}")
    print(f"  output_dir created: OK")
    print()
    
    print()
    
    # Change to scripts directory (scripts expect this as CWD)
    os.chdir("/app/1_download_merge_and_clip")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("\n✓ Processing completed successfully")
        if result.stdout:
            print("\n=== Script Output ===")
            print(result.stdout)
        
        # Inspect downloaded files for Sentinel-2
        if satellite == "sentinel2":
            inspect_sentinel2_files(params)
        
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Processing failed with exit code {e.returncode}")
        if e.stdout:
            print("\n=== Script Output ===")
            print(e.stdout)
        if e.stderr:
            print("\n=== Script Error ===")
            print(e.stderr)
        
        # Inspect files even if processing failed
        if satellite == "sentinel2":
            inspect_sentinel2_files(params)
        
        # Also try to read the log file if it was created
        log_path = f"{params['base_dir']}/slurm_jobs/{satellite}/logs/{params['log_name']}"
        if os.path.exists(log_path):
            print(f"\n=== Log File Contents ({log_path}) ===")
            with open(log_path, 'r') as f:
                print(f.read())
        return e.returncode
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return 1


def inspect_sentinel2_files(params):
    """Inspect downloaded Sentinel-2 files to diagnose corruption issues"""
    import glob
    
    print("\n" + "=" * 60)
    print("FILE INSPECTION - Sentinel-2 Downloads")
    print("=" * 60)
    
    download_dir = f"{params['base_dir']}/1_download_merge_and_clip/sentinel2/{params['regions']}/download"
    
    if not os.path.exists(download_dir):
        print(f"Download directory does not exist: {download_dir}")
        return
    
    # Find all TIF files
    tif_files = glob.glob(f"{download_dir}/**/*.tif", recursive=True)
    
    if not tif_files:
        print("No TIF files found in download directory")
        return
    
    print(f"Found {len(tif_files)} TIF files")
    print()
    
    # Inspect first 3 files
    for tif_file in tif_files[:3]:
        print(f"File: {os.path.basename(tif_file)}")
        
        # Check size
        size = os.path.getsize(tif_file)
        size_mb = size / 1024 / 1024
        print(f"  Size: {size:,} bytes ({size_mb:.2f} MB)")
        
        # Check file type using first few bytes
        with open(tif_file, 'rb') as f:
            header = f.read(200)
            
            # TIFF files start with II (little-endian) or MM (big-endian)
            if header[:2] in [b'II', b'MM']:
                print(f"  ✅ Valid TIFF magic number detected")
            elif b'<?xml' in header or b'<Error>' in header or b'<html>' in header.lower():
                print(f"  ❌ CORRUPTED: Contains XML/HTML (likely S3 error response)")
                print(f"  First 200 bytes:")
                try:
                    print(f"    {header.decode('utf-8', errors='ignore')}")
                except:
                    print(f"    {header[:200]}")
            else:
                print(f"  ⚠️ Unknown format")
                print(f"  First 50 bytes: {header[:50]}")
        
        print()
    
    print("=" * 60)


def main():
    print("=" * 60)
    print("Container Wrapper - Phase 2 (Real Processing)")
    print("=" * 60)
    
    # Load parameters
    params = get_params()
    
    # Validate
    if not validate_params(params):
        sys.exit(1)
    
    # Display parameters
    print("\nParameters:")
    for key, value in params.items():
        if key not in ["s3_bucket", "aws_region"] or value:  # Only show AWS params if set
            print(f"  {key:15} = {value}")
    
    # Determine processing script based on satellite
    satellite = params["satellite"]
    if satellite == "landsat":
        script_path = "/app/1_download_merge_and_clip/landsat/download_clip_landsat.py"
    elif satellite == "sentinel2":
        script_path = "/app/1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py"
    else:
        print(f"ERROR: Unknown satellite '{satellite}'")
        sys.exit(1)
    
    # Verify script exists
    if not Path(script_path).exists():
        print(f"ERROR: Processing script not found: {script_path}")
        sys.exit(1)
    
    # Run processing
    exit_code = run_processing(params, script_path, satellite)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

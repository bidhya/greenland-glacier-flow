"""
AWS Lambda Handler for Greenland Glacier Flow Satellite Processing

This module provides serverless processing of satellite imagery for Greenland glacier analysis.
Supports both Sentinel-2 and Landsat satellites with automatic region-based processing.

Key Features:
- Single-region processing per Lambda invocation (ensures reliability within limits)
- Automatic download of processing scripts from S3
- Support for Sentinel-2 L2A and Landsat Collection 1/2 data
- Results uploaded to S3 maintaining consistent directory structure
- Comprehensive error handling and logging

Processing Strategy:
- One glacier region per Lambda call (prevents timeouts and resource conflicts)
- 10GB memory allocation, 15-minute timeout limit
- Asynchronous invocation for background processing
- Results stored in S3 with predictable paths

Usage:
    Invoked via AWS Lambda with JSON event payload containing:
    - satellite: "sentinel2" or "landsat"
    - region: glacier identifier (e.g., "134_Arsuk")
    - date1/date2: processing date range
    - s3_bucket: storage location
    - processing flags and parameters

================================================================================
LAMBDA-SPECIFIC ENHANCEMENTS (Future Implementation)
================================================================================

Lambda Environment Constraints:
- Ephemeral storage (/tmp) is wiped between invocations
- No persistent file system state
- 10GB storage limit, 10GB memory limit, 15-minute timeout

HPC vs Lambda File Handling Differences:

1. EXISTENCE CHECKS COMPATIBILITY:
   HPC Behavior (Working):
   - Core scripts check for existing clipped files locally
   - pystac-client skips downloading existing files
   - Efficient incremental processing

   Lambda Challenge:
   - /tmp is empty on each invocation
   - Local existence checks always return "not found"
   - Downloads happen every time (by design for fresh data)

   Lambda Solution (Future Enhancement):
   - Add S3-based existence checks before processing
   - Check if final outputs exist on S3, skip if found
   - Maintain core script compatibility (no changes needed)

2. DOWNLOAD OPTIMIZATION:
   HPC: pystac-client prevents duplicate downloads
   Lambda: Downloads always occur (ephemeral storage)
   Status: Acceptable for Lambda (ensures data freshness)

3. PROCESSING LOGIC:
   HPC: Incremental processing with local state
   Lambda: Always process (stateless, fresh results)
   Status: Working as designed

Future Enhancement: S3 Existence Checks
---------------------------------------
When implemented, add to lambda_handler():
- check_s3_outputs() function to verify existing results
- Skip processing if outputs exist (unless force_reprocess=True)
- Maintain HPC core script compatibility
- Reduce costs for regions with existing data

================================================================================

Author: Greenland Glacier Flow Team
Date: January 2026
"""

# AWS Lambda Handler for Greenland Glacier Flow Processing
# Processes Sentinel-2 and Landsat satellite imagery for single glacier regions
# Designed for serverless execution with one region per Lambda invocation

import json
import boto3
import subprocess
import os
import tempfile
import logging
import zipfile
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_processing_scripts(s3_client, s3_bucket):
    """Download complete greenland-glacier-flow project from S3 to Lambda's tmp directory.

    Downloads all processing scripts and dependencies needed for satellite data processing.
    Always downloads fresh to ensure latest code version.

    Args:
        s3_client: Boto3 S3 client instance
        s3_bucket: S3 bucket name containing the project scripts

    Returns:
        tuple: (project_dir, downloaded_files)
            - project_dir (Path): Local directory where project was downloaded
            - downloaded_files (list): List of relative file paths that were downloaded

    Raises:
        Exception: If download fails for any reason
    """
    try:
        project_dir = Path("/tmp/greenland-glacier-flow")
        
        # Always download fresh - clear any cached version
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)
            logger.info("Cleared cached project directory")
        
        logger.info("Downloading complete greenland-glacier-flow project from S3...")
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # List all objects in the project directory
        s3_prefix = "scripts/greenland-glacier-flow/"
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=s3_bucket, Prefix=s3_prefix)
        
        downloaded_files = []
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    s3_key = obj['Key']
                    
                    # Skip directory markers
                    if s3_key.endswith('/'):
                        continue
                        
                    # Calculate local file path
                    relative_path = s3_key[len(s3_prefix):]  # Remove prefix
                    if not relative_path:  # Skip if empty
                        continue
                        
                    local_path = project_dir / relative_path
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Download the file
                    try:
                        s3_client.download_file(s3_bucket, s3_key, str(local_path))
                        downloaded_files.append(relative_path)
                        logger.debug(f"Downloaded: {relative_path}")
                    except Exception as e:
                        logger.warning(f"Could not download {s3_key}: {e}")
        
        # Make scripts executable
        for script_file in project_dir.rglob('*.py'):
            script_file.chmod(0o755)
        for script_file in project_dir.rglob('*.sh'):
            script_file.chmod(0o755)
            
        logger.info(f"Complete project downloaded successfully: {len(downloaded_files)} files")
        
        logger.info(f"Project contains {len(downloaded_files)} files")
        return project_dir, downloaded_files
        
    except Exception as e:
        logger.error(f"Failed to download complete project: {e}")
        return None, []

def run_sentinel2_processing(project_dir, region, date1, date2, base_dir):
    """Run Sentinel-2 satellite data processing for a single glacier region.

    Executes the Sentinel-2 processing pipeline which includes:
    - Downloading Sentinel-2 L2A surface reflectance data
    - Merging tiles and clipping to glacier boundaries
    - Post-processing for glacier flow analysis

    Args:
        project_dir (Path): Local directory containing the processing scripts
        region (str): Single glacier region identifier (e.g., '134_Arsuk')
        date1 (str): Start date in YYYY-MM-DD format
        date2 (str): End date in YYYY-MM-DD format
        base_dir (Path): Output directory for processed results

    Returns:
        dict: Processing results with keys:
            - 'returncode' (int): Process exit code (0 = success)
            - 'stdout' (str): Standard output from processing
            - 'stderr' (str): Standard error output
            - 'success' (bool): True if processing completed successfully

    Raises:
        subprocess.TimeoutExpired: If processing exceeds 800 second timeout
        Exception: For any other processing errors
    """
    try:
        # Use the Lambda Python environment directly
        python_exec = "/var/lang/bin/python"
        
        # Change to processing directory within the complete project
        sentinel2_dir = project_dir / "1_download_merge_and_clip" / "sentinel2"
        os.chdir(sentinel2_dir)
        
        # Build command for Sentinel-2 processing
        # Single region processing only
        cmd = [
            python_exec, "download_merge_clip_sentinel2.py",
            "--regions", region
        ]
        
        # Add other required arguments
        cmd.extend([
            "--date1", date1,      # Updated for parameter reconciliation
            "--date2", date2,       # Updated for parameter reconciliation
            "--download_flag", "1",
            "--post_processing_flag", "1", 
            "--cores", "1",
            "--base_dir", str(base_dir),  # Satellite-specific directory
            "--log_name", "lambda_processing.log"
        ])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Python executable: {python_exec}")
        logger.info(f"Sentinel-2 script exists: {os.path.exists('download_merge_clip_sentinel2.py')}")
        
        # Set up environment variables
        env = os.environ.copy()
        env['PYTHONPATH'] = str(sentinel2_dir)
        
        logger.info(f"Environment PYTHONPATH: {env.get('PYTHONPATH')}")
        
        # Run the processing with timeout
        logger.info("Starting subprocess...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=800,  # 13+ minutes (leave buffer for cleanup)
            env=env,
            cwd=sentinel2_dir
        )
        logger.info("Subprocess completed.")
        
        logger.info(f"Process completed with return code: {result.returncode}")
        if result.stdout:
            logger.info(f"STDOUT (last 500 chars): {result.stdout[-500:]}")
        if result.stderr:
            logger.warning(f"STDERR (last 500 chars): {result.stderr[-500:]}")
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'success': result.returncode == 0
        }
        
    except subprocess.TimeoutExpired:
        logger.error("Processing timed out after 800 seconds")
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': 'Processing timed out (800s limit)',
            'success': False
        }
    except Exception as e:
        logger.error(f"Processing failed with exception: {e}", exc_info=True)
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': str(e),
            'success': False
        }

def run_landsat_processing(project_dir, region, date1, date2, base_dir):
    """Run Landsat satellite data processing for a single glacier region.

    Executes the Landsat processing pipeline which includes:
    - Downloading Landsat Collection 1/2 Level-1 data
    - Orthorectification and atmospheric correction
    - Clipping to glacier boundaries

    Args:
        project_dir (Path): Local directory containing the processing scripts
        region (str): Single glacier region identifier (e.g., '134_Arsuk')
        date1 (str): Start date in YYYY-MM-DD format
        date2 (str): End date in YYYY-MM-DD format
        base_dir (Path): Output directory for processed results

    Returns:
        dict: Processing results with keys:
            - 'returncode' (int): Process exit code (0 = success)
            - 'stdout' (str): Standard output from processing
            - 'stderr' (str): Standard error output
            - 'success' (bool): True if processing completed successfully

    Raises:
        subprocess.TimeoutExpired: If processing exceeds 800 second timeout
        Exception: For any other processing errors
    """
    try:
        # Use the Lambda Python environment directly
        python_exec = "/var/lang/bin/python"
        
        # Change to processing directory within the complete project
        landsat_dir = project_dir / "1_download_merge_and_clip" / "landsat"
        os.chdir(landsat_dir)
        
        # Build command for Landsat processing
        # Single region processing only
        cmd = [
            python_exec, "download_clip_landsat.py",
            "--regions", region
        ]
        
        # Add other required arguments
        cmd.extend([
            "--date1", date1,
            "--date2", date2,
            "--base_dir", str(base_dir),  # Satellite-specific directory
            "--log_name", "lambda_processing.log"
        ])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        # Set up environment variables
        env = os.environ.copy()
        env['PYTHONPATH'] = str(landsat_dir)
        
        # Run the processing with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=800,  # 13+ minutes (leave buffer for cleanup)
            env=env,
            cwd=landsat_dir
        )
        
        logger.info(f"Process completed with return code: {result.returncode}")
        if result.stdout:
            logger.info(f"STDOUT (last 500 chars): {result.stdout[-500:]}")
        if result.stderr:
            logger.warning(f"STDERR (last 500 chars): {result.stderr[-500:]}")
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'success': result.returncode == 0
        }
        
    except subprocess.TimeoutExpired:
        logger.error("Processing timed out after 800 seconds")
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': 'Processing timed out (800s limit)',
            'success': False
        }
    except Exception as e:
        logger.error(f"Processing failed with exception: {e}", exc_info=True)
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': str(e),
            'success': False
        }

def upload_results_to_s3(s3_bucket, base_dir, satellite, s3_base_path='1_download_merge_and_clip'):
    """Upload all processed results to S3 maintaining directory structure.

    Recursively uploads all files from the processing output directory to S3,
    preserving the same folder structure used in local/HPC processing.

    S3 Structure (matches local/HPC):
      s3://{bucket}/{s3_base_path}/{satellite}/{region}/{subfolders}/

    Examples:
      - Sentinel-2: s3://bucket/1_download_merge_and_clip/sentinel2/clipped/134_Arsuk/...
      - Landsat: s3://bucket/1_download_merge_and_clip/landsat/134_Arsuk/...

    Args:
        s3_bucket (str): S3 bucket name for uploading results
        base_dir (Path): Local directory containing processed results
        satellite (str): Satellite type ('sentinel2' or 'landsat')
        s3_base_path (str): Base path in S3 (default: '1_download_merge_and_clip')

    Returns:
        list: List of S3 keys that were successfully uploaded

    Raises:
        Exception: If upload fails for any file
    """
    try:
        s3_client = boto3.client('s3')
        uploaded_files = []
        base_path = Path(base_dir)
        
        if not base_path.exists():
            logger.warning(f"Base directory does not exist: {base_dir}")
            return []
        
        logger.info(f"Uploading all files from: {base_dir}")
        logger.info(f"S3 structure: s3://{s3_bucket}/{s3_base_path}/{satellite}/")
        
        # Upload ALL files matching local/HPC structure
        for file_path in base_path.rglob("*"):
            if file_path.is_file():
                # Create S3 key matching local structure
                # /tmp/glacier_processing/landsat/134_Arsuk/file.tif
                # -> s3://bucket/1_download_merge_and_clip/landsat/134_Arsuk/file.tif
                relative_path = file_path.relative_to(base_path)
                s3_key = f"{s3_base_path}/{satellite}/{relative_path}"
                
                # Upload file
                s3_client.upload_file(str(file_path), s3_bucket, s3_key)
                uploaded_files.append(s3_key)
                logger.info(f"Uploaded: {s3_key}")
        
        logger.info(f"Total files uploaded: {len(uploaded_files)}")
        logger.info(f"S3 location: s3://{s3_bucket}/{s3_base_path}/{satellite}/")
        return uploaded_files
        
    except Exception as e:
        logger.error(f"Failed to upload results: {e}", exc_info=True)
        return []

def lambda_handler(event, context):
    """AWS Lambda handler for Greenland glacier satellite data processing.

    Processes a single glacier region for either Sentinel-2 or Landsat satellites.
    Designed for serverless execution with one region per invocation to ensure
    reliable processing within Lambda limits (10GB memory, 15min timeout).

    Processing Pipeline:
    1. Download processing scripts from S3
    2. Execute satellite-specific processing (Sentinel-2 or Landsat)
    3. Upload results back to S3
    4. Clean up temporary files

    Expected Event Structure:
    {
        "satellite": "sentinel2" | "landsat",
        "region": "134_Arsuk",
        "date1": "2025-01-01",
        "date2": "2025-12-31",
        "s3_bucket": "greenland-glacier-data",
        "s3_base_path": "1_download_merge_and_clip",
        "download_flag": 1,
        "post_processing_flag": 1,
        "cores": 1,
        "base_dir": "/tmp/glacier_processing/sentinel2",
        "log_name": "satellite_glacier.log"
    }

    Args:
        event (dict): Lambda event containing processing parameters
        context: Lambda context object (provides runtime info)

    Returns:
        dict: Response with processing results and metadata:
            - statusCode (int): HTTP status code (200=success, 500=error)
            - body (str): JSON string with detailed results including:
                - satellite, region, dates processed
                - S3 location of results
                - processing statistics and file counts
                - success/failure status

    Raises:
        ValueError: If required parameters are missing
        Exception: For any processing failures (logged and returned in response)
    """
    
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")
    
    # Use Lambda's /tmp directory for processing
    temp_dir = "/tmp/glacier_processing"
    
    try:
        # Extract parameters from event
        satellite = event.get('satellite', 'sentinel2')
        region = event.get('region', '134_Arsuk')
        date1 = event.get('date1')  # Updated for parameter reconciliation
        date2 = event.get('date2')    # Updated for parameter reconciliation
        s3_bucket = event.get('s3_bucket', 'greenland-glacier-data')
        download_flag = event.get('download_flag', 1)
        post_processing_flag = event.get('post_processing_flag', 1)
        job_name = event.get('job_name', f'lambda-{satellite}-{region}')
        
        # Validate required parameters
        if not date1 or not date2:
            raise ValueError("date1 and date2 are required")
        
        logger.info(f"Processing {satellite} data for region: {region}")
        logger.info(f"Date range: {date1} to {date2}")
        logger.info(f"S3 bucket: {s3_bucket}")
        logger.info(f"Job name: {job_name}")
        
        # HPC-style: Create satellite-specific base directory for isolated outputs
        # This prevents cross-contamination between Landsat and Sentinel-2 outputs
        satellite_dir = satellite.lower()
        base_dir = Path(temp_dir) / satellite_dir
        base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using satellite-specific output directory: {base_dir}")
        
        # Create S3 client for project download
        s3_client = boto3.client('s3')
        
        # Step 1: Download complete project from S3
        logger.info("Step 1: Downloading complete greenland-glacier-flow project...")
        project_dir, downloaded_files = download_processing_scripts(s3_client, s3_bucket)
        
        if not project_dir:
            raise ValueError("Could not download complete project from S3")
        
        logger.info(f"Successfully downloaded project with {len(downloaded_files)} files")
        
        # Step 2: Run satellite processing based on type
        logger.info(f"Step 2: Running {satellite} processing in isolated directory...")
        if satellite.lower() == "landsat":
            processing_result = run_landsat_processing(
                project_dir, region, date1, date2, base_dir
            )
        else:  # Default to Sentinel-2
            processing_result = run_sentinel2_processing(
                project_dir, region, date1, date2, base_dir
            )
        
        # Step 3: Upload ALL files from satellite-specific directory to S3
        # Using standardized structure matching local/HPC layout
        logger.info(f"Step 3: Uploading all files from {satellite} directory to S3...")
        s3_base_path = event.get('s3_base_path', '1_download_merge_and_clip')
        uploaded_files = upload_results_to_s3(s3_bucket, base_dir, satellite, s3_base_path)
        
        # Step 4: Cleanup - Remove satellite-specific directory to free space
        logger.info(f"Step 4: Cleaning up {satellite} directory...")
        try:
            import shutil
            shutil.rmtree(base_dir)
            logger.info(f"Successfully cleaned up: {base_dir}")
        except Exception as cleanup_error:
            logger.warning(f"Cleanup failed (non-critical): {cleanup_error}")
        
        # Prepare response
        if processing_result['success']:
            result = {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Sentinel-2 processing completed successfully with geospatial libraries',
                    'satellite': satellite,
                    'region': region,
                    'date1': date1,
                    'date2': date2,
                    's3_bucket': s3_bucket,
                    's3_location': f's3://{s3_bucket}/{s3_base_path}/{satellite}/',
                    'job_name': job_name,
                    'mode': 'full_processing_geospatial',
                    'processing_time_remaining': context.get_remaining_time_in_millis(),
                    'downloaded_scripts': len(downloaded_files),
                    'uploaded_files': len(uploaded_files),
                    'processing_stdout': processing_result['stdout'][-1000:],  # Last 1000 chars
                    'files_uploaded': uploaded_files,
                    'geospatial_libraries': 'pip_installed'
                })
            }
        else:
            result = {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Sentinel-2 processing failed',
                    'satellite': satellite,
                    'region': region,
                    'job_name': job_name,
                    'processing_stderr': processing_result['stderr'],
                    'processing_stdout': processing_result['stdout'],
                    'returncode': processing_result['returncode']
                })
            }
        
        logger.info(f"Processing completed: {result['statusCode']}")
        return result
        
    except Exception as e:
        error_msg = f"Lambda processing failed: {str(e)}"
        logger.error(error_msg)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_msg,
                'event': event,
                'job_name': event.get('job_name', 'unknown')
            })
        }

# Test function for local development
if __name__ == "__main__":
    # Test event
    test_event = {
        "satellite": "sentinel2",
        "region": "134_Arsuk",
        "date1": "2025-05-04",   # Updated for parameter reconciliation
        "date2": "2025-05-07",   # Updated for parameter reconciliation
        "s3_bucket": "greenland-glacier-data",
        "download_flag": 1,
        "post_processing_flag": 1
    }
    
    # Mock context
    class MockContext:
        def get_remaining_time_in_millis(self):
            return 900000  # 15 minutes in milliseconds
    
    result = lambda_handler(test_event, MockContext())
    print(f"Test result: {json.dumps(result, indent=2)}")
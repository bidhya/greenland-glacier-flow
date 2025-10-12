# AWS Lambda Handler for Sentinel-2 Processing
# This code runs real Sentinel-2 glacier flow processing in AWS Lambda

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
    """Download complete greenland-glacier-flow project from S3 to Lambda's tmp directory using boto3"""
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

def run_sentinel2_processing(project_dir, regions, start_date, end_date, base_dir):
    """Run the actual Sentinel-2 processing with pip-installed geospatial libraries
    
    Args:
        base_dir: Satellite-specific output directory (e.g., /tmp/glacier_processing/sentinel2/)
    """
    try:
        # Use the Lambda Python environment directly
        python_exec = "/var/lang/bin/python"
        
        # Change to processing directory within the complete project
        sentinel2_dir = project_dir / "1_download_merge_and_clip" / "sentinel2"
        os.chdir(sentinel2_dir)
        
        # Build command for Sentinel-2 processing
        cmd = [
            python_exec, "download_merge_clip_sentinel2.py",
            "--regions", regions,
            "--date1", start_date,      # Updated for parameter reconciliation
            "--date2", end_date,       # Updated for parameter reconciliation
            "--download_flag", "1",
            "--post_processing_flag", "1", 
            "--cores", "1",
            "--base_dir", str(base_dir),  # Satellite-specific directory
            "--log_name", "lambda_processing.log"
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        # Set up environment variables
        env = os.environ.copy()
        env['PYTHONPATH'] = str(sentinel2_dir)
        
        # Run the processing with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=800,  # 13+ minutes (leave buffer for cleanup)
            env=env,
            cwd=sentinel2_dir
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

def run_landsat_processing(project_dir, regions, start_date, end_date, base_dir):
    """Run the actual Landsat processing with pip-installed geospatial libraries
    
    Args:
        base_dir: Satellite-specific output directory (e.g., /tmp/glacier_processing/landsat/)
    """
    try:
        # Use the Lambda Python environment directly
        python_exec = "/var/lang/bin/python"
        
        # Change to processing directory within the complete project
        landsat_dir = project_dir / "1_download_merge_and_clip" / "landsat"
        os.chdir(landsat_dir)
        
        # Build command for Landsat processing (note: different arguments than Sentinel-2)
        cmd = [
            python_exec, "download_clip_landsat.py",
            "--regions", regions,
            "--date1", start_date,
            "--date2", end_date,
            "--base_dir", str(base_dir),  # Satellite-specific directory
            "--log_name", "lambda_processing.log"
        ]
        
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
    """
    Upload all files from base_dir to S3 matching local/HPC directory structure
    
    S3 Structure (matches local/HPC):
      s3://{bucket}/{s3_base_path}/{satellite}/{subfolders}/
      
    Examples:
      - Sentinel-2: s3://bucket/1_download_merge_and_clip/sentinel2/clipped/134_Arsuk/...
      - Landsat: s3://bucket/1_download_merge_and_clip/landsat/134_Arsuk/...
    
    Args:
        s3_bucket: S3 bucket name
        base_dir: Satellite-specific base directory (e.g., /tmp/glacier_processing/landsat/)
        satellite: Satellite type ('sentinel2' or 'landsat')
        s3_base_path: Base path in S3 (default: '1_download_merge_and_clip')
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
    """
    AWS Lambda handler for Sentinel-2 glacier flow processing
    
    Expected event structure:
    {
        "satellite": "sentinel2",
        "regions": "134_Arsuk",
        "start_date": "2025-05-04",
        "end_date": "2025-05-07",
        "s3_bucket": "greenland-glacier-data",
        "download_flag": 1,
        "post_processing_flag": 1,
        "job_name": "aws-sentinel2-20250504"
    }
    """
    
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")
    
    # Use Lambda's /tmp directory for processing
    temp_dir = "/tmp/glacier_processing"
    
    try:
        # Extract parameters from event
        satellite = event.get('satellite', 'sentinel2')
        regions = event.get('regions', '134_Arsuk')
        start_date = event.get('date1')  # Updated for parameter reconciliation
        end_date = event.get('date2')    # Updated for parameter reconciliation
        s3_bucket = event.get('s3_bucket', 'greenland-glacier-data')
        download_flag = event.get('download_flag', 1)
        post_processing_flag = event.get('post_processing_flag', 1)
        job_name = event.get('job_name', f'lambda-{satellite}-{regions}')
        
        # Validate required parameters
        if not start_date or not end_date:
            raise ValueError("date1 and date2 are required")
        
        logger.info(f"Processing {satellite} data for regions: {regions}")
        logger.info(f"Date range: {start_date} to {end_date}")
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
                project_dir, regions, start_date, end_date, base_dir
            )
        else:  # Default to Sentinel-2
            processing_result = run_sentinel2_processing(
                project_dir, regions, start_date, end_date, base_dir
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
                    'regions': regions,
                    'start_date': start_date,
                    'end_date': end_date,
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
                    'regions': regions,
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
        "regions": "134_Arsuk",
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
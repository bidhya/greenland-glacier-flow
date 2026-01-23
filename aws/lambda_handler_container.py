"""
AWS Lambda Handler for Greenland Glacier Flow Satellite Processing - Container Version

Self-contained containerized Lambda handler based on Fargate's proven architecture.
All processing code baked into container (no S3 downloads).

Key Features:
- Self-contained: Processing code included in container image
- Credential fetching: ECS-style boto3 credential handling for GDAL
- GDAL configuration: Optimized for AWS S3 and requester-pays buckets
- Single-region processing per Lambda invocation
- Results uploaded to S3 with consistent directory structure

Processing Strategy:
- One glacier region per Lambda call (prevents timeouts)
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

Author: Greenland Glacier Flow Team
Date: January 11, 2026
"""

import json
import boto3
import subprocess
import os
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_aws_credentials():
    """Fetch AWS credentials from Lambda execution role for GDAL/rasterio.
    
    Lambda functions have credentials available via environment variables by default,
    but we explicitly fetch and set them for GDAL compatibility (same pattern as Fargate).
    
    Returns:
        bool: True if credentials successfully set, False otherwise
    """
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if credentials:
            os.environ['AWS_ACCESS_KEY_ID'] = credentials.access_key
            os.environ['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
            if credentials.token:
                os.environ['AWS_SESSION_TOKEN'] = credentials.token
            
            logger.info("AWS credentials configured for GDAL")
            return True
        else:
            logger.warning("Could not fetch AWS credentials")
            return False
            
    except Exception as e:
        logger.error(f"Failed to setup AWS credentials: {e}")
        return False

def setup_gdal_environment():
    """Configure GDAL environment variables for optimal S3 access.
    
    Sets environment variables for:
    - Requester-pays bucket access
    - Read optimization (disable directory listing)
    - File type filtering
    """
    os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
    os.environ['AWS_REQUEST_PAYER'] = 'requester'
    os.environ['CPL_VSIL_CURL_ALLOWED_EXTENSIONS'] = '.tif,.TIF,.tiff'
    logger.info("GDAL environment configured")

def run_sentinel2_processing(region, date1, date2, base_dir):
    """Run Sentinel-2 satellite data processing for a single glacier region.
    
    Uses self-contained processing scripts from ${LAMBDA_TASK_ROOT}.

    Args:
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
    """
    try:
        # Use self-contained scripts from Lambda task root
        script_path = Path(os.environ.get('LAMBDA_TASK_ROOT', '/var/task')) / \
                     '1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py'
        
        logger.info(f"Using self-contained script: {script_path}")
        
        # Use Lambda Python environment
        python_exec = "/var/lang/bin/python"
        
        # Run processing script with argparse flags
        log_file = f"/tmp/logs/sentinel2_{region}_{date1}.log"
        cmd = [
            python_exec,
            str(script_path),
            '--regions', region,
            '--date1', date1,
            '--date2', date2,
            '--base_dir', str(base_dir),
            '--log_name', log_file,
            '--download_flag', '1',
            '--post_processing_flag', '1'
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Use Popen to stream output in real-time (critical for Fargate CloudWatch logging)
        # Force unbuffered Python output so print() and logging calls appear on stdout
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True,
            env=env  # Pass environment with PYTHONUNBUFFERED
        )
        
        # Stream output line-by-line to CloudWatch
        stdout_lines = []
        try:
            for line in process.stdout:
                line_stripped = line.rstrip()
                logger.info(f"[SUBPROCESS] {line_stripped}")
                stdout_lines.append(line_stripped)
            
            # Wait with timeout
            returncode = process.wait(timeout=800)
            
        except subprocess.TimeoutExpired:
            logger.error("Processing timed out after 800 seconds - killing subprocess")
            process.kill()
            process.wait()
            returncode = -1
        
        logger.info(f"Processing completed with return code: {returncode}")
        stdout_text = '\n'.join(stdout_lines)
        
        # Read log file and output to CloudWatch (script writes to file, not stdout)
        if Path(log_file).exists():
            logger.info(f"Reading Sentinel-2 log file: {log_file}")
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        logger.info(f"[S2_LOG] {line.rstrip()}")
            except Exception as e:
                logger.warning(f"Could not read log file: {e}")
        else:
            logger.warning(f"Sentinel-2 log file not found: {log_file}")
        
        return {
            'returncode': returncode,
            'stdout': stdout_text,
            'stderr': '',  # Merged into stdout
            'success': returncode == 0
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
        logger.error(f"Processing failed: {e}", exc_info=True)
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': str(e),
            'success': False
        }

def run_landsat_processing(region, date1, date2, base_dir):
    """Run Landsat satellite data processing for a single glacier region.
    
    Uses self-contained processing scripts from ${LAMBDA_TASK_ROOT}.

    Args:
        region (str): Single glacier region identifier (e.g., '134_Arsuk')
        date1 (str): Start date in YYYY-MM-DD format
        date2 (str): End date in YYYY-MM-DD format
        base_dir (Path): Output directory for processed results

    Returns:
        dict: Processing results (same structure as run_sentinel2_processing)
    """
    try:
        # Use self-contained scripts from Lambda task root
        script_path = Path(os.environ.get('LAMBDA_TASK_ROOT', '/var/task')) / \
                     '1_download_merge_and_clip/landsat/download_clip_landsat.py'
        
        logger.info(f"Using self-contained script: {script_path}")
        
        # Use Lambda Python environment
        python_exec = "/var/lang/bin/python"
        
        # Run processing script with argparse flags
        log_file = f"/tmp/logs/landsat_{region}_{date1}.log"
        cmd = [
            python_exec,
            str(script_path),
            '--regions', region,
            '--date1', date1,
            '--date2', date2,
            '--base_dir', str(base_dir),
            '--log_name', log_file
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Use Popen to stream output in real-time (critical for Fargate CloudWatch logging)
        # Force unbuffered Python output so print() and logging calls appear on stdout
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True,
            env=env  # Pass environment with PYTHONUNBUFFERED
        )
        
        # Stream output line-by-line to CloudWatch
        stdout_lines = []
        try:
            for line in process.stdout:
                line_stripped = line.rstrip()
                logger.info(f"[SUBPROCESS] {line_stripped}")
                stdout_lines.append(line_stripped)
            
            # Wait with timeout
            returncode = process.wait(timeout=800)
            
        except subprocess.TimeoutExpired:
            logger.error("Processing timed out after 800 seconds - killing subprocess")
            process.kill()
            process.wait()
            returncode = -1
        
        logger.info(f"Processing completed with return code: {returncode}")
        stdout_text = '\n'.join(stdout_lines)
        
        # Read log file and output to CloudWatch (script writes to file, not stdout)
        if Path(log_file).exists():
            logger.info(f"Reading Landsat log file: {log_file}")
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        logger.info(f"[LANDSAT_LOG] {line.rstrip()}")
            except Exception as e:
                logger.warning(f"Could not read log file: {e}")
        else:
            logger.warning(f"Landsat log file not found: {log_file}")
        
        return {
            'returncode': returncode,
            'stdout': stdout_text,
            'stderr': '',  # Merged into stdout
            'success': returncode == 0
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
        logger.error(f"Processing failed: {e}", exc_info=True)
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': str(e),
            'success': False
        }

def upload_results_to_s3(s3_bucket, base_dir, satellite, s3_base_path='1_download_merge_and_clip'):
    """Upload all processed results to S3 maintaining directory structure.

    Args:
        s3_bucket (str): S3 bucket name for uploading results
        base_dir (Path): Local directory containing processed results
        satellite (str): Satellite type ('sentinel2' or 'landsat')
        s3_base_path (str): Base path in S3 (default: '1_download_merge_and_clip')

    Returns:
        list: List of S3 keys that were successfully uploaded
    """
    try:
        s3_client = boto3.client('s3')
        uploaded_files = []
        
        # Find all files in base directory
        for local_file in Path(base_dir).rglob('*'):
            if local_file.is_file():
                # Calculate relative path from base_dir
                relative_path = local_file.relative_to(base_dir)
                
                # Construct S3 key maintaining directory structure
                s3_key = f"{s3_base_path}/{satellite}/{relative_path}"
                
                # Upload file
                try:
                    s3_client.upload_file(str(local_file), s3_bucket, s3_key)
                    uploaded_files.append(s3_key)
                    logger.info(f"Uploaded: {s3_key}")
                except Exception as e:
                    logger.error(f"Failed to upload {local_file}: {e}")
        
        logger.info(f"Upload complete: {len(uploaded_files)} files")
        return uploaded_files
        
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        return []

def handler(event, context):
    """Lambda handler for satellite processing - container version.
    
    Self-contained handler using processing code baked into container.
    No S3 downloads required (faster cold starts).
    
    Args:
        event (dict): Lambda event payload containing processing parameters
        context: Lambda context object
        
    Returns:
        dict: Processing results with statusCode and body
    """
    try:
        logger.info("=" * 80)
        logger.info("Lambda Container Handler - Self-Contained Architecture")
        logger.info("=" * 80)
        logger.info(f"Event: {json.dumps(event, indent=2)}")
        
        # Extract parameters from event
        satellite = event.get('satellite', 'sentinel2')
        region = event.get('region', '140_CentralLindenow')
        date1 = event.get('date1', '2024-10-01')
        date2 = event.get('date2', '2024-10-05')
        s3_bucket = event.get('s3_bucket', 'greenland-glacier-data')
        s3_base_path = event.get('s3_base_path', '1_download_merge_and_clip')
        job_name = event.get('job_name', f'{satellite}_{region}_{date1}')
        
        logger.info(f"Processing: {satellite.upper()} - Region: {region}")
        logger.info(f"Date range: {date1} to {date2}")
        logger.info(f"S3 bucket: {s3_bucket}")
        logger.info(f"Job name: {job_name}")
        
        # Validate summer months (May-September) - winter may have no data in Greenland
        from datetime import datetime
        try:
            start_date = datetime.strptime(date1, '%Y-%m-%d')
            end_date = datetime.strptime(date2, '%Y-%m-%d')
            
            # Check if any date falls in summer months (May=5 to September=9)
            summer_months = {5, 6, 7, 8, 9}
            date_months = set()
            current = start_date
            while current <= end_date:
                date_months.add(current.month)
                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            
            if not date_months.intersection(summer_months):
                logger.warning(f"Date range {date1} to {date2} is outside summer months (May-Sep)")
                logger.warning("Winter months may have limited or no satellite data in Greenland")
                logger.warning("Processing will continue but may find no imagery")
        except Exception as e:
            logger.warning(f"Could not validate summer months: {e}")
        
        # Setup AWS credentials for GDAL
        credentials_ok = setup_aws_credentials()
        if not credentials_ok:
            logger.warning("Credentials not explicitly set, relying on Lambda defaults")
        
        # Setup GDAL environment
        setup_gdal_environment()
        
        # Create temporary processing directory
        base_dir = Path("/tmp") / "processing" / satellite / region
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logs directory for processing scripts
        log_dir = Path("/tmp") / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Processing directory: {base_dir}")
        logger.info(f"Log directory: {log_dir}")
        
        # Run processing based on satellite type
        logger.info(f"Starting {satellite} processing...")
        if satellite == "sentinel2":
            processing_result = run_sentinel2_processing(region, date1, date2, base_dir)
        elif satellite == "landsat":
            processing_result = run_landsat_processing(region, date1, date2, base_dir)
        else:
            raise ValueError(f"Unsupported satellite: {satellite}")
        
        # Upload results to S3
        logger.info("Uploading results to S3...")
        uploaded_files = upload_results_to_s3(s3_bucket, base_dir, satellite, s3_base_path)
        
        # Build response
        if processing_result['success']:
            result = {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'{satellite.upper()} processing completed successfully',
                    'satellite': satellite,
                    'region': region,
                    'date1': date1,
                    'date2': date2,
                    's3_bucket': s3_bucket,
                    's3_location': f's3://{s3_bucket}/{s3_base_path}/{satellite}/',
                    'job_name': job_name,
                    'mode': 'self_contained_container',
                    'processing_time_remaining': context.get_remaining_time_in_millis(),
                    'uploaded_files': len(uploaded_files),
                    'processing_stdout': processing_result['stdout'][-1000:],  # Last 1000 chars
                    'files_uploaded': uploaded_files
                })
            }
        else:
            result = {
                'statusCode': 500,
                'body': json.dumps({
                    'error': f'{satellite.upper()} processing failed',
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
        logger.error(error_msg, exc_info=True)
        
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
    # Check if running in Fargate mode (environment variable set by Fargate task)
    if os.environ.get('FARGATE_MODE') == '1':
        # Fargate mode: Read parameters from environment variables
        test_event = {
            "satellite": os.environ.get('SATELLITE', 'sentinel2'),
            "region": os.environ.get('REGION', '134_Arsuk'),
            "date1": os.environ.get('DATE1', '2024-10-01'),
            "date2": os.environ.get('DATE2', '2024-10-05'),
            "s3_bucket": os.environ.get('S3_BUCKET', 'greenland-glacier-data')
        }
        logger.info(f"Running in Fargate mode with parameters: {test_event}")
    else:
        # Local development mode: Use hardcoded test values
        test_event = {
            "satellite": "sentinel2",
            "region": "134_Arsuk",
            "date1": "2024-10-01",
            "date2": "2024-10-05",
            "s3_bucket": "greenland-glacier-data"
        }
    
    # Mock context
    class MockContext:
        def get_remaining_time_in_millis(self):
            return 900000  # 15 minutes in milliseconds
    
    result = handler(test_event, MockContext())
    print(f"Test result: {json.dumps(result, indent=2)}")


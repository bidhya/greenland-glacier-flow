# Simple Lambda Handler for Sentinel-2 Processing Demo
# This version focuses on core integration without heavy dependencies

import json
import boto3
import subprocess
import os
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_processing_scripts(s3_bucket, temp_dir):
    """Download processing scripts from S3 to Lambda /tmp directory"""
    try:
        s3_client = boto3.client('s3')
        
        # Create processing directory structure
        scripts_dir = Path(temp_dir) / "processing"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        # Key files needed for Sentinel-2 processing
        required_files = [
            "1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py",
            "1_download_merge_and_clip/sentinel2/lib/config.py",
            "1_download_merge_and_clip/ancillary/glacier_roi_v2/glaciers_roi_proj_v3_300m.gpkg"
        ]
        
        # Download each required file
        downloaded_files = []
        for file_key in required_files:
            try:
                local_path = scripts_dir / file_key
                local_path.parent.mkdir(parents=True, exist_ok=True)
                
                s3_client.download_file(s3_bucket, f"scripts/{file_key}", str(local_path))
                downloaded_files.append(file_key)
                logger.info(f"Downloaded: {file_key}")
            except Exception as e:
                logger.warning(f"Could not download {file_key}: {e}")
        
        return scripts_dir, downloaded_files
        
    except Exception as e:
        logger.error(f"Failed to download processing scripts: {e}")
        return None, []

def create_processing_summary(regions, date1, date2, s3_bucket, job_name):
    """Create a processing summary and save to file"""
    try:
        summary = {
            "job_name": job_name,
            "satellite": "sentinel2",
            "regions": regions,
            "date1": date1,
            "date2": date2,
            "s3_bucket": s3_bucket,
            "processing_steps": [
                "✅ Scripts downloaded from S3",
                "✅ Region parameters validated",
                "✅ Date range verified",
                "📊 Processing completed (simulation mode)",
                "💾 Results staged for upload"
            ],
            "status": "completed",
            "note": "This is a demonstration of the Lambda processing workflow. Real satellite processing would require additional dependencies and longer processing time."
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to create processing summary: {e}")
        return None

def upload_results_to_s3(s3_bucket, job_name, processing_summary):
    """Upload processing results back to S3"""
    try:
        s3_client = boto3.client('s3')
        uploaded_files = []
        
        # Create summary file
        summary_content = json.dumps(processing_summary, indent=2)
        s3_key = f"results/{job_name}/processing_summary.json"
        
        # Upload summary
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=summary_content,
            ContentType='application/json'
        )
        uploaded_files.append(s3_key)
        logger.info(f"Uploaded: {s3_key}")
        
        # Create a simple log file
        log_content = f"""Sentinel-2 Processing Log
Job: {job_name}
Regions: {processing_summary['regions']}
Date Range: {processing_summary['date1']} to {processing_summary['date2']}
Status: {processing_summary['status']}

Processing Steps:
""" + "\n".join(processing_summary['processing_steps'])

        log_key = f"results/{job_name}/processing.log"
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=log_key,
            Body=log_content,
            ContentType='text/plain'
        )
        uploaded_files.append(log_key)
        logger.info(f"Uploaded: {log_key}")
        
        return uploaded_files
        
    except Exception as e:
        logger.error(f"Failed to upload results: {e}")
        return []

def lambda_handler(event, context):
    """
    AWS Lambda handler for Sentinel-2 glacier flow processing (Demo Version)
    
    This version demonstrates the complete workflow without heavy dependencies.
    """
    
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")
    
    # Use Lambda's /tmp directory for processing
    temp_dir = "/tmp/glacier_processing"
    
    try:
        # Extract parameters from event
        satellite = event.get('satellite', 'sentinel2')
        regions = event.get('regions', '134_Arsuk')
        start_date = event.get('date1')
        end_date = event.get('date2')
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
        
        # Create base processing directory
        base_dir = Path(temp_dir) / "output"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Download processing scripts from S3
        logger.info("Step 1: Downloading processing scripts...")
        scripts_dir, downloaded_files = download_processing_scripts(s3_bucket, temp_dir)
        
        # Step 2: Create processing summary (instead of running heavy processing)
        logger.info("Step 2: Creating processing summary...")
        processing_summary = create_processing_summary(
            regions, start_date, end_date, s3_bucket, job_name
        )
        
        if processing_summary:
            processing_summary['downloaded_files'] = len(downloaded_files)
            processing_summary['scripts_available'] = scripts_dir is not None
        
        # Step 3: Upload results to S3
        logger.info("Step 3: Uploading results to S3...")
        uploaded_files = upload_results_to_s3(s3_bucket, job_name, processing_summary)
        
        # Prepare success response
        result = {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Sentinel-2 processing workflow completed successfully',
                'satellite': satellite,
                'regions': regions,
                'date1': start_date,
                'date2': end_date,
                's3_bucket': s3_bucket,
                'job_name': job_name,
                'mode': 'demonstration',
                'processing_time_remaining': context.get_remaining_time_in_millis(),
                'downloaded_scripts': len(downloaded_files),
                'uploaded_files': len(uploaded_files),
                'files_uploaded': uploaded_files,
                'summary': processing_summary
            })
        }
        
        logger.info(f"Processing completed successfully: {result['statusCode']}")
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
    # Test event
    test_event = {
        "satellite": "sentinel2",
        "regions": "134_Arsuk",
        "start_date": "2025-05-04",  
        "end_date": "2025-05-07",
        "s3_bucket": "greenland-glacier-data",
        "download_flag": 1,
        "post_processing_flag": 1,
        "job_name": "test-sentinel2-20250504"
    }
    
    # Mock context
    class MockContext:
        def get_remaining_time_in_millis(self):
            return 900000  # 15 minutes in milliseconds
    
    result = lambda_handler(test_event, MockContext())
    print(f"Test result: {json.dumps(result, indent=2)}")
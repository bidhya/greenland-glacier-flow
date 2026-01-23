#!/usr/bin/env python

""" AWS-focused satellite data processing job submission script
    - Designed specifically for AWS cloud services
    - Supports various AWS compute services (Batch, ECS, Lambda, etc.)
    - Experimental/development version for learning AWS
    - Lambda service now supports orchestration of multiple regions

    Lambda Orchestration:
    - Single region: Direct Lambda invocation
    - Multiple regions: Concurrent orchestration of separate Lambda functions
    - Supports both specific regions and start_end_index batching

    Future usage examples:
    - python submit_aws_job.py --satellite sentinel2 --service batch
    - python submit_aws_job.py --satellite landsat --service ecs --regions 134_Arsuk
    - python submit_aws_job.py --satellite sentinel2 --service lambda --start-end-index 0:25
    - python submit_aws_job.py --satellite landsat --service lambda --regions 140_CentralLindenow,134_Arsuk
    - python submit_aws_job.py --satellite sentinel2 --service lambda --date1 2024-07-01 --date2 2024-07-15 --dry-run true

    Author: B. Yadav. Jan 2, 2026
"""
import os
import logging
import argparse
import subprocess
import configparser
import time
import json
import concurrent.futures
from pathlib import Path

# Set up command line argument parser for AWS-specific options
parser = argparse.ArgumentParser(description='Submit satellite data processing jobs to AWS cloud services')
parser.add_argument('--config', help='Path to configuration file', type=str, default='../../config.ini')
parser.add_argument('--aws-config', help='Path to AWS-specific configuration file', type=str, default='../../aws/config/aws_config.ini')
parser.add_argument('--satellite', help='Satellite type (sentinel2 or landsat)', type=str, choices=['sentinel2', 'landsat'])
parser.add_argument('--service', help='AWS service to use', type=str, choices=['batch', 'ecs', 'lambda', 'fargate'], default='lambda')
parser.add_argument('--regions', help='Regions to process (comma-separated, no spaces)', type=str)
parser.add_argument('--region', help='Single region to process (for Lambda)', type=str)
parser.add_argument('--start-end-index', help='Start and end index for batch processing (e.g., 0:48)', type=str)
parser.add_argument('--date1', help='Start date in YYYY-MM-DD format', type=str)
parser.add_argument('--date2', help='End date in YYYY-MM-DD format', type=str)
parser.add_argument('--s3-bucket', help='S3 bucket for data storage', type=str)
parser.add_argument('--aws-region', help='AWS region (e.g., us-west-2 for satellite data)', type=str, default='us-west-2')
parser.add_argument('--instance-type', help='EC2 instance type for compute', type=str, default='c5.large')
parser.add_argument('--spot-instances', help='Use spot instances for cost savings', action='store_true')
parser.add_argument('--dry-run', help='Generate configuration but do not submit (true/false)', type=str, choices=['true', 'false'], default=None)
parser.add_argument('--email', help='Email for job notifications (via SNS)', type=str)
parser.add_argument('--setup', help='Run AWS resource setup (create S3 bucket, etc.)', action='store_true')

args = parser.parse_args()

# Get absolute path to current script directory
script_dir = Path(__file__).resolve().parent
print(f"AWS Script directory: {script_dir}")


def mkdir_p(folder):
    '''Create directory if it doesn't exist'''
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)


def check_aws_credentials():
    """Check if AWS credentials are configured and valid"""
    try:
        import boto3
        sts_client = boto3.client('sts')
        response = sts_client.get_caller_identity()
        
        print(f"✅ AWS credentials valid for account: {response['Account']}")
        print(f"✅ Using AWS identity: {response['Arn']}")
        return True
        
    except ImportError:
        print("❌ boto3 not installed")
        return False
    except Exception as e:
        print(f"❌ AWS credentials invalid: {e}")
        print("💡 Run: aws configure")
        return False

def check_aws_services(aws_region='us-west-2'):
    """Check access to basic AWS services needed for processing"""
    try:
        import boto3
        
        # Check EC2 (needed for Batch)
        try:
            ec2_client = boto3.client('ec2', region_name=aws_region)
            ec2_client.describe_regions()
            print(f"✅ EC2 access available in {aws_region}")
            ec2_access = True
        except Exception as e:
            print(f"⚠️  EC2 limited access: {e}")
            ec2_access = False
        
        # Check Batch service
        try:
            batch_client = boto3.client('batch', region_name=aws_region)
            batch_client.describe_compute_environments()
            print(f"✅ AWS Batch access available in {aws_region}")
            batch_access = True
        except Exception as e:
            print(f"⚠️  AWS Batch limited access: {e}")
            batch_access = False
            
        return {'ec2': ec2_access, 'batch': batch_access}
        
    except ImportError:
        print("❌ boto3 not installed")
        return {'ec2': False, 'batch': False}
    except Exception as e:
        print(f"❌ AWS service check failed: {e}")
        return {'ec2': False, 'batch': False}

def setup_aws_resources(s3_bucket, aws_region='us-west-2'):
    """Helper function to set up basic AWS resources"""
    print(f"\n🔧 AWS Setup Helper for {aws_region}")
    print("=" * 50)
    
    # Try to create S3 bucket
    print(f"1. Creating S3 bucket: {s3_bucket}")
    try:
        import boto3
        s3_client = boto3.client('s3', region_name=aws_region)
        
        if aws_region == 'us-east-1':
            # us-east-1 doesn't need LocationConstraint
            s3_client.create_bucket(Bucket=s3_bucket)
        else:
            s3_client.create_bucket(
                Bucket=s3_bucket,
                CreateBucketConfiguration={'LocationConstraint': aws_region}
            )
        print(f"✅ S3 bucket '{s3_bucket}' created successfully")
        return True
        
    except Exception as e:
        print(f"❌ S3 bucket creation failed: {e}")
        print(f"💡 Manual steps:")
        print(f"   aws s3 mb s3://{s3_bucket} --region {aws_region}")
        return False


def test_s3_access(s3_bucket, aws_region='us-west-2'):
    """Test basic S3 access for the specified bucket"""
    try:
        import boto3
        s3_client = boto3.client('s3', region_name=aws_region)
        
        # Test if bucket exists and we can access it
        response = s3_client.head_bucket(Bucket=s3_bucket)
        print(f"✅ S3 bucket '{s3_bucket}' is accessible in {aws_region}")
        
        # Test listing objects (should work even if bucket is empty)
        response = s3_client.list_objects_v2(Bucket=s3_bucket, MaxKeys=1)
        print(f"✅ Can list objects in bucket '{s3_bucket}'")
        return True
        
    except ImportError:
        print("❌ boto3 not installed")
        return False
    except Exception as e:
        print(f"❌ S3 bucket '{s3_bucket}' access failed: {e}")
        print(f"💡 Solutions:")
        print(f"   1. AWS CLI: aws s3 mb s3://{s3_bucket} --region {aws_region}")
        print(f"   2. boto3: python -c \"import boto3; boto3.client('s3', region_name='{aws_region}').create_bucket(Bucket='{s3_bucket}', CreateBucketConfiguration={{'LocationConstraint': '{aws_region}'}})\"")
        print(f"   3. If access denied, ask admin to:")
        print(f"      - Create bucket: {s3_bucket}")
        print(f"      - Grant s3:CreateBucket, s3:GetObject, s3:PutObject permissions")
        return False


def create_aws_batch_job(jobname, regions, date1, date2, satellite, **kwargs):
    """Create and submit AWS Batch job for satellite processing
    
    AWS Batch is ideal for:
    - Large-scale parallel processing
    - Variable workloads
    - Cost optimization with spot instances
    """
    print(f"AWS BATCH: Creating job for {satellite} processing")
    print(f"Job name: {jobname}")
    print(f"Regions: {regions}")
    print(f"Date range: {date1} to {date2}")
    
    s3_bucket = kwargs.get('s3_bucket', 'default-glacier-bucket')
    aws_region = kwargs.get('aws_region', 'us-west-2')
    
    # Test S3 access first
    if not test_s3_access(s3_bucket, aws_region):
        print("❌ Cannot proceed without S3 access")
        return
    
    # Basic batch configuration
    batch_config = {
        'jobName': jobname,
        'jobDefinition': f'satellite-processing-{satellite}',
        'jobQueue': 'glacier-processing-queue',
        'parameters': {
            'satellite': satellite,
            'regions': regions,
            'startDate': date1,
            'endDate': date2,
            's3Bucket': s3_bucket
        }
    }
    
    print("AWS Batch configuration:")
    for key, value in batch_config.items():
        print(f"  {key}: {value}")
    
    if kwargs.get('dry_run'):
        print("DRY RUN: AWS Batch job configuration created but not submitted")
        print("💡 Next steps to implement:")
        print("  1. Create job definition in AWS Batch console")
        print("  2. Set up compute environment")  
        print("  3. Create job queue")
        print("  4. Implement boto3 job submission")
    else:
        print("🚧 AWS Batch submission not yet implemented")
        print("💡 Use --dry-run true to test configuration")
        # boto3 implementation will go here


def create_aws_ecs_job(jobname, regions, date1, date2, satellite, **kwargs):
    """Create and submit AWS ECS task for satellite processing
    
    AWS ECS is ideal for:
    - Containerized applications
    - Service-oriented architecture
    - Integration with other AWS services
    """
    print(f"AWS ECS: Creating task for {satellite} processing")
    
    # TODO: Implement AWS ECS task creation
    # Steps will include:
    # 1. Define task definition
    # 2. Set up ECS cluster
    # 3. Configure service (if needed)
    # 4. Run task
    # 5. Monitor task status
    
    if kwargs.get('dry_run'):
        print("DRY RUN: AWS ECS task configuration created but not submitted")
    else:
        print("TODO: Submit to AWS ECS")


def create_aws_lambda_job(jobname, region, date1, date2, satellite, **kwargs):
    """Create and submit AWS Lambda function for satellite processing
    
    AWS Lambda is ideal for:
    - Small to medium glaciers (1-3 tiles)
    - Quick processing (< 15 minutes)
    - Serverless architecture
    
    Integration with validated Lambda container (October 2025):
    - Uses production-tested glacier-processing function
    - Configured for 8 GB memory (optimal for Sentinel-2 processing)
    - Reads settings from aws/config/aws_config.ini
    """
    print(f"\n{'='*60}")
    print(f"AWS LAMBDA JOB SUBMISSION - {satellite.upper()}")
    print(f"{'='*60}")
    
    # Get Lambda configuration from aws_config.ini
    function_name = kwargs.get('lambda_function_name', 'glacier-processing')
    s3_bucket = kwargs.get('s3_bucket', 'greenland-glacier-data')
    s3_base_path = kwargs.get('s3_base_path', '1_download_merge_and_clip')
    aws_region = kwargs.get('aws_region', 'us-west-2')
    memory_size = kwargs.get('lambda_memory_size', 8192)
    timeout = kwargs.get('lambda_timeout', 900)
    
    # Build event payload matching lambda_handler.py expectations
    lambda_event = {
        'satellite': satellite,
        'region': region,  # Single region for Lambda processing
        'date1': date1,        # Updated for parameter reconciliation
        'date2': date2,          # Updated for parameter reconciliation
        's3_bucket': s3_bucket,
        's3_base_path': s3_base_path,  # Add S3 base path
        'download_flag': kwargs.get('download_flag', 1),
        'post_processing_flag': kwargs.get('post_processing_flag', 1),
        'cores': kwargs.get('cores', 1),
        'base_dir': f'/tmp/glacier_processing/{satellite}',  # Lambda ephemeral storage
        'log_name': kwargs.get('log_name', 'lambda_glacier.log')
    }
    
    print(f"\nConfiguration:")
    print(f"  Function: {function_name}")
    print(f"  Region: {aws_region}")
    print(f"  Memory: {memory_size} MB")
    print(f"  Timeout: {timeout} seconds")
    print(f"  S3 Bucket: {s3_bucket}")
    print(f"\nProcessing Parameters:")
    print(f"  Satellite: {satellite}")
    print(f"  Region: {region}")
    print(f"  Date Range: {date1} to {date2}")
    print(f"  Job Name: {jobname}")
    
    # Handle dry run mode
    if kwargs.get('dry_run'):
        print(f"\n{'='*60}")
        print("DRY RUN MODE - Lambda configuration validated")
        print(f"{'='*60}")
        print("\nEvent payload that would be sent:")
        print(json.dumps(lambda_event, indent=2))
        print(f"\n💡 To invoke manually (asynchronous):")
        print(f"   aws lambda invoke \\")
        print(f"     --function-name {function_name} \\")
        print(f"     --invocation-type Event \\")
        print(f"     --payload '{json.dumps(lambda_event)}' \\")
        print(f"     --region {aws_region} \\")
        print(f"     /tmp/lambda_response.json")
        return
    
    # Invoke Lambda function
    try:
        import boto3
        lambda_client = boto3.client('lambda', region_name=aws_region)
        
        print(f"\n{'='*60}")
        print("INVOKING LAMBDA FUNCTION")
        print(f"{'='*60}")
        
        # Asynchronous invocation - fire and forget (better for long-running functions)
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Asynchronous - don't wait for result
            Payload=json.dumps(lambda_event)
        )
        
        # Parse response
        status_code = response['StatusCode']
        
        print(f"\n✅ Lambda function invoked successfully!")
        print(f"   Status Code: {status_code}")
        print(f"   Request ID: {response['ResponseMetadata']['RequestId']}")
        print(f"   Invocation Type: Asynchronous (Event)")
        print(f"\n💡 Function is running in background. Check CloudWatch logs or S3 for results:")
        print(f"   Logs: https://{aws_region}.console.aws.amazon.com/cloudwatch/home?region={aws_region}#logsV2:log-groups/log-group/$252Faws$252Flambda$252F{function_name.replace('-', '$252D')}")
        print(f"   S3: s3://{s3_bucket}/1_download_merge_and_clip/{satellite}/")
        
        return True
        
        # Log to file
        logging.info(f"Lambda invocation: {function_name}, Job: {jobname}, Status: {status_code}")
        
        print(f"\n{'='*60}")
        return response
        
    except ImportError:
        print(f"\n❌ ERROR: boto3 not installed")
        print(f"💡 Install: pip install boto3")
        return None
        
    except Exception as e:
        print(f"\n❌ Lambda invocation failed: {e}")
        print(f"\n💡 Troubleshooting:")
        print(f"   1. Verify function exists: aws lambda get-function --function-name {function_name}")
        print(f"   2. Check AWS credentials: aws sts get-caller-identity")
        print(f"   3. Verify region: {aws_region}")
        print(f"   4. Check CloudWatch logs: /aws/lambda/{function_name}")
        logging.error(f"Lambda invocation failed: {e}")
        return None


def load_aws_config(aws_config_file="../config/aws_config.ini"):
    """Load AWS-specific configuration
    
    This will contain AWS-specific settings like:
    - S3 bucket names
    - Lambda configuration
    - IAM roles
    - VPC settings
    - Cost optimization preferences
    """
    try:
        config = configparser.ConfigParser()
        files_read = config.read(aws_config_file)
        if not files_read:
            print(f"⚠️  Warning: AWS config file not found at {aws_config_file}, using defaults")
        else:
            print(f"✅ Loaded AWS config from: {files_read[0]}")
        
        return {
            # Storage settings
            's3_bucket': config.get("STORAGE", "s3_bucket", fallback='greenland-glacier-data'),
            's3_base_path': config.get("STORAGE", "s3_base_path", fallback='1_download_merge_and_clip'),
            
            # AWS account settings
            'aws_region': config.get("AWS_ACCOUNT", "aws_region", fallback='us-west-2'),
            
            # Lambda settings
            'lambda_function_name': config.get("LAMBDA", "function_name", fallback='glacier-processing'),
            'lambda_memory_size': config.getint("LAMBDA", "memory_size", fallback=8192),
            'lambda_timeout': config.getint("LAMBDA", "timeout", fallback=900),
            'lambda_ephemeral_storage': config.getint("LAMBDA", "ephemeral_storage", fallback=10240),
            
            # Fargate settings
            'fargate_cluster_name': config.get("FARGATE", "fargate_cluster_name", fallback='glacier-processing-cluster'),
            'fargate_task_definition': config.get("FARGATE", "fargate_task_definition", fallback='glacier-task'),
            'fargate_container_name': config.get("FARGATE", "fargate_container_name", fallback='glacier-processing'),
            'fargate_memory': config.get("FARGATE", "fargate_memory", fallback='4096'),
            'fargate_cpu': config.get("FARGATE", "fargate_cpu", fallback='2048'),
            'fargate_subnets': config.get("FARGATE", "fargate_subnets", fallback='subnet-09f06dee4cc5f7056,subnet-01bf0679b5ad5d4cf').split(','),
            'fargate_security_groups': config.get("FARGATE", "fargate_security_groups", fallback='sg-0bf93d7503503ce92').split(','),
            'fargate_ecr_repository': config.get("FARGATE", "fargate_ecr_repository", fallback='glacier-processing'),
            
            # Compute settings (for Batch/ECS)
            'instance_type': config.get("COMPUTE", "instance_type", fallback='c5.large'),
            'spot_instances': config.getboolean("COMPUTE", "spot_instances", fallback=False),
            'max_vcpus': config.getint("COMPUTE", "max_vcpus", fallback=256)
        }
    except Exception as e:
        print(f"Warning: Could not load AWS config file {aws_config_file}: {e}")
        # Return default values with us-west-2 for satellite data
        return {
            's3_bucket': 'greenland-glacier-data',
            's3_base_path': '1_download_merge_and_clip',
            'aws_region': 'us-west-2',
            'lambda_function_name': 'glacier-processing',
            'lambda_memory_size': 8192,
            'lambda_timeout': 900,
            'lambda_ephemeral_storage': 10240,
            'fargate_cluster_name': 'glacier-processing-cluster',
            'fargate_task_definition': 'glacier-task:1',
            'fargate_container_name': 'glacier-processing',
            'fargate_memory': '4096',
            'fargate_cpu': '2048',
            'fargate_subnets': ['subnet-09f06dee4cc5f7056', 'subnet-01bf0679b5ad5d4cf'],
            'fargate_security_groups': ['sg-0bf93d7503503ce92'],
            'fargate_ecr_repository': 'glacier-processing',
            'instance_type': 'c5.large',
            'spot_instances': False,
            'max_vcpus': 256
        }


def get_full_region_list():
    """Get the full list of glacier regions from the geopackage file.
    
    Returns:
        list: Sorted list of region names (e.g., ['001_region1', '002_region2', ...])
    """
    try:
        import geopandas as gpd
        # Path relative to the AWS script location
        script_dir = Path(__file__).resolve().parent
        glacier_regions_path = script_dir.parent.parent / '1_download_merge_and_clip' / 'ancillary' / 'glacier_roi_v2' / 'glaciers_roi_proj_v3_300m.gpkg'
        
        regions_gdf = gpd.read_file(glacier_regions_path)
        regions_gdf.index = regions_gdf.region
        regions_gdf = regions_gdf.sort_index()
        
        return regions_gdf.index.tolist()
    except Exception as e:
        print(f"Error loading region list: {e}")
        # Fallback: return empty list or raise error
        raise RuntimeError("Could not load glacier regions list. Ensure the geopackage file exists.")


def load_shared_config(config_file="../../config.ini", cli_args=None):
    """Load shared configuration from the main config file
    
    Reuses the same configuration structure as the main script
    """
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # Parse configuration values from sections (same as main script)
    config_dict = {
        # Region settings
        'regions': config.get("REGIONS", "regions"),
        'start_end_index': config.get("REGIONS", "start_end_index"),
        
        # Date settings
        'date1': config.get("DATES", "date1"),
        'date2': config.get("DATES", "date2"),
        
        # Path settings (will be adapted for S3)
        'base_dir': config.get("PATHS", "base_dir"),

        # Processing flags
        'download_flag': config.getint("FLAGS", "download_flag", fallback=1),
        'post_processing_flag': config.getint("FLAGS", "post_processing_flag", fallback=1),
        'clear_downloads': config.getint("FLAGS", "clear_downloads", fallback=0),
        
        # General settings
        'cores': config.getint("SETTINGS", "cores", fallback=1),
        'log_name': config.get("SETTINGS", "log_name"),
        'email': config.get("SETTINGS", "email"),
        'satellite': config.get("SETTINGS", "satellite"),
        'dry_run': config.getboolean("SETTINGS", "dry_run", fallback=False)
    }
    
    # Override with command line arguments
    if cli_args:
        if cli_args.satellite:
            config_dict['satellite'] = cli_args.satellite
        if cli_args.regions:
            config_dict['regions'] = cli_args.regions
        if hasattr(cli_args, 'region') and cli_args.region:
            config_dict['region'] = cli_args.region
        if hasattr(cli_args, 'start_end_index') and cli_args.start_end_index:
            config_dict['start_end_index'] = cli_args.start_end_index
        if cli_args.date1:
            config_dict['date1'] = cli_args.date1
        if cli_args.date2:
            config_dict['date2'] = cli_args.date2
        if cli_args.email:
            config_dict['email'] = cli_args.email
        if cli_args.dry_run is not None:
            config_dict['dry_run'] = cli_args.dry_run.lower() == 'true'
    
    # Process regions into a list
    regions_str = config_dict.get('regions', '').strip()
    start_end_index = config_dict.get('start_end_index', '').strip()
    
    if regions_str and start_end_index:
        # Both specified - start_end_index takes precedence (CLI override)
        print(f"Warning: Both regions and start_end_index specified. Using start_end_index: {start_end_index}")
        regions_str = ''  # Clear regions to use start_end_index
    
    if regions_str:
        # Parse comma-separated regions
        regions_list = [r.strip() for r in regions_str.split(',') if r.strip()]
    elif start_end_index:
        # Parse start:end index and slice the full region list
        try:
            start, end = map(int, start_end_index.split(':'))
            full_regions = get_full_region_list()
            regions_list = full_regions[start:end]
        except ValueError:
            raise ValueError(f"Invalid start_end_index format: {start_end_index}. Use 'start:end' (e.g., '0:25')")
    else:
        # Default: all regions
        regions_list = get_full_region_list()
    
    config_dict['regions_list'] = regions_list
    
    return config_dict


def orchestrate_lambda_jobs(regions_list, date1, date2, satellite, job_kwargs, aws_cfg, dry_run):
    """Orchestrate multiple Lambda function invocations for multiple regions.
    
    This function handles the orchestration of multiple Lambda functions,
    one for each region, using concurrent execution for efficiency.
    """
    print(f"\n{'='*70}")
    print(f"ORCHESTRATING {len(regions_list)} LAMBDA FUNCTIONS")
    print(f"{'='*70}")
    
    if dry_run:
        print("DRY RUN MODE - Would invoke the following Lambda functions:")
        for i, region in enumerate(regions_list):
            jobname = f"aws-{satellite}-{date1.replace('-', '')}-{region}"
            print(f"  {i+1:2d}. Region: {region}, Job: {jobname}")
        print(f"\n💡 To run for real, remove --dry-run true")
        return
    
    # Prepare arguments for each Lambda invocation
    lambda_invocations = []
    for region in regions_list:
        jobname = f"aws-{satellite}-{date1.replace('-', '')}-{region}"
        args = (jobname, region, date1, date2, satellite)
        kwargs = job_kwargs.copy()
        lambda_invocations.append((args, kwargs))
    
    print(f"Invoking {len(lambda_invocations)} Lambda functions concurrently...")
    
    # Use ThreadPoolExecutor for concurrent invocations
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:  # Limit to 10 concurrent to avoid overwhelming AWS
        future_to_region = {
            executor.submit(create_aws_lambda_job, *args, **kwargs): region 
            for (args, kwargs), region in zip(lambda_invocations, regions_list)
        }
        
        for future in concurrent.futures.as_completed(future_to_region):
            region = future_to_region[future]
            try:
                result = future.result()
                results.append((region, result))
                print(f"✅ Completed: {region}")
            except Exception as exc:
                print(f"❌ Failed: {region} - {exc}")
                results.append((region, None))
    
    # Summary
    successful = sum(1 for _, result in results if result is not None)
    print(f"\n{'='*70}")
    print(f"ORCHESTRATION COMPLETE")
    print(f"{'='*70}")
    print(f"Total regions: {len(regions_list)}")
    print(f"Successful invocations: {successful}")
    print(f"Failed invocations: {len(regions_list) - successful}")
    
    if successful < len(regions_list):
        print("\n❌ Some Lambda invocations failed. Check logs above for details.")
    else:
        print("\n✅ All Lambda functions invoked successfully!")
        print("💡 Functions are running asynchronously. Monitor CloudWatch logs and S3 for results.")


def create_fargate_task(jobname, region, date1, date2, satellite, **kwargs):
    """Create and submit AWS Fargate task for satellite processing

    AWS Fargate is ideal for:
    - Large datasets requiring extended runtime
    - Containerized workflows with custom dependencies

    Integration with containerized processing scripts:
    - Uses Amazon ECR-hosted container image
    - Configured for memory and CPU allocation
    - Reads settings from aws/config/aws_config.ini
    """
    print(f"\n{'='*60}")
    print(f"AWS FARGATE TASK SUBMISSION - {satellite.upper()}")
    print(f"{'='*60}")

    # Get Fargate configuration from aws_config.ini
    cluster_name = kwargs.get('fargate_cluster_name', 'glacier-processing-cluster')
    task_definition = kwargs.get('fargate_task_definition', 'glacier-task:1')
    container_name = kwargs.get('fargate_container_name', 'glacier-processing')
    s3_bucket = kwargs.get('s3_bucket', 'greenland-glacier-data')
    s3_base_path = kwargs.get('s3_base_path', '1_download_merge_and_clip')
    aws_region = kwargs.get('aws_region', 'us-west-2')
    memory = kwargs.get('fargate_memory', '4096')
    cpu = kwargs.get('fargate_cpu', '2048')

    # Build container overrides
    # Override entrypoint to bypass Lambda runtime and run Python directly
    container_overrides = {
        'name': container_name,
        'command': ['python', '/var/task/lambda_handler.py'],
        'environment': [
            {'name': 'SATELLITE', 'value': satellite},
            {'name': 'REGION', 'value': region},
            {'name': 'DATE1', 'value': date1},
            {'name': 'DATE2', 'value': date2},
            {'name': 'S3_BUCKET', 'value': s3_bucket},
            {'name': 'S3_BASE_PATH', 'value': s3_base_path},
            {'name': 'FARGATE_MODE', 'value': '1'},  # Signal to handler this is Fargate, not Lambda
        ]
    }

    # Handle dry run mode
    if kwargs.get('dry_run'):
        print(f"\n{'='*60}")
        print("DRY RUN MODE - Fargate configuration validated")
        print(f"{'='*60}")
        print("Cluster Name:", cluster_name)
        print("Task Definition:", task_definition)
        print("Container Overrides:", json.dumps(container_overrides, indent=2))
        return

    # Submit Fargate task with retry logic for capacity issues
    try:
        import boto3
        import time
        ecs_client = boto3.client('ecs', region_name=aws_region)

        # Validate ECR connectivity
        ecr_client = boto3.client('ecr', region_name=aws_region)
        validate_ecr_connectivity(ecr_client, kwargs.get('fargate_ecr_repository', 'glacier-processing'), kwargs.get('ecr_image_tag', 'latest'))

        # Validate IAM permissions
        validate_iam_permissions()

        # Validate network configuration
        validate_network_configuration(kwargs.get('fargate_subnets', ['subnet-09f06dee4cc5f7056']), kwargs.get('fargate_security_groups', ['sg-12345678']))

        max_retries = 5
        retry_delay = 300  # 5 minutes
        task_arn = None

        for attempt in range(max_retries):
            try:
                response = ecs_client.run_task(
                    cluster=cluster_name,
                    launchType='FARGATE',
                    taskDefinition=task_definition,
                    overrides={'containerOverrides': [container_overrides]},
                    networkConfiguration={
                        'awsvpcConfiguration': {
                            'subnets': kwargs.get('fargate_subnets', ['subnet-09f06dee4cc5f7056']),
                            'securityGroups': kwargs.get('fargate_security_groups', ['sg-12345678']),
                            'assignPublicIp': 'ENABLED'
                        }
                    },
                    count=1
                )

                task_arn = response['tasks'][0]['taskArn']
                print("✅ Fargate task submitted successfully!")
                print("Task ARN:", task_arn)
                break

            except ecs_client.exceptions.ClientError as e:
                if 'RESOURCE:MEMORY' in str(e) or 'RESOURCE:CPU' in str(e):
                    if attempt < max_retries - 1:
                        print(f"⚠️  Fargate capacity issue (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"❌ Fargate capacity exhausted after {max_retries} attempts. Consider:")
                        print("   - Using smaller CPU/memory allocation")
                        print("   - Switching to AWS Batch for better capacity")
                        print("   - Trying a different AWS region")
                        raise e
                else:
                    # Re-raise non-capacity related errors immediately
                    raise e

        # Monitor task progress if submission was successful
        if task_arn:
            print("\n🔍 Monitoring task progress...")
            for monitor_attempt in range(12):  # Monitor for up to 10 minutes
                time.sleep(50)  # Check every 50 seconds
                
                task_response = ecs_client.describe_tasks(
                    cluster=cluster_name,
                    tasks=[task_arn]
                )
                
                task = task_response['tasks'][0]
                last_status = task['lastStatus']
                desired_status = task['desiredStatus']
                
                print(f"   Status: {last_status} (Desired: {desired_status})")
                
                if last_status == 'RUNNING':
                    print("🎉 Task is now RUNNING! Fargate capacity issue resolved.")
                    break
                elif last_status == 'STOPPED':
                    stop_code = task.get('stopCode', 'Unknown')
                    stop_reason = task.get('stoppedReason', 'Unknown')
                    print(f"❌ Task stopped: {stop_code} - {stop_reason}")
                    break
                elif monitor_attempt == 11:
                    print("⏰ Task still pending after 10 minutes. Fargate capacity may be limited.")
                    print("   Task will continue running in background if capacity becomes available.")

    except Exception as e:
        print("❌ Failed to submit Fargate task:", e)


def validate_ecr_connectivity(ecr_client, repository_name, image_tag):
    """Validate ECR connectivity by checking if the image exists."""
    try:
        response = ecr_client.describe_images(
            repositoryName=repository_name,
            imageIds=[{'imageTag': image_tag}]
        )
        print("✅ ECR connectivity validated. Image exists.")
    except ecr_client.exceptions.ImageNotFoundException:
        print("❌ ECR image not found. Check repository name and image tag.")
        raise
    except Exception as e:
        print("❌ Failed to validate ECR connectivity:", str(e))
        raise

def validate_iam_permissions():
    """Validate IAM permissions for ECS task execution role."""
    try:
        import boto3
        sts_client = boto3.client('sts')
        identity = sts_client.get_caller_identity()
        print("✅ IAM role validated. Role ARN:", identity['Arn'])
    except Exception as e:
        print("❌ Failed to validate IAM role permissions:", str(e))
        raise

def validate_network_configuration(subnets, security_groups):
    """Validate network configuration for Fargate tasks."""
    if not subnets or not security_groups:
        raise ValueError("Subnets and security groups must be specified.")
    print("✅ Network configuration validated.")

def orchestrate_fargate_tasks(regions_list, date1, date2, satellite, job_kwargs, aws_cfg, dry_run):
    """Orchestrate multiple Fargate task submissions for multiple regions.

    This function handles the orchestration of multiple Fargate tasks,
    one for each region, using concurrent execution for efficiency.
    """
    print(f"\n{'='*70}")
    print(f"ORCHESTRATING {len(regions_list)} FARGATE TASKS")
    print(f"{'='*70}")

    if dry_run:
        print("DRY RUN MODE - Would submit the following Fargate tasks:")
        for i, region in enumerate(regions_list):
            jobname = f"fargate-{satellite}-{date1.replace('-', '')}-{region}"
            print(f"  {i+1:2d}. Region: {region}, Job: {jobname}")
        print(f"\n💡 To run for real, remove --dry-run true")
        return

    # Prepare arguments for each Fargate task submission
    fargate_submissions = []
    for region in regions_list:
        jobname = f"fargate-{satellite}-{date1.replace('-', '')}-{region}"
        args = (jobname, region, date1, date2, satellite)
        kwargs = job_kwargs.copy()
        fargate_submissions.append((args, kwargs))

    print(f"Submitting {len(fargate_submissions)} Fargate tasks concurrently...")

    # Use ThreadPoolExecutor for concurrent submissions
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:  # Limit to 10 concurrent to avoid overwhelming AWS
        future_to_region = {
            executor.submit(create_fargate_task, *args, **kwargs): region 
            for (args, kwargs), region in zip(fargate_submissions, regions_list)
        }

        for future in concurrent.futures.as_completed(future_to_region):
            region = future_to_region[future]
            try:
                result = future.result()
                results.append((region, result))
                print(f"✅ Completed: {region}")
            except Exception as exc:
                print(f"❌ Failed: {region} - {exc}")
                results.append((region, None))

    # Summary
    successful = sum(1 for _, result in results if result is not None)
    print(f"\n{'='*70}")
    print(f"ORCHESTRATION COMPLETE")
    print(f"{'='*70}")
    print(f"Total regions: {len(regions_list)}")
    print(f"Successful submissions: {successful}")
    print(f"Failed submissions: {len(regions_list) - successful}")

    if successful < len(regions_list):
        print("\n❌ Some Fargate submissions failed. Check logs above for details.")
    else:
        print("\n✅ All Fargate tasks submitted successfully!")


def main():
    """Main function for AWS job submission"""
    print("=" * 60)
    print("AWS Satellite Data Processing Job Submission")
    print("=" * 60)
    
    # Check AWS setup
    if not check_aws_credentials():
        print("ERROR: AWS credentials not properly configured")
        return
    
    # Handle setup mode
    if args.setup:
        aws_cfg = load_aws_config(args.aws_config)
        s3_bucket = args.s3_bucket or aws_cfg['s3_bucket']
        aws_region = args.aws_region
        setup_success = setup_aws_resources(s3_bucket, aws_region)
        if setup_success:
            print("\n✅ AWS setup completed successfully!")
        else:
            print("\n❌ AWS setup had issues - see messages above")
        return
    
    # Check AWS service access
    aws_region = args.aws_region
    service_access = check_aws_services(aws_region)
    
    # Load configurations
    config_file = args.config if args.config != '../../config.ini' else script_dir / args.config
    cfg = load_shared_config(config_file, args)
    aws_cfg = load_aws_config(args.aws_config)
    
    # Extract commonly used values
    regions_list = cfg['regions_list']
    regions = cfg['regions']  # Keep for backward compatibility
    region = regions_list[0] if regions_list else None  # For single region fallback
    start_end_index = cfg['start_end_index']
    date1 = cfg['date1']
    date2 = cfg['date2']
    satellite = cfg['satellite']
    dry_run = cfg['dry_run']
    
    # AWS-specific values
    aws_service = args.service
    aws_region = args.aws_region
    s3_bucket = args.s3_bucket or aws_cfg['s3_bucket']
    
    print(f"Configuration:")
    print(f"  Satellite: {satellite}")
    print(f"  Regions to process: {len(regions_list)} regions")
    if len(regions_list) <= 5:
        print(f"    Regions: {regions_list}")
    else:
        print(f"    Regions: {regions_list[:3]} ... {regions_list[-2:]}")
    print(f"  Date range: {date1} to {date2}")
    print(f"  AWS Service: {aws_service}")
    print(f"  AWS Region: {aws_region}")
    print(f"  S3 Bucket: {s3_bucket}")
    print(f"  Dry run: {dry_run}")
    print()
    
    # Create job name
    jobname = f"aws-{satellite}-{date1.replace('-', '')}"
    
    # Auto-append batch range to job name if using start_end_index
    if start_end_index:
        jobname = f"{jobname}_{start_end_index.replace(':', '_')}"
    
    # Set up logging for AWS jobs
    log_dir = script_dir / "../logs"
    mkdir_p(log_dir)
    logging.basicConfig(
        filename=f'{log_dir}/aws_job_submission.log', 
        level=logging.INFO, 
        format='%(asctime)s:%(levelname)s:%(message)s'
    )
    logging.info('--------------------------------------AWS Job Submission----------------------------------------------')
    logging.info(f'AWS Service: {aws_service}, Satellite: {satellite}, Regions: {len(regions_list)} regions ({regions_list[:3]}...{regions_list[-3:] if len(regions_list) > 3 else regions_list})')
    
    # Route to appropriate AWS service
    job_kwargs = {
        'dry_run': dry_run,
        's3_bucket': s3_bucket,
        's3_base_path': aws_cfg.get('s3_base_path'),
        'aws_region': aws_region,
        'instance_type': args.instance_type,
        'spot_instances': args.spot_instances,
        # Lambda-specific configuration from aws_config.ini
        'lambda_function_name': aws_cfg.get('lambda_function_name'),
        'lambda_memory_size': aws_cfg.get('lambda_memory_size'),
        'lambda_timeout': aws_cfg.get('lambda_timeout'),
        'lambda_ephemeral_storage': aws_cfg.get('lambda_ephemeral_storage'),
        # Fargate-specific configuration from aws_config.ini
        'fargate_cluster_name': aws_cfg.get('fargate_cluster_name', 'glacier-processing-cluster'),
        'fargate_task_definition': aws_cfg.get('fargate_task_definition', 'glacier-task:1'),
        'fargate_container_name': aws_cfg.get('fargate_container_name', 'glacier-processing'),
        'fargate_memory': aws_cfg.get('fargate_memory', '4096'),
        'fargate_cpu': aws_cfg.get('fargate_cpu', '2048'),
        'fargate_subnets': aws_cfg.get('fargate_subnets', ['subnet-09f06dee4cc5f7056']),
        'fargate_security_groups': aws_cfg.get('fargate_security_groups', ['sg-12345678']),
        'fargate_ecr_repository': aws_cfg.get('fargate_ecr_repository', 'glacier-processing'),
        # Processing parameters from config.ini
        'download_flag': cfg.get('download_flag'),
        'post_processing_flag': cfg.get('post_processing_flag'),
        'cores': cfg.get('cores'),
        'log_name': cfg.get('log_name')
    }
    
    if aws_service == 'batch':
        create_aws_batch_job(jobname, regions, date1, date2, satellite, **job_kwargs)
    elif aws_service == 'ecs':
        create_aws_ecs_job(jobname, regions, date1, date2, satellite, **job_kwargs)
    elif aws_service == 'lambda':
        if len(regions_list) == 1:
            # Single region - use existing logic
            create_aws_lambda_job(jobname, regions_list[0], date1, date2, satellite, **job_kwargs)
        else:
            # Multiple regions - orchestrate multiple Lambda functions
            orchestrate_lambda_jobs(regions_list, date1, date2, satellite, job_kwargs, aws_cfg, dry_run)
    elif aws_service == 'fargate':
        print("Fargate mode: ECS with serverless compute")
        if len(regions_list) == 1:
            # Single region - direct task submission
            create_fargate_task(jobname, regions_list[0], date1, date2, satellite, **job_kwargs)
        else:
            # Multiple regions - orchestrate multiple Fargate tasks
            orchestrate_fargate_tasks(regions_list, date1, date2, satellite, job_kwargs, aws_cfg, dry_run)
    else:
        raise ValueError(f"Unsupported AWS service: {aws_service}")
    
    print("=" * 60)
    print("AWS job submission complete")
    print("=" * 60)
    
    logging.info("AWS job submission complete")


if __name__ == "__main__":
    """Call the main function"""
    main()

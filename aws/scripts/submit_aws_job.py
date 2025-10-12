#!/usr/bin/env python

""" AWS-focused satellite data processing job submission script
    - Designed specifically for AWS cloud services
    - Supports various AWS compute services (Batch, ECS, Lambda, etc.)
    - Experimental/development version for learning AWS

    Future usage examples:
    - python submit_aws_job.py --satellite sentinel2 --service batch
    - python submit_aws_job.py --satellite landsat --service ecs --regions 134_Arsuk
    - python submit_aws_job.py --satellite sentinel2 --service lambda --dry-run true

    Author: B. Yadav. Sep 30, 2025
"""
import os
import logging
import argparse
import subprocess
import configparser
import time
import json
from pathlib import Path

# Set up command line argument parser for AWS-specific options
parser = argparse.ArgumentParser(description='Submit satellite data processing jobs to AWS cloud services')
parser.add_argument('--config', help='Path to configuration file', type=str, default='../../config.ini')
parser.add_argument('--aws-config', help='Path to AWS-specific configuration file', type=str, default='../config/aws_config.ini')
parser.add_argument('--satellite', help='Satellite type (sentinel2 or landsat)', type=str, choices=['sentinel2', 'landsat'])
parser.add_argument('--service', help='AWS service to use', type=str, choices=['batch', 'ecs', 'lambda', 'fargate'], default='batch')
parser.add_argument('--regions', help='Regions to process (comma-separated, no spaces)', type=str)
parser.add_argument('--start-date', help='Start date in YYYY-MM-DD format', type=str)
parser.add_argument('--end-date', help='End date in YYYY-MM-DD format', type=str)
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


def create_aws_batch_job(jobname, regions, start_date, end_date, satellite, **kwargs):
    """Create and submit AWS Batch job for satellite processing
    
    AWS Batch is ideal for:
    - Large-scale parallel processing
    - Variable workloads
    - Cost optimization with spot instances
    """
    print(f"AWS BATCH: Creating job for {satellite} processing")
    print(f"Job name: {jobname}")
    print(f"Regions: {regions}")
    print(f"Date range: {start_date} to {end_date}")
    
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
            'startDate': start_date,
            'endDate': end_date,
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


def create_aws_ecs_job(jobname, regions, start_date, end_date, satellite, **kwargs):
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


def create_aws_lambda_job(jobname, regions, start_date, end_date, satellite, **kwargs):
    """Create and submit AWS Lambda function for satellite processing
    
    AWS Lambda is ideal for:
    - Small glaciers (1-2 tiles)
    - Quick processing (< 15 minutes)
    - Serverless architecture
    
    Integration with validated Lambda container (October 2025):
    - Uses production-tested glacier-sentinel2-processor function
    - Configured for 5 GB memory (optimal for small regions)
    - Reads settings from aws/config/aws_config.ini
    """
    print(f"\n{'='*60}")
    print(f"AWS LAMBDA JOB SUBMISSION - {satellite.upper()}")
    print(f"{'='*60}")
    
    # Get Lambda configuration from aws_config.ini
    function_name = kwargs.get('lambda_function_name', 'glacier-sentinel2-processor')
    s3_bucket = kwargs.get('s3_bucket', 'greenland-glacier-data')
    s3_base_path = kwargs.get('s3_base_path', '1_download_merge_and_clip')
    aws_region = kwargs.get('aws_region', 'us-west-2')
    memory_size = kwargs.get('lambda_memory_size', 5120)
    timeout = kwargs.get('lambda_timeout', 900)
    
    # Build event payload matching lambda_handler.py expectations
    lambda_event = {
        'satellite': satellite,
        'regions': regions,
        'start_date': start_date,
        'end_date': end_date,
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
    print(f"  Regions: {regions}")
    print(f"  Date Range: {start_date} to {end_date}")
    print(f"  Job Name: {jobname}")
    
    # Handle dry run mode
    if kwargs.get('dry_run'):
        print(f"\n{'='*60}")
        print("DRY RUN MODE - Lambda configuration validated")
        print(f"{'='*60}")
        print("\nEvent payload that would be sent:")
        print(json.dumps(lambda_event, indent=2))
        print(f"\n💡 To invoke manually:")
        print(f"   aws lambda invoke \\")
        print(f"     --function-name {function_name} \\")
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
        
        # Synchronous invocation to get immediate response
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',  # Synchronous - wait for result
            Payload=json.dumps(lambda_event)
        )
        
        # Parse response
        status_code = response['StatusCode']
        payload = json.loads(response['Payload'].read())
        
        print(f"\n✅ Lambda invocation successful!")
        print(f"   Status Code: {status_code}")
        print(f"   Request ID: {response['ResponseMetadata']['RequestId']}")
        
        # Check for function errors
        if 'FunctionError' in response:
            print(f"\n⚠️  Lambda function error detected:")
            print(f"   Error Type: {response['FunctionError']}")
            print(f"\n   Response payload:")
            print(json.dumps(payload, indent=2))
        else:
            print(f"\n✅ Processing completed successfully!")
            
            # Parse response body if present
            if 'body' in payload:
                body = json.loads(payload['body'])
                print(f"\nResults:")
                print(f"   Uploaded Files: {body.get('uploaded_files', 'N/A')}")
                print(f"   S3 Location: {body.get('s3_location', 'N/A')}")
                print(f"   Message: {body.get('message', 'N/A')}")
            else:
                print(f"\nResponse:")
                print(json.dumps(payload, indent=2))
        
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
        config.read(aws_config_file)
        
        return {
            # Storage settings
            's3_bucket': config.get("STORAGE", "s3_bucket", fallback='greenland-glacier-data'),
            's3_base_path': config.get("STORAGE", "s3_base_path", fallback='1_download_merge_and_clip'),
            
            # AWS account settings
            'aws_region': config.get("AWS_ACCOUNT", "aws_region", fallback='us-west-2'),
            
            # Lambda settings
            'lambda_function_name': config.get("LAMBDA", "function_name", fallback='glacier-sentinel2-processor'),
            'lambda_memory_size': config.getint("LAMBDA", "memory_size", fallback=5120),
            'lambda_timeout': config.getint("LAMBDA", "timeout", fallback=900),
            'lambda_ephemeral_storage': config.getint("LAMBDA", "ephemeral_storage", fallback=10240),
            
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
            'lambda_function_name': 'glacier-sentinel2-processor',
            'lambda_memory_size': 5120,
            'lambda_timeout': 900,
            'lambda_ephemeral_storage': 10240,
            'instance_type': 'c5.large',
            'spot_instances': False,
            'max_vcpus': 256
        }


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
        'start_date': config.get("DATES", "date1"),
        'end_date': config.get("DATES", "date2"),
        
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
        if cli_args.start_date:
            config_dict['start_date'] = cli_args.start_date
        if cli_args.end_date:
            config_dict['end_date'] = cli_args.end_date
        if cli_args.email:
            config_dict['email'] = cli_args.email
        if cli_args.dry_run is not None:
            config_dict['dry_run'] = cli_args.dry_run.lower() == 'true'
    
    return config_dict


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
    regions = cfg['regions']
    start_date = cfg['start_date']
    end_date = cfg['end_date']
    satellite = cfg['satellite']
    dry_run = cfg['dry_run']
    
    # AWS-specific values
    aws_service = args.service
    aws_region = args.aws_region
    s3_bucket = args.s3_bucket or aws_cfg['s3_bucket']
    
    print(f"Configuration:")
    print(f"  Satellite: {satellite}")
    print(f"  Regions: {regions}")
    print(f"  Date range: {start_date} to {end_date}")
    print(f"  AWS Service: {aws_service}")
    print(f"  AWS Region: {aws_region}")
    print(f"  S3 Bucket: {s3_bucket}")
    print(f"  Dry run: {dry_run}")
    print()
    
    # Create job name
    jobname = f"aws-{satellite}-{start_date.replace('-', '')}"
    
    # Set up logging for AWS jobs
    log_dir = script_dir / "../logs"
    mkdir_p(log_dir)
    logging.basicConfig(
        filename=f'{log_dir}/aws_job_submission.log', 
        level=logging.INFO, 
        format='%(asctime)s:%(levelname)s:%(message)s'
    )
    logging.info('--------------------------------------AWS Job Submission----------------------------------------------')
    logging.info(f'AWS Service: {aws_service}, Satellite: {satellite}, Regions: {regions}')
    
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
        # Processing parameters from config.ini
        'download_flag': cfg.get('download_flag'),
        'post_processing_flag': cfg.get('post_processing_flag'),
        'cores': cfg.get('cores'),
        'log_name': cfg.get('log_name')
    }
    
    if aws_service == 'batch':
        create_aws_batch_job(jobname, regions, start_date, end_date, satellite, **job_kwargs)
    elif aws_service == 'ecs':
        create_aws_ecs_job(jobname, regions, start_date, end_date, satellite, **job_kwargs)
    elif aws_service == 'lambda':
        create_aws_lambda_job(jobname, regions, start_date, end_date, satellite, **job_kwargs)
    elif aws_service == 'fargate':
        print("Fargate mode: ECS with serverless compute")
        create_aws_ecs_job(jobname, regions, start_date, end_date, satellite, **job_kwargs)
    else:
        raise ValueError(f"Unsupported AWS service: {aws_service}")
    
    print("=" * 60)
    print("AWS job submission complete")
    print("=" * 60)
    
    logging.info("AWS job submission complete")


if __name__ == "__main__":
    """Call the main function"""
    main()

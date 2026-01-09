# AWS Batch Implementation Plan with S3 Direct Storage

**Created**: January 9, 2026  
**Status**: Planning Phase  
**Objective**: Migrate glacier processing from Lambda to AWS Batch for unlimited runtime, scalable memory, and parallel processing of 192 glacier regions with direct S3 writes

---

## Executive Summary

### Why AWS Batch?

**Current State**:
- ✅ **Lambda**: Working (October 2025) but limited to 15 min runtime, 10GB memory, 10GB storage
- ❌ **Fargate**: Blocked on 403 ECR authentication errors despite 4+ hours troubleshooting
- ✅ **HPC**: Production-ready but slower (serial batches, queue wait times)

**AWS Batch Advantages**:
- Unlimited runtime (vs. Lambda's 15 min)
- Scalable memory up to 120GB (vs. Lambda's 10GB)
- Cost-optimized Spot instances (70% savings)
- Parallel processing (process 192 regions simultaneously)
- Built for batch workloads (exactly our use case)
- Direct S3 writes (no ephemeral storage limits)
- Proven ECR integration (unlike Fargate's 403 mystery)

**Strategic Approach**:
- **Incremental validation** with clear go/no-go checkpoints
- **Hello-world first** to validate authentication independently
- **2-day time budget** with abandonment triggers
- **Zero contamination** of working HPC core scripts (all work in `aws/` folder)

---

## Defensive Implementation Strategy

### Core Principles

1. **Start Simple, Build Incrementally**
   - Hello-world container → S3 write test → Geospatial stack → Single glacier → Production scale
   - Validate each layer before adding complexity

2. **Clear Go/No-Go Decision Points**
   - Every step has explicit success criteria and time limits
   - Abandon early if blocked (not after days of debugging like Fargate)
   - Alternative plans documented at each checkpoint

3. **Preserve Working Systems**
   - All changes confined to `aws/` folder
   - Never modify `1_download_merge_and_clip/` core processing scripts
   - Lambda remains untouched and operational
   - HPC workflow continues as production fallback

4. **Time-Boxed Troubleshooting**
   - Total budget: 2 days (16 hours)
   - Individual step limits: 1-6 hours
   - No endless "just one more try" cycles

---

## Implementation Steps

### Step 1: Hello-World Container Validation (1 hour)

**Objective**: Validate basic Batch infrastructure and ECR authentication

**Tasks**:
1. Create `aws/batch/hello_world/Dockerfile`:
   ```dockerfile
   FROM python:3.12-slim
   COPY hello.py /app/
   CMD ["python", "/app/hello.py"]
   ```

2. Create `aws/batch/hello_world/hello.py`:
   ```python
   print("Hello from AWS Batch!")
   with open("/tmp/test.txt", "w") as f:
       f.write("Batch container working!\n")
   print("Test file created successfully")
   ```

3. Build and push to ECR:
   ```bash
   aws ecr create-repository --repository-name glacier-batch-hello
   docker build -t glacier-batch-hello aws/batch/hello_world/
   docker tag glacier-batch-hello:latest 425980623116.dkr.ecr.us-west-2.amazonaws.com/glacier-batch-hello:latest
   aws ecr get-login-password | docker login --username AWS --password-stdin 425980623116.dkr.ecr.us-west-2.amazonaws.com
   docker push 425980623116.dkr.ecr.us-west-2.amazonaws.com/glacier-batch-hello:latest
   ```

4. Create Batch compute environment:
   - Name: `glacier-batch-hello-env`
   - Type: Managed
   - Instance types: `c5.large` (Spot)
   - Max vCPUs: 2 (minimal for testing)
   - VPC: Reuse Fargate subnets (`subnet-09f06dee4cc5f7056`, `subnet-01bf0679b5ad5d4cf`)
   - Region: `us-west-2`

5. Create job queue:
   - Name: `glacier-batch-hello-queue`
   - Priority: 1
   - Compute environment: Link to above

6. Create IAM execution role:
   - Name: `BatchExecutionRole`
   - Policies: `AWSBatchServiceRole`, ECR pull, CloudWatch logs
   - Trust relationship: `batch.amazonaws.com`, `ecs-tasks.amazonaws.com`

7. Register job definition:
   ```json
   {
     "jobDefinitionName": "hello-world-test",
     "type": "container",
     "containerProperties": {
       "image": "425980623116.dkr.ecr.us-west-2.amazonaws.com/glacier-batch-hello:latest",
       "vcpus": 0.5,
       "memory": 512,
       "executionRoleArn": "arn:aws:iam::425980623116:role/BatchExecutionRole"
     }
   }
   ```

8. Wait 30 minutes for IAM propagation (lesson from Fargate)

9. Submit test job:
   ```bash
   aws batch submit-job \
     --job-name hello-world-test-001 \
     --job-queue glacier-batch-hello-queue \
     --job-definition hello-world-test:1
   ```

10. Monitor via CloudWatch logs: `/aws/batch/job`

**Success Criteria**:
- ✅ Job completes with status `SUCCEEDED`
- ✅ CloudWatch logs show "Hello from AWS Batch!"
- ✅ No ECR 403 errors (unlike Fargate)
- ✅ Job runtime < 2 minutes

**⚠️ GO/NO-GO Decision**:
- **GO**: If job succeeds → Proceed to Step 2
- **NO-GO**: If ECR 403 persists after 30-min IAM wait → **ABANDON BATCH**, evaluate alternatives (ECS on EC2 or accept Lambda limitations)

**Time Limit**: 1 hour (including IAM propagation wait)

---

### Step 2: S3 Write Authentication Test (2 hours)

**Objective**: Validate Batch can write directly to S3 (critical for production)

**Tasks**:
1. Create IAM job role:
   - Name: `BatchJobRole`
   - Policies: S3 read/write to `greenland-glacier-data` bucket
   ```json
   {
     "Effect": "Allow",
     "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
     "Resource": [
       "arn:aws:s3:::greenland-glacier-data",
       "arn:aws:s3:::greenland-glacier-data/*"
     ]
   }
   ```

2. Update `aws/batch/hello_world/hello.py`:
   ```python
   import boto3
   from datetime import datetime
   
   s3 = boto3.client('s3')
   timestamp = datetime.utcnow().isoformat()
   content = f"Batch S3 write test at {timestamp}\n"
   
   s3.put_object(
       Bucket='greenland-glacier-data',
       Key='batch-test/hello.txt',
       Body=content.encode()
   )
   
   print(f"Successfully wrote to S3: s3://greenland-glacier-data/batch-test/hello.txt")
   ```

3. Update job definition to include `jobRoleArn`:
   ```json
   {
     "jobDefinitionName": "hello-world-s3-test",
     "type": "container",
     "containerProperties": {
       "image": "425980623116.dkr.ecr.us-west-2.amazonaws.com/glacier-batch-hello:latest",
       "vcpus": 0.5,
       "memory": 512,
       "executionRoleArn": "arn:aws:iam::425980623116:role/BatchExecutionRole",
       "jobRoleArn": "arn:aws:iam::425980623116:role/BatchJobRole"
     }
   }
   ```

4. Wait 30 minutes for IAM propagation

5. Submit test job and monitor

6. Verify file appears in S3:
   ```bash
   aws s3 ls s3://greenland-glacier-data/batch-test/hello.txt
   aws s3 cp s3://greenland-glacier-data/batch-test/hello.txt -
   ```

**Success Criteria**:
- ✅ Job completes with status `SUCCEEDED`
- ✅ File appears in S3 within 60 seconds
- ✅ File content matches expected timestamp format
- ✅ No IAM permission errors

**⚠️ GO/NO-GO Decision**:
- **GO**: If S3 write succeeds → Proceed to Step 3
- **NO-GO**: If access denied after 2 hours IAM troubleshooting → **ABANDON BATCH** or escalate to AWS Support (decision point: is it worth waiting for support ticket?)

**Time Limit**: 2 hours (including IAM propagation and troubleshooting)

---

### Step 3: Geospatial Stack Container (3 hours)

**Objective**: Build production container with full geospatial dependencies

**Tasks**:
1. Create `aws/batch/Dockerfile.batch` based on `aws/lambda/Dockerfile.lambda`:
   ```dockerfile
   FROM python:3.12-slim
   
   # System dependencies (GDAL, etc.)
   RUN apt-get update && apt-get install -y \
       gcc g++ make wget tar gzip \
       libgdal-dev gdal-bin \
       libgeos-dev libproj-dev \
       && rm -rf /var/lib/apt/lists/*
   
   # Python geospatial stack (proven from Lambda)
   RUN pip install --no-cache-dir \
       boto3 numpy pandas pyproj shapely fiona geopandas \
       rasterio rioxarray pystac-client dask opencv-python-headless \
       tqdm netcdf4 xarray joblib scikit-learn scipy matplotlib seaborn requests
   
   # Copy test script
   COPY test_imports.py /app/
   WORKDIR /app
   CMD ["python", "test_imports.py"]
   ```

2. Create `aws/batch/test_imports.py`:
   ```python
   import sys
   import boto3
   from datetime import datetime
   
   print("Testing imports...")
   imports = [
       'geopandas', 'rasterio', 'rioxarray', 'pystac_client',
       'numpy', 'pandas', 'shapely', 'fiona', 'pyproj'
   ]
   
   for module in imports:
       try:
           __import__(module)
           print(f"✅ {module}")
       except ImportError as e:
           print(f"❌ {module}: {e}")
           sys.exit(1)
   
   # Write success to S3
   s3 = boto3.client('s3')
   timestamp = datetime.utcnow().isoformat()
   content = f"Geospatial stack validated at {timestamp}\n"
   content += "All imports successful\n"
   
   s3.put_object(
       Bucket='greenland-glacier-data',
       Key='batch-test/geospatial_test.txt',
       Body=content.encode()
   )
   
   print("All imports successful! Wrote to S3.")
   ```

3. Build and push (expect ~648MB like Fargate):
   ```bash
   aws ecr create-repository --repository-name glacier-batch-processor
   docker build -t glacier-batch-processor aws/batch/
   docker tag glacier-batch-processor:latest 425980623116.dkr.ecr.us-west-2.amazonaws.com/glacier-batch-processor:latest
   docker push 425980623116.dkr.ecr.us-west-2.amazonaws.com/glacier-batch-processor:latest
   ```

4. Register job definition:
   - vCPUs: 2 (matches single-region processing needs)
   - Memory: 4096 MB (8GB proven sufficient from Lambda)
   - Execution role + Job role from previous steps

5. Submit test job

6. Verify S3 file and CloudWatch logs

**Success Criteria**:
- ✅ Container builds successfully (~600-700MB)
- ✅ ECR push completes without errors
- ✅ Job pulls image and runs (no 403 errors)
- ✅ All geospatial imports succeed
- ✅ S3 file written with success message
- ✅ Job runtime < 5 minutes

**⚠️ GO/NO-GO Decision**:
- **GO**: If all imports work and S3 write succeeds → Proceed to Step 4
- **NO-GO**: If container crashes, imports fail, or timeout → Debug for max 3 hours (check package conflicts, memory limits, GDAL versions), then **ABANDON BATCH** if unresolved

**Time Limit**: 3 hours (including build, troubleshooting, and validation)

---

### Step 4: Single Glacier Processing Trial (4 hours)

**Objective**: Run actual glacier workflow via Batch, compare outputs with Lambda baseline

**Tasks**:
1. Create `aws/batch/batch_entrypoint.py`:
   ```python
   import os
   import sys
   import subprocess
   import boto3
   from datetime import datetime
   
   # Read environment variables (passed from job submission)
   satellite = os.environ.get('SATELLITE', 'sentinel2')
   region = os.environ.get('REGION', '140_CentralLindenow')
   date1 = os.environ.get('DATE1', '2025-08-01')
   date2 = os.environ.get('DATE2', '2025-08-06')
   s3_bucket = os.environ.get('S3_BUCKET', 'greenland-glacier-data')
   s3_base_path = os.environ.get('S3_BASE_PATH', '1_download_merge_and_clip')
   
   print(f"Starting Batch processing: {satellite} / {region} / {date1} to {date2}")
   
   # Download processing scripts from S3 (same as Lambda)
   s3 = boto3.client('s3')
   def download_dir(bucket, prefix, local_dir):
       """Download S3 directory to local filesystem"""
       paginator = s3.get_paginator('list_objects_v2')
       for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
           for obj in page.get('Contents', []):
               key = obj['Key']
               local_path = os.path.join(local_dir, key.replace(prefix, '', 1).lstrip('/'))
               os.makedirs(os.path.dirname(local_path), exist_ok=True)
               s3.download_file(bucket, key, local_path)
   
   # Download project code
   print("Downloading project code from S3...")
   download_dir(s3_bucket, 'scripts/greenland-glacier-flow/', '/tmp/greenland-glacier-flow/')
   
   # Change to project directory
   os.chdir('/tmp/greenland-glacier-flow')
   
   # Execute processing script (same as Lambda subprocess pattern)
   if satellite == 'sentinel2':
       script = '1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py'
   else:
       script = '1_download_merge_and_clip/landsat/download_clip_landsat.py'
   
   cmd = [
       '/usr/local/bin/python', script,
       '--regions', region,
       '--date1', date1,
       '--date2', date2,
       '--base_dir', f'/tmp/glacier_processing/{satellite}',
       '--download_flag', '1',
       '--post_processing_flag', '1',
       '--cores', '1'
   ]
   
   print(f"Executing: {' '.join(cmd)}")
   result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
   
   print("STDOUT:", result.stdout)
   if result.stderr:
       print("STDERR:", result.stderr)
   
   if result.returncode != 0:
       print(f"Processing failed with exit code {result.returncode}")
       sys.exit(1)
   
   # Upload results to S3 (same as Lambda)
   local_output_dir = f'/tmp/glacier_processing/{satellite}'
   s3_output_prefix = f'{s3_base_path}/{satellite}/'
   
   def upload_dir(local_dir, bucket, prefix):
       """Upload local directory to S3"""
       for root, dirs, files in os.walk(local_dir):
           for file in files:
               local_path = os.path.join(root, file)
               relative_path = os.path.relpath(local_path, local_dir)
               s3_key = os.path.join(prefix, relative_path).replace('\\', '/')
               print(f"Uploading {relative_path} to s3://{bucket}/{s3_key}")
               s3.upload_file(local_path, bucket, s3_key)
   
   print("Uploading results to S3...")
   upload_dir(local_output_dir, s3_bucket, s3_output_prefix)
   
   print(f"Batch processing complete for {region}")
   ```

2. Update Dockerfile to use batch_entrypoint.py:
   ```dockerfile
   # Add to aws/batch/Dockerfile.batch
   COPY batch_entrypoint.py /app/
   CMD ["python", "/app/batch_entrypoint.py"]
   ```

3. Rebuild and push container image

4. Create production job definition:
   - vCPUs: 2
   - Memory: 8192 MB (8GB - matches Lambda successful runs)
   - Timeout: 1800 seconds (30 minutes - conservative vs Lambda's 96s actual)
   - Environment variables: SATELLITE, REGION, DATE1, DATE2, S3_BUCKET, S3_BASE_PATH

5. Submit test job for `140_CentralLindenow` (Aug 1-7, 2025):
   ```bash
   aws batch submit-job \
     --job-name glacier-test-sentinel2-140 \
     --job-queue glacier-batch-hello-queue \
     --job-definition glacier-processing:1 \
     --container-overrides '{
       "environment": [
         {"name": "SATELLITE", "value": "sentinel2"},
         {"name": "REGION", "value": "140_CentralLindenow"},
         {"name": "DATE1", "value": "2025-08-01"},
         {"name": "DATE2", "value": "2025-08-06"},
         {"name": "S3_BUCKET", "value": "greenland-glacier-data"},
         {"name": "S3_BASE_PATH", "value": "1_download_merge_and_clip"}
       ]
     }'
   ```

6. Monitor CloudWatch logs for processing progress

7. Compare S3 outputs with Lambda baseline:
   ```bash
   # Expected Lambda baseline (from LAMBDA_CONTAINER_SUCCESS.md):
   # - 20 files for Sentinel-2
   # - ~1.2 MB each
   # - Location: s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/140_CentralLindenow/clipped/
   
   aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/140_CentralLindenow/clipped/ --recursive --human-readable
   ```

**Success Criteria**:
- ✅ Job completes with status `SUCCEEDED`
- ✅ Output file count matches Lambda (20 files for Sentinel-2)
- ✅ File sizes approximately match Lambda (~1.2 MB each)
- ✅ Directory structure matches Lambda
- ✅ Processing time < 5 minutes (Lambda baseline: 96 seconds)
- ✅ No memory errors (8GB sufficient)

**⚠️ GO/NO-GO Decision**:
- **GO**: If outputs match Lambda and job succeeds → Proceed to Step 5
- **NO-GO**: If outputs differ, processing fails, or timeout → Debug for max 4 hours (check subprocess execution, S3 paths, file permissions), then **ESCALATE** to decision: abandon or continue with modified approach?

**Time Limit**: 4 hours (including troubleshooting and validation)

---

### Step 5: Batch Submission Integration (6 hours)

**Objective**: Extend `submit_aws_job.py` to support Batch job submission

**Tasks**:
1. Add Batch configuration to `aws/config/aws_config.ini`:
   ```ini
   [BATCH]
   compute_environment = glacier-batch-hello-env
   job_queue = glacier-batch-hello-queue
   job_definition = glacier-processing
   vcpus = 2
   memory = 8192
   timeout = 1800
   ```

2. Implement `create_batch_job()` in `aws/scripts/submit_aws_job.py`:
   ```python
   def create_batch_job(config, satellite, regions, date1, date2, dry_run=False):
       """Submit Batch job for glacier processing"""
       import boto3
       
       batch = boto3.client('batch', region_name=config.get('AWS_ACCOUNT', 'aws_region'))
       
       # Read Batch config
       job_queue = config.get('BATCH', 'job_queue')
       job_definition = config.get('BATCH', 'job_definition')
       s3_bucket = config.get('STORAGE', 's3_bucket')
       s3_base_path = config.get('STORAGE', 's3_base_path')
       
       jobs = []
       for region in regions:
           job_name = f"glacier-{satellite}-{region}-{date1.replace('-', '')}"
           
           container_overrides = {
               'environment': [
                   {'name': 'SATELLITE', 'value': satellite},
                   {'name': 'REGION', 'value': region},
                   {'name': 'DATE1', 'value': date1},
                   {'name': 'DATE2', 'value': date2},
                   {'name': 'S3_BUCKET', 'value': s3_bucket},
                   {'name': 'S3_BASE_PATH', 'value': s3_base_path}
               ]
           }
           
           if dry_run:
               print(f"DRY RUN: Would submit Batch job: {job_name}")
               print(f"  Queue: {job_queue}")
               print(f"  Definition: {job_definition}")
               print(f"  Environment: {container_overrides['environment']}")
               continue
           
           response = batch.submit_job(
               jobName=job_name,
               jobQueue=job_queue,
               jobDefinition=job_definition,
               containerOverrides=container_overrides
           )
           
           job_id = response['jobId']
           jobs.append({'jobId': job_id, 'jobName': job_name, 'region': region})
           print(f"Submitted Batch job: {job_name} (ID: {job_id})")
       
       return jobs
   ```

3. Add Batch service option to CLI:
   ```python
   # In submit_aws_job.py main()
   parser.add_argument('--service', choices=['lambda', 'batch'], default='lambda')
   
   # In main logic
   if args.service == 'batch':
       jobs = create_batch_job(config, satellite, regions, date1, date2, args.dry_run)
       if not args.dry_run:
           monitor_batch_jobs(jobs)
   ```

4. Implement job monitoring:
   ```python
   def monitor_batch_jobs(jobs):
       """Monitor Batch job status until completion"""
       import boto3
       import time
       
       batch = boto3.client('batch', region_name='us-west-2')
       
       pending = {job['jobId']: job for job in jobs}
       
       while pending:
           time.sleep(30)  # Check every 30 seconds
           
           job_ids = list(pending.keys())
           response = batch.describe_jobs(jobs=job_ids)
           
           for job in response['jobs']:
               job_id = job['jobId']
               status = job['status']
               job_name = pending[job_id]['jobName']
               
               if status in ['SUCCEEDED', 'FAILED']:
                   print(f"{job_name}: {status}")
                   del pending[job_id]
               else:
                   print(f"{job_name}: {status} (checking...)")
       
       print("All Batch jobs completed")
   ```

5. Test single-region submission:
   ```bash
   python aws/scripts/submit_aws_job.py \
     --service batch \
     --satellite sentinel2 \
     --regions 140_CentralLindenow \
     --date1 2025-08-01 \
     --date2 2025-08-06 \
     --dry-run true
   ```

6. Test actual submission (single region):
   ```bash
   python aws/scripts/submit_aws_job.py \
     --service batch \
     --satellite sentinel2 \
     --regions 140_CentralLindenow \
     --date1 2025-08-01 \
     --date2 2025-08-06
   ```

7. Test multi-region submission (3 regions):
   ```bash
   python aws/scripts/submit_aws_job.py \
     --service batch \
     --satellite sentinel2 \
     --regions 140_CentralLindenow,134_Arsuk,191_Hagen_Brae \
     --date1 2025-08-01 \
     --date2 2025-08-06
   ```

8. Verify all 3 jobs complete successfully and S3 outputs are correct

**Success Criteria**:
- ✅ Dry-run shows correct job parameters
- ✅ Single-region submission succeeds (1/1 jobs)
- ✅ Multi-region submission succeeds (3/3 jobs)
- ✅ All S3 outputs match expected structure
- ✅ Job monitoring works (shows status updates)
- ✅ No Lambda functionality broken (regression test)

**⚠️ GO/NO-GO Decision**:
- **GO**: If 3/3 multi-region jobs succeed → Proceed to Step 6 (production scale)
- **NO-GO**: If >1 job fails → Investigate root cause (timeout? memory? race condition?), debug for max 6 hours, then **DECIDE**: continue debugging, modify approach (smaller batches?), or revert to Lambda

**Time Limit**: 6 hours (including implementation, testing, and troubleshooting)

---

### Step 6: Production Array Job (1 day)

**Objective**: Scale to 25-region test batch, validate for full 192-region deployment

**Tasks**:
1. Scale up compute environment:
   - Max vCPUs: 64 (process 32 regions in parallel)
   - Spot instances: 70% cost savings
   - Instance types: `c5.large`, `c5.xlarge`

2. Submit 25-region test batch:
   ```bash
   python aws/scripts/submit_aws_job.py \
     --service batch \
     --satellite sentinel2 \
     --start-end-index 0:25 \
     --date1 2025-08-01 \
     --date2 2025-08-06
   ```

3. Monitor via CloudWatch:
   - Job completion rate
   - Runtime distribution
   - Memory usage patterns
   - Spot interruption rate (if any)

4. Calculate costs:
   ```bash
   # Expected cost formula:
   # 25 regions × 2 vCPUs × ~2 min runtime × $0.04/vCPU-hour (Spot c5.large)
   # ≈ 25 × 2 × 2/60 × 0.04 = $0.07 for 25-region batch
   ```

5. Validate outputs:
   ```bash
   # Check completion for all 25 regions
   aws s3 ls s3://greenland-glacier-data/1_download_merge_and_clip/sentinel2/ | wc -l
   # Should show 25 region directories
   ```

6. Compare with Lambda performance/cost:
   - Lambda: ~$0.50 for 25 regions (10GB × 96s × $0.0000166667/GB-sec)
   - Batch: ~$0.07 for 25 regions (Spot instance pricing)
   - **Expected savings**: 85%

**Success Criteria**:
- ✅ Success rate >95% (24/25 or better)
- ✅ No memory errors (8GB sufficient for all regions)
- ✅ Spot interruptions <5% (acceptable for stateless processing)
- ✅ Cost <$0.10 for 25 regions
- ✅ Average runtime <5 minutes per region

**⚠️ GO/NO-GO Decision**:
- **GO**: If success rate >95% → **DECLARE BATCH PRODUCTION-READY**, scale to full 192 regions
- **NO-GO**: If success rate <90% → **ANALYZE FAILURE MODES**:
  - Spot interruptions too high? → Switch to On-Demand
  - Memory errors? → Increase to 16GB
  - Timeout issues? → Increase to 60 minutes
  - Consistent failures? → **ABANDON BATCH** after max 1 day debugging

**Time Limit**: 1 day (including monitoring, cost analysis, and decision making)

---

## Abandonment Triggers

### Stop Immediately If:

1. **ECR 403 persists >30 minutes after IAM role creation** (Step 1)
   - Indicates same authentication issue as Fargate
   - Alternative: Try ECS on EC2 (different authentication flow)

2. **S3 write fails after 2 hours IAM troubleshooting** (Step 2)
   - Indicates fundamental permission issue
   - Alternative: Use EBS + periodic S3 sync (hybrid approach)

3. **Geospatial imports crash repeatedly (>3 attempts)** (Step 3)
   - Indicates package incompatibility or environment issue
   - Alternative: Simplify container, use conda instead of pip

4. **Single glacier outputs differ from Lambda after 4 hours debugging** (Step 4)
   - Indicates workflow execution issue
   - Alternative: Accept Lambda limitations, optimize HPC instead

5. **Multi-region test <90% success rate after 1 day** (Step 6)
   - Indicates systemic issue (not transient failures)
   - Alternative: Revert to Lambda for production, use Batch only for large glaciers

### Decision Matrix at Each Checkpoint

| Step | Success | Continue | Failure | Alternative | Time Limit |
|------|---------|----------|---------|-------------|------------|
| 1. Hello-world | Job succeeds | → Step 2 | ECR 403 | Try ECS on EC2 | 1 hour |
| 2. S3 write | File in S3 | → Step 3 | Access denied | Use EBS + sync | 2 hours |
| 3. Geospatial | All imports work | → Step 4 | Crashes | Simplify container | 3 hours |
| 4. Single glacier | Outputs match | → Step 5 | Processing fails | Debug or abandon | 4 hours |
| 5. Multi-region | 3/3 succeed | → Step 6 | >1 fails | Investigate or stop | 6 hours |
| 6. Production test | >95% success | Deploy | <90% success | Analyze or revert | 1 day |

---

## Isolation Strategy

### File Organization

```
aws/
├── batch/                          # NEW - All Batch code here
│   ├── hello_world/                # Step 1: Hello-world test
│   │   ├── Dockerfile
│   │   └── hello.py
│   ├── Dockerfile.batch            # Step 3: Production container
│   ├── batch_entrypoint.py         # Step 4: Glacier processing entrypoint
│   └── test_imports.py             # Step 3: Geospatial validation
├── lambda/                         # UNTOUCHED - Preserve working Lambda
│   ├── Dockerfile.lambda
│   └── lambda_handler.py
├── fargate/                        # ARCHIVED - Fargate attempt (blocked)
│   └── ... (preserved for reference)
├── scripts/
│   └── submit_aws_job.py           # MODIFIED - Add Batch support
├── config/
│   └── aws_config.ini              # MODIFIED - Add Batch config section
└── docs/
    ├── AWS_BATCH_IMPLEMENTATION_PLAN.md  # THIS FILE
    └── ... (other docs untouched)
```

### Core Scripts Protection

**NEVER modify**:
- `1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py`
- `1_download_merge_and_clip/landsat/download_clip_landsat.py`
- Any files in `1_download_merge_and_clip/` folder

**Invoke via subprocess only** (same pattern as Lambda):
```python
subprocess.run([
    '/usr/local/bin/python',
    '1_download_merge_and_clip/sentinel2/download_merge_clip_sentinel2.py',
    '--regions', region,
    '--date1', date1,
    '--date2', date2,
    # ... other args
])
```

### Rollback Plan

If Batch abandoned:
1. Delete `aws/batch/` folder
2. Revert changes to `submit_aws_job.py` (remove `--service batch` option)
3. Revert changes to `aws_config.ini` (remove `[BATCH]` section)
4. Zero contamination of working systems

---

## Time Budget and Decision Timeline

### Total Time Budget: 2 Days (16 Hours)

**Day 1** (8 hours):
- 09:00-10:00: Step 1 - Hello-world container (1 hour)
  - ✅ **Checkpoint**: ECR authentication works
- 10:00-12:00: Step 2 - S3 write test (2 hours)
  - ✅ **Checkpoint**: S3 permissions correct
- 12:00-15:00: Step 3 - Geospatial stack (3 hours)
  - ✅ **Checkpoint**: Production container functional
- 15:00-17:00: Break + buffer for troubleshooting

**Day 2** (8 hours):
- 09:00-13:00: Step 4 - Single glacier test (4 hours)
  - ✅ **Checkpoint**: Outputs match Lambda
- 13:00-17:00: Step 5 - Multi-region integration (4 hours)
  - ✅ **Checkpoint**: Submission script works

**Day 3** (Optional - if Steps 1-5 successful):
- Full day: Step 6 - Production test (25 regions)
  - ✅ **Final Decision**: Deploy or revert

### Escalation Points

If blocked at any checkpoint:
1. **1-hour mark**: Review error messages, check AWS documentation
2. **2-hour mark**: Search GitHub issues, AWS forums for similar problems
3. **3-hour mark**: Consider alternative approaches (different AWS service?)
4. **4-hour mark**: **ESCALATE**: Continue debugging or abandon?

No "just one more try" without re-evaluating overall strategy.

---

## Success Metrics

### Technical Metrics

- ✅ ECR authentication: No 403 errors (unlike Fargate)
- ✅ S3 writes: Direct writes without copy step
- ✅ Processing time: <5 minutes per region (vs. Lambda's 96s)
- ✅ Memory usage: <8GB per region (Lambda baseline)
- ✅ Job success rate: >95% for production batches

### Operational Metrics

- ✅ Parallelism: Process 32 regions simultaneously
- ✅ Cost: <$50 for full 192-region batch (vs. Lambda's ~$400)
- ✅ Runtime: Complete 192 regions in <1 hour (vs. HPC's serial batches)
- ✅ Reliability: Automatic retry on transient failures

### Comparison Table

| Metric | HPC | Lambda | Batch (Target) |
|--------|-----|--------|----------------|
| Runtime limit | 24 hours | 15 min | Unlimited |
| Memory limit | 60GB | 10GB | 120GB |
| Storage limit | 1TB Lustre | 10GB /tmp | Unlimited S3 |
| Parallelism | Serial batches | Manual orchestration | Automatic |
| Cost (192 regions) | Fixed allocation | ~$400 | ~$50 |
| Queue wait | Yes (hours) | No | No |
| Setup complexity | High | Low | Medium |

---

## Alternative Strategies

### If AWS Batch Fails

**Option 1: ECS on EC2**
- More control than Batch, less overhead than Fargate
- Uses standard EC2 IAM roles (different from Fargate)
- Requires manual instance management
- Time to implement: +2 days

**Option 2: Hybrid Lambda + EBS**
- Use Lambda for small glaciers (<10GB processing)
- Use HPC for large glaciers (>10GB processing)
- Split workload based on glacier size
- Time to implement: +1 day

**Option 3: Optimize HPC Workflow**
- Accept HPC limitations, optimize batch processing
- Parallelize within HPC (SLURM array jobs)
- Improve data transfer efficiency
- Time to implement: +3 days

**Option 4: Step Functions + Lambda**
- Orchestrate multiple Lambda invocations per glacier
- Split large glaciers into tiles
- Complex but leverages working Lambda
- Time to implement: +2 days

### Decision Framework

After each failed checkpoint, evaluate:
1. **Root cause**: Authentication? Permissions? Service limit?
2. **Time invested**: How much time already spent?
3. **Alternative viability**: Which option most likely to succeed?
4. **Business value**: Is cloud migration worth continued effort?

---

## Documentation Requirements

### After Each Step

Create brief status update in `aws/docs/`:
- `BATCH_STEP1_STATUS.md` - Hello-world results
- `BATCH_STEP2_STATUS.md` - S3 write results
- `BATCH_STEP3_STATUS.md` - Geospatial stack results
- `BATCH_STEP4_STATUS.md` - Single glacier results
- `BATCH_STEP5_STATUS.md` - Multi-region results
- `BATCH_STEP6_STATUS.md` - Production test results

### Final Documentation

If successful:
- `AWS_BATCH_DEPLOYMENT_GUIDE.md` - Production deployment instructions
- `AWS_BATCH_OPERATIONS.md` - Daily operations guide
- Update `AWS_AGENTS.md` - Add Batch to available services

If failed:
- `AWS_BATCH_FAILURE_ANALYSIS.md` - Why it didn't work, lessons learned
- Preserve all troubleshooting logs for future reference

---

## Status Tracking

**Current Status**: Planning Phase  
**Started**: January 9, 2026  
**Completed Steps**: 0/6  
**Time Invested**: 0 hours  
**Next Action**: Create `aws/batch/hello_world/` folder and begin Step 1

---

## References

### Working Baselines
- Lambda success: `aws/docs/LAMBDA_CONTAINER_SUCCESS.md`
- Lambda deployment: `aws/docs/LAMBDA_DEPLOYMENT_GUIDE.md`
- HPC workflow: `PRODUCTION_WORKFLOW.md`

### Failure Analysis
- Fargate blocked: `aws/docs/FARGATE_DEPLOYMENT_STATUS_2026-01-09.md`
- Fargate troubleshooting: `aws/docs/FARGATE_TROUBLESHOOTING.md`

### AWS Documentation
- AWS Batch: https://docs.aws.amazon.com/batch/
- IAM Best Practices: https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
- ECR Authentication: https://docs.aws.amazon.com/AmazonECR/latest/userguide/security-iam.html

---

**End of Plan**

**Remember**: Start simple, validate incrementally, abandon early if blocked. Lambda works, HPC works - Batch is optimization, not necessity.

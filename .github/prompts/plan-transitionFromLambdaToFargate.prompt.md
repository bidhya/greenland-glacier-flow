## Plan: Transition from Lambda to Fargate

To transition from AWS Lambda to AWS Fargate for processing Greenland glacier satellite data, we will adapt the existing Lambda-based workflow to leverage Fargate's containerized execution environment. This will address Lambda's limitations (e.g., `/tmp` storage, runtime constraints) while maintaining compatibility with S3 and existing processing scripts.

### Steps
1. **Analyze Lambda Workflow**:
   - Review `submit_aws_job.py` for Lambda invocation logic (e.g., `create_aws_lambda_job`).
   - Study `lambda_handler.py` for processing pipelines (e.g., `run_sentinel2_processing`, `run_landsat_processing`).

2. **Define Fargate Task Requirements**:
   - Identify container image requirements (e.g., dependencies, scripts).
   - Specify task parameters (e.g., memory, CPU, S3 paths).

3. **Adapt `submit_aws_job.py`**:
   - Add a `create_fargate_task` function for Fargate task submission.
   - Implement CLI options for Fargate (e.g., `--service fargate`).

4. **Containerize Processing Scripts**:
   - Create a Dockerfile to package `download_merge_clip_sentinel2.py` and `download_clip_landsat.py`.
   - Include dependencies (e.g., GDAL, Rasterio) and S3 credentials.

5. **Test Fargate Integration**:
   - Deploy the container to Amazon Elastic Container Registry (ECR).
   - Submit Fargate tasks using `submit_aws_job.py` with test regions and dates.

6. **Validate Results**:
   - Verify output files in S3.
   - Compare Fargate results with Lambda outputs for consistency.

### Further Considerations
1. **Configuration Management**:
   - Should `aws_config.ini` include Fargate-specific settings (e.g., task definitions)?
2. **Resource Optimization**:
   - Determine optimal memory/CPU allocation for Fargate tasks.
3. **Error Handling**:
   - Implement robust logging and retries for Fargate tasks.

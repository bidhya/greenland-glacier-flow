# AWS Directory - Cloud Processing Components

This directory contains all AWS-related components for cloud-based satellite data processing, organized by function.

## Directory Structure

```
aws/
├── config/             # AWS configuration files
│   ├── aws_config.ini                   # AWS service configuration
│   └── minimal-lambda-policy.json       # Lambda IAM policy template
├── docs/               # AWS documentation
│   ├── AWS_SETUP_STATUS.md             # Current AWS setup status
│   ├── AWS_GETTING_STARTED.md          # AWS getting started guide
│   ├── LAMBDA_DEPLOYMENT_GUIDE.md      # Lambda deployment instructions
│   └── LAMBDA_CONTAINER_SUCCESS.md     # Lambda containerization milestone
├── lambda/             # Lambda-specific files
│   ├── lambda_handler.py               # Production Lambda handler (container-ready)
│   ├── lambda_handler_simple.py        # Simple Lambda handler
│   ├── Dockerfile.lambda               # Lambda container Dockerfile
│   └── lambda-deployment.zip          # Legacy zip deployment package
├── logs/               # AWS logs (created dynamically)
└── scripts/            # AWS deployment and management scripts
    ├── submit_aws_job.py               # Main AWS job submission script
    ├── deploy_lambda_container.sh      # Lambda container deployment
    ├── deploy_lambda.sh                # Lambda zip deployment (legacy)
    ├── build_lambda_layer.sh           # Lambda layer builder
    └── test_lambda_container.sh        # Lambda container testing
```

## Key Components

### 1. Main AWS Job Submission (`scripts/submit_aws_job.py`)
- **Purpose**: Unified interface for AWS cloud services (Batch, ECS, Lambda)
- **Services Supported**: AWS Batch, ECS, Lambda, Fargate
- **Usage**: `python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda`

### 2. Lambda Container System (`lambda/`)
- **Production Handler**: `lambda_handler.py` - Complete project context with boto3 S3 integration
- **Container Image**: Built via `Dockerfile.lambda` with full geospatial Python stack
- **Status**: ✅ **PRODUCTION READY** - Successfully processing Sentinel-2 workflows

### 3. Deployment Automation (`scripts/`)
- **Container Deployment**: `deploy_lambda_container.sh` - Automated ECR + Lambda deployment
- **Legacy Deployment**: `deploy_lambda.sh` - Original zip-based deployment
- **Testing**: `test_lambda_container.sh` - Container functionality validation

### 4. Configuration Management (`config/`)
- **AWS Settings**: `aws_config.ini` - S3 buckets, regions, instance types
- **IAM Policy**: `minimal-lambda-policy.json` - Required Lambda permissions

## Usage Examples

### Lambda Container Deployment
```bash
# Deploy complete Lambda container system
cd aws/scripts
./deploy_lambda_container.sh

# Test Lambda function
./test_lambda_container.sh
```

### AWS Job Submission
```bash
# Submit Sentinel-2 job to Lambda
python aws/scripts/submit_aws_job.py --satellite sentinel2 --service lambda --dry-run true

# Submit to AWS Batch (when implemented)
python aws/scripts/submit_aws_job.py --satellite landsat --service batch --regions 134_Arsuk
```

### Configuration Updates
```bash
# Edit AWS settings
nano aws/config/aws_config.ini

# Update Lambda IAM policy
nano aws/config/minimal-lambda-policy.json
```

## Recent Achievements (October 2025)

### Fresh Download Success ✅ (October 2, 2025)
- **Achievement**: Successfully tested complete workflow with clean S3 bucket
- **Process**: Deleted results/ and scripts/ folders, re-synced, processed fresh Sentinel-2 data
- **Path Fix**: Corrected glacier regions file path (`script_dir.parent / 'ancillary'`)
- **Result**: 8 files uploaded to S3, complete end-to-end processing

### Lambda Container Success ✅
- **Achievement**: Complete AWS Lambda containerization with full geospatial processing
- **Container Size**: 1.4GB with 30+ scientific libraries
- **Execution**: Real satellite data processing (~55s for Sentinel-2)
- **Integration**: Complete `greenland-glacier-flow` project context in Lambda

### Technical Breakthroughs
1. **Conda Licensing Resolution**: Switched to pip-based installation
2. **Complete Project Access**: S3-based project download in Lambda execution (98 files)
3. **Native AWS Integration**: boto3 S3 operations replacing AWS CLI dependencies
4. **Production Pipeline**: Automated ECR deployment with version management
5. **Path Resolution Fix**: Corrected sibling directory access for ancillary files

## Migration Notes

### File Relocations (October 2025)
Original root files have been organized into functional subdirectories:

- `submit_aws_job.py` → `aws/scripts/submit_aws_job.py`
- `lambda_handler.py` → `aws/lambda/lambda_handler.py`
- `deploy_lambda_container.sh` → `aws/scripts/deploy_lambda_container.sh`
- `AWS_*.md` files → `aws/docs/`
- `aws_config.ini` → `aws/config/aws_config.ini`

### Path Updates Required
Scripts referencing old paths need updates:
- Configuration file references: `../../config.ini` (from scripts directory)
- Docker build context: `../../` (from scripts directory)
- Log directory: `../logs/` (from scripts directory)

## Development Workflow

### 1. Local Development
```bash
# Work in aws/ directory
cd aws/

# Test configurations
python scripts/submit_aws_job.py --satellite sentinel2 --dry-run true

# Build and test containers locally
cd scripts/
./deploy_lambda_container.sh
```

### 2. Production Deployment
```bash
# Deploy to AWS Lambda
cd aws/scripts/
./deploy_lambda_container.sh

# Monitor via AWS Console or CLI
aws lambda invoke --function-name glacier-sentinel2-processor response.json
```

### 3. Documentation Updates
```bash
# Update AWS documentation
cd aws/docs/
nano AWS_SETUP_STATUS.md

# Update README
nano ../README.md
```

## Integration with Main Project

### Configuration Integration
- AWS scripts read main project `config.ini` via relative paths
- AWS-specific settings in `aws/config/aws_config.ini`
- Logging directed to `aws/logs/` directory

### Processing Integration
- Lambda handlers download complete project from S3
- Processing scripts called with same parameters as HPC/local modes
- Results uploaded to S3 buckets for further analysis

## Future Enhancements

### Planned Additions
- [ ] AWS Batch implementation for large-scale processing
- [ ] ECS task definitions for containerized workflows
- [ ] CloudFormation templates for infrastructure as code
- [ ] AWS Step Functions for workflow orchestration
- [ ] Cost optimization with spot instances

### Architecture Evolution
- **Current**: Lambda container processing with project context
- **Next**: Full multi-service AWS processing pipeline
- **Future**: Serverless workflow orchestration with event-driven processing

## Support and Troubleshooting

### Multi-Satellite Processing Status (October 2025)

#### ✅ Sentinel-2 Processing
**Status**: PRODUCTION READY - Fully functional on AWS Lambda

- Complete end-to-end workflow (download, clip, post-process)
- 8 files successfully processed per region
- Processing time: ~56 seconds per region
- Resources: 5GB RAM, 10GB ephemeral storage

**Test Command**:
```bash
aws lambda invoke --function-name glacier-sentinel2-processor \
  --payload '{"satellite": "sentinel2", "regions": "134_Arsuk", "start_date": "2024-08-01", "end_date": "2024-08-01", "s3_bucket": "greenland-glacier-data"}' \
  result.json
```

#### 🔄 Landsat Processing
**Status**: IN PROGRESS - Infrastructure ready, debugging underway

- Lambda handler implemented with correct argument mapping
- AWS credential fallback mechanism in place
- Script starts but exits early (return code 1)
- **See**: `docs/LANDSAT_LAMBDA_TROUBLESHOOTING.md` for detailed troubleshooting guide

**Known Issues**:
- Early script exit without error messages
- Possible STAC API connectivity or authentication issue
- Output directory permissions investigation needed

### Common Issues
1. **IAM Permissions**: Ensure Lambda execution role has S3 access and requester-pays permissions
2. **Container Size**: Monitor 1.4GB image size limits
3. **Timeout Settings**: Lambda functions may need 15+ minute timeouts for processing
4. **Region Settings**: Use `us-west-2` for optimal satellite data access
5. **Docker Cache**: Use `--no-cache` flag when rebuilding after code changes
6. **Path Resolution**: Ensure ancillary folder accessed correctly (`script_dir.parent / 'ancillary'`)

### Debug Resources
- **CloudWatch Logs**: `/aws/lambda/glacier-sentinel2-processor` for execution details
- **ECR Repository**: `glacier-sentinel2-processor` for container image management
- **S3 Bucket**: `greenland-glacier-data` for data storage and results
- **Path Fix Guide**: See `docs/PATH_FIX_GUIDE.md` for sibling directory access issues
- **Fresh Download**: See `docs/FRESH_DOWNLOAD_WORKFLOW.md` for clean S3 workflow
- **Troubleshooting**: See `docs/LANDSAT_LAMBDA_TROUBLESHOOTING.md` for Landsat-specific issues
- **Deployment**: See `docs/LAMBDA_DEPLOYMENT_GUIDE.md` for rebuild procedures

### Documentation Quick Reference
- **Fresh Download Workflow**: `docs/FRESH_DOWNLOAD_WORKFLOW.md` - Clean S3 and reprocess guide
- **Path Fix Guide**: `docs/PATH_FIX_GUIDE.md` - Sibling directory resolution fix
- **Deployment Guide**: `docs/LAMBDA_DEPLOYMENT_GUIDE.md` - Docker rebuild, ECR push, Lambda update
- **Landsat Troubleshooting**: `docs/LANDSAT_LAMBDA_TROUBLESHOOTING.md` - Active debugging document
- **Container Success**: `docs/LAMBDA_CONTAINER_SUCCESS.md` - Milestone achievements
- **Setup Status**: `docs/AWS_SETUP_STATUS.md` - Current AWS configuration

### Contact
- **Architecture**: Documented in `../AGENTS.md`
- **Status**: Current implementation status in `docs/AWS_SETUP_STATUS.md`
- **Migration**: Complete reorganization October 2025
- **Latest Update**: October 2, 2025 - Multi-satellite Lambda support with Sentinel-2 production-ready
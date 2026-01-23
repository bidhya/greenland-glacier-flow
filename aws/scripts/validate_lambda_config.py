#!/usr/bin/env python3
"""
Validate AWS Lambda configuration against required specifications.

This script prevents configuration drift by checking critical Lambda settings
before deployment or testing. Run this after any Lambda configuration changes.

Usage:
    python validate_lambda_config.py --function-name glacier-processing
    
Exit codes:
    0 = All validations passed
    1 = One or more validations failed (deployment NOT recommended)
"""

import sys
import argparse
import boto3
from typing import Dict, List, Tuple

# CRITICAL CONFIGURATION REQUIREMENTS
# Update these if requirements change
REQUIRED_CONFIG = {
    'MemorySize': {
        'min': 10240,  # 10GB minimum for Sentinel-2 processing
        'recommended': 10240,
        'reason': 'Sentinel-2 processing peaks at ~3-4GB memory usage'
    },
    'Timeout': {
        'min': 600,  # 10 minutes minimum
        'recommended': 900,  # 15 minutes recommended
        'reason': 'Large date ranges or multiple regions can take 10-15 minutes'
    },
    'EphemeralStorage': {
        'min': 10240,  # 10GB minimum (NOT 512MB default!)
        'recommended': 10240,
        'reason': 'Sentinel-2 tiles are 60-200MB each, typically 6 tiles = 360-1200MB + processing outputs'
    }
}

REQUIRED_PACKAGE_TYPE = 'Image'  # Must be container-based for GDAL dependencies


class ConfigValidator:
    """Validates Lambda configuration against requirements."""
    
    def __init__(self, function_name: str):
        self.function_name = function_name
        self.lambda_client = boto3.client('lambda')
        self.errors = []
        self.warnings = []
        
    def validate(self) -> bool:
        """Run all validation checks. Returns True if all passed."""
        print(f"🔍 Validating Lambda function: {self.function_name}\n")
        
        # Get current configuration
        try:
            config = self.lambda_client.get_function_configuration(
                FunctionName=self.function_name
            )
        except Exception as e:
            self.errors.append(f"Failed to get function configuration: {e}")
            return False
        
        # Run validation checks
        self._check_memory(config)
        self._check_timeout(config)
        self._check_ephemeral_storage(config)
        self._check_package_type(config)
        self._check_image_uri(config)
        
        # Display results
        self._display_results()
        
        return len(self.errors) == 0
    
    def _check_memory(self, config: Dict):
        """Validate memory configuration."""
        current = config.get('MemorySize', 0)
        required = REQUIRED_CONFIG['MemorySize']
        
        if current < required['min']:
            self.errors.append(
                f"❌ Memory: {current}MB (minimum: {required['min']}MB)\n"
                f"   Reason: {required['reason']}"
            )
        elif current < required['recommended']:
            self.warnings.append(
                f"⚠️  Memory: {current}MB (recommended: {required['recommended']}MB)\n"
                f"   Reason: {required['reason']}"
            )
        else:
            print(f"✅ Memory: {current}MB")
    
    def _check_timeout(self, config: Dict):
        """Validate timeout configuration."""
        current = config.get('Timeout', 0)
        required = REQUIRED_CONFIG['Timeout']
        
        if current < required['min']:
            self.errors.append(
                f"❌ Timeout: {current}s (minimum: {required['min']}s)\n"
                f"   Reason: {required['reason']}"
            )
        elif current < required['recommended']:
            self.warnings.append(
                f"⚠️  Timeout: {current}s (recommended: {required['recommended']}s)\n"
                f"   Reason: {required['reason']}"
            )
        else:
            print(f"✅ Timeout: {current}s")
    
    def _check_ephemeral_storage(self, config: Dict):
        """Validate ephemeral storage configuration - MOST CRITICAL CHECK."""
        storage_config = config.get('EphemeralStorage', {})
        current = storage_config.get('Size', 512)  # Default is 512MB
        required = REQUIRED_CONFIG['EphemeralStorage']
        
        if current < required['min']:
            self.errors.append(
                f"❌ CRITICAL: Ephemeral Storage: {current}MB (minimum: {required['min']}MB)\n"
                f"   Reason: {required['reason']}\n"
                f"   This WILL cause 'No space left on device' errors during Sentinel-2 processing!\n"
                f"   Fix: aws lambda update-function-configuration --function-name {self.function_name} --ephemeral-storage Size={required['min']}"
            )
        else:
            print(f"✅ Ephemeral Storage: {current}MB")
    
    def _check_package_type(self, config: Dict):
        """Validate package type is Image (container-based)."""
        current = config.get('PackageType', 'Zip')
        
        if current != REQUIRED_PACKAGE_TYPE:
            self.errors.append(
                f"❌ Package Type: {current} (required: {REQUIRED_PACKAGE_TYPE})\n"
                f"   Reason: Container deployment required for GDAL/geopandas dependencies"
            )
        else:
            print(f"✅ Package Type: {current}")
    
    def _check_image_uri(self, config: Dict):
        """Validate container image URI is set correctly."""
        if config.get('PackageType') == 'Image':
            image_uri = config.get('ImageUri', '')
            
            if 'glacier-lambda' not in image_uri:
                self.warnings.append(
                    f"⚠️  Image URI: {image_uri}\n"
                    f"   Expected ECR repository: glacier-lambda"
                )
            else:
                # Extract just the repo name and digest for cleaner output
                repo_name = image_uri.split('/')[-1].split(':')[0]
                print(f"✅ Image URI: {repo_name} (from ECR)")
    
    def _display_results(self):
        """Display validation results with clear pass/fail status."""
        print("\n" + "="*70)
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"\n{warning}")
        
        if self.errors:
            print("\n❌ VALIDATION FAILED:")
            for error in self.errors:
                print(f"\n{error}")
            print("\n" + "="*70)
            print("🚫 Deployment NOT recommended until errors are fixed!")
        else:
            print("\n✅ ALL VALIDATIONS PASSED")
            print("="*70)
            print("✨ Configuration meets all requirements - safe to deploy/test")


def main():
    parser = argparse.ArgumentParser(
        description='Validate Lambda configuration against requirements',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--function-name',
        default='glacier-processing',
        help='Lambda function name to validate (default: glacier-processing)'
    )
    
    args = parser.parse_args()
    
    validator = ConfigValidator(args.function_name)
    success = validator.validate()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

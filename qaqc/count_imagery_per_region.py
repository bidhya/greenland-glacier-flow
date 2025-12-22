#!/usr/bin/env python3
"""
QAQC Script: Count Imagery Per Region

This script counts satellite imagery files per glacier region and generates
a summary report of data availability and processing status.

Usage:
    python count_imagery_per_region.py --data-dir /path/to/processed/data [--output-csv report.csv]

Author: Greenland Glacier Flow Processing Team
Date: October 17, 2025
"""

import argparse
from pathlib import Path
from typing import Dict, List
import pandas as pd
from tqdm import tqdm


def count_files_in_directory(directory: Path, extensions: List[str] = None) -> int:
    """
    Count files in a directory with optional extension filtering.

    Args:
        directory: Path to directory to count files in
        extensions: List of file extensions to count (e.g., ['.tif', '.tiff'])

    Returns:
        Number of files found
    """
    if extensions:
        return len([f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in extensions])

    return len([f for f in directory.iterdir() if f.is_file()])


def analyze_region_data(region_dir: Path, satellite_name: str = None) -> Dict[str, int]:
    """
    Analyze data for a specific region.

    Args:
        region_dir: Path to region directory

    Returns:
        Dictionary with counts of different file types
    """
    results = {
        'region': region_dir.name,
        'total_files': 0,
        'sentinel2_files': 0,
        'landsat_files': 0,
        'metadata_files': 0,
        'template_files': 0,
        'has_clipped': 0,
        'has_downloaded': 0
    }

    if not region_dir.exists():
        return results

    # Count all files
    results['total_files'] = count_files_in_directory(region_dir)

    # Count Sentinel-2 files (typically .tif directly in region directory for Sentinel-2)
    if satellite_name == 'sentinel2':
        # For Sentinel-2, files are directly in the region directory
        sentinel2_files = list(region_dir.glob('*.tif')) + list(region_dir.glob('*.tiff'))
        results['sentinel2_files'] = len(sentinel2_files)
        results['has_clipped'] = 1 if results['sentinel2_files'] > 0 else 0
    else:
        # For Landsat, check clipped directory (though Landsat typically doesn't use this structure)
        clipped_dir = region_dir / 'clipped'
        if clipped_dir.exists():
            results['sentinel2_files'] = count_files_in_directory(clipped_dir, ['.tif', '.tiff'])
            results['has_clipped'] = 1 if results['sentinel2_files'] > 0 else 0

    # Count Landsat files (typically .tif in region directory)
    landsat_files = list(region_dir.glob('*.tif')) + list(region_dir.glob('*.tiff'))
    results['landsat_files'] = len(landsat_files)

    # Count metadata files
    metadata_files = list(region_dir.glob('*.csv'))
    results['metadata_files'] = len(metadata_files)

    # Count template files
    template_files = list(region_dir.glob('*template*')) + list(region_dir.glob('*reference*'))
    results['template_files'] = len(template_files)

    # Check for downloaded data
    download_indicators = list(region_dir.glob('*download*')) + list(region_dir.glob('*raw*'))
    results['has_downloaded'] = 1 if len(download_indicators) > 0 or results['sentinel2_files'] > 0 else 0

    return results


def main():
    """Main function to run the imagery counting analysis."""
    parser = argparse.ArgumentParser(
        description="Count satellite imagery files per glacier region",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python count_imagery_per_region.py --data-dir ./data/processed
    python count_imagery_per_region.py --data-dir /path/to/data --output-csv region_counts.csv
        """
    )

    parser.add_argument(
        '--data-dir',
        type=str,
        required=True,
        help='Path to processed data directory containing satellite subdirectories'
    )

    parser.add_argument(
        '--output-csv',
        type=str,
        default='region_imagery_counts.csv',
        help='Output CSV file path (default: region_imagery_counts.csv)'
    )

    parser.add_argument(
        '--satellite',
        type=str,
        choices=['sentinel2', 'landsat', 'both'],
        default='both',
        help='Which satellite data to analyze (default: both)'
    )

    args = parser.parse_args()

    # Validate input directory
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: Data directory does not exist: {data_dir}")
        return 1

    print(f"🔍 Analyzing imagery counts in: {data_dir}")
    print(f"🛰️  Satellite filter: {args.satellite}")
    print(f"📊 Output: {args.output_csv}")
    print("-" * 60)

    # Find satellite directories
    satellite_dirs = []
    if args.satellite in ['sentinel2', 'both']:
        sentinel_dir = data_dir / 'sentinel2'
        if sentinel_dir.exists():
            satellite_dirs.append(('sentinel2', sentinel_dir))

    if args.satellite in ['landsat', 'both']:
        landsat_dir = data_dir / 'landsat'
        if landsat_dir.exists():
            satellite_dirs.append(('landsat', landsat_dir))

    if not satellite_dirs:
        print(f"Error: No satellite directories found in {data_dir}")
        print("Expected: sentinel2/ and/or landsat/ subdirectories")
        return 1

    # Analyze each satellite
    all_results = []

    for satellite_name, satellite_dir in satellite_dirs:
        print(f"\n📡 Processing {satellite_name.upper()} data...")

        # Find all region directories
        if satellite_name == 'sentinel2':
            # For Sentinel-2, regions are nested in subdirectories like clipped/, download/, etc.
            region_dirs = []
            for subdir in satellite_dir.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('_'):
                    # Look for region directories inside each subdirectory
                    for potential_region in subdir.iterdir():
                        if potential_region.is_dir() and not potential_region.name.startswith('_'):
                            region_dirs.append(potential_region)
        else:
            # For Landsat, regions are directly in the satellite directory
            region_dirs = [d for d in satellite_dir.iterdir() if d.is_dir() and not d.name.startswith('_')]

        if not region_dirs:
            print(f"  No region directories found in {satellite_dir}")
            continue

        print(f"  Found {len(region_dirs)} region directories")

        # Analyze each region
        satellite_results = []
        for region_dir in tqdm(region_dirs, desc=f"  Analyzing {satellite_name} regions"):
            result = analyze_region_data(region_dir, satellite_name)
            result['satellite'] = satellite_name
            satellite_results.append(result)

        all_results.extend(satellite_results)

        # Print summary for this satellite
        total_files = sum(r['total_files'] for r in satellite_results)
        processed_regions = sum(1 for r in satellite_results if r['total_files'] > 0)

        print(f"  ✅ {satellite_name.upper()} Summary:")
        print(f"     Regions with data: {processed_regions}/{len(region_dirs)}")
        print(f"     Total files: {total_files}")

    # Create DataFrame and save results
    if all_results:
        df = pd.DataFrame(all_results)

        # Sort by satellite, then by region
        df = df.sort_values(['satellite', 'region'])

        # Save to CSV
        df.to_csv(args.output_csv, index=False)

        print(f"\n💾 Results saved to: {args.output_csv}")
        print(f"📈 Total regions analyzed: {len(df)}")
        print(f"🗂️  Total files found: {df['total_files'].sum()}")

        # Print summary statistics
        print("\n📊 Summary by Satellite:")
        for satellite in df['satellite'].unique():
            sat_data = df[df['satellite'] == satellite]
            print(f"  {satellite.upper()}: {len(sat_data)} regions, {sat_data['total_files'].sum()} files")

    else:
        print("\n⚠️  No data found in any region directories")
        return 1

    print("\n✅ Analysis complete!")
    return 0


if __name__ == "__main__":
    exit(main())

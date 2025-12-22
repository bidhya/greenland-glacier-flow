#!/usr/bin/env python3
"""
QAQC Script: Generate Quicklook Images

This script creates thumbnail/quicklook images from processed satellite data
for visual inspection and quality assessment.

Usage:
    python generate_quicklooks.py --input-dir /path/to/processed/data --output-dir ./quicklooks [--region region_name]

Author: Greenland Glacier Flow Processing Team
Date: October 17, 2025
"""

import argparse
from pathlib import Path
from typing import List
import numpy as np
from PIL import Image
import rasterio
from tqdm import tqdm


def create_quicklook(raster_path: Path, output_path: Path, size: tuple = (300, 300)) -> bool:
    """
    Create a quicklook thumbnail from a raster file.

    Args:
        raster_path: Path to input raster file
        output_path: Path to output thumbnail image
        size: Tuple of (width, height) for thumbnail

    Returns:
        True if successful, False otherwise
    """
    try:
        with rasterio.open(raster_path) as src:
            # Read the first band (or a composite if multi-band)
            if src.count >= 3:
                # RGB composite for multi-band images
                r = src.read(1)
                g = src.read(2)
                b = src.read(3)

                # Normalize to 0-255 range
                r_norm = ((r - r.min()) / (r.max() - r.min()) * 255).astype(np.uint8)
                g_norm = ((g - g.min()) / (g.max() - g.min()) * 255).astype(np.uint8)
                b_norm = ((b - b.min()) / (b.max() - b.min()) * 255).astype(np.uint8)

                # Create RGB image
                rgb = np.stack([r_norm, g_norm, b_norm], axis=2)
                img = Image.fromarray(rgb)

            else:
                # Single band - create grayscale
                data = src.read(1)
                # Normalize to 0-255 range
                data_norm = ((data - data.min()) / (data.max() - data.min()) * 255).astype(np.uint8)
                img = Image.fromarray(data_norm)

            # Resize to thumbnail size
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Save thumbnail
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, 'JPEG', quality=85)

            return True

    except Exception as e:
        print(f"Error processing {raster_path}: {e}")
        return False


def find_raster_files(directory: Path, extensions: List[str] = None) -> List[Path]:
    """
    Find all raster files in a directory recursively.

    Args:
        directory: Directory to search
        extensions: File extensions to include (default: common raster formats)

    Returns:
        List of raster file paths
    """
    if extensions is None:
        extensions = ['.tif', '.tiff', '.jp2', '.png']

    raster_files = []
    for ext in extensions:
        raster_files.extend(directory.rglob(f'*{ext}'))

    return sorted(raster_files)


def main():
    """Main function to generate quicklook images."""
    parser = argparse.ArgumentParser(
        description="Generate quicklook thumbnail images from satellite data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate_quicklooks.py --input-dir ./data/processed --output-dir ./quicklooks
    python generate_quicklooks.py --input-dir /path/to/data --region 134_Arsuk --size 500 500
        """
    )

    parser.add_argument(
        '--input-dir',
        type=str,
        required=True,
        help='Path to input data directory containing processed satellite data'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='./quicklooks',
        help='Output directory for quicklook images (default: ./quicklooks)'
    )

    parser.add_argument(
        '--region',
        type=str,
        help='Specific region to process (default: all regions)'
    )

    parser.add_argument(
        '--size',
        type=int,
        nargs=2,
        default=[300, 300],
        metavar=('WIDTH', 'HEIGHT'),
        help='Thumbnail size in pixels (default: 300 300)'
    )

    parser.add_argument(
        '--extensions',
        type=str,
        nargs='+',
        default=['.tif', '.tiff'],
        help='File extensions to process (default: .tif .tiff)'
    )

    args = parser.parse_args()

    # Validate input directory
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Error: Input directory does not exist: {input_dir}")
        return 1

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"🖼️  Generating quicklooks from: {input_dir}")
    print(f"📁 Output directory: {output_dir}")
    print(f"📏 Thumbnail size: {args.size[0]}x{args.size[1]}")
    if args.region:
        print(f"🎯 Region filter: {args.region}")
    print(f"📄 Extensions: {', '.join(args.extensions)}")
    print("-" * 60)

    # Find all raster files
    print("🔍 Finding raster files...")
    raster_files = find_raster_files(input_dir, args.extensions)

    if not raster_files:
        print(f"No raster files found in {input_dir} with extensions {args.extensions}")
        return 1

    # Filter by region if specified
    if args.region:
        raster_files = [f for f in raster_files if args.region in str(f)]
        print(f"🎯 Filtered to region '{args.region}': {len(raster_files)} files")

    print(f"📊 Found {len(raster_files)} raster files to process")

    # Process files and create quicklooks
    successful = 0
    failed = 0

    for raster_path in tqdm(raster_files, desc="Creating quicklooks"):
        # Create output path - maintain directory structure
        relative_path = raster_path.relative_to(input_dir)
        output_path = output_dir / relative_path.with_suffix('.jpg')

        if create_quicklook(raster_path, output_path, tuple(args.size)):
            successful += 1
        else:
            failed += 1

    # Print summary
    print("\n✅ Quicklook generation complete!")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Output directory: {output_dir}")

    if successful > 0:
        print(f"\n💡 Tip: Open {output_dir} in your file browser to view the thumbnails")

    return 0 if successful > 0 else 1


if __name__ == "__main__":
    exit(main())

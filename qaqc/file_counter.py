#!/usr/bin/env python3
"""
Simple File Counter

Given a path, counts the number of files in that directory.
Optionally shows total file size when --size flag is used.

Usage:
    python file_counter.py /path/to/directory [--size]
"""

import argparse
from pathlib import Path


def calculate_total_size(directory_path: str) -> tuple[int, int, str]:
    """
    Calculate total size and count of files in a directory.

    Args:
        directory_path: Path to the directory to calculate size for

    Returns:
        Tuple of (file_count, total_size_bytes, formatted_size_string)
    """
    directory = Path(directory_path)

    if not directory.exists():
        print(f"Error: Directory does not exist: {directory_path}")
        return 0, 0, "0 B"

    if not directory.is_dir():
        print(f"Error: Path is not a directory: {directory_path}")
        return 0, 0, "0 B"

    # Calculate total size and count of all files
    total_size = 0
    file_count = 0
    for item in directory.iterdir():
        if item.is_file():
            file_count += 1
            total_size += item.stat().st_size

    # Format size with appropriate units
    formatted_size = format_size(total_size)
    return file_count, total_size, formatted_size


def format_size(size_bytes: int) -> str:
    """
    Format size in bytes to appropriate units (KB, MB, GB).

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"

    # Define unit thresholds
    units = [
        (1024**3, "GB"),
        (1024**2, "MB"),
        (1024**1, "KB"),
        (1, "B")
    ]

    for threshold, unit in units:
        if size_bytes >= threshold:
            value = size_bytes / threshold
            if unit == "B":
                return f"{int(value)} {unit}"
            else:
                return f"{value:.1f} {unit}"

    return f"{size_bytes} B"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Count files in a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Examples:
        python file_counter.py /path/to/directory
        python file_counter.py /path/to/directory --size
        """
    )

    parser.add_argument(
        'directory',
        help='Path to the directory to count files in'
    )

    parser.add_argument(
        '--size', '-s',
        action='store_true',
        help='Also show total file size'
    )

    args = parser.parse_args()

    file_count, total_bytes, formatted_size = calculate_total_size(args.directory)

    if args.size:
        print(f"{file_count} files, {formatted_size}")
    else:
        print(file_count)


if __name__ == "__main__":
    main()

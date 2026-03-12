#!/usr/bin/env python3
"""
Compare Step 1 file counts between two processing years.

Reads CSVs produced by count_step1_files.py and prints a side-by-side
summary.  Lightweight — safe to run on the HPC login node.

Usage:
    python compare_step1_counts.py                      # compare 2024 vs 2025 (default)
    python compare_step1_counts.py --year1 2023 --year2 2025
    python compare_step1_counts.py --diff-threshold 10  # flag regions with >10 fewer files
"""

from pathlib import Path

import pandas as pd
import typer

app = typer.Typer()


# CSVs live in ~/QAQC_Results/Step1/ after rsync from HPC
DEFAULT_OUT_DIR = Path.home() / "QAQC_Results" / "Step1"


def load_csv(out_dir: Path, year: str) -> pd.DataFrame:
    path = out_dir / f"step1_file_counts_{year}.csv"
    if not path.exists():
        typer.echo(f"ERROR: {path} not found. Run count_step1_files.py --year {year} first.")
        raise typer.Exit(1)
    return pd.read_csv(path)


@app.command()
def main(
    year1: str = typer.Option("2024", help="Baseline year (older)"),
    year2: str = typer.Option("2025", help="Comparison year (newer)"),
    out_dir: Path = typer.Option(DEFAULT_OUT_DIR, file_okay=False, help="Folder containing the CSVs"),
    diff_threshold: int = typer.Option(20, help="Flag regions where year2 has fewer files than year1 by this amount"),
):
    """Compare Step 1 file counts between two years."""

    df1 = load_csv(out_dir, year1)
    df2 = load_csv(out_dir, year2)

    typer.echo(f"\n{'='*70}")
    typer.echo(f"  Step 1 File Count Comparison:  {year1}  vs  {year2}")
    typer.echo(f"{'='*70}")
    typer.echo(f"  Regions in {year1}: {len(df1)}  |  Regions in {year2}: {len(df2)}")

    # Regions present in one year but not the other
    only1 = sorted(set(df1.region) - set(df2.region))
    only2 = sorted(set(df2.region) - set(df1.region))
    if only1:
        typer.echo(f"\n  Regions only in {year1} ({len(only1)}): {only1}")
    if only2:
        typer.echo(f"\n  Regions only in {year2} ({len(only2)}): {only2}")

    # Merge on common regions
    df = df1.merge(df2, on="region", suffixes=(f"_{year1}", f"_{year2}"))

    # Totals
    typer.echo(f"\n  {'Metric':<30} {year1:>10} {year2:>10} {'Diff':>10}")
    typer.echo(f"  {'-'*62}")
    for col in ["sentinel2_downloads", "sentinel2_clipped", "landsat"]:
        c1, c2 = f"{col}_{year1}", f"{col}_{year2}"
        t1, t2 = df[c1].sum(), df[c2].sum()
        diff = t2 - t1
        sign = "+" if diff >= 0 else ""
        typer.echo(f"  {col:<30} {t1:>10,} {t2:>10,} {sign}{diff:>9,}")

    # Per-region flags: regions significantly worse in year2
    for col in ["sentinel2_clipped", "landsat"]:
        c1, c2 = f"{col}_{year1}", f"{col}_{year2}"
        df[f"diff_{col}"] = df[c2] - df[c1]
        flagged = df[df[f"diff_{col}"] < -diff_threshold].sort_values(f"diff_{col}")[
            ["region", c2, c1, f"diff_{col}"]
        ]
        typer.echo(f"\n  Regions with >{diff_threshold} fewer {col} in {year2} ({len(flagged)}):")
        if flagged.empty:
            typer.echo("    None — all regions look comparable.")
        else:
            typer.echo(f"  {'region':<40} {year2:>8} {year1:>8} {'diff':>8}")
            for _, row in flagged.iterrows():
                typer.echo(f"  {row['region']:<40} {int(row[c2]):>8} {int(row[c1]):>8} {int(row[f'diff_{col}']):>8}")

    typer.echo(f"\n{'='*70}\n")


if __name__ == "__main__":
    app()

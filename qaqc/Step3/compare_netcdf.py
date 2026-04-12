#!/usr/bin/env python3
"""
NetCDF Comparison Script for Step 3

Compares NetCDF delivery files between two Step 3 runs. Paths are resolved
from data_paths.yml using year keys (e.g. "2025", "2025_old", "2024"),
so no hardcoded paths are needed.

Usage:
    # structure comparison (default — dims + index count):
    python compare_netcdf.py --year1 2025 --year2 2025_old

    # encoding comparison (NSIDC compliance — dtypes, encodings, attrs vs 2024 accepted):
    # All values read from reference file — no hardcoded specs.
    # NaN _FillValue values are treated as equal (not flagged as differences).
    # creation_date and data_acknowledgement attrs excluded (year-specific by design).
    python compare_netcdf.py --year1 2025 --year2 2024 --mode encoding

    # pixel-perfect comparison (use when validating environment changes):
    python compare_netcdf.py --year1 2025 --year2 2025_old --mode pixel-perfect

    # single glacier:
    python compare_netcdf.py --year1 2025 --year2 2024 --glacier 134_Arsuk --mode encoding

    # raw paths (escape hatch — skips data_paths.yml):
    python compare_netcdf.py --base1 /path/to/new --base2 /path/to/old
"""
import typer
from pathlib import Path
import xarray as xr
import yaml
import time
from typing import Optional

app = typer.Typer()


def _resolve_base(year: str) -> Path:
    """Resolve delivery root directory for a given year key from data_paths.yml."""
    yml = Path(__file__).resolve().parents[1] / "data_paths.yml"
    with open(yml) as f:
        data = yaml.safe_load(f)
    if year not in data:
        raise ValueError(f"Year key '{year}' not found in data_paths.yml. Available: {list(data.keys())}")
    p = data[year]
    return Path(p["root"]) / p["step3"]["subfolder"]


def _delivery_dir(base: Path) -> Path:
    return base / "nsidic_v01.1_delivery"


def _discover(base: Path) -> list:
    d = _delivery_dir(base)
    if not d.exists():
        return []
    return sorted(f.name for f in d.iterdir() if f.is_file() and f.suffix == ".nc")


def _glacier_id(filename: str) -> str:
    """Return the 3-digit_Name prefix, e.g. '014_Courtauld'."""
    parts = Path(filename).stem.split("_")
    return "_".join(parts[:2])


def compare_data(path1: Path, path2: Path, label: str):
    try:
        ds1 = xr.open_dataset(path1, decode_timedelta=True)
        ds2 = xr.open_dataset(path2, decode_timedelta=True)
    except Exception as e:
        raise RuntimeError(f"Error loading files: {e}")
    ds1.attrs.pop("creation_date", None)
    ds2.attrs.pop("creation_date", None)
    try:
        xr.testing.assert_identical(ds1, ds2)
        print(f"✅ {label:<40} identical")
    except AssertionError as e:
        print(f"❌ {label:<40} differs: {e}")
        raise
    finally:
        ds1.close()
        ds2.close()


def compare_structure(path1: Path, path2: Path, label: str):
    try:
        ds1 = xr.open_dataset(path1, decode_timedelta=True)
        ds2 = xr.open_dataset(path2, decode_timedelta=True)
    except Exception as e:
        raise RuntimeError(f"Error loading files: {e}")
    try:
        x1, y1 = ds1.sizes.get("x"), ds1.sizes.get("y")
        x2, y2 = ds2.sizes.get("x"), ds2.sizes.get("y")
        idx1 = ds1.sizes.get("index")
        idx2 = ds2.sizes.get("index")
        if x1 != x2 or y1 != y2:
            print(f"❌ {label:<40} spatial shape mismatch x:{x1}/{x2}, y:{y1}/{y2}")
            return
        pct = f" ({round(idx1 / idx2 * 100, 1)}%)" if idx1 and idx2 else ""
        print(f"🔍 {label:<40} x/y match ({x1}×{y1}); index(base1/base2)={idx1}/{idx2}{pct}")
    finally:
        ds1.close()
        ds2.close()


# Encoding keys to compare per variable.
_ENCODING_KEYS = ["dtype", "units", "_FillValue", "calendar", "zlib", "complevel", "shuffle"]


def _enc_equal(a, b) -> bool:
    """Encoding value equality that treats NaN == NaN as True."""
    import math
    if a is b:
        return True
    try:
        if math.isnan(a) and math.isnan(b):
            return True
    except (TypeError, ValueError):
        pass
    return a == b


def compare_encoding(path1: Path, path2: Path, label: str) -> bool:
    """
    Compare variable dtypes, per-variable encodings, and global attributes between
    a new file (path1) and the reference file (path2, typically 2024 NSIDC-accepted).

    Checks:
      1. Same variable set
      2. Same spatial dimensions
      3. Per-variable in-memory dtype
      4. Per-variable encoding (dtype, units, _FillValue, calendar, zlib, complevel, shuffle)
      5. Global attributes (excluding creation_date and data_acknowledgement)

    All comparisons are read directly from the reference file — no hardcoded specs.
    Returns True if all checks pass, False otherwise.
    """
    try:
        ds1 = xr.open_dataset(path1, decode_timedelta=True)
        ds2 = xr.open_dataset(path2, decode_timedelta=True)
    except Exception as e:
        print(f"❌ {label:<40} could not open: {e}")
        return False

    issues = []

    try:
        # 1. Variable sets
        all_vars1 = set(ds1.data_vars) | set(ds1.coords)
        all_vars2 = set(ds2.data_vars) | set(ds2.coords)
        only_new = sorted(all_vars1 - all_vars2)
        only_ref = sorted(all_vars2 - all_vars1)
        if only_new:
            issues.append(f"  vars only in new   : {only_new}")
        if only_ref:
            issues.append(f"  vars only in ref   : {only_ref}")

        # 2. Spatial dimensions
        for dim in ["x", "y"]:
            s1, s2 = ds1.sizes.get(dim), ds2.sizes.get(dim)
            if s1 != s2:
                issues.append(f"  dim '{dim}'          : new={s1}, ref={s2}")

        # 3 & 4. Per-variable dtype + encoding
        common_vars = sorted(all_vars1 & all_vars2)
        for var in common_vars:
            v1 = ds1[var]
            v2 = ds2[var]
            # in-memory dtype
            if v1.dtype != v2.dtype:
                issues.append(f"  {var:<35} dtype       : new={v1.dtype}, ref={v2.dtype}")
            # encoding fields
            for k in _ENCODING_KEYS:
                e1 = v1.encoding.get(k)
                e2 = v2.encoding.get(k)
                if not _enc_equal(e1, e2):
                    issues.append(f"  {var:<35} enc[{k!r:<12}]: new={e1!r}, ref={e2!r}")

        # 5. Global attributes
        skip_attrs = {"creation_date", "data_acknowledgement"}
        a1 = {k: v for k, v in ds1.attrs.items() if k not in skip_attrs}
        a2 = {k: v for k, v in ds2.attrs.items() if k not in skip_attrs}
        for k in sorted(set(a1) | set(a2)):
            if a1.get(k) != a2.get(k):
                issues.append(f"  global attr '{k}'   : new={a1.get(k)!r}, ref={a2.get(k)!r}")

    finally:
        ds1.close()
        ds2.close()

    # Report
    if issues:
        print(f"❌ {label:<40} encoding differs from 2024 reference")
        for iss in issues:
            print(iss)
        return False
    else:
        print(f"✅ {label:<40} encoding matches 2024 reference")
        return True


@app.command()
def main(
    year1: Optional[str] = typer.Option(None, help="Year key for base1, resolved from data_paths.yml (e.g. '2025', '2025_old', '2024')"),
    year2: Optional[str] = typer.Option(None, help="Year key for base2, resolved from data_paths.yml"),
    base1: Optional[str] = typer.Option(None, help="Raw path override for base1 (skips data_paths.yml)"),
    base2: Optional[str] = typer.Option(None, help="Raw path override for base2 (skips data_paths.yml)"),
    glacier: Optional[str] = typer.Option(None, help="Compare a single glacier prefix (e.g. '134_Arsuk')"),
    mode: str = typer.Option("structure", help="'structure' = dims/index only (default), 'encoding' = dtype+encoding+attrs vs reference (NSIDC compliance), 'pixel-perfect' = exact value match"),
    reverse: bool = typer.Option(False, help="Swap base1 and base2"),
):
    """Compare Step 3 NetCDF delivery files between two runs."""

    # Resolve bases — year keys take priority; raw paths are the escape hatch
    if base1 is None and base2 is None:
        if not year1 or not year2:
            typer.echo("ERROR: provide --year1/--year2 (from data_paths.yml) or --base1/--base2 (raw paths).", err=True)
            raise typer.Exit(1)
        b1 = _resolve_base(year1)
        b2 = _resolve_base(year2)
    else:
        if base1 is None or base2 is None:
            typer.echo("ERROR: provide both --base1 and --base2 when using raw paths.", err=True)
            raise typer.Exit(1)
        b1, b2 = Path(base1), Path(base2)
        year1 = year1 or b1.name
        year2 = year2 or b2.name

    if reverse:
        b1, b2 = b2, b1
        year1, year2 = year2, year1

    # Sanity check: count delivery files
    d1 = _delivery_dir(b1)
    d2 = _delivery_dir(b2)
    c1 = len(list(d1.glob("*.nc"))) if d1.exists() else 0
    c2 = len(list(d2.glob("*.nc"))) if d2.exists() else 0
    print(f"Delivery counts  base1({year1}): {c1},  base2({year2}): {c2}")

    print(f"\nNetCDF Comparison  mode={mode}")
    print(f"  base1 [{year1}]: {b1}")
    print(f"  base2 [{year2}]: {b2}")
    print("-" * 70)

    # Build file list from base1; match to base2 by glacier id
    files1 = _discover(b1)
    if glacier:
        files1 = [f for f in files1 if f.startswith(glacier)]
        if not files1:
            typer.echo(f"❌ No file found for glacier '{glacier}' in base1.")
            raise typer.Exit(1)

    print(f"Found {len(files1)} files in base1\n")

    # Build glacier-id → filename index for base2 (handles different year in filename)
    files2 = _discover(b2)
    idx2 = {_glacier_id(f): f for f in files2}

    success, skipped, failed = 0, 0, 0
    for f1 in files1:
        gid = _glacier_id(f1)
        f2 = idx2.get(gid)
        if not f2:
            print(f"⚠️  {gid}: not found in base2 — skipped")
            skipped += 1
            continue
        p1, p2 = d1 / f1, d2 / f2
        label = gid
        try:
            if mode == "pixel-perfect":
                compare_data(p1, p2, label)
                success += 1
            elif mode == "encoding":
                ok = compare_encoding(p1, p2, label)
                if ok:
                    success += 1
                else:
                    failed += 1
            else:
                compare_structure(p1, p2, label)
                success += 1
        except Exception as e:
            failed += 1
            if glacier:
                raise

    print(f"\n{'='*70}")
    print(f"Compared {success} | Skipped {skipped} | Failed {failed}  (of {len(files1)} in base1)")


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
NetCDF Comparison Script for Step 3 — regression check against the NSIDC delivery.

Compares the Step 3 NetCDF delivery files of a candidate run against a known-good
baseline delivery. Paths are embedded below (see BASELINES / CANDIDATE_DEFAULT);
--baseline and --candidate override them.

⚠️ This tool is NOT sufficient on its own. Run validate_netcdf.py as well.
   xr.testing.assert_identical() deliberately ignores .encoding, so a file can be
   pixel-perfect here while its on-disk dtype or _FillValue has silently changed.
   That is exactly what NSIDC flagged in the 2025 delivery.

HPC only — no Step 3 NetCDF data exists locally. Allocate resources first:
    srun --cpus-per-task=1 --mem=32gb -t 04:00:00 -p howat,batch --pty bash -i

Usage:
    # full-domain regression, default baseline (2025) vs default candidate:
    python compare_netcdf.py --mode pixel-perfect

    # structure comparison (dims + index count):
    python compare_netcdf.py

    # single glacier:
    python compare_netcdf.py --glacier 134_Arsuk --mode pixel-perfect

    # explicit roots (either or both):
    python compare_netcdf.py --candidate /path/to/new/run --mode pixel-perfect
    python compare_netcdf.py --baseline /path/to/ref --candidate /path/to/new
"""
import typer
from pathlib import Path
import xarray as xr
from typing import Optional

app = typer.Typer()


# ---------------------------------------------------------------------------
# Paths — embedded constants, mirroring 1_download_merge_and_clip/tests/compare_raster.py.
# Deliberately NOT read from qaqc/data_paths.yml: qaqc/ is gitignored, so a tracked
# test may not depend on it. validate_netcdf.py imports these constants from here.
# ---------------------------------------------------------------------------

# All roots below are DELIVERY ROOTS. The delivery subfolder is appended internally.
DELIVERY_SUBDIR = "nsidic_v01.1_delivery"

# Known-good baselines, keyed by processing year. Add a line when a year is delivered.
# The year prefix is applied BY HAND after a delivery is accepted — see the Step 3
# AGENTS.md "Year prefixing of the output directory" section. A prefixed directory
# means delivered and authoritative; an unprefixed one is a test run.
BASELINES = {
    # Delivered to NSIDC April 19, 2026. Read-only, permanent, the reference for 2026.
    "2025": "/fs/project/howat.4-3/greenland_glacier_flow/2025_3_orthocorrect_and_netcdf-package",
}

DEFAULT_YEAR = "2025"

# Recognised comparison modes. An unrecognised --mode is a usage error, not a silent
# fallback to the default — running the wrong check and reporting a pass is the exact
# failure this suite exists to prevent.
MODES = ("structure", "encoding", "pixel-perfect")

# Where a fresh Step 3 run writes — mirrors WD in 3_orthocorrect_and_netcdf-package/lib/config.py.
# Override with --candidate when a run was directed somewhere else.
CANDIDATE_DEFAULT = "/fs/project/howat.4-3/greenland_glacier_flow/3_orthocorrect_and_netcdf-package"


def _resolve_baseline(year: str) -> Path:
    """Resolve the baseline delivery root for a processing year."""
    if year not in BASELINES:
        typer.echo(
            f"ERROR: no baseline recorded for year '{year}'. Available: {sorted(BASELINES)}",
            err=True,
        )
        raise typer.Exit(1)
    return Path(BASELINES[year])


def _delivery_dir(base: Path) -> Path:
    return base / DELIVERY_SUBDIR


def _discover(base: Path) -> list:
    d = _delivery_dir(base)
    if not d.exists():
        return []
    return sorted(f.name for f in d.iterdir() if f.is_file() and f.suffix == ".nc")


def _glacier_id(filename: str) -> str:
    """Return the 3-digit_Name prefix, e.g. '014_Courtauld'."""
    parts = Path(filename).stem.split("_")
    return "_".join(parts[:2])


def compare_data(path1: Path, path2: Path, label: str) -> bool:
    """Exact value match. Returns True if identical, False otherwise.

    ⚠️ xr.testing.assert_identical() deliberately ignores .encoding, so passing here
    does NOT prove NSIDC conformance. Run validate_netcdf.py as well.
    """
    try:
        ds1 = xr.open_dataset(path1, decode_timedelta=True)
        ds2 = xr.open_dataset(path2, decode_timedelta=True)
    except Exception as e:
        print(f"❌ {label:<40} could not open: {e}")
        return False
    ds1.attrs.pop("creation_date", None)
    ds2.attrs.pop("creation_date", None)
    try:
        xr.testing.assert_identical(ds1, ds2)
        print(f"✅ {label:<40} identical")
        return True
    except AssertionError as e:
        print(f"❌ {label:<40} differs: {e}")
        return False
    finally:
        ds1.close()
        ds2.close()


def compare_structure(path1: Path, path2: Path, label: str) -> bool:
    """Spatial-shape check. Returns True if x/y match, False otherwise.

    The `index` dimension (number of stacked velocity fields) is reported as a ratio
    but does NOT fail — two runs can legitimately hold different numbers of fields.
    That makes this mode diagnostic; **pixel-perfect is the regression mode.**
    """
    try:
        ds1 = xr.open_dataset(path1, decode_timedelta=True)
        ds2 = xr.open_dataset(path2, decode_timedelta=True)
    except Exception as e:
        print(f"❌ {label:<40} could not open: {e}")
        return False
    try:
        x1, y1 = ds1.sizes.get("x"), ds1.sizes.get("y")
        x2, y2 = ds2.sizes.get("x"), ds2.sizes.get("y")
        idx1 = ds1.sizes.get("index")
        idx2 = ds2.sizes.get("index")
        if x1 != x2 or y1 != y2:
            print(f"❌ {label:<40} spatial shape mismatch x:{x1}/{x2}, y:{y1}/{y2}")
            return False
        pct = f" ({round(idx1 / idx2 * 100, 1)}%)" if idx1 and idx2 else ""
        print(f"🔍 {label:<40} x/y match ({x1}×{y1}); index(candidate/baseline)={idx1}/{idx2}{pct}")
        return True
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
    the candidate file (path1) and the baseline reference file (path2).

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
            issues.append(f"  vars only in candidate : {only_new}")
        if only_ref:
            issues.append(f"  vars only in baseline  : {only_ref}")

        # 2. Spatial dimensions
        for dim in ["x", "y"]:
            s1, s2 = ds1.sizes.get(dim), ds2.sizes.get(dim)
            if s1 != s2:
                issues.append(f"  dim '{dim}'          : candidate={s1}, baseline={s2}")

        # 3 & 4. Per-variable dtype + encoding
        common_vars = sorted(all_vars1 & all_vars2)
        for var in common_vars:
            v1 = ds1[var]
            v2 = ds2[var]
            # in-memory dtype
            if v1.dtype != v2.dtype:
                issues.append(f"  {var:<35} dtype       : candidate={v1.dtype}, baseline={v2.dtype}")
            # encoding fields
            for k in _ENCODING_KEYS:
                e1 = v1.encoding.get(k)
                e2 = v2.encoding.get(k)
                if not _enc_equal(e1, e2):
                    issues.append(f"  {var:<35} enc[{k!r:<12}]: candidate={e1!r}, baseline={e2!r}")

        # 5. Global attributes
        skip_attrs = {"creation_date", "data_acknowledgement"}
        a1 = {k: v for k, v in ds1.attrs.items() if k not in skip_attrs}
        a2 = {k: v for k, v in ds2.attrs.items() if k not in skip_attrs}
        for k in sorted(set(a1) | set(a2)):
            if a1.get(k) != a2.get(k):
                issues.append(f"  global attr '{k}'   : candidate={a1.get(k)!r}, baseline={a2.get(k)!r}")

    finally:
        ds1.close()
        ds2.close()

    # Report
    if issues:
        print(f"❌ {label:<40} encoding differs from baseline")
        for iss in issues:
            print(iss)
        return False
    else:
        print(f"✅ {label:<40} encoding matches baseline")
        return True


@app.command()
def main(
    year: str = typer.Option(DEFAULT_YEAR, help=f"Baseline year key. Available: {sorted(BASELINES)}"),
    baseline: Optional[str] = typer.Option(None, help="Raw path to the baseline delivery root (overrides --year)"),
    candidate: Optional[str] = typer.Option(None, help=f"Raw path to the candidate delivery root (default: {CANDIDATE_DEFAULT})"),
    glacier: Optional[str] = typer.Option(None, help="Compare a single glacier prefix (e.g. '134_Arsuk')"),
    mode: str = typer.Option("structure", help="'structure' = dims/index only (default), 'encoding' = dtype+encoding+attrs vs baseline (NSIDC compliance), 'pixel-perfect' = exact value match"),
):
    """Compare a candidate Step 3 NetCDF delivery against a baseline delivery."""

    # An unrecognised mode must not fall through to `structure` and report a pass.
    if mode not in MODES:
        typer.echo(f"ERROR: unknown --mode '{mode}'. Choose one of: {', '.join(MODES)}", err=True)
        raise typer.Exit(1)

    # Resolve roots — candidate drives the file list, baseline is the reference.
    b_base = Path(baseline) if baseline else _resolve_baseline(year)
    b_cand = Path(candidate) if candidate else Path(CANDIDATE_DEFAULT)

    b1, b2 = b_cand, b_base

    # Sanity check: count delivery files
    d1 = _delivery_dir(b1)
    d2 = _delivery_dir(b2)
    c1 = len(list(d1.glob("*.nc"))) if d1.exists() else 0
    c2 = len(list(d2.glob("*.nc"))) if d2.exists() else 0
    print(f"Delivery counts  candidate: {c1},  baseline: {c2}")

    print(f"\nNetCDF Comparison  mode={mode}")
    print(f"  candidate: {b1}")
    print(f"  baseline : {b2}")
    print("-" * 70)

    # A run that cannot check anything must say so — exit 2, never 0.
    if c1 == 0:
        typer.echo(f"⚠️  COULD NOT CHECK: no .nc files under {d1}", err=True)
        raise typer.Exit(2)
    if c2 == 0:
        typer.echo(f"⚠️  COULD NOT CHECK: no baseline .nc files under {d2}", err=True)
        raise typer.Exit(2)

    # Build file list from the candidate; match to the baseline by glacier id
    files1 = _discover(b1)
    if glacier:
        files1 = [f for f in files1 if f.startswith(glacier)]
        if not files1:
            typer.echo(f"⚠️  COULD NOT CHECK: no file for glacier '{glacier}' in the candidate.", err=True)
            raise typer.Exit(2)

    print(f"Found {len(files1)} files in the candidate\n")

    # Build glacier-id → filename index for the baseline (handles different year in filename)
    files2 = _discover(b2)
    idx2 = {_glacier_id(f): f for f in files2}

    success, skipped, failed = 0, 0, 0
    for f1 in files1:
        gid = _glacier_id(f1)
        f2 = idx2.get(gid)
        if not f2:
            print(f"⚠️  {gid}: not found in baseline — skipped")
            skipped += 1
            continue
        p1, p2 = d1 / f1, d2 / f2
        label = gid
        if mode == "pixel-perfect":
            ok = compare_data(p1, p2, label)
        elif mode == "encoding":
            ok = compare_encoding(p1, p2, label)
        else:
            ok = compare_structure(p1, p2, label)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n{'='*70}")
    print(f"Compared {success} | Skipped {skipped} | Failed {failed}  (of {len(files1)} in the candidate)")

    # Exit code is the contract: 0 passed · 1 failed · 2 could not check.
    if failed:
        print(f"RESULT: FAIL — {failed} glacier(s) differ from the baseline")
        raise typer.Exit(1)
    if success == 0:
        print("RESULT: COULD NOT CHECK — no glacier was compared (all skipped)")
        raise typer.Exit(2)
    print(f"RESULT: PASS — {success} glacier(s) match the baseline (mode={mode})")
    raise typer.Exit(0)


if __name__ == "__main__":
    app()

#!/usr/bin/env python3
"""
NSIDC Absolute Compliance Validator for Step 3 NetCDF Files.

Validates delivery files against a fixed NSIDC spec held in the constants below.
**No baseline needed** — this is what makes it usable on a season with nothing to
compare against, which is what 2026 will be.

⚠️ This tool and compare_netcdf.py are BOTH required; neither replaces the other.
   In 2025 a library update silently changed a fill value, compare_netcdf.py
   --mode pixel-perfect passed, and NSIDC flagged the delivery — because
   xr.testing.assert_identical() ignores .encoding. This validator reads encoding
   directly, and catches that.
   The gap in the other direction: this is a pure WHITELIST checker. Every check
   iterates the spec, never the file, so it detects anything MISSING and nothing
   ADDED. A library that injects a new attribute or variable passes here silently;
   compare_netcdf.py --mode encoding compares variable sets and would see it.

Spec checks:
  1. Required dimensions present (index, x, y)
  2. Required variables and coordinates present
  3. Per-variable encoding: dtype, zlib, complevel, shuffle, units, calendar, _FillValue
  4. Global attributes: exact value for fixed attrs; presence-only for variable attrs

HPC only — no Step 3 NetCDF data exists locally. Allocate resources first:
    srun --cpus-per-task=1 --mem=32gb -t 04:00:00 -p howat,batch --pty bash -i

Usage:
    # the candidate run (default — same default root as compare_netcdf.py):
    python validate_netcdf.py

    # a recorded baseline delivery instead:
    python validate_netcdf.py --year 2025

    # single glacier:
    python validate_netcdf.py --glacier 014_Courtauld

    # explicit delivery root:
    python validate_netcdf.py --candidate /path/to/3_orthocorrect_and_netcdf-package

    # single file:
    python validate_netcdf.py --file /path/to/014_Courtauld_2025_v01.1.nc

Exit codes: 0 passed · 1 failed · 2 could not check.
"""

import math
import typer
from pathlib import Path
from typing import Optional

import xarray as xr
import numpy as np

# Path constants are defined once, in compare_netcdf.py, and imported here —
# mirroring 1_download_merge_and_clip/tests/check_raster_sanity.py, which imports
# from compare_raster.py. Both files previously carried their own copy.
from compare_netcdf import (
    BASELINES,
    CANDIDATE_DEFAULT,
    DEFAULT_YEAR,
    _delivery_dir,
    _glacier_id,
    _resolve_baseline,
)

app = typer.Typer()

# ---------------------------------------------------------------------------
# NSIDC Spec: derived from 014_Courtauld_2024_v01.1.nc (NSIDC-accepted)
# Inspected: April 2026. Do not edit without re-validating against a new
# NSIDC-accepted reference file.
#
# The 2024 filename is PROVENANCE — where these numbers were first read from —
# not a statement that the spec tracks 2024. No 2024 file is opened at runtime.
# The spec is a FORMAT CONTRACT, not a year: the 2025 delivery passes it 184/184,
# which is itself the evidence that it describes the accepted 2025 format. Do not
# "re-base" it onto a 2025 file; that would change no values.
# ---------------------------------------------------------------------------

_REQUIRED_DIMS = {"index", "x", "y"}

# Per-variable encoding spec.
# Keys used:
#   enc_dtype     expected encoding dtype string (compared via np.dtype())
#   zlib          expected zlib compression boolean
#   complevel     expected compression level  (only checked when zlib=True)
#   shuffle       expected shuffle boolean
#   units         expected units string
#   calendar      expected CF calendar string
#   has_fillvalue True  = _FillValue must be present (and must be NaN)
#   no_fillvalue  True  = _FillValue must NOT appear in encoding
_VAR_SPEC: dict[str, dict] = {
    # --- 3D velocity fields (index × y × x) ---
    "vx": {"enc_dtype": "float32", "zlib": True, "complevel": 5, "shuffle": True, "has_fillvalue": True},
    "vy": {"enc_dtype": "float32", "zlib": True, "complevel": 5, "shuffle": True, "has_fillvalue": True},

    # --- Datetime variables (1D: index) ---
    "scene_1_datetime": {
        "enc_dtype": "int64", "zlib": False,
        "units": "seconds since 1970-01-01", "calendar": "proleptic_gregorian",
        "no_fillvalue": True,
    },
    "scene_2_datetime": {
        "enc_dtype": "int64", "zlib": False,
        "units": "seconds since 1970-01-01", "calendar": "proleptic_gregorian",
        "no_fillvalue": True,
    },
    "midpoint_datetime": {
        "enc_dtype": "float64", "zlib": False,
        "units": "seconds since 1970-01-01", "calendar": "proleptic_gregorian",
        "has_fillvalue": True,
    },

    # --- Timedelta variable (1D: index) ---
    "baseline_days": {
        "enc_dtype": "int64", "zlib": True, "complevel": 5, "shuffle": True,
        "units": "days",
    },

    # --- 1D float error / stats fields (index) ---
    "percent_ice_area_notnull": {"enc_dtype": "float32", "zlib": True, "complevel": 5, "shuffle": True, "has_fillvalue": True},
    "error_mag_rmse":           {"enc_dtype": "float32", "zlib": True, "complevel": 5, "shuffle": True, "has_fillvalue": True},
    "error_dx_mean":            {"enc_dtype": "float32", "zlib": True, "complevel": 5, "shuffle": True, "has_fillvalue": True},
    "error_dx_sd":              {"enc_dtype": "float32", "zlib": True, "complevel": 5, "shuffle": True, "has_fillvalue": True},
    "error_dy_mean":            {"enc_dtype": "float32", "zlib": True, "complevel": 5, "shuffle": True, "has_fillvalue": True},
    "error_dy_sd":              {"enc_dtype": "float32", "zlib": True, "complevel": 5, "shuffle": True, "has_fillvalue": True},

    # --- String / char fields (S1 encoded) ---
    "id":                         {"enc_dtype": "S1", "zlib": True, "complevel": 5, "shuffle": True},
    "scene_1_satellite":          {"enc_dtype": "S1", "zlib": True, "complevel": 5, "shuffle": True},
    "scene_2_satellite":          {"enc_dtype": "S1", "zlib": True, "complevel": 5, "shuffle": True},
    "scene_1_orbit":              {"enc_dtype": "S1", "zlib": True, "complevel": 5, "shuffle": True},
    "scene_2_orbit":              {"enc_dtype": "S1", "zlib": True, "complevel": 5, "shuffle": True},
    "scene_1_processing_version": {"enc_dtype": "S1", "zlib": True, "complevel": 5, "shuffle": True},
    "scene_2_processing_version": {"enc_dtype": "S1", "zlib": True, "complevel": 5, "shuffle": True},

    # --- CRS scalar ---
    "crs": {"enc_dtype": "float64", "zlib": False, "has_fillvalue": True},
}

# Coordinate spec (index, x, y)
_COORD_SPEC: dict[str, dict] = {
    "index": {"enc_dtype": "int64",   "zlib": False},
    "x":     {"enc_dtype": "float64", "zlib": False, "has_fillvalue": True},
    "y":     {"enc_dtype": "float64", "zlib": False, "has_fillvalue": True},
}

# Global attribute spec: (attr_name, check_value, expected_value)
#   check_value = True  → exact value must match
#   check_value = False → only presence required (value varies per glacier/year)
#
# Exactly three vary: glacier_id, data_acknowledgement, creation_date. This list is
# the authoritative classification of which global attributes are allowed to differ.
# compare_netcdf.py skips only two of them (creation_date, data_acknowledgement) and
# that difference is correct, not a bug: compare pairs glacier X against glacier X,
# so glacier_id is already identical between the two files. Do not "reconcile" them.
_GLOBAL_ATTR_SPEC: list[tuple] = [
    ("project",                 True,  "MEaSUREs Greenland Ice Mapping Project (GIMP)"),
    ("title",                   True,  "MEaSUREs Greenland Ice Velocity: Selected Glacier Site Singel-Pair Velocity Maps from Optical Images."),
    ("version",                 True,  "01.1"),
    ("glacier_id",              False, None),   # varies per glacier
    ("data",                    True,  "ice surface velocity"),
    ("units",                   True,  "m d^{-1}"),
    ("source",                  True,  "Landsat-8 and Sentinel-2 optical imagery"),
    ("projection",              True,  "WGS 84 / NSDIC Sea Ice Polar Stereographic North"),
    ("epsg",                    True,  "3413"),
    ("coordinate_unit",         True,  "m"),
    ("spatial_resolution",      True,  "100 m"),
    ("institution",             True,  "Byrd Polar & Climate Research Center | Ohio State University"),
    ("contributors",            True,  "Tom Chudley, Ian Howat, Bidhya Yadev, MJ Noh, Michael Gravina"),
    ("contact_name",            True,  "Ian Howat"),
    ("contact_email",           True,  "howat.4@osu.edu"),
    ("software",                True,  "Feature-tracking performed using SETSM SDM module | https://github.com/setsmdeveloper/SETSM"),
    ("funding_acknowledgement", True,  "Supported by National Aeronautics and Space Administration MEaSUREs programme (80NSSC18M0078)"),
    ("data_acknowledgement",    False, None),   # varies (contains year)
    ("Conventions",             True,  "CF-1.7"),
    ("creation_date",           False, None),   # varies per run
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nan_equal(a, b) -> bool:
    """Return True if a == b, treating NaN == NaN as equal."""
    try:
        if math.isnan(a) and math.isnan(b):
            return True
    except (TypeError, ValueError):
        pass
    return a == b


def _check_var_encoding(var_name: str, enc: dict, spec: dict, issues: list) -> None:
    """Append encoding issues for one variable to the issues list."""
    prefix = f"  {var_name:<36}"

    if "enc_dtype" in spec:
        expected_dt = np.dtype(spec["enc_dtype"])
        actual_dt = enc.get("dtype")
        if actual_dt is None:
            issues.append(f"{prefix} enc[dtype]    : missing (expected {spec['enc_dtype']})")
        elif actual_dt != expected_dt:
            issues.append(f"{prefix} enc[dtype]    : got={actual_dt}, exp={expected_dt}")

    if "zlib" in spec:
        actual = enc.get("zlib")
        if actual != spec["zlib"]:
            issues.append(f"{prefix} enc[zlib]     : got={actual!r}, exp={spec['zlib']!r}")

    if spec.get("zlib") and "complevel" in spec:
        actual = enc.get("complevel")
        if actual != spec["complevel"]:
            issues.append(f"{prefix} enc[complevel]: got={actual!r}, exp={spec['complevel']!r}")

    if "shuffle" in spec:
        actual = enc.get("shuffle")
        if actual != spec["shuffle"]:
            issues.append(f"{prefix} enc[shuffle]  : got={actual!r}, exp={spec['shuffle']!r}")

    if "units" in spec:
        actual = enc.get("units")
        if actual != spec["units"]:
            issues.append(f"{prefix} enc[units]    : got={actual!r}, exp={spec['units']!r}")

    if "calendar" in spec:
        actual = enc.get("calendar")
        if actual != spec["calendar"]:
            issues.append(f"{prefix} enc[calendar] : got={actual!r}, exp={spec['calendar']!r}")

    if spec.get("has_fillvalue"):
        fv = enc.get("_FillValue")
        if fv is None:
            issues.append(f"{prefix} _FillValue    : missing (expected NaN)")
        else:
            try:
                if not math.isnan(fv):
                    issues.append(f"{prefix} _FillValue    : expected NaN, got={fv!r}")
            except (TypeError, ValueError):
                issues.append(f"{prefix} _FillValue    : expected NaN, got={fv!r}")

    if spec.get("no_fillvalue"):
        if "_FillValue" in enc:
            issues.append(f"{prefix} _FillValue    : found {enc['_FillValue']!r} (must be absent per NSIDC spec)")


def validate_file(path: Path) -> bool:
    """Validate one NetCDF file against the NSIDC absolute spec.

    Returns True if all checks pass, False otherwise.
    Prints a ✅ / ❌ line with details on failure.
    """
    label = path.stem
    issues: list[str] = []

    try:
        ds = xr.open_dataset(path, decode_timedelta=True)
    except Exception as e:
        print(f"❌ {label:<40} could not open: {e}")
        return False

    try:
        all_vars = set(ds.data_vars)
        all_coords = set(ds.coords)

        # 1. Required dimensions
        missing_dims = _REQUIRED_DIMS - set(ds.dims)
        if missing_dims:
            issues.append(f"  missing dims          : {sorted(missing_dims)}")

        # 2. Required data variables
        missing_vars = set(_VAR_SPEC) - all_vars
        if missing_vars:
            issues.append(f"  missing data_vars     : {sorted(missing_vars)}")

        # 3. Required coordinates
        missing_coords = set(_COORD_SPEC) - all_coords
        if missing_coords:
            issues.append(f"  missing coords        : {sorted(missing_coords)}")

        # 4. Per-variable encoding
        for var_name, spec in _VAR_SPEC.items():
            if var_name not in all_vars:
                continue  # already reported under missing_vars
            _check_var_encoding(var_name, ds[var_name].encoding, spec, issues)

        # 5. Coordinate encoding
        for coord_name, spec in _COORD_SPEC.items():
            if coord_name not in all_coords:
                continue  # already reported under missing_coords
            _check_var_encoding(coord_name, ds[coord_name].encoding, spec, issues)

        # 6. Global attributes
        for attr_name, check_value, expected in _GLOBAL_ATTR_SPEC:
            if attr_name not in ds.attrs:
                issues.append(f"  missing global attr   : {attr_name!r}")
            elif check_value and ds.attrs[attr_name] != expected:
                issues.append(f"  global attr {attr_name!r:<25}: got={ds.attrs[attr_name]!r}")
                issues.append(f"  {'':>38}  exp={expected!r}")

    finally:
        ds.close()

    if issues:
        print(f"❌ {label:<40} FAIL  ({len(issues)} issue(s))")
        for iss in issues:
            print(iss)
        return False
    else:
        print(f"✅ {label:<40} PASS")
        return True


def _discover(base: Path) -> list[Path]:
    """List .nc files in the delivery subfolder of a delivery ROOT."""
    d = _delivery_dir(base)
    if not d.exists():
        return []
    return sorted(f for f in d.iterdir() if f.is_file() and f.suffix == ".nc")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@app.command()
def main(
    year: Optional[str] = typer.Option(None, help=f"Validate a recorded baseline delivery instead of the candidate. Available: {sorted(BASELINES)}"),
    candidate: Optional[str] = typer.Option(None, help=f"Delivery ROOT to validate (default: {CANDIDATE_DEFAULT})"),
    glacier: Optional[str] = typer.Option(None, help="Validate a single glacier prefix (e.g. '014_Courtauld')"),
    file: Optional[str] = typer.Option(None, help="Absolute path to a single .nc file to validate"),
):
    """Validate Step 3 NetCDF delivery files against the NSIDC absolute spec."""

    if year and candidate:
        typer.echo("ERROR: --year and --candidate are mutually exclusive.", err=True)
        raise typer.Exit(1)

    # --- Collect files to validate ---
    files: list[Path] = []
    source = ""

    if file:
        p = Path(file)
        if not p.exists():
            typer.echo(f"⚠️  COULD NOT CHECK: file not found: {p}", err=True)
            raise typer.Exit(2)
        files = [p]
        source = str(p)
    else:
        # --year selects a recorded baseline root; otherwise the candidate root.
        # Both are delivery ROOTS — the nsidic_v01.1_delivery/ subfolder is appended
        # internally, matching compare_netcdf.py. (The qaqc/ original's --base took
        # the subfolder itself; --candidate is deliberately a new name so the changed
        # meaning cannot be inherited silently by an old saved command.)
        if year:
            base = _resolve_baseline(year)
        else:
            base = Path(candidate) if candidate else Path(CANDIDATE_DEFAULT)
        source = str(base)
        files = _discover(base)
        if not files:
            typer.echo(f"⚠️  COULD NOT CHECK: no .nc files under {_delivery_dir(base)}", err=True)
            raise typer.Exit(2)
        if glacier:
            files = [f for f in files if _glacier_id(f.name) == glacier]
            if not files:
                typer.echo(f"⚠️  COULD NOT CHECK: no file for glacier '{glacier}' under {_delivery_dir(base)}", err=True)
                raise typer.Exit(2)

    # --- Run validation ---
    print("NSIDC Absolute Compliance Validator")
    print("Spec provenance: 014_Courtauld_2024_v01.1.nc — a format contract, not a year")
    print(f"Validating: {source}")
    print(f"Files to validate: {len(files)}")
    print("-" * 70)

    passed, failed = 0, 0
    for f in files:
        ok = validate_file(f)
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*70}")
    print(f"PASS: {passed}  |  FAIL: {failed}  |  Total: {len(files)}")

    # Exit code is the contract: 0 passed · 1 failed · 2 could not check.
    if failed:
        print(f"RESULT: FAIL — {failed} file(s) do not meet the NSIDC spec")
        raise typer.Exit(1)
    print(f"RESULT: PASS — {passed} file(s) meet the NSIDC spec")
    raise typer.Exit(0)


if __name__ == "__main__":
    app()

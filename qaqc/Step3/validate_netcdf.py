#!/usr/bin/env python3
"""
NSIDC Absolute Compliance Validator for Step 3 NetCDF Files.

Validates NetCDF delivery files against the fixed NSIDC spec derived from the
2024 NSIDC-accepted reference (014_Courtauld_2024_v01.1.nc).

No reference file needed — all specs are hardcoded from the accepted 2024 delivery.

Spec checks:
  1. Required dimensions present (index, x, y)
  2. Required variables and coordinates present
  3. Per-variable encoding: dtype, zlib, complevel, shuffle, units, calendar, _FillValue
  4. Global attributes: exact value for fixed attrs; presence-only for variable attrs

Usage:
    # All files for a year (from data_paths.yml):
    python validate_netcdf.py --year 2025

    # Single glacier:
    python validate_netcdf.py --year 2025 --glacier 014_Courtauld

    # Raw path to a single file:
    python validate_netcdf.py --file /path/to/014_Courtauld_2025_v01.1.nc

    # Raw path to a delivery directory:
    python validate_netcdf.py --base /path/to/nsidic_v01.1_delivery/
"""

import math
import typer
import yaml
from pathlib import Path
from typing import Optional

import xarray as xr
import numpy as np

app = typer.Typer()

# ---------------------------------------------------------------------------
# NSIDC Spec: derived from 014_Courtauld_2024_v01.1.nc (NSIDC-accepted)
# Inspected: April 2026. Do not edit without re-validating against a new
# NSIDC-accepted reference file.
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


# ---------------------------------------------------------------------------
# Path resolution (mirrors compare_netcdf.py conventions)
# ---------------------------------------------------------------------------

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


def _discover(base: Path) -> list[Path]:
    d = _delivery_dir(base)
    if not d.exists():
        return []
    return sorted(f for f in d.iterdir() if f.is_file() and f.suffix == ".nc")


def _glacier_id(filename: str) -> str:
    """Return the 3-digit_Name prefix, e.g. '014_Courtauld'."""
    parts = Path(filename).stem.split("_")
    return "_".join(parts[:2])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@app.command()
def main(
    year:    Optional[str] = typer.Option(None, help="Year key from data_paths.yml (e.g. '2025', '2024')"),
    glacier: Optional[str] = typer.Option(None, help="Glacier prefix to validate (e.g. '014_Courtauld'). Used with --year."),
    file:    Optional[str] = typer.Option(None, help="Absolute path to a single .nc file to validate."),
    base:    Optional[str] = typer.Option(None, help="Absolute path to a delivery directory (raw override; skips data_paths.yml)."),
):
    """Validate Step 3 NetCDF delivery files against the NSIDC absolute spec."""

    # --- Collect files to validate ---
    files: list[Path] = []

    if file:
        # Single-file mode
        p = Path(file)
        if not p.exists():
            typer.echo(f"ERROR: file not found: {p}", err=True)
            raise typer.Exit(1)
        files = [p]

    elif base:
        # Raw directory override — treat as the delivery directory directly (no subfolder appended)
        b = Path(base)
        files = sorted(f for f in b.iterdir() if f.is_file() and f.suffix == ".nc") if b.exists() else []
        if not files:
            typer.echo(f"ERROR: no .nc files found under {base}", err=True)
            raise typer.Exit(1)

    elif year:
        try:
            b = _resolve_base(year)
        except ValueError as e:
            typer.echo(f"ERROR: {e}", err=True)
            raise typer.Exit(1)
        files = _discover(b)
        if not files:
            typer.echo(f"ERROR: no .nc files found in delivery dir for year '{year}'", err=True)
            raise typer.Exit(1)
        if glacier:
            files = [f for f in files if _glacier_id(f.name) == glacier]
            if not files:
                typer.echo(f"ERROR: no file matching glacier '{glacier}' in year '{year}'", err=True)
                raise typer.Exit(1)
    else:
        typer.echo("ERROR: provide --year, --file, or --base.", err=True)
        raise typer.Exit(1)

    # --- Run validation ---
    print(f"NSIDC Absolute Compliance Validator")
    print(f"Spec source: 014_Courtauld_2024_v01.1.nc (NSIDC-accepted 2024 delivery)")
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
    if failed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

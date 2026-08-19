# Step 1 — Test Suite Reference

**Status: stable.** Five tools in `1_download_merge_and_clip/tests/`, git-tracked, verified on HPC
against both production years and both satellites. Nothing in Step 1 is currently known-broken.

**This file**: what the tests have established, why they are shaped the way they are, and what they
do **not** cover. `tests/README.md` says how to run them. `AGENTS.md` → *Testing* covers rotating
test parameters.

---

## Exit-code contract

| Code | Meaning |
|---|---|
| `0` | passed |
| `1` | **failed** — something is wrong |
| `2` | **could not check** — baseline missing, nothing found. **Not a pass.** |

`2` exists because "I couldn't check" and "I checked and it was fine" are different answers.
Conflating them is how a broken test quietly reports success. **Always check the exit code.**

⚠️ **A Step 1 *run* exiting 0 proves nothing** — job scripts have no `set -e`. The tests are the
opposite: their exit codes are the contract.

---

## Known-good reference results

Any change must continue to reproduce these.

### 2024 — 104 rasters, both machines

| Region | Satellite | Rasters | Verified |
|---|---|---|---|
| `138_SermiitsiaqInTasermiut` | Sentinel-2 | 2 identical | local + HPC |
| `138_SermiitsiaqInTasermiut` | Landsat | 2 identical | local |
| `191_Hagen_Brae` | Sentinel-2 | 20 identical | HPC |
| `191_Hagen_Brae` | Landsat | 76 identical | HPC |

Dates 2024-08-01 → 2024-08-07.

### 2025 — the standing baseline

`/fs/project/howat.4-3/greenland_glacier_flow` (`--year 2025`, the default).

| Region | Tiles | Area km² | Dates | Result |
|---|---|---|---|---|
| `049_jakobshavn` | 1 | 2,645 | 2025-07-10 → 07-15 | ✅ both satellites |
| `090_petermann` | **5** | 11,457 | 2025-07-10 → 07-15 | ✅ both satellites |
| `140_CentralLindenow` | 1 | — | 2025-05-06 → 05-12 | ✅ both satellites, 10 rasters bit-identical |

`090_petermann` is the **only 5-tile region in the domain** — the strictest multi-tile geometry
available.

### All-regions mode, and S2C

`compare_raster.py sentinel2 --run-mode hpc --year 2025` across the whole candidate tree:

```
Matched: 2/4 regions (22 rasters) | MISMATCHED: 0 | Baseline unavailable: 2
EXIT=2
```

**Exit 2 is correct here**, not a failure — two regions held 2024-dated output against the 2025
baseline. This is the mode where the original `qaqc/` defect lived; on real data that prototype
would have crashed.

Satellite mix in the 22 matched: **10 S2C, 8 S2B, 4 S2A** — consistent with S2C replacing S2A as
primary from January 2025. S2C is verified bit-identical to production.

### Full-suite run, both satellites

All five tools against one region, both satellites — **8 invocations, 8 × exit 0**:

| Tool | Sentinel-2 | Landsat |
|---|---|---|
| `check_environment.py` | 7/7 packages match pins (shared) | — |
| `check_job_generation.py` | 4/4 job files, both satellites × both modes (shared) | — |
| `check_output_structure.py` | 15 `.tif` in region tree | 3 `.tif`, `_reference/` at satellite level |
| `check_raster_sanity.py` | 7/7 sane | 3/3 sane |
| `compare_raster.py` | **7/7 bit-identical** | **3/3 bit-identical** |

Scene mix `3 S2A / 2 S2B / 2 S2C` and `2 LC09 / 1 LC08` — every member of both constellations.

---

## Settled — do not re-open

- **`date2` is inclusive.** The STAC interval `datetime=f'{start}/{end}'` made this ambiguous;
  observed on real scenes, both boundary dates produced.
- **A test run cannot overwrite production.** Candidate resolves to
  `/fs/project/howat.4/yadav.111/...`, baseline to `howat.4-3` — separate trees by construction.
  ⚠️ `config.ini:74` holds the baseline tree as a commented-out `base_dir`; **leave it commented.**
- **Landsat paths and labels are handled correctly.** `compare_raster.py` labels the satellite
  correctly against Landsat's shallower layout, and `check_raster_sanity.py` is satellite-aware
  (15 m for Landsat, 10 m for Sentinel-2).
- **All five tools work on HPC**, including all-regions mode and the local-mode job builder HPC
  would never otherwise exercise.

**Method worth reusing**: choose date windows by listing the baseline first —
`ls {baseline}/1_download_merge_and_clip/{satellite}/{region}/` — rather than guessing. Scenes are
then guaranteed to exist on both sides, and nothing returns exit 2.

---

## Why the tools are shaped this way

### `compare_raster.py` — the defect that justified hardening

The `qaqc/` prototype caught three conditions in one `except`:

| Condition | Exception | Prototype result | Correct |
|---|---|---|---|
| Candidate has no `.tif` (subset download) | `FileNotFoundError` | "Skipped" | ✅ **deliberate — keep** |
| Values differ (real regression) | `AssertionError` | "Skipped", **exit 0** | ❌ must fail |
| Baseline file missing | `RasterioIOError` | uncaught crash | ❌ should exit 2 |

**The subset-download skip is intentional** — you can download a subset and the rest skip cleanly.
The other two were fixed. ⚠️ **Do not fall back to `qaqc/Step1/compare_raster.py`**: in all-regions
mode a real mismatch prints "Skipped" and exits 0.

### `check_environment.py` — two tiers, deliberately

`environment.yml` pins only `python=3.13` and `gdal=3.10.3`; rioxarray, xarray, geopandas and numpy
float. Hard-failing on floating packages would fire on an honest `conda env create`, and a check
that cries wolf gets switched off.

| Tier | Packages | Source of truth | On mismatch |
|---|---|---|---|
| **Pinned** | Python `3.13.x`, GDAL `3.10.3`, rasterio `1.4.x` | `environment.yml` | **hard fail**, exit 1 |
| **Advisory** | rioxarray, xarray, geopandas, numpy | current known-good set | warn, exit 0 |

- rasterio is checked at **minor** level — the constraint is "not 1.5", and a 1.4.5 patch is not a
  reason to block production.
- GDAL is checked **exactly** — `environment.yml` says `gdal=3.10.3`, not a range.
- GDAL version comes from `rasterio.__gdal_version__`, **not** `from osgeo import gdal`. Step 1 has
  zero `osgeo` imports and this keeps it that way.
- `--allow-version-drift` downgrades a hard failure to a warning, for deliberate experiments in a
  `glacier_velocity1` env. The safe path is the default.

⚠️ **The advisory tier tracks the *current* environment, not the 2025-season one.** Rebuilding to
match the 2025 season emits advisory warnings and still exits 0 — correct, but surprising. Both
version sets, and the drift procedure, are in `docs/ENVIRONMENT_PROVENANCE.md`.

### `check_raster_sanity.py` — the one that survives 2026

The only tool that works with **no baseline**, which is the situation for the entire 2026 season.
It would also have caught the historical `x_` prefix corruption without needing a reference.

---

## Failure modes are proven, not assumed

A test whose failure mode is untested is not trustworthy. Every behavioural claim below was
demonstrated with a deliberately broken input, exit codes captured.

### `check_environment.py`

| Scenario | Expected | Exit |
|---|---|---|
| Real `glacier_velocity` environment | pass | `0` ✅ |
| Simulated GDAL drift | hard fail | `1` ✅ |
| Same drift + `--allow-version-drift` | warn, continue | `0` ✅ |
| rasterio unimportable | fail, no crash | `1` ✅ |
| Advisory-only drift (numpy) | warn, still pass | `0` ✅ |

### `check_raster_sanity.py`

Expectations: **Sentinel-2** EPSG:3413 / 10 m / uint16 / nodata 0 / 1 band · **Landsat** identical
but **15 m**.

| Fixture | Exit |
|---|---|
| correct raster (control) | `0` ✅ |
| `EPSG:4326` | `1` ✅ |
| 30 m resolution | `1` ✅ |
| `uint8` | `1` ✅ |
| all nodata | `1` ✅ |
| constant value | `1` ✅ |
| duplicated scene | `1` ✅ |
| 3 bands | `1` ✅ |
| empty tree | `2` ✅ |
| missing tree | `2` ✅ |

The two `2`s matter as much as the `1`s: "nothing to check" stays distinct from "checked and fine".

### `compare_raster.py`

Mismatch → exit 1 · missing baseline → exit 2 · subset-download skip preserved. Verified on
synthetic fixtures **and** on real data, where a genuinely absent baseline reported cleanly and
exited 2 rather than crashing as the prototype did.

---

## Not covered

| Gap | Note |
|---|---|
| **Batch mode** (`--start_end_index`) | Production uses it for all three Sentinel-2 batches. Region selection is the only difference from `--regions`, which *is* tested. |
| **`cores > 1`** | Production runs `cores = 1`, so serial **is** the production path. Testing parallel would validate a configuration nobody uses. |
| **Regions beyond those listed** | `104_sorgenfri`, `134_Arsuk`, `139_SouthLindenow` remain untouched. |
| **`check_environment.py` is manual** | It protects the `gdal` pin only if someone runs it. Automating it means modifying `submit_satellite_job.py` — core Step 1 logic, off-limits without instruction. |

**Known quirk, not a bug**: `submit_satellite_job.py` applies CLI `--base-dir`, then overrides
`root_dir` with `config.ini`'s `local_base_dir` when `execution_mode == 'local'` — inverting the
documented *CLI > config* precedence. It plausibly exists to stop local runs writing to HPC paths.
`check_job_generation.py` works around it with a temporary `--config`.

**Open, not a Step 1 defect**: a NumPy 2.5 deprecation fires inside rasterio 1.4.4's read path on
both satellites. Harmless today. It is an environment-drift risk — the durable context is in
`docs/ENVIRONMENT_PROVENANCE.md`; the open decision is carried in local-only working notes.

---

## Out of scope

- Deleting or reorganizing `qaqc/` — the user's decision, later
- Modifying Step 1 processing scripts, regardless of test results
- Anything in Step 3 — separate suite, separate effort

# Step 1 Tests

Git-tracked tests for Step 1 (download, merge, clip). These travel with the code they test.

---

## Start here — what these five tools are

**If you only know regression testing, start with `compare_raster.py`.** That is the regression test: run Step 1, compare the output to a known-good production baseline, assert every pixel is identical. It is the most important tool here and the one you already use.

The other four exist because a regression test can only answer **one** question — *"did anything change?"* — and it can only answer it when a baseline exists. These are the questions it cannot answer:

| Question | Tool | When it helps |
|---|---|---|
| Does the output **match production**? | `compare_raster.py` | after any code or environment change |
| Is the **environment** the right one? | `check_environment.py` | before a production run |
| Does **job generation** still work? | `check_job_generation.py` | after touching config or the job generator |
| Is the output **complete**? | `check_output_structure.py` | after a run that exited 0 — did it write everything? |
| Is the output **well-formed**? | `check_raster_sanity.py` | on data with **no baseline** — e.g. the 2026 season |

The last one matters most in the long run. A regression test compares against a baseline, so **when 2026 data arrives there will be nothing to compare it to** — by definition. `check_raster_sanity.py` is the only tool here that still works then. It is also the kind of check that would have caught the historical `x_` prefix corruption without needing a reference.

### They are complements, not substitutes

Each can pass while another fails, and that is the point:

- output can **match the baseline exactly** and still have been produced by a drifted environment that will diverge next run → `check_environment.py`
- output can be **structurally perfect** and still be the wrong pixels → `compare_raster.py`
- output can be **bit-identical for the regions that exist** while half the regions were never written → `check_output_structure.py`

### One convention across all five

Every tool uses the same exit codes, so they behave identically in a script:

| Code | Meaning |
|---|---|
| `0` | passed |
| `1` | **failed** — something is wrong, investigate |
| `2` | **could not check** — baseline missing, nothing found. **Not a pass.** |

`2` exists because "I couldn't check" and "I checked and it was fine" are different answers, and conflating them is how a broken test quietly reports success. **Always check the exit code**, not just the output — a run can print reassuring text and still exit non-zero.

### Typical order

```
check_environment.py        ← is my environment right?
   (run Step 1)
check_output_structure.py   ← did it write everything?
check_raster_sanity.py      ← is what it wrote sane?
compare_raster.py           ← does it match production?
```

`check_job_generation.py` is separate — run it after touching `config.ini` or the job generator. It takes seconds and downloads nothing.

---

## Why this folder exists

Step 1 testing used to live in `qaqc/Step1/`, which is **gitignored** — it never travelled with the repo, and had to be rsynced to HPC separately. `qaqc/` was a prototyping and proof-of-concept area, and it still holds prototypes, investigations, and superseded scripts alongside working ones.

**Anything in this folder is authoritative.** Where a script exists both here and in `qaqc/Step1/`, this copy is current and the `qaqc/` one is the older prototype.

`qaqc/` is **not** being deleted. That decision belongs to the project owner, at a much later date.

---

## `check_environment.py` — preflight environment check

Verifies the conda environment matches Step 1's pinned dependencies **before** a run. Environment drift is the failure mode that changes delivered data without changing a line of code.

Run it from the repository root:

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/check_environment.py; echo "EXIT=$?"
```

### Two tiers, and why

`environment.yml` pins only `python=3.13` and `gdal=3.10.3`. rioxarray, xarray, geopandas and numpy all **float** — a legitimate `conda env create` months from now may resolve them differently. Hard-failing on those would fire on an honest rebuild, and a check that cries wolf gets switched off.

| Tier | Packages | On mismatch |
|---|---|---|
| **Pinned** | Python `3.13.x`, GDAL `3.10.3`, rasterio `1.4.x` | ❌ **hard fail**, exit 1 |
| **Advisory** | rioxarray, xarray, geopandas, numpy | ⚠️ warn, exit 0 |

- rasterio is checked at **minor** level. The constraint is "not 1.5"; a 1.4.5 patch is not a reason to block production.
- GDAL is checked **exactly** — `environment.yml` says `gdal=3.10.3`, not a range.
- GDAL comes from `rasterio.__gdal_version__`, **not** `from osgeo import gdal`. Step 1 has zero `osgeo` imports and this keeps it that way.

### Why the GDAL pin matters

`gdal=3.10.3` is the **single point of protection** against a rasterio upgrade — there is no separate `rasterio<1.5` guard anywhere:

```
rasterio 1.4.4  requires libgdal-core >=3.10.3,<3.11
rasterio 1.5.0  requires libgdal-core >=3.13.2
```

Relax the GDAL pin and rasterio moves too, reopening the 1.5.0 compatibility work (CPLE warnings, bilinear vs cubic resampling). Step 1 output goes to NSIDC, so a silent resampling change is a delivery bug.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | pinned dependencies match (advisory drift may still be reported) |
| `1` | a pinned dependency drifted, or a required package is missing |

### Escape hatch

`--allow-version-drift` downgrades a hard failure to a loud warning, so deliberate experiments in a `glacier_velocity1` environment stay possible:

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/check_environment.py --allow-version-drift; echo "EXIT=$?"
```

**Not for production runs.** The default is the safe path, so you get it by accident rather than by discipline.

**Verified** against five scenarios — real environment, simulated GDAL drift, drift with the escape hatch, unimportable rasterio, and advisory-only drift. Evidence in `docs/STEP1_TEST_PLAN.md`.

---

## `check_job_generation.py` — smoke test

Generates job files for both satellites with `--dry-run true` and asserts the important lines are present. Seconds, downloads nothing, submits nothing.

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/check_job_generation.py; echo "EXIT=$?"
```

Catches config/argparse breakage before a production run — a renamed flag, a `config.ini` key that stopped resolving, a broken f-string in the job template. None of that surfaces until a job is submitted and fails hours later, or worse, runs on the wrong interpreter and *succeeds* with the wrong output.

**The activation guard is the line most worth protecting.** Job scripts have no `set -e`, and `eval "$(conda shell.bash hook)"` exits 0 even when broken — so a failed activation falls through to the ambient PATH and the job appears to succeed on the wrong Python. If the guard ever disappears from the template, this test fails.

**Both job builders are exercised.** `submit_satellite_job.py` has `create_bash_job` (local) and `create_slurm_job` (HPC), and only one runs on a given machine. `--execution-mode` forces each in turn, so 4 combinations are checked from either machine.

> ⚠️ **Redirection uses a temporary `--config`, not `--base-dir`.** In local execution mode the generator overrides `base_dir` with `config.ini`'s `local_base_dir`, so `--base-dir` alone does not redirect a local-mode run — it would write into the real output tree. Rewriting both keys in a temp config is the only way to redirect both modes. This is pre-existing generator behaviour and is **not** worked around anywhere else.

`--generator PATH` points the test at a modified generator, to check one before committing it. `--keep` retains the generated job files for inspection.

| Code | Meaning |
|---|---|
| `0` | all 4 job files generated with expected content |
| `1` | a job file was missing, or missing expected content |

**Verified**: passes against the real generator; against a generator with the guard stripped it fails all 4 combinations with `missing: activation guard`.

---

## `check_output_structure.py` — output completeness

Asserts each processed region has the directories its workflow should produce. Directory stats only, no raster reads.

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/check_output_structure.py sentinel2 --run-mode hpc; echo "EXIT=$?"
```

A Step 1 run can fail partway and still exit 0. The clipped rasters may be fine while `metadata/` or `template/` never got written, and nothing complains until Step 2 or Step 3 does.

### Expected layout

| Sentinel-2 | Landsat |
|---|---|
| `{region}/clipped/` — feeds Step 2 | `{region}/` — scenes directly, no subdirectories |
| `{region}/metadata/` | `_reference/` — shared, satellite level |
| `{region}/template/` | |
| `{region}/download/` — **optional** | |

> ⚠️ The two layouts are **not symmetric**, deliberately — they were written by different people. Do not "fix" the asymmetry here.
>
> ⚠️ `download/` is **optional by design**: it is deleted after processing to reclaim storage (~15.56 TB freed for 2024). A missing `download/` is a note, not a failure. `clipped/` is the one that feeds Step 2 and must exist.

| Code | Meaning |
|---|---|
| `0` | every region has its required directories |
| `1` | a required directory is missing |
| `2` | nothing found to check — **not a pass** |

**Verified**: complete region passes; region missing `metadata/` fails with exit 1; region missing only `download/` passes with a note; Landsat missing `_reference/` fails with exit 1; nonexistent tree exits 2.

---

## `check_raster_sanity.py` — baseline-free sanity checks

Validates Step 1 output against known invariants **without** a production baseline.

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/check_raster_sanity.py sentinel2 --region 138_SermiitsiaqInTasermiut --run-mode hpc; echo "EXIT=$?"
```

### Why this exists

`compare_raster.py` answers *"did anything change?"* — it needs a baseline, so it is **structurally unable** to check data that has none. The 2026 season will have no baseline by definition.

This script answers a different question: *"is this output sane?"* That works on any data, new or old. It is also the class of check that would have caught the historical `x_` prefix corruption without needing a reference.

The two are complements, not substitutes. Passing here does **not** mean the output matches production.

### Invariants

Derived by inspecting real production rasters on August 14, 2026 — not assumed:

| | CRS | Resolution | dtype | nodata | bands |
|---|---|---|---|---|---|
| **Sentinel-2** | EPSG:3413 | 10 m | uint16 | 0 | 1 |
| **Landsat** | EPSG:3413 | 15 m | uint16 | 0 | 1 |

> ⚠️ `landsat/_reference/*.tif` are **uint8** templates, not scene output. They sit in a directory starting with `_` and are excluded by region discovery, exactly as in `compare_raster.py`. Do not "fix" the dtype expectation to accommodate them.

### Content checks

- **not entirely nodata** — an all-nodata raster is a failed clip
- **not constant** — a single-valued raster is not imagery
- **not pixel-identical to a sibling** — two names, identical bytes means the same scene was written twice

### Exit codes

| Code | Meaning |
|---|---|
| `0` | all rasters passed |
| `1` | at least one raster failed a check |
| `2` | nothing found to check — **not a pass** |

**Verified** against ten fixtures, each isolating one defect — wrong CRS, wrong resolution, wrong dtype, all-nodata, constant value, duplicated scene, wrong band count, empty tree, missing tree, plus a correct raster as control. Evidence in `docs/STEP1_TEST_PLAN.md`.

### Known noise

rasterio 1.4.4 with numpy 2.5.2 emits a `DeprecationWarning` about setting array shape on `src.read()`. Harmless, and **not suppressed on purpose** — it is a genuine early signal of library drift, and hiding it would defeat the point of `check_environment.py`.

---

## `compare_raster.py` — raster regression test

Compares Step 1 output against a known-good production baseline and asserts the rasters are **bit-identical** (`xr.testing.assert_identical` — values, coordinates, dtype, and attributes).

This is the test that proves a code or environment change did not alter delivered data. Step 1 output feeds NSIDC and must match the legacy format, so "close enough" is not a pass.

**Copied from `qaqc/Step1/compare_raster.py` on August 14, 2026** and hardened.

### Usage

Each command is a single line so it pastes cleanly into an HPC terminal.

**1. On HPC only — allocate resources first.** Do not run comparisons on a login node:

```bash
srun --cpus-per-task=1 --mem=16gb -t 01:00:00 -p howat,batch --pty bash -i
```

**2. Change to the repository root, once.** Every command below is relative to it:

```bash
cd ~/Github/greenland-glacier-flow
```

**3. Run a comparison.**

Sentinel-2, one region:

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/compare_raster.py sentinel2 --region 138_SermiitsiaqInTasermiut --run-mode hpc; echo "EXIT=$?"
```

Landsat, one region:

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/compare_raster.py landsat --region 191_Hagen_Brae --run-mode hpc; echo "EXIT=$?"
```

All regions — omit `--region` to compare every region found in the candidate output:

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/compare_raster.py sentinel2 --run-mode hpc; echo "EXIT=$?"
```

Locally on WSL2 — drop `--run-mode hpc` and it auto-detects (`detect_execution_mode()` picks `local` when `sbatch` is absent):

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/compare_raster.py sentinel2 --region 138_SermiitsiaqInTasermiut; echo "EXIT=$?"
```

The trailing `; echo "EXIT=$?"` is there on purpose — see the exit codes below. Drop it if you only want the output.

### Exit codes

| Code | Meaning | Action |
|---|---|---|
| `0` | every raster compared was identical | pass |
| `1` | at least one raster differed | **regression — investigate** |
| `2` | a baseline was missing or unreadable; nothing mismatched | comparison could not be made — **not a pass** |

`1` outranks `2`: if anything mismatched, the exit code is `1`.

**Check the exit code, not just the output.** That is the whole point of the hardening below.

### Outcomes per region

| Situation | Reported as | Exit contribution |
|---|---|---|
| Rasters identical | `✅` matched | 0 |
| Rasters differ | `❌ MISMATCH` | 1 |
| Baseline file missing/unreadable | `🚫 No baseline` | 2 |
| Candidate region has no `.tif` files | `⚠️ Skipped` | 0 — see below |

**The skip is deliberate.** Downloading a subset of regions is routine, so regions with no candidate data are skipped without failing. This behaviour is preserved exactly as the prototype had it.

---

## ⛔ Do not fall back to `qaqc/Step1/compare_raster.py`

The prototype in `qaqc/Step1/` has two defects, both verified empirically on August 14, 2026:

1. **In all-regions mode a real mismatch prints `⚠️ Skipped` and exits `0`** — with a `🎉`. A genuine regression looks like a clean run. (Single-region `--region` mode is correct and exits 1, which is why the August 14 verification runs were trustworthy — all used `--region`.)
2. **A missing baseline crashes** with an uncaught `RasterioIOError` — an `OSError`, not a `FileNotFoundError`, so the handler never caught it.

Both are fixed here. Side by side on identical fixtures containing one real mismatch:

```
PROTOTYPE EXIT=0    ⚠️  Skipped 002_mismatch: ...not identical
                    🎉 Completed: 1/3 regions compared successfully

HARDENED  EXIT=1    ❌ MISMATCH 002_mismatch: ...not identical
                    ❌ FAILED - output differs from baseline
```

**Full verification evidence for all five tools — every fixture, every exit code, and the reasoning behind each design decision — is in `docs/STEP1_TEST_PLAN.md`** (tracked, travels with the repo).

---

## Choosing a baseline

`--year` selects which production tree to compare against on HPC:

| `--year` | Baseline tree | Notes |
|---|---|---|
| `2025` | `/fs/project/howat.4-3/greenland_glacier_flow` | **default** — survives until 2026 data lands |
| `2024` | `/fs/project/howat.4/greenland_glacier_flow` | shorter lifetime, may be cleared |

To compare against the 2024 tree instead:

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/compare_raster.py sentinel2 --region 138_SermiitsiaqInTasermiut --run-mode hpc --year 2024; echo "EXIT=$?"
```

> ⚠️ **The year must match the dates the candidate was produced with.** Comparing 2024-dated output against the 2025 tree reports mismatches that are **not** regressions.
>
> To reproduce the August 14, 2026 verification runs — which used 2024-dated data — pass `--year 2024` explicitly. The resolved baseline prints at the top of every run; check that line before trusting a result.

**Local mode has no year** — it holds a single saved snapshot at `/home/bny/greenland_glacier_flow_prod` (**do not delete**). Passing `--year` locally prints a warning saying it was ignored, rather than silently doing nothing.

For a tree that is not one of the known years, override the roots entirely:

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/compare_raster.py sentinel2 --baseline /path/to/baseline --candidate /path/to/candidate; echo "EXIT=$?"
```

The resolved roots are printed at the top of every run, so what you compared is always visible in the log.

**If the baseline tree is missing entirely** — e.g. the 2024 allocation gets cleared — the run stops immediately with exit `2` and names the known baselines, instead of emitting a confusing pile of per-region "no baseline" messages.

## Known limitations

- The tool assumes a two-environment candidate-vs-baseline layout. Only one conda environment exists; it works today because `_prod` is a saved snapshot.
- Year → path mapping is duplicated from `qaqc/data_paths.yml`, which is gitignored and so cannot be imported by tracked code. **Adding a year means updating both.**

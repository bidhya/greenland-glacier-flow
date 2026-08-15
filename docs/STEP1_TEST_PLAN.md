# Step 1 — Test Formalization Plan

**Created**: August 14, 2026
**Branch**: `feature/step1-tests` (from `dev` at `7a2ac40`)
**Status**: **Phase 1 complete** (August 14, 2026). Phases 2–5 not started.

**Cold start**: read `AGENTS.md` → *Cold Start* first for project-wide orientation. This file covers Step 1 testing only.

**Current reality check**:

- `1_download_merge_and_clip/tests/` **exists** and holds `compare_raster.py` + `README.md`
- that copy is **authoritative**; `qaqc/Step1/compare_raster.py` is the older prototype, left in place untouched
- the hardened version was verified against synthetic fixtures — mismatch → exit 1, missing baseline → exit 2, subset-download skip preserved. Evidence is in `1_download_merge_and_clip/tests/README.md`

---

## Goal

Move Step 1 testing out of the gitignored `qaqc/` prototyping area into **`1_download_merge_and_clip/tests/`**, so tests are git-tracked and travel with the code they test.

`qaqc/` was a prototyping and proof-of-concept area. It is not going away — but it should stop being the place you have to visit to test Step 1.

---

## Standing Rules

1. **Copy, never move.** `qaqc/` stays intact. Deleting anything there is the user's decision, at a much later date. Not the agent's call.
2. **Record provenance on every copy.** In the copied file's header *and* in `tests/README.md`, state the source path and date, and that the `tests/` version is authoritative while the `qaqc/` one is the older prototype.
3. **Stay inside `tests/`.** `1_download_merge_and_clip/` is otherwise off-limits without explicit instruction. This work is authorized only for the new `tests/` subfolder — do not touch the processing scripts.
4. **Verify assumptions before changing behaviour.** Existing oddities are frequently deliberate. Reproduce and confirm before "fixing" (see the verified findings below for a case where the first read was wrong).
5. **Prove failures, not just successes.** A test whose failure mode is untested is not trustworthy. Each behavioural change must be demonstrated with a deliberately broken input.

---

## Verified Findings (August 14, 2026)

Empirically confirmed, not assumed. These motivate Phase 1.

### `compare_raster.py` all-regions mode conflates three conditions

```python
except (ValueError, FileNotFoundError, AssertionError) as e:
    typer.echo(f"⚠️  Skipped {region_name}: {e}", err=True)
    continue
```

| Condition | Exception | Caught? | Current result | Correct? |
|---|---|---|---|---|
| Candidate region has no `.tif` files (subset download) | `FileNotFoundError`, raised explicitly in `compare_raster_files` | yes | "Skipped" | ✅ **deliberate — keep** |
| Values differ (real regression) | `AssertionError` from `xr.testing.assert_identical` | yes | "Skipped", exit 0 | ❌ must fail |
| Baseline file missing | `RasterioIOError` (an `OSError`, **not** `FileNotFoundError`) | **no** | uncaught crash | ❌ should skip |

**The subset-download skip is real and intentional** — you can download a subset of regions and the rest skip cleanly. Preserve it. `README_raster_compare.md` documents the skip as *"Region skipped (missing data)"*, which supports the reading that catching mismatches there was an oversight.

Single-region mode (`--region`) exits 1 correctly. This is why the August 14 verification runs were trustworthy — all used `--region`.

### Other confirmed issues

- **Hardcoded baselines.** `prod_base` / `dev_base` are fixed in `main()`. The HPC baseline points at the **2024** tree; 2025 (`/fs/project/howat.4-3/greenland_glacier_flow`) is the preferred baseline going forward and is not wired up.
- **Two-environment model.** The tool assumes concurrent `glacier_velocity` vs `glacier_velocity1` environments. Only one env exists; it works today only because `_prod` is a saved snapshot.
- **Landsat satellite label wrong.** `dev_path.parent.parent.name` assumes Sentinel-2 path depth (`.../sentinel2/{region}/clipped`); Landsat is one level shallower, printing `Satellite: 1_download_merge_and_clip`.

---

## Known-Good Reference Results

Any change must continue to reproduce these (August 14, 2026, current environment):

| Region | Satellite | Rasters | Baseline | Re-verified with hardened `tests/` copy |
|---|---|---|---|---|
| `138_SermiitsiaqInTasermiut` | Sentinel-2 | 2 identical | local `_prod` snapshot + HPC 2024 production | ✅ local **and** HPC |
| `138_SermiitsiaqInTasermiut` | Landsat | 2 identical | same | ✅ local |
| `191_Hagen_Brae` | Sentinel-2 | 20 identical | HPC 2024 production | ✅ HPC |
| `191_Hagen_Brae` | Landsat | 76 identical | HPC 2024 production | ✅ HPC |

All dates 2024-08-01 → 2024-08-07. 104 rasters total across both machines.

### 2025 baseline verification (August 15, 2026)

**First real exercise of `--year 2025`.** Two regions not previously used, chosen by `tile_count` from `glaciers_roi_proj_v3_300m.gpkg` rather than from doc examples. Dates 2025-07-10 → 2025-07-15.

| Region | Tiles | Area km² | Sentinel-2 | Landsat |
|---|---|---|---|---|
| `049_jakobshavn` | 1 | 2,645 | ✅ exit 0 | ✅ exit 0 |
| `090_petermann` | **5** | 11,457 | ✅ exit 0 | ✅ exit 0 |

`check_raster_sanity.py` passed on all four combinations as well — **8/8 exit 0**, exit codes captured.

What this establishes:

- the **2025 baseline path is correct** (`/fs/project/howat.4-3/greenland_glacier_flow`) — previously taken from `qaqc/data_paths.yml` and never exercised
- `--year 2025` resolves and compares correctly against live data
- Step 1 reproduces 2025 production output for regions it had not been tested on
- `090_petermann` is the **only 5-tile region in the domain** — the strictest multi-tile geometry available, stricter than `191_Hagen_Brae` (4 tiles)
- `check_raster_sanity.py` verified on HPC for the first time, on both satellites

⚠️ Raster counts were not captured, only exit codes. Exit 0 in single-region mode does mean every raster found was identical.

### Remaining tools verified on HPC (August 15, 2026)

The three tools that had never had HPC exit codes captured, now all confirmed:

| Tool | Result |
|---|---|
| `check_environment.py` | ✅ exit 0 — all 7 versions **identical to local**, confirming both machines match by tooling rather than by eye |
| `check_job_generation.py` | ✅ exit 0 — 4/4 job files. Forcing `--execution-mode local` exercised `create_bash_job` on a machine that would otherwise always use SLURM. The temp-config redirection also works against HPC's `config.ini`, which has entirely different paths |
| `check_output_structure.py` | ✅ exit 0 — 4/4 regions, run in **all-regions mode** (no `--region`) |

Regions present in the HPC candidate tree at that point, with total `.tif` counts including `download/`:

```
049_jakobshavn                11
090_petermann                 94
138_SermiitsiaqInTasermiut     5
191_Hagen_Brae               140
```

**All five tools are now verified on HPC.**

### All-regions mode on HPC, and S2C (August 15, 2026)

`compare_raster.py sentinel2 --run-mode hpc --year 2025` across the whole candidate tree — **the last unexercised mode**, and the one where the original defect lived.

```
Matched:              2/4 regions (22 rasters)
Skipped (no data):    0
Baseline unavailable: 2
MISMATCHED:           0
  no baseline: 138_SermiitsiaqInTasermiut, 191_Hagen_Brae
EXIT=2
```

**Exit 2 is the correct answer here**, not a failure: 22 rasters matched, none mismatched, and two regions could not be compared because they hold 2024-dated output while the baseline is the 2025 tree.

Two things this establishes that fixtures could not:

1. **The Phase 1 fix works on real data.** On `138_SermiitsiaqInTasermiut` the baseline file genuinely does not exist. The `qaqc/` prototype would have crashed with an uncaught `RasterioIOError`; this reports cleanly and exits 2, keeping "could not check" distinct from "checked and fine".
2. **S2C scenes are verified.** 10 of the 22 matched rasters are S2C — 2 in `049_jakobshavn`, 8 in `090_petermann` — all bit-identical to 2025 production. S2C had been on the untested list since the start.

Satellite mix in the 22 matched rasters: **10 S2C, 8 S2B, 4 S2A** — consistent with S2C having replaced S2A as the primary unit from January 2025.

**Hardened-copy verification complete (August 14, 2026)**. Every satellite × geometry combination reproduced its prototype result exactly — 102 of the 104 rasters re-run, all identical, all exit 0:

| | Single-tile (`138`) | Multi-tile (`191`) |
|---|---|---|
| **Sentinel-2** | ✅ 2/2 local + 2/2 HPC | ✅ 20/20 HPC (4 MGRS tiles) |
| **Landsat** | ✅ 2/2 local | ✅ 76/76 HPC |

The hardening therefore changed **no passing behaviour** — it only changed what happens when something fails.

Not re-run: HPC single-tile Landsat (`138`, 2 rasters), which is redundant with local `138` Landsat (same code path) and HPC `191` Landsat.

Incidental confirmations: `detect_execution_mode()` works — an HPC run with no `--run-mode` flag resolved to HPC paths. The Landsat runs printed `Satellite: 1_download_merge_and_clip`, confirming the known cosmetic label defect scheduled for Phase 2.

---

## Agreed execution order

Phases are numbered by original planning order, but agreed on August 14, 2026 to be **worked in this order**, one at a time:

**Phase 1 ✅ → Phase 3 → Phase 2 → Phase 5 → Phase 4**

Rationale: Phase 3 is the cheapest remaining win and guards the GDAL pin. Phase 2 unblocks testing against the 2025 baseline. Phase 5 is the only class of test that works on data with no baseline at all — the 2026 season — so it closes the largest real gap. Phase 4 is useful but catches the least severe failures.

---

## Phases

### Phase 1 — Harden the regression test ✅ *(complete, August 14, 2026)*

- [x] Create `1_download_merge_and_clip/tests/`; copy `qaqc/Step1/compare_raster.py` with a provenance header
- [x] Separate `AssertionError` from the missing-data handler so a real mismatch **fails**
- [x] Catch `RasterioIOError` so a missing baseline file **skips** instead of crashing
- [x] Distinct exit codes: `0` all matched · `1` mismatch · `2` baseline missing. Non-zero on mismatch in all-regions mode
- [x] Preserve the subset-download skip (`FileNotFoundError`) unchanged
- [x] Write `tests/README.md` — provenance, exit codes, `tests/` is authoritative over `qaqc/`
- [x] Verify `138_SermiitsiaqInTasermiut` still reports 4/4 identical
- [x] Deliberately construct a mismatch; confirm it **fails with exit 1** rather than skipping
- [x] Confirm a missing baseline file **skips with exit 2** rather than crashing

**Proof the defect was real** — same fixtures, one genuine mismatch, all-regions mode:

```
PROTOTYPE EXIT=0    ⚠️  Skipped 002_mismatch: ...not identical
                    🎉 Completed: 1/3 regions compared successfully
HARDENED  EXIT=1    ❌ MISMATCH 002_mismatch: ...not identical
                    ❌ FAILED - output differs from baseline
```

### Phase 2 — Parameterize baselines ✅ *(complete, August 14, 2026)*

- [x] `--year 2024|2025` selects the HPC baseline tree; `--baseline` / `--candidate` override roots entirely
- [x] 2025 wired up (`/fs/project/howat.4-3/greenland_glacier_flow`) and set as the **default**; 2024 available via `--year 2024`
- [x] Renamed `dev` / `prod` → `candidate` / `baseline` throughout
- [x] Landsat satellite label fixed — `satellite` is passed in rather than inferred from path depth
- [x] Summary now reports regions **and** raster counts
- [x] Resolved roots printed at the top of every run
- [x] Missing baseline tree fails fast with exit 2 instead of per-region noise

**Default is 2025** (user decision, August 14, 2026). 2025 survives until 2026 data is delivered, so it is the longer-lived reference; 2024 may be cleared.

⚠️ **Consequence**: the August 14 verification runs used 2024-dated data, so reproducing them now requires `--year 2024` explicitly. Running them without it compares 2024 output against the 2025 tree and reports mismatches that are **not** regressions. The resolved baseline prints at the top of every run — check that line before trusting a result.

**Year → path mapping is duplicated** from `qaqc/data_paths.yml`. That file is gitignored, so tracked code cannot import it; `tests/` must stay self-contained on a fresh clone. Adding a year means updating both.

Verified:

| Scenario | Expected | Exit |
|---|---|---|
| Default invocation, both satellites | unchanged, 2/2 each | `0` ✅ |
| Landsat label | prints `landsat`, not `1_download_merge_and_clip` | ✅ |
| `--year 2099` | rejected, lists known years | `1` ✅ |
| `--baseline /nope/gone` | fail fast, "NOT a pass" | `2` ✅ |
| `--baseline`/`--candidate` override + all-regions | summary with raster counts | `1` ✅ (fixtures contain a real mismatch) |
| `--year` in local mode | warns it was ignored | `0` ✅ |

### Phase 3 — Preflight environment check ✅ *(complete, August 14, 2026)*

Implemented as `1_download_merge_and_clip/tests/check_environment.py`. Verified behaviour:

| Scenario | Expected | Exit |
|---|---|---|
| Real `glacier_velocity` environment | pass | `0` ✅ |
| Simulated GDAL drift | hard fail | `1` ✅ |
| Same drift + `--allow-version-drift` | warn, continue | `0` ✅ |
| rasterio unimportable | fail, no crash | `1` ✅ |
| Advisory-only drift (numpy) | warn, still pass | `0` ✅ |


Assert the pinned dependencies before a production run. The GDAL pin is the single point of protection against a rasterio upgrade; this makes drift fail loudly instead of silently changing output.

**Two tiers — decided August 14, 2026 after reading `environment.yml`.** It pins only `python=3.13` and `gdal=3.10.3`; rioxarray, xarray, geopandas and numpy all float. Hard-failing on floating packages would fire on an honest `conda env create`, and a check that cries wolf gets switched off.

| Tier | Packages | Source of truth | On mismatch |
|---|---|---|---|
| **Pinned** | Python `3.13.x`, GDAL `3.10.3`, rasterio `1.4.x` | `environment.yml` | **hard fail**, exit 1 |
| **Advisory** | rioxarray, xarray, geopandas, numpy | verified-good snapshot, Aug 14 2026 | warn, exit 0 |

- rasterio is checked at **minor** level (`1.4.x`): the hard constraint is "not 1.5.0", and a 1.4.5 patch is not a reason to block production.
- GDAL is checked **exactly** — `environment.yml` says `gdal=3.10.3`, not a range.
- GDAL version comes from `rasterio.__gdal_version__`, **not** `from osgeo import gdal`. Step 1 has zero `osgeo` imports and this keeps it that way.
- `--allow-version-drift` downgrades a hard failure to a loud warning, so deliberate experiments in a `glacier_velocity1` env stay possible. The safe path is what you get by default.

### Phase 4 — Smoke and structure tests ✅ *(complete, August 14, 2026)*

**Smoke** — `check_job_generation.py`. Generates job files for both satellites × both execution modes with `--dry-run true`, asserting the activation guard, conda activation, processing-script invocation, and pass-through of region/dates. 4 combinations, seconds, no data.

Verified: passes against the real generator; against a generator with the guard stripped it fails all 4 with `missing: activation guard`.

⚠️ **Finding — `--base-dir` does not redirect a local-mode run.** `submit_satellite_job.py` applies the CLI `--base-dir` to `config_dict['base_dir']`, then later overrides `root_dir` with `config.ini`'s `local_base_dir` when `execution_mode == 'local'`. This inverts the documented precedence (*CLI args > config.ini*). **Not changed** — it is core Step 1 logic and may be deliberate, to stop local runs writing to HPC paths. The smoke test works around it with a temporary `--config` that rewrites both keys. Worth a decision later; parked, not fixed.

**Structure** — `check_output_structure.py`. Per region, asserts the expected directories exist.

| Sentinel-2 | Landsat |
|---|---|
| `{region}/clipped/`, `metadata/`, `template/` required | `{region}/` required |
| `{region}/download/` **optional** | `_reference/` required, satellite level |

`download/` is optional by design — it is deleted after processing to reclaim storage (~15.56 TB freed for 2024), so its absence is a note, not a failure.

Verified: complete region passes; missing `metadata/` → exit 1; missing only `download/` → exit 0 with a note; Landsat missing `_reference/` → exit 1; nonexistent tree → exit 2.

### Phase 5 — Baseline-free sanity checks ✅ *(complete, August 14, 2026)*

Implemented as `1_download_merge_and_clip/tests/check_raster_sanity.py`.

**This is the only test that works on genuinely new data** — e.g. the 2026 season, where no production baseline exists by definition. It is also the class of check that would have caught the historical `x_` prefix corruption without needing a reference.

Invariants, derived by inspecting real production rasters rather than assumed:

| | CRS | Resolution | dtype | nodata | bands |
|---|---|---|---|---|---|
| Sentinel-2 | EPSG:3413 | 10 m | uint16 | 0 | 1 |
| Landsat | EPSG:3413 | 15 m | uint16 | 0 | 1 |

⚠️ **Finding**: `landsat/_reference/*.tif` are **uint8** templates, not scene output. They are excluded by the `_` prefix rule in region discovery. Do not relax the dtype expectation to accommodate them.

Plus content checks: not entirely nodata, not constant, and not pixel-identical to a sibling raster.

Verified — ten scenarios, each fixture isolating one defect:

| Fixture | Exit |
|---|---|
| correct raster | `0` ✅ |
| `EPSG:4326` | `1` ✅ |
| 30 m resolution | `1` ✅ |
| `uint8` | `1` ✅ |
| all nodata | `1` ✅ |
| constant value | `1` ✅ |
| duplicated scene | `1` ✅ |
| 3 bands | `1` ✅ |
| empty tree | `2` ✅ |
| missing tree | `2` ✅ |

Path logic is imported from `compare_raster.py` rather than restated — the Sentinel-2/Landsat depth asymmetry is a known way to get it wrong twice.

---

## Out of Scope

- Deleting or reorganizing `qaqc/` — the user's decision, later
- Modifying Step 1 processing scripts
- Anything in Step 3 (untested against the current environment; separate effort)
- Changes to `README.md`, `docs/QUICKSTART.md`, or other docs during the current refactor

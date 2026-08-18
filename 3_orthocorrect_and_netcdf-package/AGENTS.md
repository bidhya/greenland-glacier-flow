# Step 3 — Orthocorrection & NetCDF Packaging

**AI agent guide.** Step 3 empirically corrects orthorectification errors in Sentinel-2 velocity
fields and packages Sentinel-2 + Landsat results into NetCDF for delivery to **NSIDC**.

**Runs on HPC only.** Development is local on WSL2; nothing in Step 3 runs locally and no NetCDF
data exists there. Host and account details are deliberately **not** recorded in this file — they
live in local-only notes and `sync_to_hpc.sh`. Do not add them back.

**Status**: processing code is stable and unchanged since April 19, 2026. The 2025 season has been
reproduced from it repeatedly, bit-for-bit.

---

## ⚠️ Hard constraints

1. **Legacy format is non-negotiable.** Output goes to NSIDC and must match the delivered format.
   **"Better" is a defect.** Pinned versions and odd conventions are usually deliberate.
2. **Do not modify processing code** — `processing_chain/`, `lib/`, `orthocorrect_netcdf-package.py`,
   `batch_glacier_processor.py` — without explicit instruction.
3. **Approval before changes.** Investigate, propose with rationale and risks, wait.
4. **Never claim "verified."** State what was checked and what it does not cover.
5. **Use only information from inside this folder.** Root-level configs and examples are Step 1's.

---

## Verification status — read before quoting any result

**Step 3 is *likely sound, not proven*.**

The 2025 season has been reproduced from the delivered baseline multiple times — 184/184
pixel-perfect, 184/184 against the NSIDC spec, and 184/184 on encoding. **What that does not
cover**: only the 2025 season has been exercised, and every check is automated. **No manual or
notebook inspection has been done.**

Because the processing code has been frozen throughout, each rerun isolates a different variable:

| Rerun | Variable under test | Result |
|---|---|---|
| First | the April code cleanup (environment constant) | held |
| Second | the environment rebuild (code constant) | held |
| Third | repeatability + first run of `--mode encoding` | held, all three modes |

⚠️ **Nothing has exercised code and environment together.** Do not flatten these into "verified
three times."

**Which library versions ran which season**, and what to do if results drift:
`docs/ENVIRONMENT_PROVENANCE.md`.

### 🚫 2024 is superseded — do not use it as a reference

**The 2025 delivery is the only reference that matters.** It was accepted by NSIDC *after* low-level
format corrections. **2026 output must match 2025.** Do not propose 2024 as a baseline, and do not
treat "2024 reprocessing untried" as a gap.

This does not affect `validate_netcdf.py`: its spec lives in hardcoded constants, no 2024 file is
read at runtime. The "derived from a 2024 file" comment is *provenance*. The 2025 delivery passing
184/184 against those constants proves they describe the 2025 format — **the spec is a format
contract, not a year.**

---

## 🔧 Operational runbook — how a season is actually run

### 0. Redirect output — manual, deliberate

Edit `WD` in `lib/config.py` directly on HPC. **`WD` is the only knob** — it flows to
`batch_glacier_processor.py` → `--base_dir` → every glacier. For a 2025 rerun nothing else changes;
`IMGDIR`, dates and `VELDIR` already point at 2025.

- ⚠️ `LOG_DIR` does **not** follow `WD`. Per-glacier logs (`{glacier}_step3.log`) overwrite the
  previous run's in place. Copy them aside first if they matter.
- ⚠️ The target directory must be **empty or nonexistent** — see the silent-skip trap below.

### 1. Run

```bash
cd ~/Github/greenland-glacier-flow/slurm_step3
```

```bash
sbatch orthocorrect_netcdf-package_batch.sh
```

No `--glaciers` flag = all available for the configured `IMGDIR`. Budget is 4 h, 90 cpus, 290 G, and
runs finish well inside it. Single-glacier test:
`python batch_glacier_processor.py --glaciers "049_jakobshavn"`.

### 2. Confirm the run really finished

```bash
sacct -j <JOBID> --format=JobID,State,Elapsed,MaxRSS,ExitCode
```

```bash
cat ~/Github/greenland-glacier-flow/slurm_step3/logs/errored_glaciers.log
```

```bash
ls {WD}/nsidic_v01.1_delivery/*.nc | wc -l
```

`COMPLETED 0:0` rules out TIMEOUT and OOM. It does **not** prove glaciers succeeded — there is no
`set -e`, and glaciers can report success when they failed. **The file count is the real check**, and
the arithmetic closing (`192 − 8 = 184`) is itself a strong signal.

### 3. Check the output

Use the tracked test suite — `tests/README.md`. **Both tools, every time.** Do not use the
`qaqc/Step3/` copies; they set no exit code on failure.

---

## ⚠️ The silent-skip trap — why the rename matters

`orthocorrect_netcdf-package.py` **skips any glacier whose output directory already exists.** A run
into a **non-empty** `WD` skips every glacier, writes nothing, exits **0**, and leaves the previous
run's output in place. A comparison against that stale output then reports `Failed 0` —
indistinguishable from a real pass.

**Resolved by existing practice**: rename the old output with an `x1_`/`x2_` prefix rather than
deleting it. Instant, non-destructive, frees the path so the guard cannot cause a silent no-op, and
self-documenting.

**Decision: keep `WD` fixed on the unprefixed path; rename before each test run.** No code change.
An automated guard was offered and **declined** — *"I might ask your suggested protection mechanism
later."* **Do not implement it unasked.**

---

## 📌 Reference baselines — which directory means what

Several directories share the `3_orthocorrect_and_netcdf-package` name across two allocations:

| Path | What it is |
|---|---|
| `/fs/project/howat.4-3/greenland_glacier_flow/`**`2025_3_`**`orthocorrect_and_netcdf-package/` | ⭐ **THE 2025 reference.** Delivered to NSIDC. Sole authoritative baseline. **The only directory that can be assumed to exist.** |
| `/fs/project/howat.4-3/greenland_glacier_flow/3_orthocorrect_and_netcdf-package/` | The unprefixed `WD` — where a fresh run lands. The candidate. Transient. |
| `.../howat.4/`**`yadav.111`**`/.../3_orthocorrect_and_netcdf-package/` | A user-scoped candidate tree. Note `howat.4`, **not** `howat.4-3`. Transient. |

**Naming rule**: `{year}_` prefix = delivered dataset · `x1_`/`x2_` = superseded run kept
deliberately · unprefixed = scratch.

### ⭐ Year prefixing is manual, and must stay manual

`WD` carries no year. Every run writes to `{WD}/nsidic_v01.1_delivery/`. After a run is checked and
accepted, the directory is renamed **by hand**:

```
3_orthocorrect_and_netcdf-package/   →   2025_3_orthocorrect_and_netcdf-package/
```

Nothing inside changes — `4c` already writes the year into each filename from the `AOI_NAMES`
mapping. **Only the directory name is manual.** The rename moves delivered data out of the write
path *and* frees the unprefixed path for the next run, which is what prevents the silent-skip trap.

---

## 📌 Operating model going forward

- **2025 is the standing regression fixture.** Occasionally rerun Step 3 for 2025 into the
  unprefixed `WD` and confirm nothing changed against `2025_3_...`.
- **When 2026 data arrives**: update `config.py` (`START_DATE`/`END_DATE` → 2026, `IMGDIR` → the 2026
  Step 1 tree), clear leftover 2025 test output, run production, then rename `WD` →
  `2026_3_orthocorrect_and_netcdf-package/` once satisfied.
- `VELDIR` / `VELDIR_LS` need no change — shared across years, filtered by date range.

### 🚫 2026 — parked. Do not build against this yet.

2026 values will legitimately differ, so `pixel-perfect` cannot be a 2026 gate. Reference only:

| Use | Tool + mode |
|---|---|
| Rerun 2025, confirm nothing changed | `compare_netcdf.py --mode pixel-perfect` vs `2025_` |
| 2026 delivery conforms to the 2025 format | `compare_netcdf.py --mode encoding` vs `2025_` |
| Cross-check, no baseline required | `validate_netcdf.py` |

*Caveat: "the 2025 regression proves 2026" holds only insofar as 2026 exercises the same code paths.
A new satellite, or a different mix of graceful-degradation cases, could reach branches 2025 never
touched.*

---

## 🟡 OPEN — the 2025 fixture has an expiry nobody controls

**Not yet acted on. Loses value the longer it waits.**

`VELDIR` is **shared across all years, date-filtered rather than year-partitioned, and owned by
Step 2 (someone else)**. The 2025 regression is only meaningful while Step 2's 2025 velocity output
stays frozen. If Step 2 ever reprocesses 2025, the regression will legitimately differ from that
point on — permanently — with no way to tell at a glance whether the cause was Step 3 code or Step 2
inputs.

Not hypothetical: an S2C reprocessing was exactly this risk, ruled out only **by inference** (output
matched, therefore inputs unchanged), not by direct evidence.

**Suggested cheap insurance — user has not asked, do not build unprompted**: a one-time manifest of
`VELDIR`/`VELDIR_LS` for the 2025 date range (per-glacier file counts + mtimes).

---

## Testing

Two tracked tools in `tests/`, verified on HPC against the real 184-file delivery, all three exit
codes proven. **Start at `tests/README.md`** for copy/paste commands.

- **What the tests establish and what they do not cover**: `tests/STEP3_TEST_PLAN.md`
- **Exit codes**: `0` pass · `1` fail · `2` could not check — **not** a pass
- ⛔ **Do not use `qaqc/Step3/*.py`** — superseded prototypes that exit 0 on failure. Do not edit
  them either; they hold the provenance of the original evidence.

**Both tools, every time.** `xr.testing.assert_identical()` excludes `.encoding` — so a library
update can silently change a fill value and still pass that check. That is precisely the gap
`--mode encoding` exists to close, and it has caught a real one. **Library upgrades, not code
edits, are the live threat.**

---

## Architecture

```
SLURM (orthocorrect_netcdf-package_batch.sh)
  └─ batch_glacier_processor.py          (parallel subprocess calls)
       └─ orthocorrect_netcdf-package.py (per-glacier orchestrator)
            └─ 6-step processing chain
```

**`orthocorrect_netcdf-package.py` is the most important file in Step 3** — it holds the core
processing chain. The batch processor and SLURM script are orchestration wrappers around it.

### Processing chain — `processing_chain/`, run sequentially

| Script | Purpose | Output |
|---|---|---|
| `1_match_to_orbits.py` | Extract orbit metadata | `{glacier}_orbits.csv` |
| `2_get_orbital_average_offset.py` | Calculate correction fields | Offset GeoTIFFs |
| `3_correct_fields.py` | Apply corrections | Corrected velocity directories |
| `4a_netcdf_stack_sentinel.py` | Package Sentinel-2 | `S2_{glacier}_v01.0.nc` |
| `4b_netcdf_stack_landsat.py` | Package Landsat | `L8_{glacier}_v01.0.nc` |
| `4c_..._combined.py` | Merge final product | `vel_{glacier}_v01.0.nc` |
| `4d_..._dem_switch.py` | ~~DEM switch~~ | **DEPRECATED** |

**Scripts 1–3 apply orbital correction to Sentinel-2 only.** Landsat bypasses correction.

**4d is deprecated**: it merged NetCDFs processed either side of the 2021-08-23 DEM switch
(PlanetDEM-90 → GLO-90). All Sentinel-2 velocity data has been reprocessed with the new DEM, so the
discontinuity no longer exists and the trigger condition is always false for current data.

### Output structure

```
{WD}/
├── nsidic_v01.1/{glacier}/          # intermediate: gpkg, gimp_masks, orbits, velocities, netcdf/
└── nsidic_v01.1_delivery/           # ⭐ FINAL — the only thing delivered
    └── {PublicID}_{year}_v01.1.nc
```

---

## Configuration

**Priority**: CLI args > `lib/config.py` > `lib/config_template.py`

**Key paths in `lib/config.py`** — the **#1 cause of failures**:

| Variable | What |
|---|---|
| `VELDIR` / `VELDIR_LS` | Sentinel-2 / Landsat velocity dirs from Step 2 |
| `IMGDIR` | Step 1 imagery — see below |
| `AOI_SHP` | Glacier AOI shapefile — the master list |
| `AOI_NAMES` | internal → public ID mapping |
| `WD` | working directory for outputs |
| `OUTDIRNAME` | output folder name (default `nsidic_v01.1`) |

### IMGDIR — check it before every run

**One directory per season.** `lib/config.py` keeps prior seasons commented out directly above the
live line, so the active `IMGDIR` is easy to misread — **confirm which line is uncommented before
`sbatch`, and record which one a run used.**

No index ranges are needed: the system finds all available glaciers under the configured `IMGDIR`.

*An earlier split across two directories, with glaciers present in both, applied to 2024 only and
has been retired.*

### AOI_NAMES — glacier ID mapping

`reference/glaciers_roi_names_v2_300m.gpkg`, with `internal_processing_ID` (e.g. `001_alison`) and
`ID` (e.g. `001_Alison`). Used by `4c` to produce `{public_id}_{year}_v{VERSION}.nc`. This is why
delivery filenames are capitalized while processing IDs are not — relevant when passing `--glacier`
to the test tools.

---

## Failure modes — three kinds, two unfixable

A full run produces ~184 of 192 glaciers. The shortfall is **data availability, not bugs**:

| Mode | Cause | Fixable? |
|---|---|---|
| **Step 2 hard failure** (~8 glaciers) | cross-track-only data — no repeat-track pairs, so no orbital reference frame can be built | ❌ architectural |
| **Step 4b graceful degradation** (~4 glaciers) | Landsat unavailable; Sentinel-2-only NetCDF still produced | ✅ working as designed |
| **No velocity data** | Step 2 never produced output for that glacier | ❌ upstream |

**Why orbital correction needs repeat-track pairs**: the algorithm builds an *a priori* velocity
field from the median of repeat-track fields on the same orbit. Cross-track pairs have different
viewing geometries and systematic errors, so they cannot substitute. This is a data limitation, not
a technical problem to solve.

**Graceful degradation is deliberate and validated** — a 4b failure yields S2-only output rather
than failing the glacier entirely. A Step 2 failure correctly stops the workflow, because without
the orbital reference frame nothing downstream is possible.

---

## Troubleshooting

1. **Check the error summary**: `slurm_step3/logs/errored_glaciers.log` (exists only if errors occurred)
2. **Individual logs**: `tail -50 slurm_step3/logs/{glacier}_step3.log`
3. **SLURM output**: `tail -50 slurm_step3/logs/ortho_nc_pkg_{JOBID}.out`
4. **Verify paths in `lib/config.py`** — the most common technical issue by a wide margin
5. **Verify Step 2 velocity data exists** — the second most common

**Date formats**: control script takes `YYYY-MM-DD`; Python scripts take `YYYYMMDD`.

**Known quirk**: if `--end_date` is omitted, the code incorrectly sets `start_date = END_DATE`.
**Always pass dates explicitly.**

---

## Moving code to HPC

Tracked code travels by `git pull` on HPC at `/home/yadav.111/Github/greenland-glacier-flow`.
`qaqc/` is gitignored entirely and reaches HPC **only** via `sync_to_hpc.sh` (rsync).

---

## Key domain concepts

**Orbital correction** — same-track pairs build an *a priori* median velocity field; cross-track
pairs give the median displacement offset. `THRESH_COUNT=5` minimum samples for a reliable median.
Reference: Chudley et al., *Cryosphere Discussions*, https://doi.org/10.5194/tc-2022-33

**Glacier naming** — `{number}_{name}`, e.g. `049_jakobshavn` internally, `049_Jakobshavn` publicly.

**S2C** — Step 3 needs no changes. The glob `S2*.tif` and positional parse `fname[:3]` handle
S2A/S2B/S2C generically, and no satellite whitelist exists anywhere in the chain. The S2A/S2B-only
restriction was in Step 2 (MATLAB), not here.

---

## Working with this code

**Line numbers**: read the file directly, echo back what is on that line, and edit only using that
verified content. Never assume or extrapolate a line number.

**Code principles**: preserve legacy comments, respect multi-author patterns, minimal diffs, test on
a single glacier first.

**File operations**: never `rm -rf`. List the target, confirm, then remove.

---

## Known technical debt — documented, not fixed

- `tindexiindexme` typo in `4b` (workaround in `4c` works)
- Bare `except` in `4c`
- Data overwrite by year within a glacier
- XArray FutureWarnings
- Intermediate per-velocity-field JSON metadata files written by
  `lib/correct_fields_parts.py → generate_metadata()` — exact HPC location never documented. Find
  with `find {WD} -name "*metadata*.json" -maxdepth 6 | head`

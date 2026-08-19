# AGENTS.md — Greenland Glacier Flow Processing

**AI agent guide, primarily for Step 1** (download, merge, clip). Step 3 has its own guide.

**⚠️ SUBFOLDER GUIDES TAKE PRECEDENCE** — when working inside a subfolder, follow its own `AGENTS.md` over this one.

| Subfolder guide | Present in a clone? |
|---|---|
| `1_download_merge_and_clip/tests/`, `3_orthocorrect_and_netcdf-package/` | ✅ tracked — travels with the repo |
| `qaqc/`, `qaqc/Step1/`, `qaqc/Step1/rasterio-upgrade-testing/`, `qaqc/Step3/` | ❌ local-only — `qaqc/` is gitignored, so these are **absent from a fresh clone** and reach HPC by `sync_to_hpc.sh` |
| `aws/`, `container/` | ❌ local-only — **dormant work, see *Pipeline Ownership*** |

**New to this project? Read *Cold Start* immediately below, then *Hard Constraints*.**

---

## 🧭 Cold Start

### Where things stand

- **Branches**: work on **`dev`**, keep `main` clean — Hard Constraint #6. HPC tracks `dev`. Check
  `git log --oneline -5 main dev` for current divergence rather than trusting a snapshot here.
- **Test verification, as of commit `5367def`**: Step 1 passed 8/8 tool invocations with 10 rasters
  bit-identical to 2025 production; Step 3 passed 184/184 on all three checks. Re-run the suites
  rather than assuming this still holds for later commits.

**Step 1 — nothing known-broken.** Verified against both production years: 104 rasters
bit-identical for 2024 (both satellites, both machines, single- and multi-tile) and three regions
for 2025, including the domain's only 5-tile region. Five tracked tools in
`1_download_merge_and_clip/tests/` — start at `tests/README.md`.

**Step 3 — likely sound, not proven.** The 2025 season has been reproduced from the delivered
baseline three times, most recently across all three check modes (pixel-perfect, NSIDC spec,
encoding), 184/184 each. **What that does not cover**: only 2025 has been exercised, and every check
is automated — no manual or notebook inspection. Two tracked tools in
`3_orthocorrect_and_netcdf-package/tests/`. Full status in that folder's `AGENTS.md` →
*Verification status*.

⚠️ **"Tests verified" is not "Step 3 verified."** Reproducing a known-good answer proves the
instrument works, not the science. Keep the two claims apart.

**2024 is superseded for Step 3** — 2025 is the reference 2026 must match. See the Step 3 guide.

**Environment**: which library versions ran which season, and what to do if results drift, is in
`docs/ENVIRONMENT_PROVENANCE.md`. Versions float deliberately — **do not propose pinning them.**

### Root-level files are part of Step 1 — a lesson from the last merge review

**Whether `dev` and `main` currently match is a `git diff --stat main dev` check**, not something to
assume from this file. The last merge review found no live Step 1 or Step 3 processing code had
diverged between them; the changes were at root level (`submit_job.sh`, `submit_satellite_job.py`,
`config.template.ini`, `environment.yml`) plus the purely additive test suites. Full record in the
local-only git working notes, §7.

⚠️ **Root-level does not mean peripheral** — a lesson worth keeping now that work resumes on `dev`.
`submit_job.sh` and `submit_satellite_job.py` **are** Step 1's entry points; they simply live at
root rather than inside `1_download_merge_and_clip/`. And `environment.yml` is a scientific
variable in this workflow, not packaging trivia.

### Prove the environment works before anything else

Roughly one minute, touches no data:

```bash
cd ~/Github/greenland-glacier-flow && ./submit_job.sh --satellite sentinel2 --regions 138_SermiitsiaqInTasermiut --date1 2024-08-01 --date2 2024-08-07 --dry-run true
```

The job file is written under `{base_dir}/slurm_jobs/{satellite}/` — **not** the directory you submitted from. Read it and confirm the conda activation guard line is present:

```
if ! python -c "import sys; sys.exit(0 if sys.prefix.split('/')[-1] == 'glacier_velocity' else 1)"; then echo "FATAL: ...
```

*Verified August 14, 2026 — this exact command produced `~/greenland_glacier_flow/slurm_jobs/sentinel2/sentinel2_20240801.job` with the guard intact.*

### Which doc answers what

| Question | Doc | Travels with the repo? |
|---|---|---|
| How do I run Step 1? | this file → *Running Step 1* | ✅ tracked |
| Install, `config.ini` structure, output structure, troubleshooting | `docs/QUICKSTART.md` | ✅ tracked |
| Project overview, production commands | `README.md` | ✅ tracked |
| System design | `docs/ARCHITECTURE.md` | ✅ tracked |
| Per-satellite processing detail | `docs/SENTINEL2_WORKFLOW_DOCUMENTATION.md`, `docs/LANDSAT_WORKFLOW_DOCUMENTATION.md` | ✅ tracked |
| Pulling processed data from S3 | `docs/SYNC_TOOL_GUIDE.md` | ✅ tracked |
| Project history | `CHANGELOG.md` | ✅ tracked |
| Which library versions ran which season, and what to do if results drift | `docs/ENVIRONMENT_PROVENANCE.md` | ✅ tracked |
| How do I test Step 1? | `1_download_merge_and_clip/tests/README.md` | ✅ tracked |
| What Step 1 tests establish, and what they do not cover | `docs/STEP1_TEST_PLAN.md` | ✅ tracked |
| Working *on* the Step 1 tests | `1_download_merge_and_clip/tests/AGENTS.md` | ✅ tracked |
| How do I test Step 3? | `3_orthocorrect_and_netcdf-package/tests/README.md` | ✅ tracked |
| What Step 3 tests establish, and what they do not cover | `3_orthocorrect_and_netcdf-package/tests/STEP3_TEST_PLAN.md` | ✅ tracked |
| Running Step 3, baselines, Step 3 risks | `3_orthocorrect_and_netcdf-package/AGENTS.md` | ✅ tracked |
| **In-flight work with no permanent home yet** | `inbox/README.md` (repo root) | no — gitignored, rsync to HPC |
| Git working notes | `docs/GIT_AGENTS.md` | no — gitignored |
| Pre-cleanup version of this file | `docs/bak.AGENTS.md` | no — gitignored |

### Step 1 code layout

| Path | What it is |
|---|---|
| `submit_job.sh` | entry point — bash wrapper |
| `submit_satellite_job.py` | the job generator it calls |
| `config.ini` | all settings (`config.template.ini` is the shipped example) |
| `1_download_merge_and_clip/sentinel2/` | `download_merge_clip_sentinel2.py` + `lib/` |
| `1_download_merge_and_clip/landsat/` | `download_clip_landsat.py` + `lib/`, `regions/` |
| `1_download_merge_and_clip/ancillary/glacier_roi_v2/` | region geometries |
| `1_download_merge_and_clip/legacy/` | superseded — do not run |
| `1_download_merge_and_clip/docs/` | gitignored (`.gitignore:161`) |

**⚠️ `bak.submit_satellite_job.py` at the repo root is a backup.** The live file is `submit_satellite_job.py`.

### Claude Code runs on HPC as well as WSL2

Since August 18, 2026. This is *why* the agent guides are tracked — context reaches the HPC checkout
by `git pull` rather than rsync.

**It runs in two places, chosen per task** — the user decides which, and starts it there:

| Where | Use it for |
|---|---|
| **Login node** | quick context work — reading files, `git log`, `squeue` |
| **Inside an `srun` allocation** | test runs, and anything touching real data at scale |

**This cluster has outbound network access on compute nodes**, so Claude works normally inside an
allocation. That is not true of every cluster — it is what makes the allocate-then-start pattern
available here at all.

⚠️ **Inside an allocation the session ends when the allocation does.** Size `-t` for the
conversation, not just for the job.

⚠️ **On a login node, keep commands light.** A recursive `find` or `grep` over `/fs/project` from a
login node is the quickest way to annoy the cluster's admins. From a compute node the CPU contention
goes away but **the shared filesystem load does not** — scale is still worth thinking about.

HPC use is **QA/QC, discovery, troubleshooting and understanding** — parsing logs and outputs to
spot problems. Production runs are the user's.

### Permission guardrails are active

`.claude/settings.json` is **tracked**, so one baseline covers both machines. **Read the file rather
than trusting a summary** — it is the authority, and any list repeated here would drift from it.

Its shape: a short read-only `allow`, a `deny` covering the irreversible and the shared-resource
actions, and everything else prompting. `.claude/settings.local.json` stays gitignored for
per-machine relaxations — but note a local file **cannot loosen a `deny`**.

**The settings guard themselves** — `.claude/**` is in `ask`, so widening a permission is a visible,
deliberate act rather than something an agent can do quietly en route to another task. And because
the baseline is tracked, such a change would otherwise ride along in a commit unnoticed.

**Claude does not submit jobs or delete things.** `sbatch`, `srun`, `salloc`, `scancel`, `rm` and
`ssh` are denied outright. When one is needed, **hand the user a single-line copy/paste command and
let them run it.** That is the intended division of labour, not an obstacle to route around — do
not reach for a Python or shell-variable equivalent to get the same effect.

These are a floor, not a sandbox — they match command *text*, so a deletion routed through Python, a
shell variable, or `ssh` would not trip them. **Confirm destructive actions with the user regardless.**

---

## ⚠️ Hard Constraints

1. **Legacy format is non-negotiable.** Output goes to **NSIDC** and must always match the legacy format. Pinned versions and unusual conventions are usually deliberate — **verify before "fixing" anything that looks stale.**

2. **`gdal=3.10.3` also pins `rasterio` at 1.4.4.** rasterio links against a specific `libgdal-core` minor, so the GDAL pin structurally blocks a rasterio upgrade. **This is the only thing preventing rasterio 1.5.0** — there is no separate guard. Do not relax it. Details in `environment.yml` and `qaqc/Step1/rasterio-upgrade-testing/RASTERIO_COMPATIBILITY_REPORT.md`.

   **Note**: Step 1 itself has **zero** `osgeo`/GDAL imports — all six `from osgeo import gdal` live in Step 3. The pin exists for Step 3's sake; Step 1 inherits it because the environment is shared. Do not reason "Step 1 doesn't need old GDAL, so the pin can go."

3. **Do not modify `1_download_merge_and_clip/`** without explicit instruction — core Step 1 logic.

4. **Do not modify the HPC SLURM workflow** unless explicitly instructed. It is operational.

5. **Never edit `config.ini` for testing** — use CLI overrides.

   ⚠️ **It nonetheless currently holds test values** — verified August 15, 2026: `regions = 138_SermiitsiaqInTasermiut`, `date1 = 2024-08-01`, `date2 = 2024-08-07`. A production run started from this file would quietly process one 46 km² region for one week of 2024. **Reset it before any production run**, and check it rather than assuming.

6. **Work on `dev`. Keep `main` clean.** Adopted August 17, 2026. `main` is the **release branch** — it moves only when `dev` is merged into it, deliberately. Do not commit to `main` directly. This is not a freeze: `main` is not protected or off-limits, it is simply not where work lands. `dev` is where day-to-day commits go, and feature branches still cut from `dev`.

7. **This repository is PUBLIC. Sanitize any guide before committing it.** `AGENTS.md` and `CLAUDE.md` are tracked so context travels to HPC — which means they publish to the internet. Before committing one, confirm it carries **no hostname, username, account or SSH detail**.

   Git history is permanent: removing a line later does **not** unpublish it. Check before the commit, not after. This is not hypothetical — a guide was found carrying a live `user@host` for the cluster, one commit away from being public forever.

   Paths already present in tracked code are not a new disclosure; the auth chain is. Guides under `qaqc/`, `aws/` and `container/` stay gitignored and are exempt.

---

## Pipeline Ownership

**Only Steps 1 and 3 are in this repo.**

| Step | Folder | Owner | Runs where |
|------|--------|-------|------------|
| **1** — download, merge, clip | `1_download_merge_and_clip/` | this project | HPC production; **local prototyping OK** |
| **2** — velocity generation | *not in repo* | **someone else** | HPC only |
| **3** — orthocorrect + NetCDF | `3_orthocorrect_and_netcdf-package/` | this project | **HPC ONLY** |

### 💤 `aws/` and `container/` are dormant

**Treat both as moot.** Neither is part of current work, neither is on any roadmap with a date, and
production runs entirely on HPC. They hold exploratory work — AWS Lambda / Batch execution, and a
Pixi-based container — that was taken to a partial state and parked.

- **Do not** propose changes there, cite them as precedent, or treat their contents as current.
- **Do not** count them when reasoning about how the pipeline runs. HPC is the whole story.
- Their `AGENTS.md` guides stay **gitignored**, so they will not appear in a clone.

Revisit only on an explicit request. Until then, unfinished state there is expected, not a defect
to report — `aws/AGENTS.md` records broken compute provisioning, and that is simply where it stopped.

- **Step 3 never runs locally.** Step 1's local option does not generalize.
- **Step 2 is not ours** — report problems there, do not fix them.
- **Step 3 context rule**: use only information from inside `3_orthocorrect_and_netcdf-package/`. Root-level configs and examples are Step 1 focused.
- **`qaqc/`** — local-only prototyping and QC area, gitignored, reaching HPC by `sync_to_hpc.sh` only. It mixes working scripts with prototypes and superseded copies, so **verify a script is current before relying on it**. ⛔ The Step 1 and Step 3 test tools have **graduated out** into `1_download_merge_and_clip/tests/` and `3_orthocorrect_and_netcdf-package/tests/` — those copies are authoritative; **do not fall back to the `qaqc/` prototypes.** Everything else about `qaqc/` lives in **`qaqc/AGENTS.md`**, deliberately, not here.

---

## Running Step 1

**Two files do everything, and the same two work on both WSL2 and HPC.** `detect_execution_mode()` submits a SLURM job if `sbatch` exists, otherwise runs directly.

- **`submit_job.sh`** — bash wrapper, handles conda activation
- **`submit_satellite_job.py`** — the Python it calls

```bash
cd ~/Github/greenland-glacier-flow
./submit_job.sh                            # sentinel2, defaults from config.ini
./submit_job.sh --satellite landsat
```

Settings live in `config.ini`. **Priority: CLI args > config.ini > script defaults.**

### Production

```bash
# Sentinel-2: 192 regions in 3 batches (AWS free tier limits concurrent downloads)
./submit_job.sh --satellite sentinel2 --start_end_index 0:65
./submit_job.sh --satellite sentinel2 --start_end_index 65:130
./submit_job.sh --satellite sentinel2 --start_end_index 130:195

# Landsat: single batch
./submit_job.sh --satellite landsat --start_end_index 0:192 --runtime 125:00:00
```

### Common overrides

```bash
--regions 134_Arsuk,191_Hagen_Brae   # mutually exclusive with --start_end_index
--date1 2024-08-01 --date2 2024-08-07
--dry-run true                       # write the job file without submitting
--memory 64G --runtime 12:00:00
--env glacier_velocity1              # override conda environment
```

### ⚠️ Sentinel-2 and Landsat are separate workflows

They were written by **different people** and are **not symmetric**. `submit_job.sh` / `submit_satellite_job.py` give them a unified entry point, but the underlying scripts differ. Known differences:

| | Sentinel-2 | Landsat |
|---|---|---|
| Split download / post-processing | `--download_flag`, `--post_processing_flag` | **not available** — one pass |
| Coverage control | — | `--intersect_thresh` |
| Output layout | `{region}/clipped/`, `template/`, `download/`, `metadata/` | `{region}/` directly, plus `_reference/` |

Neither flag pair is exposed on `submit_satellite_job.py` — they are `config.ini`-only there.

**Reconciling the two is an ongoing goal, not a finished state.** Do not assume a difference between them is a bug, and do not "unify" them unasked. The differing output layouts are why any tool that assumes a fixed path depth mislabels the satellite for Landsat.

**⚠️ `--start_end_index` uses underscores.** The hyphenated form does not work. This is deliberate — it matches the `config.ini` key. All other multi-word flags stay hyphenated (`--base-dir`, `--dry-run`, `--execution-mode`). Do not "fix" it.

### Known quirks — observed, harmless, do not "fix" unasked

- **SLURM output `OUT/%x_%j.out` is relative to the slurm job directory under `base_dir`** from `config.ini` — *not* the directory you submitted from. A common source of "where did my log go?".
- **`--base-dir` does not redirect a local-mode run.** `submit_satellite_job.py` applies the CLI flag, then overrides `root_dir` with `config.ini`'s `local_base_dir` when `execution_mode == 'local'`, inverting the documented *CLI > config* precedence. Possibly deliberate, to stop local runs writing to HPC paths. `1_download_merge_and_clip/tests/check_job_generation.py` works around it with a temporary `--config`.
- **`cp -r {script_dir}/1_download_merge_and_clip .`** in generated job scripts copies the directory into itself if run from the repo root — `cp` warns and exits 1, and the script continues because there is no `set -e`. Harmless in practice: the wrapper runs from the output tree.
- **`.job` files are not gitignored**, and `*.log` is commented out at `.gitignore:59`. Not a problem today — job files are written to the output tree, not the repo.

---

## Environment

One conda env: **`glacier_velocity`** (Python 3.13, older rasterio/GDAL — production ready). Verified-good set as of August 17, 2026, identical on WSL2 and HPC: Python 3.13.15, rasterio 1.4.4, rioxarray 0.23.0, xarray 2026.7.0, geopandas 1.1.4, numpy 2.5.2, GDAL 3.10.3. **`glacier_velocity1`** is the convention for a newer-library test env; it does not currently exist.

⚠️ **Rebuilding from `environment.yml` does NOT reproduce exactly this** — corrected August 17, 2026, having previously claimed it did. Only `python=3.13` and `gdal=3.10.3` are pinned; rioxarray, xarray, geopandas and numpy float, so a rebuild resolves to whatever is current that day. This is not theoretical: the 2025 season ran on rioxarray 0.20.0 / xarray 2025.12.0 / geopandas 1.1.1, and the list above is what a later rebuild produced. **Both sets, and a drift procedure, are in `docs/ENVIRONMENT_PROVENANCE.md`.** The floating versions are deliberate — do not propose pinning them.

**Directory separation**: a non-default `--env` automatically suffixes output directories with the env name, so test runs cannot contaminate production data.

### ⚠️ Conda and mamba activation syntax differ

```bash
eval "$(conda shell.bash hook)"           # conda only
eval "$(mamba shell hook --shell bash)"   # mamba only
```

Substituting one for the other yields a silently broken hook. **This project uses conda** — `submit_job.sh` and both job generators in `submit_satellite_job.py` use the conda form; do not change them. `mamba run -n glacier_velocity <cmd>` is convenient for one-off commands and keeps working if the `conda` CLI itself breaks.

### ⚠️ Activation can fail silently

Job scripts have no `set -e`, and a broken conda hook still exits 0 — so a failed activation falls through to the ambient PATH and the job *appears* to succeed on the wrong interpreter. Both job generators now emit a guard that aborts with a diagnostic. **When a result looks odd, check the job's own `python --version; which python` output before anything else.**

---

## Moving Files Between WSL2 and HPC

| Payload | Mechanism |
|---------|-----------|
| Tracked code | `git pull` on HPC (`/home/yadav.111/Github/greenland-glacier-flow/`) |
| `qaqc/` folder | `sync_to_hpc.sh` (rsync) — nothing in `qaqc/` is tracked, so this is the only route |
| Processed data | `sync_from_s3.sh` — see `docs/SYNC_TOOL_GUIDE.md` |

**HPC tracks `dev`** — decided August 17, 2026, and the HPC checkout has been switched and pulled.

```bash
git pull origin dev
```

Rationale: essentially all HPC activity is *testing*, and under the *work on `dev`* model `main`
moves only at merge points — so pulling `main` would leave HPC running code older than what is being
tested. Verify with `git branch --show-current` on HPC rather than assuming.

**`docs/QUICKSTART.md` still says `git pull origin main`, and that is correct — do not "fix" it.**
It documents a fresh setup, where the release branch is the right thing to install. Tracking `dev`
is a deliberate choice for *this* working checkout, not general guidance.

**⚠️ `sync_to_hpc.sh` syncs only `qaqc/`, not the repo** — the name oversells it. It has no `--delete`, so files removed locally persist on HPC. Do not rename or generalise it unasked.

---

## Testing

### Rotate test parameters

Do not reuse identical parameters consecutively — rotate regions, dates, or years. **Exception**: a regression test against a baseline deliberately reuses them.

- **Dates**: ~5 days; rotate years 2023–2026. Prefer **March–November**; avoid **December–February** (polar night — data may genuinely not exist).
- **Regions**: mix *geometries*. `1_download_merge_and_clip/ancillary/glacier_roi_v2/glaciers_roi_proj_v3_300m.gpkg` has a `tile_count` column — pick from it rather than guessing.
  - Single-tile: `138_SermiitsiaqInTasermiut` (tiny, 46 km²), `049_jakobshavn` (2,645 km²), `140_CentralLindenow`, `104_sorgenfri`
  - Multi-tile: `191_Hagen_Brae` (4 tiles), `090_petermann` (**5 tiles**, the only one in the domain), `134_Arsuk`, `139_SouthLindenow`
  - Already exercised: `138_SermiitsiaqInTasermiut`, `191_Hagen_Brae` (2024); `049_jakobshavn`, `090_petermann`, `140_CentralLindenow` (2025). Rotate to others next — `104_sorgenfri`, `134_Arsuk`, `139_SouthLindenow` remain untouched.
  - Date windows used so far in 2025: 2025-07-10 → 07-15, and 2025-08-17's run of 2025-05-06 → 05-12. **Pick dates from the baseline listing, not from guesswork** — `ls {baseline}/1_download_merge_and_clip/sentinel2/{region}/clipped/` shows exactly what production holds, so a window can be chosen that is guaranteed to have scenes to compare against.
- **`--dry-run true`** to inspect the generated job first.

**A Step 1 *run* exiting 0 proves nothing** — job scripts have no `set -e`, so a run can die halfway and still exit 0. Validate the output, not the run's exit code.

**The *tests* are the opposite**: their exit codes are the contract, deliberately. `0`/`1`/`2` are meaningful and must be checked — see the suite below.

### Local vs HPC

**Local holds only a small data sample** — a local run proves the code executes, not that it is correct. **HPC holds both 2024 and 2025 data**, the full domain; scale-up testing belongs there.

**Prefer 2025 for regression tests.** 2025 data survives until 2026 data is delivered, so it has the longer lifetime and is the better default baseline. 2024 is the shorter-lived of the two — still usable, but do not build on it as the standing reference.

### The Step 1 test suite

**Five tools in `1_download_merge_and_clip/tests/`** — git-tracked, so they reach HPC via `git pull`, no rsync. Full usage in `tests/README.md`.

| Tool | Answers |
|---|---|
| `compare_raster.py` | does output match the production baseline? |
| `check_environment.py` | is the conda environment the pinned one? |
| `check_job_generation.py` | does job generation still produce valid jobs? |
| `check_output_structure.py` | did the run write everything it should? |
| `check_raster_sanity.py` | is output well-formed, **with no baseline needed**? |

`check_raster_sanity.py` is the only one that works on data with no baseline — which is what the 2026 season will be.

**Shared exit codes**: `0` passed · `1` **failed** · `2` **could not check** (baseline missing, nothing found) — *not* a pass.

On HPC, allocate resources first — never run comparisons on a login node:

```bash
srun --cpus-per-task=1 --mem=16gb -t 01:00:00 -p howat,batch --pty bash -i
```

```bash
cd ~/Github/greenland-glacier-flow
```

```bash
mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/compare_raster.py sentinel2 --region <region> --run-mode hpc; echo "EXIT=$?"
```

**Baselines** — `--year` selects the tree; `--baseline`/`--candidate` override roots entirely:

| `--year` | Tree |
|---|---|
| `2025` | `/fs/project/howat.4-3/greenland_glacier_flow` — **default**, longer lifetime |
| `2024` | `/fs/project/howat.4/greenland_glacier_flow` — may be cleared |

Local has no year — one saved snapshot at `/home/bny/greenland_glacier_flow_prod` (**do not delete**).

**⚠️ `--year` must match the dates the candidate was produced with.** 2024-dated output against the 2025 tree reports differences that are not regressions. The resolved baseline prints at the top of every run — check that line.

**⚠️ Use the `tests/` copy, never the superseded `qaqc/` prototype** — in all-regions mode the prototype reports a real mismatch as "Skipped" and exits 0, and it crashes on a missing baseline. Both are fixed here. See `qaqc/AGENTS.md` if you need the detail.

**Current state**: Step 1 verified against **both** production years.

- **2024** — 104 rasters bit-identical across both satellites, both machines, single- and multi-tile (`138_SermiitsiaqInTasermiut`, `191_Hagen_Brae`).
- **2025** — verified August 15, 2026 on `049_jakobshavn` (single-tile, 2,645 km²) and `090_petermann` (**5 tiles**, 11,457 km², the only 5-tile region in the domain), dates 2025-07-10 → 2025-07-15. Regression **and** sanity checks, both satellites: **8/8 exit 0**. This was the first real exercise of `--year 2025` and confirmed the 2025 baseline path.

### 📌 Post-merge check, August 17, 2026 — Step 1 still reproduces production

Run **after** `dev` merged into `main` (`4730f05`), to confirm the root-level changes to Step 1's entry points did not alter output. `140_CentralLindenow`, Sentinel-2, 2025-05-06 → 2025-05-12, both region and date window previously unexercised.

**Both satellites, 8 tool invocations, every one exit 0. 10 rasters bit-identical to production.**

| Tool | Sentinel-2 | Landsat |
|---|---|---|
| `check_environment.py` | exit 0 — all 7 packages match their pins (shared) | — |
| `check_job_generation.py` | exit 0 — 4/4, both satellites × both execution modes (shared) | — |
| `check_output_structure.py` | exit 0 — 15 `.tif` across the region tree | exit 0 — 3 `.tif`, `_reference/` found at satellite level |
| `check_raster_sanity.py` | exit 0 — 7/7 sane | exit 0 — 3/3 sane |
| `compare_raster.py` | exit 0 — **7/7 bit-identical** | exit 0 — **3/3 bit-identical** |

Scene mix was **3 S2A / 2 S2B / 2 S2C** and **2 LC09 / 1 LC08** — every satellite in both constellations matched.

**Three things this settled that had been assumed:**

1. **`date2` is inclusive** — both `20250512` Sentinel-2 scenes were produced. Previously unverified; the STAC interval `datetime=f'{start}/{end}'` had made it ambiguous.
2. **A test run cannot overwrite production.** Candidate writes to `/fs/project/howat.4/yadav.111/...`, baseline is `howat.4-3` — separate trees by construction. ⚠️ But `config.ini:74` holds the baseline tree as a commented-out `base_dir`; leave it commented.
3. **`check_raster_sanity.py` is satellite-aware, and `compare_raster.py`'s Landsat path handling is correct.** Sanity expects 15 m for Landsat vs 10 m for Sentinel-2, and `compare_raster.py` labelled the satellite correctly against the shallower Landsat layout — the first Landsat exercise of the path-depth fix.

**Method worth reusing**: dates were chosen by listing the baseline first (`ls {baseline}/.../{region}/`) rather than guessing, so scenes were guaranteed to exist on both sides. That is why nothing returned exit 2.

**Does not cover**: batch mode, `cores > 1`, any region beyond this one, or any window beyond these 6 days. And see `inbox/numpy-2.5-rasterio.md` — both satellites surfaced the same NumPy 2.5 deprecation inside rasterio 1.4.4, harmless today.

**All five test tools are verified on HPC** (August 15, 2026, exit codes captured). `check_environment.py` confirmed both machines carry identical versions; `check_job_generation.py` passed 4/4 including the local-mode builder HPC would never otherwise use; `check_output_structure.py` passed 4/4 in all-regions mode.

**All-regions mode verified on HPC** (August 15, 2026) — the last unexercised mode, and the one the original defect lived in. 22 rasters matched, 0 mismatched, 2 regions correctly reported as *baseline unavailable* (2024-dated output against the 2025 tree) with **exit 2**.

**S2C scenes verified** — 10 of those 22 rasters are S2C, bit-identical to 2025 production. Mix was 10 S2C / 8 S2B / 4 S2A, consistent with S2C replacing S2A as primary from January 2025.

**Untested**: batch mode (`--start_end_index`), `cores > 1` (production uses `cores = 1`, so serial *is* the production path).

---

## Working With This Project

### Response vs. action
1. **Questions first** — explain, do not immediately execute.
2. **Confirm before significant changes.**
3. **Do only what is asked.** No adjacent improvements. Park extra findings in `inbox/` at the repo root — one file per thread, any step. Read `inbox/README.md` first; everything there is expected to graduate out and be deleted.
4. **Prefer doc updates** over code changes when either would do.

### Code and commands
- **Line numbers**: use exactly as shown on screen.
- **Shell commands**: always a **single line** — no backslash continuations, they break when pasted into an HPC terminal.
- **Git**: do not suggest `add`/`commit`/`push` unprompted. **No AI attribution in commit messages.** Local-only git working notes cover the setup and its known traps — read them first if present.

### Destructive actions — confirm first
File deletion, git operations, Docker cleanup, environment changes, anything touching data or outputs. **Clarify ambiguous nouns before acting** (e.g. "container" — runtime or code?). When uncertain, stop and ask.

### Before editing, check the file is tracked
```bash
git ls-files --error-unmatch <path> 2>/dev/null   # exit 0 = tracked; 1 = gitignored
```
Many files are gitignored for prototyping. Run `git status --short` after changes.

### Branches

**`main` ← `dev` ← feature branches.** Work lands on **`dev`**; `main` is the release branch and
moves only when `dev` is merged in. **Do not commit to `main` directly** (Hard Constraint #6).

Check `git log --oneline -3 main dev` and `git branch -a` for current commits and whether any
feature branches exist, rather than trusting a snapshot here:

| Branch | Role |
|---|---|
| `dev` | **where work goes** — day-to-day commits, and the branch point for feature work |
| `main` | release branch — clean, moves only by merge from `dev` |

Cut new feature branches from `dev`.

**Both test-suite feature branches were deleted August 17, 2026**, local, remote and HPC. In each
case the content was already on `main` and the tools were byte-identical, so only the granular
commits went — 15 for `feature/step1-tests` (tip `2e2df6f`), 9 for `feature/step3-tests` (tip
`cf8db86`). **No tags were made, deliberately.** Those tips survive only in the local reflog and
expire around **mid-September 2026**. The pre-trim `STEP3_TEST_PLAN.md` that `feature/step3-tests`
carried is independently recoverable from `main`'s history at `3abf9d5`.

⚠️ **Squash merges are invisible to `git branch -d`** — it refuses, and `-D` is required. `-D` is
also in the `deny` list in `.claude/settings.json`, so an agent cannot run it at all; hand the
user the command instead. Check with `git branch -vv` — this block will go stale.

### Backups
- **`bak.` prefix** for file backups; recover by removing it. **Never use `x_` on a code file** — it has caused import errors and data corruption, because an `x_`-prefixed script still gets imported and globbed.
  - ⚠️ **This rule is about code files only.** On **data directories** an `x1_`/`x2_` prefix is the user's deliberate, working convention for superseding a run — instant, non-destructive, self-documenting, and the thing that prevents Step 3's silent-skip trap. Do not flag it as a mistake.
- **Git tags** before major work: `git tag -a backup/pre-cleanup-YYYY-MM-DD -m "..."`.
- **Verifying a copy**: `diff -r` is authoritative for content. Plain `du -sh` will show *different* sizes for identical trees (it counts allocated blocks; an aged directory carries more overhead than a fresh copy) — use `du -sh --apparent-size` to compare content.
- **Dated folder snapshots** (made with `cp -a`, verified with `diff -r`) are **transient** — never rely on one, and do not create or delete one unasked. Authoritative backups live on separate drives. Two exist as of August 15, 2026, both verified: `/home/bny/Github/greenland-glacier-flow_2026-08-14` and `/home/yadav.111/Github/greenland-glacier-flow_2026-08-14`. **Deleting them is the user's call.**

**Pandoc** converts docs for non-technical collaborators: `pandoc README.md -o README.docx`

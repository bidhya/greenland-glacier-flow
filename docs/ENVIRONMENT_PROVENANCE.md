# Environment Provenance

**Which library versions were actually in use for each processing season, what that record proves,
and what to do if results ever stop matching.**

Companion to `environment.yml`. That file **declares** the environment — what conda is asked to
install. This file **records** what was observed to be installed, and when.

> ⚠️ **This is a record for backtracking, NOT a set of pins, and NOT an argument for adding any.**
> Only `python=3.13` and `gdal=3.10.3` are pinned. rioxarray, xarray, geopandas and numpy float
> deliberately: pinning them would make an honest `conda env create` start failing months from now,
> and a check that cries wolf gets switched off. A dated snapshot costs nothing and blocks nothing.

---

## Scope — this environment does not span the whole delivery

```
Step 1 (this env)  ->  Step 2 (MATLAB, someone else, NOT this env)
                   ->  Step 3 (this env)  ->  NSIDC delivery
```

**No block below "produced the delivery" on its own.** Step 1's output is an input to Step 2 and is
never delivered; Step 2 sits in the middle and is outside this repository's control entirely.

---

## Why `gdal` is the one pin that matters

**Who actually needs GDAL** — verified August 17, 2026 by import count:

| Step | `from osgeo import gdal` |
|---|---|
| **Step 3** | **6** — across `processing_chain/` and `lib/` |
| **Step 1** | **0** — none anywhere in live Step 1 code |

Step 1 inherits the pin only because both steps share one conda environment. **Do not reason "Step 1
doesn't need old GDAL, so the pin can go"** — it is there for Step 3, and Step 1's tests check it
only because they run in the same env.

This also explains a choice in `check_environment.py` that would otherwise look arbitrary: it reads
`rasterio.__gdal_version__` rather than importing `osgeo`, to keep Step 1's zero-osgeo property
true while still checking the pin.

The mechanism — how `gdal=3.10.3` transitively holds rasterio at 1.4.4 — is documented in
`environment.yml` itself, next to the pin.

---

## The record

### A — the 2025 season

In use for the Step 1 and Step 3 processing whose **Step 3 output NSIDC accepted, April 2026**.

```
python 3.13.11 | xarray 2025.12.0 | rioxarray 0.20.0
geopandas 1.1.1 | rasterio 1.4.4  | gdal 3.10.3
```

numpy was not captured for this block.

### B — August 2026

```
python 3.13.15 | xarray 2026.7.0 | rioxarray 0.23.0
geopandas 1.1.4 | rasterio 1.4.4 | gdal 3.10.3 | numpy 2.5.2
```

Reproduced A's output under **both** steps:

| Run | Result |
|---|---|
| Step 3, Aug 15 | 184/184 pixel-perfect **and** 184/184 NSIDC spec |
| Step 3, Aug 17 | 184/184 on **all three** checks — pixel-perfect, NSIDC spec, encoding. `Skipped 0` |
| Step 1, Aug 17 | 10/10 rasters bit-identical, both satellites |

---

## ⭐ What the pair establishes

| Package | A | B | Moved? |
|---|---|---|---|
| python | 3.13.11 | 3.13.15 | patch |
| **xarray** | **2025.12.0** | **2026.7.0** | **minor** |
| **rioxarray** | **0.20.0** | **0.23.0** | **3 minors** |
| geopandas | 1.1.1 | 1.1.4 | patch |
| rasterio | 1.4.4 | 1.4.4 | **no** |
| GDAL | 3.10.3 | 3.10.3 | **no** |

An xarray **minor** bump plus a 3-minor rioxarray bump changed **neither Step 1 rasters nor Step 3
NetCDFs** — *with rasterio and GDAL held fixed by the pin*. Step 3's processing code has been frozen
since April 19, 2026, so on that side the environment was the only variable.

That matters because the 2025 NSIDC rejection was caused by exactly this class of event: a library
silently altering how a variable was written. This time it did not.

### Three limits, all real

1. **Does not generalise to rasterio or GDAL.** Everything above was demonstrated with those two
   fixed. A jump carrying either is unproven and needs re-testing the same way.
2. **Says nothing about Step 2.** A→B is silent on whether Step 2's velocity output changed; the
   2025 comparison assumes it did not. See `3_orthocorrect_and_netcdf-package/AGENTS.md` →
   *the 2025 fixture has an expiry nobody controls*.
3. **Not "the environment doesn't matter."** It says these four moves were safe, once.

---

## 🔧 If results drift — do this before suspecting the code

1. **Run the environment check.**
   ```bash
   mamba run -n glacier_velocity python 1_download_merge_and_clip/tests/check_environment.py; echo "EXIT=$?"
   ```
   It names the package that moved and whether it was **PINNED** (hard fail, exit 1) or **ADVISORY**
   (warn, exit 0).

2. **PINNED moved** — python / GDAL / rasterio → **stop.** Nothing here covers that case; those were
   fixed in both blocks. Restore the pin before investigating anything else.

3. **Only ADVISORY moved** — rioxarray / xarray / geopandas / numpy → the A→B record shows this
   class of move was safe once. That is **evidence, not a guarantee**: re-run the regression to
   confirm, then append a new block to this file.

4. **Then, and only then, suspect the code.** For Step 3 especially, the environment is nearly
   always the cheaper hypothesis — its processing code has not changed since April 19, 2026.

> ⚠️ `check_environment.py`'s `ADVISORY` set tracks **block B**, not block A. Rebuilding to match the
> 2025 season would emit advisory warnings and still exit 0. That is correct behaviour, not a
> failure. `ADVISORY` and block B describe the same environment and are currently identical — if one
> is updated after a future rebuild, update the other in the same change.

---

## Where the numbers come from

The Step 3 SLURM job prints its own version block on every run. **It omits numpy** — the one library
both unpinned and currently emitting a deprecation warning through rasterio 1.4.4.
Use `check_environment.py` for the complete set.

---

## Maintaining this file

Append one block per season. Record what was **observed**, not what was declared, and note which
runs it was verified against. Do not delete old blocks — block A is only useful because it is old.

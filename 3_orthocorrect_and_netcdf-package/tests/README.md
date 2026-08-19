# Step 3 Tests

Git-tracked tests for Step 3 (orthocorrection + NetCDF packaging). These travel with the code they test, so they reach HPC by `git pull` — no rsync.

**Step 3 runs on HPC only, and so do these tests.** No Step 3 NetCDF data exists on the local machine and none will: Step 3 consumes Step 2 velocity output, which lives only on HPC.

---

## Start here — two tools, and you must run both

| Tool | Question it answers | Needs a baseline? |
|---|---|---|
| `compare_netcdf.py` | does this run match the delivered baseline? | **yes** |
| `validate_netcdf.py` | does this run meet the NSIDC spec? | **no** |

They are complements, not alternatives, and **neither one is sufficient**.

### Why both — this is not a precaution, it already happened

In 2025 a library update silently changed how a variable was written to disk. `compare_netcdf.py --mode pixel-perfect` **passed**. NSIDC flagged the delivery.

The cause is that `xr.testing.assert_identical()` — the heart of the pixel-perfect check — deliberately ignores `.encoding`. Two files can hold byte-for-byte identical *values* while differing in on-disk dtype, `_FillValue`, or compression. `validate_netcdf.py` was written in response: it reads encoding directly and compares it to a fixed NSIDC spec.

This is reproducible with the current tools. Two files, identical values, differing only in datetime encoding (`float64` where the spec says `int64` — the actual April 2026 bug):

| Tool | Verdict | Exit |
|---|---|---|
| `compare_netcdf.py --mode pixel-perfect` | `Compared 1 \| Failed 0` — **PASS** | **0** |
| `validate_netcdf.py` | `PASS: 0 \| FAIL: 1` | **1** |

**Pixel-perfect passes a file NSIDC would reject.** Run both, every time.

The gap runs the other way too. `validate_netcdf.py` is a **whitelist** checker: every check walks the spec, never the file. It sees anything *missing* and nothing *added*. A library that injects a new attribute or variable passes it silently — and `compare_netcdf.py` compares variable sets, so that is the half it covers.

### The standard is "identical to 2025", not "better"

The `2025_` delivery went to NSIDC in April 2026 and will not change. **NSIDC complains when a delivery does not match the legacy format — an improvement is a defect.** These tools exist to prove a code or environment change did *not* alter delivered data.

### Exit codes — the same contract as the Step 1 suite

| Code | Meaning |
|---|---|
| `0` | passed |
| `1` | **failed** — something is wrong, investigate |
| `2` | **could not check** — nothing found, baseline missing. **Not a pass.** |

`2` exists because "I couldn't check" and "I checked and it was fine" are different answers, and conflating them is how a broken test quietly reports success.

**Check the exit code, not just the output.** Every command below ends in `; echo "EXIT=$?"` on purpose.

---

## Running them

**1. Allocate resources first. Never run these on a login node.**

```bash
srun --cpus-per-task=2 --mem=32gb -t 03:00:00 -p howat,batch --pty bash -i
```

Both tools are serial loops, so **one tool gains nothing from extra CPUs** — raise memory and wall time instead. The 2 CPUs let the two tools run at the same time without contending for a single core, which is worth it because the pixel-perfect comparison is long: a full 184-file run took 28 minutes.

⚠️ **If you background one yourself with a shell `&`, you lose the verdict.** `$?` then reports that the job *started*, not whether it passed — and the exit code is the whole contract here. Capture the PID and `wait` on it, or simply run the two tools one after the other.

**2. Change to the repository root, once.** Every command below is relative to it:

```bash
cd ~/Github/greenland-glacier-flow
```

**3. Regression check — does the run match the delivered baseline?**

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/compare_netcdf.py --mode pixel-perfect; echo "EXIT=$?"
```

**4. Compliance check — does the run meet the NSIDC spec?**

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/validate_netcdf.py; echo "EXIT=$?"
```

Both default to the same candidate root, so a normal run needs no path arguments.

---

## `compare_netcdf.py` — regression against the delivered baseline

Compares every delivery `.nc` file in a candidate run against the baseline, matching files by their `{3-digit}_{Name}` prefix so a differing year in the filename does not matter.

The **candidate drives the file list**; the baseline is the reference index.

### Modes

| `--mode` | What it compares | Use it for |
|---|---|---|
| `pixel-perfect` | exact values, coordinates, dtype, attributes (`assert_identical`) | **the regression test** |
| `encoding` | variable sets, dims, per-variable dtype and encoding, global attrs | encoding drift, including *additions* |
| `structure` (default) | spatial dims, and reports the `index` ratio | diagnostic only — see below |

> ⚠️ **`structure` is the default but is not the regression test.** It fails on a spatial-shape mismatch, but reports the `index` dimension — the number of stacked velocity fields — as a ratio **without failing on it**, because two runs can legitimately hold different numbers of fields. That is what the mode was built to measure. **Pass `--mode pixel-perfect` when you mean "did anything change".**

An unrecognised `--mode` is a usage error (exit 1), not a silent fallback to the default.

### Single glacier

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/compare_netcdf.py --glacier 014_Courtauld --mode pixel-perfect; echo "EXIT=$?"
```

### Explicit roots

Both flags take the delivery **root** — the `nsidic_v01.1_delivery/` subfolder is appended internally. These two spell out the built-in defaults, so they are what a bare run resolves to:

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/compare_netcdf.py --candidate /fs/project/howat.4-3/greenland_glacier_flow/3_orthocorrect_and_netcdf-package --mode pixel-perfect; echo "EXIT=$?"
```

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/compare_netcdf.py --baseline /fs/project/howat.4-3/greenland_glacier_flow/2025_3_orthocorrect_and_netcdf-package --candidate /fs/project/howat.4-3/greenland_glacier_flow/3_orthocorrect_and_netcdf-package --mode pixel-perfect; echo "EXIT=$?"
```

The resolved candidate and baseline print at the top of every run. **Check that line before trusting a result.**

### Outcomes

| Situation | Reported as | Exit contribution |
|---|---|---|
| Files identical | `✅` | 0 |
| Files differ | `❌` | 1 |
| File will not open | `❌ could not open` | 1 — a delivery file that will not open is a real problem |
| Glacier absent from the baseline | `⚠️ skipped` | 0, but if *everything* was skipped the run exits 2 |
| Candidate or baseline delivery empty | stops immediately | 2 |

---

## `validate_netcdf.py` — absolute NSIDC compliance

Validates files against a fixed spec: required dimensions, required variables and coordinates, per-variable encoding (`dtype`, `zlib`, `complevel`, `shuffle`, `units`, `calendar`, `_FillValue`), and 20 global attributes.

**No baseline needed** — which is what makes it usable on a season with nothing to compare against. That is what 2026 will be.

### The spec is a format contract, not a year

The constants were first read from `014_Courtauld_2024_v01.1.nc`. That filename is **provenance** — no 2024 file is opened at runtime, and clearing the 2024 tree costs nothing. The 2025 delivery passes this spec 184/184, which is itself the evidence that it describes the accepted format. Do not "re-base" it onto a 2025 file; it would change no values.

Exactly three global attributes are allowed to vary: `glacier_id` (per glacier), `data_acknowledgement` (contains the year), `creation_date` (per run). The other 17 must match exactly.

> ⚠️ `compare_netcdf.py` skips only **two** of those three. That is correct, not an oversight: compare pairs glacier X against glacier X, so `glacier_id` is already identical between them. Validate checks every file against one shared spec, so there it must be presence-only. **Do not reconcile the two lists.**

### Validating something other than the candidate

A recorded baseline:

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/validate_netcdf.py --year 2025; echo "EXIT=$?"
```

A single glacier:

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/validate_netcdf.py --glacier 014_Courtauld; echo "EXIT=$?"
```

A single file:

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/validate_netcdf.py --file /fs/project/howat.4-3/greenland_glacier_flow/2025_3_orthocorrect_and_netcdf-package/nsidic_v01.1_delivery/014_Courtauld_2025_v01.1.nc; echo "EXIT=$?"
```

> ⚠️ **`--candidate` takes the delivery ROOT**, not the `nsidic_v01.1_delivery/` subfolder. The superseded `qaqc/Step3/` version had a `--base` flag that took the subfolder. It was **renamed rather than redefined** precisely so an old saved command fails loudly instead of silently pointing one level too deep.

---

## Which directory is the baseline

`WD` in `lib/config.py` carries no year. Every run writes to `{WD}/nsidic_v01.1_delivery/`. After a run is checked and accepted, the directory is renamed **by hand** to prepend the year. Nothing inside it changes.

```
3_orthocorrect_and_netcdf-package/   →   2025_3_orthocorrect_and_netcdf-package/
```

| Directory | Meaning |
|---|---|
| `{year}_3_orthocorrect_and_netcdf-package/` | **Delivered to NSIDC. Authoritative** — this is the baseline. |
| `3_orthocorrect_and_netcdf-package/` | A test or in-progress run. The candidate. Not authoritative. |
| `x1_`, `x2_` … prefixes | Superseded runs kept temporarily before deletion. Never a baseline. |

**Only the `{year}_` delivery can be assumed to exist.** Everything else is transient and may be deleted or recreated at any time. That is why a missing baseline or candidate exits `2` rather than failing — data vanishing here is the normal case, not an anomaly.

The manual rename is deliberate and **must not be automated**: it moves delivered data out of the write path so a later run cannot overwrite it, *and* frees the unprefixed path for the next run.

> ⚠️ **The skip-if-exists trap.** `orthocorrect_netcdf-package.py` skips any glacier whose output directory already exists. A run into a still-occupied `WD` silently produces nothing **and still exits 0**. Confirm the target is empty before a rerun — do not infer it from the exit code.

Baselines are recorded in `BASELINES` in `compare_netcdf.py`, keyed by year. Adding a delivered year is one line.

---

## Why this folder exists

These tools came from `qaqc/Step3/`, a local prototyping area that still holds prototypes and superseded scripts alongside working ones. **As of August 16, 2026 nothing in `qaqc/` is tracked** — it reaches HPC only by `sync_to_hpc.sh`.

> The two originals were, for a time, tracked as explicit `.gitignore` exceptions, so "`qaqc/` is gitignored" was **not** true of them. Those exceptions were removed once these hardened copies were verified on HPC. The move's real justification was never distribution — it was the two verified defects below, the exit-code contract, and putting the tools beside the code they test.

**Anything in this folder is authoritative.** Where a script exists both here and in `qaqc/Step3/`, this copy is current and the `qaqc/` one is the older prototype.

### ⛔ Do not fall back to `qaqc/Step3/compare_netcdf.py`

It has two defects, both reproduced empirically on August 15, 2026 against fixtures containing one real mismatch:

1. **It never sets an exit code on comparison failure.** `typer.Exit(1)` fires only for *usage* errors. The script exits `0` whether `Failed` is 0 or 184.
2. **`--mode structure` counts a failure as a success.** On a spatial mismatch it prints `❌` and returns normally; the caller then increments the success count. `structure` is the **default** mode.

Side by side on identical fixtures:

```
PROTOTYPE  --mode pixel-perfect   Compared 1 | Skipped 0 | Failed 1     EXIT=0
PROTOTYPE  --mode structure       Compared 2 | Skipped 0 | Failed 0     EXIT=0

HARDENED   --mode pixel-perfect   Compared 1 | Skipped 0 | Failed 1     EXIT=1
                                  RESULT: FAIL — 1 glacier(s) differ from the baseline
```

Defect 2 is the worse of the two: the summary reports **`Failed 0`**. The mismatch prints a `❌` line and then vanishes from the totals entirely.

`qaqc/` is **not** being deleted. That decision belongs to the project owner, at a much later date.

---

## Verifying the tools themselves

A test whose failure mode has never been exercised is not trustworthy. A passing run only proves the `0` path — these prove `1` and `2`, and they take about a minute.

**Exit 2 — could not check.** Point the baseline at something that is not there. Must exit `2`, not `1` and not `0`:

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/compare_netcdf.py --baseline /fs/project/howat.4-3/does_not_exist --mode pixel-perfect; echo "EXIT=$?"
```

**Exit 1 — a real mismatch.** No two delivery trees on HPC differ any more, so a mismatch has to be **constructed**. Copy two delivery files into a scratch directory, then overwrite the first with the second's *content* while keeping the first's *filename*:

```bash
mkdir -p ~/step3_mismatch_fixture/nsidic_v01.1_delivery && cp $(ls /fs/project/howat.4-3/greenland_glacier_flow/2025_3_orthocorrect_and_netcdf-package/nsidic_v01.1_delivery/*.nc | head -2) ~/step3_mismatch_fixture/nsidic_v01.1_delivery/
```

```bash
F=~/step3_mismatch_fixture/nsidic_v01.1_delivery; cp $(ls $F/*.nc | sed -n 2p) $(ls $F/*.nc | sed -n 1p)
```

The first file now holds the wrong glacier's data under its own name. One run proves the fail path, the pass path, and that the summary counts both:

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/compare_netcdf.py --candidate ~/step3_mismatch_fixture --mode pixel-perfect; echo "EXIT=$?"
```

Expect `Compared 1 | Skipped 0 | Failed 1` and **exit 1**.

**Structure mode on the same fixture.** If the two glaciers have different spatial extents — likely, since AOIs differ in size — this must report a failure and exit `1`, where the superseded prototype counted it as a success:

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/compare_netcdf.py --candidate ~/step3_mismatch_fixture --mode structure; echo "EXIT=$?"
```

> ⚠️ **If the two glaciers happen to share x/y extents, this passes with exit `0`** — verified, not assumed. That is not a bug: `structure` only compares spatial dims, so a file holding an entirely different glacier's values passes it. It is the clearest possible demonstration of why **`structure` is diagnostic and `pixel-perfect` is the regression test**. If it passes here, pick a different pair of files, or just trust the pixel-perfect result above.

**The validator on the same fixture should still PASS** — the copied file is a valid NSIDC file, just the wrong glacier's. That is the whole point of running both tools: this one cannot see a wrong-content file, and the comparison cannot see a wrong-encoding file:

```bash
mamba run -n glacier_velocity python 3_orthocorrect_and_netcdf-package/tests/validate_netcdf.py --candidate ~/step3_mismatch_fixture; echo "EXIT=$?"
```

Delete `~/step3_mismatch_fixture` by hand when finished. It is deliberately outside `/fs/project` and outside the repo.

---

## Known limitations

- **`validate_netcdf.py` imports its path constants from `compare_netcdf.py`.** The two files must sit in the same directory. This mirrors the Step 1 suite, where `check_raster_sanity.py` imports from `compare_raster.py`.
- **`--glacier` matches differently in the two tools**, inherited from the `qaqc/` originals and not yet unified. `compare_netcdf.py` matches by **filename prefix**, so `--glacier 014` works. `validate_netcdf.py` matches the **exact** `{3-digit}_{Name}` id, so `--glacier 014` finds nothing and exits `2`. **Pass the full id — `014_Courtauld` — to both, and they agree.**
- **Glacier ids are the public, capitalised form** used in delivery filenames (`014_Courtauld`), not the lowercase internal processing name (`014_courtauld`). The mapping lives in the `AOI_NAMES` geopackage. Both tools match case-sensitively.
- **The whitelist gap**: `validate_netcdf.py` cannot detect *additions* — a new variable, coordinate, or global attribute passes silently. `compare_netcdf.py --mode encoding` covers that, but has not been re-run since April 2026.
- **`--mode encoding` is under-exercised.** Its April 2026 result (0 failures across 184 glaciers) is a record, not something re-confirmed since.
- **Baselines are duplicated** from `qaqc/data_paths.yml`, which is gitignored and therefore cannot be imported by tracked code. Adding a year means updating both. The failure mode is safe — an unknown year is rejected with a list of the known ones.
- **These tools check the delivery files.** They do not check that the run *produced* everything it should have; the `192 − 8 = 184` reconciliation is still done by hand against `errored_glaciers.log`.

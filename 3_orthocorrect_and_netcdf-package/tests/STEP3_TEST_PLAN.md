# Step 3 — Test Formalization Plan

**Status**: 🟢 **All six phases complete** — Phases 1–4 built and pushed, Phase 5 passed 7/7 on HPC (August 16, 2026), Phase 6 closed out. Four items remain open; see *Still open after Phase 6*.
**Landed on `dev` as a single squashed commit, `0d7fe55`** (August 16, 2026), which folds in nine commits from `feature/step3-tests` (branched from `dev` at `a3c2a59`).

> ⚠️ **Hashes cited in this file are from `feature/step3-tests`, not `dev`.** The squash discarded
> them, so `git show <hash>` resolves only while that branch exists — it is **kept, not deleted**,
> exactly as `feature/step1-tests` was, precisely so the granular history survives. On `dev` the
> whole of this work is `0d7fe55`; the qaqc untracking and the recovered changelog entry are folded
> into that commit's body rather than being separately findable.
**Created**: August 15, 2026
**Tracked** since August 16, 2026 — it was gitignored while it was a moving target, and promoted once all six phases closed, because it holds the only record of the Phase 1–5 verification evidence. Mirrors `docs/STEP1_TEST_PLAN.md`, which is tracked for the same reason.

**Division of labour**: `tests/README.md` says *how to run* the tools · this file is *why they are shaped that way and the proof they work* · `3_orthocorrect_and_netcdf-package/AGENTS.md` covers running Step 3 itself.

---

## Goal

Move the two Step 3 comparison tools out of `qaqc/Step3/` into
`3_orthocorrect_and_netcdf-package/tests/`, hardening them on the way, so their failure modes are
trustworthy and they sit beside the code they test.

**Not** a Step 3 QC framework. Two tools, two known defects, nothing invented.

> ⛔ **Correction, August 16, 2026 — one of the original justifications was false.**
> This plan said the move was needed "so they reach HPC by `git pull` instead of `sync_to_hpc.sh`."
> **They were already tracked and committed** — `.gitignore:189-193` explicitly un-ignores
> `qaqc/Step3/compare_netcdf.py` and `validate_netcdf.py` (commits `5e65ad8`, `254acad`), and
> `qaqc/data_paths.yml` is tracked too. They already travelled by `git pull`.
>
> **What survives, and is what actually justified the work:**
> - two **verified defects** in `compare_netcdf.py` — reproduced, then fixed
> - the exit-code contract, matching Step 1 — `0`/`1`/`2` now meaningful in both tools
> - path unification (`--candidate` takes the root in both) and a single source of constants
> - a tracked `tests/README.md`, which did not exist before
> - co-location with the code under test
>
> **What did not survive:** the "it is gitignored so a tracked test cannot depend on it" reasoning
> used for embedding constants instead of reading `data_paths.yml`.
>
> ✅ **Resolved August 16, 2026 by making the claim true.** `qaqc/` was untracked entirely
> (commit `eaab2fd` on `feature/step3-tests`, squashed into `0d7fe55` on `dev`) — all 8 exceptions removed. `data_paths.yml` is now genuinely unreachable
> from tracked code, so the embedded constants are correct *and* correctly justified. This was
> cleaner than editing the claim across four tracked files.
>
> The Step 1 docs were **checked and are accurate**: `qaqc/Step1/compare_raster.py` was never
> tracked, so "it never travelled with the repo" is true of its subject. Only the Step 3
> `tests/README.md` sentence was wrong, and it has been corrected.

---

## Standing Rules

1. **No rush.** One phase at a time, user approves between phases.
2. **Do not modify `qaqc/Step3/*.py`.** Those exact files produced the August 15 evidence.
   Editing them destroys the provenance of that result. Copy, then harden the copy.
3. **HPC-only verification.** No NetCDF data exists locally and none will. Code is written
   blind; the user runs it; we iterate on output.
4. **Exit codes are the contract** — `0` pass · `1` fail · `2` could not check. Matching Step 1.
5. **Never claim "verified."** State what was checked and what it does not cover.

---

## Locked decisions (August 15, 2026)

| Decision | Choice |
|---|---|
| What moves | `compare_netcdf.py`, `validate_netcdf.py` |
| What stays in `qaqc/` | `extract_metadata.py`, `compare_step3_metadata.py` (analysis, not tests) |
| Location | `3_orthocorrect_and_netcdf-package/tests/` |
| Path config | **Embedded constants**, mirroring `1_download_merge_and_clip/tests/compare_raster.py`. No `data_paths.yml` dependency. |
| Constants shape | Year-keyed dict (`{"2025": ...}`) so 2026 is a one-line addition |
| `--year1/--year2` yaml resolution | **Dropped entirely** — would reference a file absent from the tracked tree |
| Local fixtures | **None.** Deferred idea: a local mirror of HPC structure holding a subset of delivery + new-run files. User: *"a lot of strategy will go here."* Revisit only if the HPC loop proves too slow. |
| Scope | Just the two tools. Pre-flight and run-completeness checks are **later**, if at all. |

---

## 🔶 REVISIT — is `--mode encoding` made redundant by `validate_netcdf.py`?

**User's hypothesis (August 15, 2026)**: *"My guess is that `validate_` may make this moot. But just my guess."*

**Partly true. Verified by reading the code, not by running anything.**

### What `--mode encoding` is

Added in commit **`39b9bb4`** (April 2026), in response to the NSIDC flag, at the same time
`validate_netcdf.py` was created. Its first HPC run surfaced three false positives, since fixed:
NaN≠NaN comparison, a hardcoded units string, and the `data_acknowledgement` year mismatch.

It compares the **container** of two files rather than their values:
variable set · spatial dims · per-variable in-memory dtype · per-variable encoding (`dtype`,
`units`, `_FillValue`, `calendar`, `zlib`, `complevel`, `shuffle`) · global attrs minus
`creation_date`/`data_acknowledgement`. Everything is read from the reference file — no hardcoded
values.

### Where the hypothesis holds

For everything **inside** `_VAR_SPEC` / `_COORD_SPEC` / `_GLOBAL_ATTR_SPEC`, `validate_netcdf.py`
covers the same ground — and does it *better*, because it needs no baseline and has a correct
exit code. On that territory, `--mode encoding` is redundant.

### Where it does not — the gap

**`validate_netcdf.py` is a pure whitelist checker. Every check iterates the spec, never the file:**

| Line | Check | Consequence |
|---|---|---|
| 234 | `missing_vars = set(_VAR_SPEC) - all_vars` | catches **missing**, never **extra** |
| 239 | same for coordinates | additions invisible |
| 244 | iterates `_VAR_SPEC.items()` | only spec'd vars encoding-checked |
| 256 | iterates `_GLOBAL_ATTR_SPEC` | only spec'd attrs checked |

**Nothing detects an addition.** A new data variable, coordinate, or global attribute passes
silently. `compare_encoding()` compares variable **sets**, so it would catch exactly that.

This is not academic: the 2025 incident was a library silently changing what got written. A
library upgrade that *adds* something — netCDF4 injecting `_NCProperties`, xarray adding an
attribute — is the same class of event, and only the relative check sees it.

### Verdict

**`validate_netcdf.py` makes `--mode encoding` redundant for everything inside the spec, and
blind for everything outside it.** Not moot — narrower than it looks, but covering a real gap.

### How to settle it empirically

Two things would resolve this properly, neither done:

1. **Run `--mode encoding`** — never exercised in the August 15 session. AGENTS.md records it
   passing 0 failures across 184 glaciers in April; that is a record, not something confirmed.
   (The `2025_` vs `x1_2025_` pair originally proposed here is **no longer available** —
   `x1_2025_` was deleted August 15, 2026.)
2. **Or close the gap in the validator instead** — add an "unexpected additions" check to
   `validate_netcdf.py` (diff `all_vars` / `ds.attrs` against the spec in the other direction).
   That would genuinely make `--mode encoding` moot, and is a small change. **Out of scope for
   this round** — it is inventing, not hardening.

**🛑 User direction, August 15, 2026**: *"Let's not `--mode encoding` get us outside the track.
Once things are settled we can always verify that part."* Between `pixel-perfect` and
`validate_netcdf.py` the user judges most regressions caught. **Do not pursue this during the
move.**

---

## ⭐ Only `2025_` can be assumed to exist — a design constraint

User, August 15, 2026: *"We can only assume `2025_` delivery lives. Other data can be deleted, recreated, etc. But that's what we want to test with these tests."*

- `2025_3_orthocorrect_and_netcdf-package/` is the **one durable artifact**. Read-only, permanent.
- **Everything else is transient** — test `WD`s, candidate runs, `x1_`/`x2_` renames, the 2024 tree.
  `x1_2025_` was deleted on August 15, hours after this plan cited it as a fixture.
- **No test may depend on any directory other than `2025_` existing.** A test needing a mismatch
  must **construct** it, never assume one is lying around. This is why the constructed-mismatch
  recipe replaced the `x1_` pair.
- **A missing baseline or candidate must exit `2`** (could not check), never `0`. Data vanishing is
  the normal case here, not an anomaly — precisely what the exit-code contract exists for.

---

## The acceptance criterion this suite serves

The `2025_` delivery is the baseline. It went to NSIDC and will not change. **NSIDC complains
when a delivery does not match the legacy format — "better" is a defect.** 2024 is superseded.

**Both tools must always be run.** In 2025 a library update silently changed a fill value,
`--mode pixel-perfect` passed, and NSIDC flagged the delivery. `xr.testing.assert_identical()`
**excludes `.encoding`** — demonstrated locally August 15: two files differing in on-disk dtype,
`_FillValue`, and `complevel` compare as *identical*. Library upgrades, not code edits, are the
live threat.

---

## Known-good reference results — the move must reproduce these

Full-domain 2025 rerun, August 15, 2026, against the April 19 NSIDC delivery:

| Check | Result | Job |
|---|---|---|
| `compare_netcdf.py --mode pixel-perfect` | `Compared 184 \| Skipped 0 \| Failed 0` | `10887196` (28 min) |
| `validate_netcdf.py` | `PASS: 184 \| FAIL: 0` | `10887199` |

Baseline: `/fs/project/howat.4-3/greenland_glacier_flow/2025_3_orthocorrect_and_netcdf-package`
Candidate: `/fs/project/howat.4/yadav.111/greenland_glacier_flow/3_orthocorrect_and_netcdf-package`

**The answer is already known, which is the point.** Any deviation after the move means the move
broke something.

Resources that worked: `--mem-per-cpu=32G --time=04:00:00`, 1 cpu (the compare loop is serial).

---

## Defects to fix — verified, not assumed

### `compare_netcdf.py` #1 — no exit code on comparison failure
`main()` prints its summary and returns. `typer.Exit(1)` fires only for *usage* errors (missing
args at lines 218/224, glacier not found at 251). The script exits **0** whether `Failed` is 0 or 184.

### `compare_netcdf.py` #2 — `--mode structure` counts a failure as a success
On spatial-shape mismatch, `compare_structure()` prints `❌` then **returns normally**; `main()`
then does `success += 1`. It also reports the `index` dimension as a ratio without ever failing on
it. **`structure` is the DEFAULT mode.**

### Not a defect — leave alone
`validate_netcdf.py` already raises `typer.Exit(1)` when any file fails. Only needs constants.

---

## How to prove the fixes work, with no local data

⚠️ **`x1_2025_3_...` was DELETED August 15, 2026.** The two remaining 2025 directories (the April
delivery and today's rerun) are *identical*, so **no pair on HPC produces a natural mismatch any
more.** A mismatch must be **constructed**.

**Constructed-mismatch recipe** — no historical data needed, ~200 MB, fully disposable:

1. `mkdir -p $SCRATCH/fake/nsidic_v01.1_delivery`
2. Copy two small delivery files in, e.g. `003_Avannarleq_2025_v01.1.nc` and `004_Balogni_2025_v01.1.nc`
3. Overwrite the first with the second's content, keeping the first's **filename**:
   `cp 004_Balogni_2025_v01.1.nc 003_Avannarleq_2025_v01.1.nc`
4. Compare `$SCRATCH/fake` against the real `2025_` delivery

Result: `003` mismatches, `004` matches. **One run proves the fail path, the pass path, and that
the summary counts both correctly.**

| Path to prove | How | Status |
|---|---|---|
| **exit 1** (real mismatch) | The constructed pair above. Must exit **1** and report `Compared 1 \| Failed 1`. | ✅ proven locally on synthetic files; HPC pending |
| **exit 2** (could not check) | Point `--baseline` at a nonexistent path. Must exit **2** — not 1, not 0. | ✅ proven locally; HPC pending |
| **exit 0** (clean pass) | Rerun the August 15 full comparison. Must reproduce `184 \| 0 \| 0`. | ⬜ **HPC only — cannot be faked** |
| **structure mode** | Same constructed pair. Must report failure instead of counting it as success. | ✅ proven locally, **with a caveat** — see below |

> ⚠️ **`structure` mode passes a wrong-content file when the two glaciers share x/y extents.**
> Verified by running it, not assumed. It compares spatial dims only, so a file holding an
> entirely different glacier's values passes. **Not a defect** — it is why `structure` is
> diagnostic and `pixel-perfect` is the regression test. It does mean the constructed-mismatch
> recipe cannot *guarantee* a structure-mode failure on HPC; if the chosen pair happens to share
> extents, exit 0 there is the correct result.

**The local proof is real but partial.** Phases 2–4 exercised every exit path against synthetic
NetCDFs built in the scratchpad — including a file constructed to satisfy the entire NSIDC spec,
and a mutation of it reproducing the April 2026 datetime bug. What that cannot do is prove
behaviour across 184 real files. **Phase 5 remains the gate.**

---

## Phases

### Phase 1 — Scaffolding and shared constants ✅ DONE August 15, 2026
- [x] Create `3_orthocorrect_and_netcdf-package/tests/`
- [x] Define the path constants (year-keyed baseline dict, candidate root, delivery subfolder name)
- [x] Decide where they live: **in `compare_netcdf.py`**, with `validate_netcdf.py` importing them
      in Phase 3 (Step 1 precedent — `check_raster_sanity.py` imports from `compare_raster.py`).
      Both qaqc originals carried their own near-identical `_resolve_base()`; that duplication was
      part of what the move exists to remove.
- [x] Path asymmetry **unified on the delivery ROOT**. `compare_netcdf.py` appends
      `DELIVERY_SUBDIR` internally, as the qaqc original did. In Phase 3 `validate_netcdf.py`'s
      `--base` changes from *delivery directory* to *delivery root* to match. The year-keyed
      constants hold roots, and the root is what the `2025_...` directory name refers to.

**What Phase 1 actually shipped**, since the constants cannot exist in a vacuum: the file
`tests/compare_netcdf.py` was created as a copy of the qaqc original **with only the path/CLI
layer replaced**. This pulled Phase 2's yaml-swap bullet forward. Everything else — the exit-code
defects and the comparison logic — is untouched, so Phase 2's diff stays about behaviour alone.

Changes in the copy, all verified by diffing the logic block against the original:
- `import yaml` and `_resolve_base()` → `BASELINES` / `DEFAULT_YEAR` / `CANDIDATE_DEFAULT` /
  `DELIVERY_SUBDIR` and `_resolve_baseline()`
- `--year1/--year2/--base1/--base2` → `--year` / `--baseline` / `--candidate`, matching
  `1_download_merge_and_clip/tests/compare_raster.py`
- `--reverse` **dropped** — with named roles you swap the two flags instead; it also decided which
  side drove the loop, which is now fixed: **the candidate drives, the baseline is the reference
  index** (preserving the original `path1=new, path2=ref` orientation of `compare_encoding`)
- `import time` removed (unused in the original too)
- Print strings only: `new`/`ref`/`base1`/`base2` → `candidate`/`baseline`, and "2024 reference" →
  "baseline" (2024 is superseded for Step 3)
- Module docstring rewritten: HPC-only, `srun` line, and the "run `validate_netcdf.py` too" warning

**Verified**: `--help` runs clean under `glacier_velocity` (exit 0); the file is git-trackable
(`git check-ignore` → 1); a diff of the comparison-logic block against the qaqc original shows
**print strings only** — no behavioural change.

Two inherited lint warnings left in place deliberately (`except Exception as e` unused at the
loop's tail, `'='*70` spacing). The first sits in the code Phase 2 rewrites.

### Phase 2 — Harden `compare_netcdf.py` ✅ DONE August 15, 2026
- [x] Copy from `qaqc/Step3/` — original untouched *(done in Phase 1)*
- [x] Fix defect #1: exit `1` on any failure, `2` when nothing could be checked
- [x] Fix defect #2: `structure` mode must fail on mismatch
- [x] Replace yaml year-key resolution with embedded constants; keep `--baseline`/`--candidate`
      *(done in Phase 1)*
- [x] **No change to comparison logic** — `assert_identical`, `compare_encoding`, the
      `creation_date`/`data_acknowledgement` exclusions all stay exactly as they are

**How it was done.** All three comparators now return `bool` (`compare_encoding` already did).
`main()`'s loop lost its blanket `try/except`, so a comparison result can no longer be discarded,
and gained a verdict block: `failed > 0` → exit 1 · `success == 0` → exit 2 · otherwise exit 0,
each preceded by a `RESULT:` line. Guards were added for an empty candidate delivery, an empty
baseline delivery, an absent `--glacier`, and an unknown `--year` — all exit 2 except the year,
which is a usage error (exit 1).

**One addition beyond the plan, flagged for approval**: `--mode` is now validated against
`MODES`. Previously any typo (`--mode pixel_perfect`) fell through the `else` branch, silently ran
`structure`, and reported a pass. Running the wrong check and reporting success is the exact
failure class this suite exists to catch, so it seemed wrong to leave. Reverting it is one `if`.

**Deliberately NOT changed**: `structure` mode still reports the `index` dimension as a ratio
without failing on it. Two runs can legitimately hold different numbers of velocity fields — that
is what the mode was built to measure. Now documented in its docstring, along with the fact that
**pixel-perfect is the regression mode and structure is diagnostic**.

Also unchanged: a file that fails to open counts as **failed**, not *could not check*. A delivery
file that will not open is a real problem, so the conservative direction is to fail loudly.

#### Evidence — 11 paths exercised locally, August 15, 2026

Real NetCDF data is HPC-only, but the **exit-code plumbing is not**. Two synthetic delivery trees
(`003_Avannarleq`, `004_Balogni`; `003` identical on both sides, `004` differing in both values
and `x` size) exercised every branch. Fixture builder lived in the session scratchpad — recreate
with `xr.Dataset` over `(index, y, x)`, write to `{root}/nsidic_v01.1_delivery/{gid}_2025_v01.1.nc`.

| # | Case | Expected | Got |
|---|---|---|---|
| A | unknown `--mode` | 1 | ✅ 1 |
| B | candidate dir absent | 2 | ✅ 2 |
| C | baseline dir absent | 2 | ✅ 2 |
| D | unknown `--year` | 1 | ✅ 1 |
| E | pixel-perfect, baseline vs itself | 0 | ✅ 0, `Compared 2 \| Failed 0` |
| F | pixel-perfect, real mismatch | 1 | ✅ 1, `Compared 1 \| Failed 1` |
| G | **structure, spatial mismatch** | 1 | ✅ 1, `Failed 1` |
| H | structure, all match | 0 | ✅ 0 |
| I | `--glacier` not present | 2 | ✅ 2 |
| J | every glacier skipped | 2 | ✅ 2, `Compared 0 \| Skipped 1` |
| K | `--glacier`, real mismatch | 1 | ✅ 1 |

**Both defects reproduced in the untouched `qaqc/Step3/` original on the same fixtures**, so the
fixes address something demonstrated, not assumed:

| Original, same fixtures | Output | Exit |
|---|---|---|
| `--mode pixel-perfect` | `Compared 1 \| Skipped 0 \| Failed 1` | **0** |
| `--mode structure` | `Compared 2 \| Skipped 0 \| Failed 0` | **0** |

Defect #2 is worse than recorded: the summary reports **`Failed 0`**. The mismatch prints a `❌`
line and then vanishes from the totals entirely.

⚠️ **This does not replace Phase 5.** These fixtures prove the control flow, not the science.
Real 184-file behaviour on HPC is still required.

### Phase 3 — Move `validate_netcdf.py` ✅ DONE August 15, 2026
- [x] Copy from `qaqc/Step3/` — original untouched
- [x] Embedded constants only; **`_VAR_SPEC` / `_COORD_SPEC` / `_GLOBAL_ATTR_SPEC` untouched**,
      verified byte-identical to the original by diff (only added comments differ)
- [x] Confirm exit-code behaviour matches the contract — **it did not, fully.** `typer.Exit(1)`
      fired correctly on validation failure, but *every* "nothing found" case also exited **1**:
      no `.nc` files, glacier not matched, `--file` absent. Those are **exit 2**. Fixed.

**Changes**, all outside the spec:
- `import yaml` and the duplicate `_resolve_base` / `_delivery_dir` / `_glacier_id` are gone;
  the file now does `from compare_netcdf import (...)`, matching
  `1_download_merge_and_clip/tests/check_raster_sanity.py`, which imports from `compare_raster.py`
  with no `sys.path` juggling (Python puts the script's own directory on the path).
- `--base` → **`--candidate`**, and its meaning changed from *delivery subfolder* to *delivery
  ROOT*, unified with `compare_netcdf.py`. **The rename is the point**: a saved
  `--base .../nsidic_v01.1_delivery` command would otherwise have silently pointed one level too
  deep. New name, new meaning, loud failure.
- Defaults to `CANDIDATE_DEFAULT`, so a bare `python validate_netcdf.py` checks the fresh run —
  the symmetric default to `compare_netcdf.py`. `--year` validates a recorded baseline instead;
  the two are mutually exclusive (exit 1).
- `RESULT:` verdict line and explicit `Exit(0)`.
- Header line "Spec source: 014_Courtauld_2024…" → "Spec **provenance**: … — a format contract,
  not a year", with the reasoning in a comment above the spec. Prevents a future reader concluding
  the tool is pinned to superseded 2024 data.
- Docstring now carries both halves of the "why both tools" argument, including this file's
  whitelist blind spot.

#### Evidence — August 15, 2026

A synthetic NetCDF was built that **satisfies the full spec** — all 20 data variables, 3
coordinates, 20 global attributes, and every encoding key. That it passes is the proof the spec
constants survived the move and still function. Fixture builder: session scratchpad,
`make_spec_fixture.py`.

| # | Case | Expected | Got |
|---|---|---|---|
| L | spec-conformant file | 0 | ✅ 0, `PASS: 1 \| FAIL: 0` |
| M | `scene_*_datetime` written float64 | 1 | ✅ 1, 4 issues, dtype **and** stray `_FillValue` |
| P | delivery dir absent | 2 | ✅ 2 |
| Q | `--glacier` not present | 2 | ✅ 2 |
| R | `--file` not found | 2 | ✅ 2 |
| S | unknown `--year` | 1 | ✅ 1 |
| T | `--year` + `--candidate` | 1 | ✅ 1 |
| U | `--glacier` match | 0 | ✅ 0 |

#### ⭐ The 2025 incident, reproduced end-to-end

Case M's mutation is the real April 2026 bug: datetime variables written `float64` instead of
`int64`, with a `_FillValue` auto-injected as a side effect. Both files hold **identical values**;
they differ only in on-disk encoding. Run through both tracked tools:

| Tool | Verdict | Exit |
|---|---|---|
| `compare_netcdf.py --mode pixel-perfect` | `Compared 1 \| Failed 0` — **PASS** | **0** |
| `validate_netcdf.py` | `PASS: 0 \| FAIL: 1` | **1** |

**This is no longer a story about 2025 — it is a reproducible property of the current tools.**
Pixel-perfect passes a file NSIDC would reject. It is the concrete answer to "why run both",
and belongs in `tests/README.md` (Phase 4).

⚠️ **First attempt at this was wrong and is recorded so it is not repeated.** The fixture builder
seeded its RNG once at module level, so the two files also differed in *values* — pixel-perfect
failed, for the wrong reason, and briefly looked like it had caught the encoding change. Re-seeding
per build isolated the variable. **When a tool appears to catch something, check what it actually
compared.**

### Phase 4 — `tests/README.md` (tracked) ✅ DONE August 15, 2026
- [x] One `cd`, then bare single-line commands, one per code block
- [x] `srun` allocation line before any comparison — never a login node
- [x] Exit-code table
- [x] **Both tools must always be run**, with the 2025 rejection as the reason — and it now opens
      with the reproduction table (pixel-perfect exit 0 / validate exit 1 on the same file)
      rather than an assertion
- [x] Baseline directory mapping — `{year}_` = delivered/authoritative · unprefixed = candidate ·
      `x1_`/`x2_` = superseded, pending deletion. (`x1_` is described as a convention, not as a
      live directory: the one that existed was deleted August 15, 2026.)

Also carried in, because they are user-facing and had no tracked home: the manual year-prefix
rename and why it must not be automated, the skip-if-exists trap, the ⛔ prototype banner with
both defects side by side, and the `glacier_id` skip-list asymmetry between the two tools.

**Two errors in the first draft, both caught by checking rather than reading**, and both were the
kind that would have wasted someone's HPC session:

1. Examples used `--glacier 049_jakobshavn`. Delivery filenames carry the **public, capitalised**
   id from `AOI_NAMES` (`014_Courtauld`), not the lowercase internal processing name. Both tools
   match case-sensitively, so every `--glacier` example was unusable. Replaced throughout with
   `014_Courtauld`, which is a real delivery filename.
2. **The two tools filter `--glacier` differently** — inherited from the qaqc originals, not
   noticed until the examples were tested. `compare_netcdf.py` uses `f.startswith(glacier)`
   (prefix); `validate_netcdf.py` uses `_glacier_id(f.name) == glacier` (exact). Verified:
   `--glacier 014` → compare exits **0**, validate exits **2**. Documented under Known
   limitations, with the safe instruction to pass the full id to both.

**🔶 Open, for the user**: unify `--glacier` matching? The failure mode is safe (exit 2, not a
false pass) and the tools are already committed, so this is deliberately left alone. Making
compare's match exact would be the smaller change and would align both on the documented id form.

### Phase 5 — HPC verification (the gate) ✅ **PASSED August 16, 2026 — 7/7**

**All seven checks ran on HPC against the real 184-file delivery, every exit code captured.**

| # | Check | Expected | Result |
|---|---|---|---|
| 1 | `validate_netcdf.py` on the new run | `184 \| 0`, exit 0 | ✅ exit 0 |
| 2 | `compare_netcdf.py --mode pixel-perfect` | `184 \| 0 \| 0`, exit 0 | ✅ exit 0 |
| 3 | nonexistent baseline | exit 2 | ✅ exit 2 |
| 4 | constructed mismatch, pixel-perfect | exit 1 | ✅ exit 1 |
| 5 | constructed mismatch, structure | exit 1 | ✅ exit 1 |
| 6 | validator on that fixture | PASS | ✅ exit 0 |
| 7 | exit codes captured throughout | — | ✅ |

**⭐ The two-tool argument, demonstrated in both directions on real data.** Same file,
`001_Alison`, same session: `pixel-perfect` **fails** it (wrong glacier's values), the validator
**passes** it (structurally valid NSIDC file). The mirror case was shown on synthetic files during
Phase 3: correct values with `float64` datetimes passes pixel-perfect and fails the validator.
**Neither tool is redundant; neither is sufficient.**

**What this does and does not establish.** It establishes that the moved and rewritten tools
reproduce the August 15 answer on the full domain, and that all three exit codes behave under real
conditions. It does **not** add evidence about Step 3 itself — that was already the position
recorded in `qaqc/Step3/AGENTS.md`, and it remains *likely sound, not proven*: only 2025 exercised,
no manual/notebook inspection.

**Every command is in `tests/README.md`, copy/paste-ready with real paths.** Do not re-derive them
here. The candidate is `/fs/project/howat.4-3/greenland_glacier_flow/3_orthocorrect_and_netcdf-package`,
which is `CANDIDATE_DEFAULT`, so the two main commands take no arguments.

- [x] `validate_netcdf.py` on the new run — **PASSED**, `PASS: 184 | FAIL: 0 | Total: 184`, **exit 0**
      *(HPC, August 16, 2026, user-run, exit code captured)*. Reproduces the August 15 result
      exactly, but through the **tracked** tool: embedded constants instead of `data_paths.yml`,
      `--candidate` defaulting to `CANDIDATE_DEFAULT` rather than an explicit `--base` pointing at
      the delivery subfolder. Confirms on real data that the path unification and the spec
      constants both survived the move.
- [x] `compare_netcdf.py --mode pixel-perfect` — **PASSED**, `Compared 184 | Skipped 0 | Failed 0`,
      **exit 0** *(HPC, August 16, 2026, user-run, exit code captured)*. Header confirmed the right
      pair before the run: `candidate: 184, baseline: 184`, candidate = the unprefixed `WD`,
      baseline = `2025_3_...`. Reproduces the August 15 result through the **tracked** tool, whose
      path layer, CLI flags, bool-returning comparators and verdict block are all new. Everything
      from `001_Alison` to `192_CHOstenfeld` identical.
- [x] Exit 2 proven via a nonexistent baseline — **PASSED** *(HPC, August 16, 2026, user-run)*.
      `Delivery counts candidate: 184, baseline: 0`, then
      `⚠️ COULD NOT CHECK: no baseline .nc files under …/does_not_exist/nsidic_v01.1_delivery`,
      **exit 2**. Both resolved paths printed *before* it stopped, so the failure is diagnosable.

      **Direct contrast, same scenario, verified locally on fixtures the same day**: the untouched
      `qaqc/Step3/` original reports `Compared 0 | Skipped 2 | Failed 0` and **exits 0**. On the
      real 184-file tree it would print 184 "skipped" lines, `Failed 0`, and exit 0 — a
      misconfigured baseline path would be indistinguishable from a clean run. This is the sharpest
      difference between the two tools on identical input.

      ⚠️ *Method note*: the first attempt at this contrast was invalid — the scratchpad had been
      cleared, so `base1` was empty and the original exited 0 for the trivial reason (nothing to
      compare) rather than the interesting one. Fixtures were rebuilt and the test re-run. **An
      exit code alone is not evidence; check the run compared what you think it did.**
- [x] Exit 1 proven via the **constructed-mismatch recipe** — **PASSED** *(HPC, August 16, 2026,
      user-run)*. `Compared 1 | Skipped 0 | Failed 1`, **exit 1**. `001_Alison` (holding
      `002_Anoritup`'s data under its own filename) failed; `002_Anoritup` passed in the same run,
      so the pass and fail paths were both exercised at once.

      **The diff is diagnosable on its own** — it ends with `glacier_id: 002_Anoritup` vs
      `001_Alison`, naming the cause directly. A real regression would not need a second run to
      interpret.

      Recipe confirmed working on real data: `ls … | head -2` then `cp $(… sed -n 2p) $(… sed -n 1p)`.
- [x] `structure` mode on the same fixture — **PASSED, and it was a real test** *(HPC, August 16,
      2026, user-run)*. `❌ 001_Alison spatial shape mismatch x:216/333, y:249/186`,
      `Compared 1 | Skipped 0 | Failed 1`, **exit 1**.

      The "exit 0 may be acceptable" caveat **did not apply**: the two real glaciers differ sharply
      in extent (216×249 vs 333×186), so the mismatch was genuinely detectable. **This is the
      direct proof of the defect-#2 fix** — on identical input the prototype prints the same `❌`
      and then reports `Failed 0`, exit 0, with `structure` being its **default** mode.

      Diagnostic behaviour preserved: `002_Anoritup` reported
      `x/y match (216×249); index(candidate/baseline)=542/542 (100.0%)` — the index ratio still
      informs without failing, exactly as intended.
- [x] `validate_netcdf.py` on the same fixture — **PASSED as expected** *(HPC, August 16, 2026,
      user-run)*. `PASS: 2 | FAIL: 0`, **exit 0**. Both files are well-formed NSIDC files;
      `001_Alison` merely holds the wrong glacier's data, which this tool structurally cannot see.
- [x] Capture every exit code with `echo "EXIT=$?"` — done for all seven.

⚠️ **Beware `| tail` and `| grep`** — they replace `$?` with the *pipe's* status. Redirect to a
file first, or put `echo "EXIT=$?"` immediately after the bare command.

### Phase 6 — Close out ✅ DONE August 16, 2026
- [x] ⛔ superseded banners on `qaqc/Step3/compare_netcdf.py` and `validate_netcdf.py` — placed in
      **both** the module docstring and the `main()` docstring, because typer shows only the
      latter in `--help`, so a module-level banner alone would be invisible to anyone who runs the
      old script rather than opening it. Behaviour unchanged; both still parse and run.
- [x] `qaqc/AGENTS.md` "Scripts that have moved out of qaqc/" table — two rows added, with the
      defects named and a note that these two no longer need `run_qaqc_job.sh` or `data_paths.yml`
- [x] `qaqc/Step3/AGENTS.md` — verification status now records the reproduction, and states the
      qaqc copies are superseded and kept only for provenance
- [x] `3_orthocorrect_and_netcdf-package/AGENTS.md` and root `AGENTS.md` — both updated
- [x] `Scratch.md` resume block replaced

**Calibration held throughout.** Every one of these says *the tests* are verified, and each carries
an explicit line that this does **not** upgrade Step 3's own status, which stays *likely sound, not
proven*. Reproducing a known-good answer proves the instrument survived the move; it is not new
evidence about the science.

**No commits.** Everything Phase 6 touched is gitignored — `qaqc/**` and every `AGENTS.md`.

---

## 🔶 Still open after Phase 6

1. **Unify `--glacier` matching?** `compare_netcdf.py` matches by filename prefix,
   `validate_netcdf.py` by exact id, so `--glacier 014` passes one and exits 2 on the other.
   Failure mode is safe and it is documented under *Known limitations* in `tests/README.md`.
   Making compare's match exact is the smaller change.
2. ✅ **RESOLVED August 16, 2026 — this plan is now tracked.** It was gitignored while it was a
   moving target; with all six phases closed it holds the only record of the Phase 1–5 evidence,
   so it was committed. Kept here in `tests/` rather than moved to `docs/`, because root `docs/`
   is effectively *Step 1's* home — Step 1's entry points live at root too — so the structural
   mirror for Step 3 is inside `3_orthocorrect_and_netcdf-package/`.
3. **`--mode encoding` remains unexercised** — see 🔶 REVISIT above. Parked at user direction.
4. **Pre-flight and run-completeness tools** — see the risk inventory below. Deliberately out of
   scope for this round.

---

## Risk inventory — what this suite deliberately does NOT cover

*Merged from `Scratch.md`, August 15, 2026. Revisit when deciding whether to add pre-flight checks.*

| Risk | Covered today? |
|---|---|
| **Silent skip** — non-empty `WD` → every glacier skipped, nothing written, **exit 0** | ❌ nothing |
| **Path misconfiguration** — 8 hardcoded paths in `lib/config.py`; the Step 3 guide calls this the #1 failure cause | ❌ nothing |
| **Step 2 input availability** — Step 3 cannot run without velocity data it does not own | ❌ nothing (would also have settled the S2C drift question directly rather than by inference) |
| **Run completeness** — attempted vs delivered vs errored reconciliation (the `192 − 8 = 184` arithmetic, done by hand) | ❌ nothing |
| **NSIDC format conformance** | ✅ `tests/validate_netcdf.py` |
| **Regression vs delivered baseline** | ✅ `tests/compare_netcdf.py` — HPC run still pending (Phase 5) |
| **Graceful degradation correctness** — a 4b failure should yield valid S2-only output, not corrupt output | ⚠️ implicitly via validate; nothing asserts "S2-only *and that is expected here*" |

**Why Step 3's suite should not mirror Step 1's five tools**: Step 1's is post-hoc because its runs
are cheap. Step 3's dominant risks are **pre-flight** — a run is 3–4 h × 90 cores × 290 G, and the
top two failure modes above both occur before any science happens. Building post-hoc tools first
was still right: they were the ones with existing evidence to preserve.

---

## Out of scope

- Any change to Step 3 **processing** code — `processing_chain/`, `lib/`, the orchestrator,
  `batch_glacier_processor.py`. Untouched since April 19, 2026 and staying that way.
- Pre-flight checks (config-path validation, `WD`-empty guard, Step 2 input availability)
- Run-completeness reconciler (the `192 − 8 = 184` arithmetic)
- A full `qaqc/` audit — explicitly declined; `qaqc/` was built on-need and never audited
- Fixing anything in `qaqc/Step3/*.py`
- 2026 tooling — *"we are overthinking for 2026 now"*
- Deleting anything from `qaqc/`

---

## Closed questions

### ✅ Which global attributes legitimately vary — ALREADY DOCUMENTED IN CODE

Answered by `validate_netcdf.py:_GLOBAL_ATTR_SPEC` (lines 115–139). It is the authoritative
classification: 20 global attributes, each tagged `check_value=True` (exact value required) or
`False` (presence only, value varies).

**Exactly three vary**: `glacier_id` (per glacier) · `data_acknowledgement` (contains the year) ·
`creation_date` (per run). The other 17 are pinned to exact strings — `project`, `title`,
`version`, `data`, `units`, `source`, `projection`, `epsg`, `coordinate_unit`,
`spatial_resolution`, `institution`, `contributors`, `contact_name`, `contact_email`, `software`,
`funding_acknowledgement`, `Conventions`.

**The two skip-lists differ for a principled reason — do not "fix" this.**
`compare_netcdf.py` skips 2 (`creation_date`, `data_acknowledgement`); `validate_netcdf.py`
treats 3 as varying. Correct: compare pairs glacier X against glacier X, so `glacier_id` is
already identical between them. Validate checks every file against one shared spec, so
`glacier_id` must be presence-only there.

### ✅ `--mode encoding` — see the 🔶 REVISIT section near the top of this file

Fully written up there: what it is, commit `39b9bb4` provenance, where it overlaps
`validate_netcdf.py`, the whitelist gap it uniquely covers, and how to settle the question
empirically. Not duplicated here.

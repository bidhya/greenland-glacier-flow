# Step 3 — Test Suite Reference

**Status: stable.** Two tracked tools in `3_orthocorrect_and_netcdf-package/tests/`, verified on HPC
against the real 184-file NSIDC delivery, all three exit codes proven under real conditions.

**This file**: what the tests have established, why they are shaped the way they are, and what they
do **not** cover. `tests/README.md` says how to run them, copy/paste-ready with real paths.
`3_orthocorrect_and_netcdf-package/AGENTS.md` covers running Step 3 itself.

⚠️ **These tools are verified — Step 3 is not.** Reproducing a known-good answer proves the
instrument works. Step 3 itself remains **likely sound, not proven**: only the 2025 season has been
exercised, and every check is automated. No manual or notebook inspection has been done.

---

## Exit-code contract

`0` passed · `1` **failed** · `2` **could not check** — baseline missing, nothing found. **Not a pass.**

Data vanishing is the normal case here, not an anomaly, which is exactly what `2` exists for.

⚠️ **Beware `| tail` and `| grep`** — they replace `$?` with the *pipe's* status. Redirect to a file
first, or put `echo "EXIT=$?"` immediately after the bare command.

---

## ⭐ Why both tools must always be run

**The `2025_` delivery is the baseline. NSIDC complains when a delivery does not match the legacy
format — "better" is a defect.** 2024 is superseded.

In 2025 a library update silently changed a fill value, `--mode pixel-perfect` passed, and NSIDC
flagged the delivery. The cause: **`xr.testing.assert_identical()` excludes `.encoding`.** Two files
differing in on-disk dtype, `_FillValue`, and `complevel` compare as *identical*.

**Library upgrades, not code edits, are the live threat.** Step 3's processing code has not changed
since April 19, 2026.

| Tool | Answers | Blind to |
|---|---|---|
| `compare_netcdf.py` | does this match the delivered baseline? | encoding, in `pixel-perfect` mode |
| `validate_netcdf.py` | does this meet the NSIDC spec, with no baseline? | **anything added** — it is a whitelist |

**Neither is redundant; neither is sufficient.** Demonstrated in both directions on real data — see
*Failure modes are proven*.

---

## ⭐ Only `2025_` can be assumed to exist

`2025_3_orthocorrect_and_netcdf-package/` is the **one durable artifact** — read-only, permanent.

**Everything else is transient**: test `WD`s, candidate runs, `x1_`/`x2_` renames, the 2024 tree.
`x1_2025_` was deleted hours after an earlier draft of this plan cited it as a fixture.

- **No test may depend on any directory other than `2025_` existing.** A test needing a mismatch
  must **construct** it, never assume one is lying around.
- **A missing baseline or candidate must exit `2`**, never `0`.

---

## Known-good reference results

Baseline: `/fs/project/howat.4-3/greenland_glacier_flow/2025_3_orthocorrect_and_netcdf-package`
(the April 19, 2026 NSIDC delivery).

| Run | `validate_netcdf.py` | `--mode pixel-perfect` | `--mode encoding` |
|---|---|---|---|
| First full-domain rerun | `184 \| 0` | `184 \| 0 \| 0` | — |
| Tracked-tool verification | ✅ exit 0 | ✅ exit 0 | — |
| Independent rerun, all modes | `184 \| 0` | `184 \| 0 \| 0` | `184 \| 0 \| 0` |

**`Skipped 0` is load-bearing** on every compare run: 184 found, 184 actually compared. This rules
out the silent-skip trap, where a run into an occupied `WD` writes nothing, exits 0, and a
comparison against the *stale* output reports `Failed 0` indistinguishably from a real pass.

**The answer is already known, which is the point.** Any deviation means something broke.

Resources that work: `--mem-per-cpu=32G --time=04:00:00`, 1 cpu — the compare loop is serial,
~28 min for 184 glaciers.

Which library versions produced which season, and what to do if results drift:
**`docs/ENVIRONMENT_PROVENANCE.md`**.

---

## Failure modes are proven, not assumed

All seven checks ran on HPC against the real 184-file delivery, every exit code captured.

| # | Check | Expected | Result |
|---|---|---|---|
| 1 | `validate_netcdf.py` on a fresh run | `184 \| 0`, exit 0 | ✅ exit 0 |
| 2 | `compare_netcdf.py --mode pixel-perfect` | `184 \| 0 \| 0`, exit 0 | ✅ exit 0 |
| 3 | nonexistent baseline | exit 2 | ✅ exit 2 |
| 4 | constructed mismatch, `pixel-perfect` | exit 1 | ✅ exit 1 |
| 5 | constructed mismatch, `structure` | exit 1 | ✅ exit 1 |
| 6 | validator on that same fixture | PASS | ✅ exit 0 |
| 7 | exit codes captured throughout | — | ✅ |

### ⭐ The two-tool argument, shown both ways on real data

Same file, `001_Alison`, holding `002_Anoritup`'s data under its own filename:

- `pixel-perfect` **fails** it — the values are wrong
- `validate_netcdf.py` **passes** it — it is a structurally valid NSIDC file

The mirror case, on synthetic files: correct values with `float64` datetimes **passes**
pixel-perfect and **fails** the validator.

### Exit 2 — the sharpest difference from the prototype

A nonexistent baseline prints `candidate: 184, baseline: 0`, then `COULD NOT CHECK`, **exit 2**,
with both resolved paths shown so the failure is diagnosable.

⛔ The untouched `qaqc/Step3/` original reports `Compared 0 | Skipped 2 | Failed 0` and **exits 0**.
On the real tree it would print 184 "skipped" lines and exit 0 — **a misconfigured baseline path
would be indistinguishable from a clean run.**

### Exit 1 — diagnosable without a second run

`Compared 1 | Skipped 0 | Failed 1`, exit 1. The diff ends with `glacier_id: 002_Anoritup` vs
`001_Alison`, naming the cause directly. `002_Anoritup` passed in the same run, so pass and fail
paths were exercised together.

`structure` mode on the same fixture: `spatial shape mismatch x:216/333, y:249/186`, exit 1. The
diagnostic ratio still informs without failing on the `index` dimension, as intended.

> ⚠️ **Method note worth keeping.** The first attempt at the exit-2 contrast was invalid — the
> scratchpad had been cleared, so the comparison ran on nothing and exited 0 for the trivial reason
> rather than the interesting one. **An exit code alone is not evidence; check that the run compared
> what you think it did.**

---

## Why the tools are shaped this way

Two verified defects in the `qaqc/Step3/` prototype, both reproduced before being fixed:

1. **No exit code on comparison failure.** `main()` printed its summary and returned. `typer.Exit(1)`
   fired only for *usage* errors, so the script exited **0** whether `Failed` was 0 or 184.
2. **`--mode structure` counted a failure as a success.** On spatial-shape mismatch it printed `❌`,
   then returned normally and incremented the success counter. **`structure` is the default mode.**

`validate_netcdf.py` was not defective — it already raised `typer.Exit(1)` correctly, and only
needed the shared constants.

⛔ **Do not use the `qaqc/Step3/` copies.** They carry banners; the `tests/` versions are
authoritative. Do not edit the `qaqc/` originals either — they produced the original evidence, and
editing them destroys its provenance.

### Which global attributes legitimately vary

Authoritative classification lives in `validate_netcdf.py:_GLOBAL_ATTR_SPEC`: 20 global attributes,
each tagged `check_value=True` (exact value required) or `False` (presence only).

**Exactly three vary**: `glacier_id` (per glacier) · `data_acknowledgement` (contains the year) ·
`creation_date` (per run). The other 17 are pinned to exact strings.

**The two skip-lists differ for a principled reason — do not "fix" this.** `compare_netcdf.py`
skips 2; `validate_netcdf.py` treats 3 as varying. Compare pairs glacier X against glacier X, so
`glacier_id` is already identical between them. Validate checks every file against one shared spec,
so `glacier_id` must be presence-only there.

---

## 🔶 Is `--mode encoding` redundant with `validate_netcdf.py`?

**Partly — and the part that is not redundant covers a real gap.**

`--mode encoding` compares the **container** of two files rather than their values: variable set ·
spatial dims · per-variable dtype · per-variable encoding (`dtype`, `units`, `_FillValue`,
`calendar`, `zlib`, `complevel`, `shuffle`) · global attrs minus the varying ones. Everything is
read from the reference file — no hardcoded values.

**Where the redundancy is real**: for everything inside `_VAR_SPEC` / `_COORD_SPEC` /
`_GLOBAL_ATTR_SPEC`, `validate_netcdf.py` covers the same ground and does it *better* — no baseline
needed, correct exit code.

**Where it is not — the whitelist gap.** `validate_netcdf.py` iterates the spec, never the file:

| Check | Consequence |
|---|---|
| `set(_VAR_SPEC) - all_vars` | catches **missing**, never **extra** |
| same for coordinates | additions invisible |
| iterates `_VAR_SPEC.items()` | only spec'd vars encoding-checked |
| iterates `_GLOBAL_ATTR_SPEC` | only spec'd attrs checked |

**Nothing detects an addition.** A new variable, coordinate, or global attribute passes silently.
`compare_encoding()` compares variable **sets**, so it catches exactly that.

Not academic: the 2025 incident was a library silently changing what got written. A library upgrade
that *adds* something — netCDF4 injecting `_NCProperties`, xarray adding an attribute — is the same
class of event, and only the relative check sees it.

**Status**: `--mode encoding` has now been run on the full domain — 184/184, `Skipped 0`, exit 0,
and **none of its three historical false positives recurred** (NaN≠NaN, hardcoded units string,
`data_acknowledgement` year).

⚠️ **That does not settle the redundancy question, and cannot.** Both tools passed on the same 184
files; agreement on a *pass* is what you would see whether they are redundant or not. Only a
**disagreement** discriminates, and the whitelist gap above is still established by reading the
code, not by observing it.

**Settling it properly** would need either a disagreeing case, or an "unexpected additions" check
added to `validate_netcdf.py` — a small change that would genuinely make `--mode encoding` moot.
**Out of scope**: that is inventing, not hardening.

---

## Not covered

| Risk | Covered? |
|---|---|
| **Silent skip** — non-empty `WD` → every glacier skipped, nothing written, **exit 0** | ❌ nothing |
| **Path misconfiguration** — 8 hardcoded paths in `lib/config.py`, the #1 failure cause | ❌ nothing |
| **Step 2 input availability** — Step 3 cannot run without velocity data it does not own | ❌ nothing |
| **Run completeness** — attempted vs delivered vs errored (the `192 − 8 = 184` arithmetic, done by hand) | ❌ nothing |
| **Graceful degradation correctness** — a 4b failure should yield valid S2-only output, not corrupt output | ⚠️ implicitly via validate; nothing asserts "S2-only *and that is expected here*" |
| **NSIDC format conformance** | ✅ `validate_netcdf.py` |
| **Regression vs delivered baseline** | ✅ `compare_netcdf.py` |

**Why this suite does not mirror Step 1's five tools**: Step 1's are post-hoc because its runs are
cheap. Step 3's dominant risks are **pre-flight** — a run is 3–4 h × 90 cores × 290 G, and the top
two failure modes above both occur before any science happens. Building post-hoc tools first was
still right: they were the ones with existing evidence to preserve.

**Known limitation**: `--glacier` matching differs between the tools — `compare_netcdf.py` matches
by filename prefix, `validate_netcdf.py` by exact id, so `--glacier 014` passes one and exits 2 on
the other. Failure mode is safe and documented in `tests/README.md`. Making compare's match exact is
the smaller change.

---

## Out of scope

- Any change to Step 3 **processing** code — `processing_chain/`, `lib/`, the orchestrator,
  `batch_glacier_processor.py`
- Pre-flight checks (config-path validation, `WD`-empty guard, Step 2 input availability)
- Run-completeness reconciler
- Fixing or auditing anything in `qaqc/`
- 2026 tooling — 2026 values will legitimately differ, so `pixel-perfect` cannot be a 2026 gate

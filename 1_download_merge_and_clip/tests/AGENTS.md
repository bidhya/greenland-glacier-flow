# AGENTS.md — Step 1 Tests

**⚠️ Read the root `AGENTS.md` first** for project-wide context (hard constraints, pipeline ownership, environment, HPC workflow). This file covers only how to *work on* the tests in this folder.

**Division of labour:**

| Doc | Audience | Tracked? |
|---|---|---|
| `README.md` (this folder) | anyone **using** the tests — how to run them, what they mean | ✅ tracked, travels to HPC |
| this file | agents **modifying** the tests | ❌ gitignored, local only |
| `docs/STEP1_TEST_PLAN.md` | full history, phases, verification evidence | ✅ tracked |

Keep that split. **User-facing content belongs in `README.md`** — it is the only one of the three that reaches a fresh clone alongside the code. Do not move usage instructions, exit codes, or design rationale into this file.

---

## What is here

Five tools, all `typer` CLIs, all sharing the same exit-code contract.

| Tool | Answers |
|---|---|
| `compare_raster.py` | does output match the production baseline? |
| `check_environment.py` | is the conda environment the pinned one? |
| `check_job_generation.py` | does job generation still produce valid jobs? |
| `check_output_structure.py` | did the run write everything it should? |
| `check_raster_sanity.py` | is the output well-formed, with no baseline needed? |

`compare_raster.py` is the **root module** — the other tools import path logic and root constants from it. Change it carefully.

---

## Standing rules

1. **Exit codes are the contract**: `0` passed · `1` failed · `2` could not check. `2` is **not** a pass. Never collapse `2` into `0`, and never let a genuine failure exit `0` — that defect is the entire reason this folder exists.
2. **Prove failures, not just successes.** A test whose failure mode is untested is not trustworthy. Every behavioural change must be demonstrated against a deliberately broken input.
3. **Verify assumptions against real data before encoding them.** Invariants here were derived by inspecting production rasters, not from docs. See the `_reference` trap below for why.
4. **Stay inside `tests/`.** The rest of `1_download_merge_and_clip/` is core Step 1 logic and off-limits without explicit instruction.
5. **Do not import path logic — reuse it.** Sentinel-2 and Landsat nest at different depths; duplicating that asymmetry is a proven way to get it wrong twice. Import `build_paths` / `discover_regions` from `compare_raster`.
6. **Never modify `qaqc/Step1/compare_raster.py`.** It is the superseded prototype, kept deliberately unchanged as a reference. It carries a ⛔ banner explaining why.

---

## How to prove a failure mode

The established pattern, used for every phase:

1. Write a fixture generator into the **scratchpad**, never the repo and never real data trees.
2. Build one fixture per defect, so a failure is attributable to exactly one cause.
3. Run the **real script** against the fixtures — do not copy the script somewhere else to test it (see the trap below).
4. Assert the exit code *and* that it failed for the **right reason**.

Both `compare_raster.py` (`--baseline`/`--candidate`) and the check tools (`--candidate`) accept explicit roots, so fixtures need no path patching. `check_job_generation.py` accepts `--generator`.

**⚠️ Do not test by copying a script to another directory.** `REPO_ROOT` is derived from `__file__`, so a relocated copy resolves the wrong repo root and fails for an unrelated reason. This produced a false positive during Phase 4 — the test exited 1 as expected, but from a `KeyError`, not the defect being probed. Use the `--generator` / `--candidate` flags instead.

---

## Traps verified the hard way

- **`landsat/_reference/*.tif` are `uint8`**, not `uint16` like scene output. They are templates. Region discovery excludes `_`-prefixed directories, so they never reach the checks. **Do not relax the dtype expectation to accommodate them** — that would blind a real defect class.
- **`--base-dir` does not redirect a local-mode run.** `submit_satellite_job.py` applies the CLI flag, then overrides `root_dir` with `config.ini`'s `local_base_dir` when `execution_mode == 'local'`, inverting documented precedence. **Not fixed** — core Step 1 logic, possibly deliberate. `check_job_generation.py` works around it with a temporary `--config` rewriting both keys.
- **`--year` must match the dates the candidate was produced with.** Default is `2025`; the August 14, 2026 verification data is 2024-dated and needs `--year 2024`. A mismatch reports differences that are not regressions.
- **The year → path map is duplicated** from `qaqc/data_paths.yml`, which is gitignored and therefore cannot be imported by tracked code. Adding a year means updating both. The failure mode is safe — an unknown year is rejected with a list of known ones.
- **rasterio 1.4.4 + numpy 2.5.2 emit a `DeprecationWarning`** on `src.read()`. **Deliberately not suppressed** — it is a genuine early signal of library drift.

---

## Conventions

- **`typer`** for CLIs, matching the existing scripts.
- **Single-line shell commands** in docs — no backslash continuations, they break when pasted into an HPC terminal.
- **One command per fenced code block** in `README.md`, so GitHub's copy button grabs exactly one.
- Commands assume the repo root; `README.md` has a single `cd` step rather than repeating it per command.
- **No AI attribution in commit messages.**

---

## Before claiming something passes

- Run the tool and capture the **exit code**, not just the output. `echo "EXIT=$?"` after every command.
- Beware `| tail` and `| grep` — they replace `$?` with the *pipe's* exit status. Redirect to a file first, then check.
- **Local runs prove the code executes; they do not prove correctness at scale.** Local holds a small sample. HPC holds the full 192-region domain for 2024 and 2025.
- If HPC results were reported but exit codes were not captured, record that honestly as *"user-reported, exit codes not captured"* rather than as verified.

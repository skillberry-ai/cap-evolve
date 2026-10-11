# SpreadsheetBench scorer audit (zero LLM spend)

Scope: how CapEvolve's `templates/adapters/spreadsheetbench/adapter.py::Adapter.score` turns an output workbook into a
reward, compared with the official SpreadsheetBench evaluation, with a diagnostic on known-good / formula / bad /
malformed outputs. All numbers below were produced on this host on 2026-10-11 by the scripts listed at the end;
raw JSON is under `/home/dev/projects2/campaign-scratch/bench/out/`.

## 1. Findings in one screen

1. **Default reward = cached values as saved, no recalculation.** `SPREADSHEETBENCH_REWARD_RECALC` defaults to `0`
   (`run_suite.sh` exports `${SB_REWARD_RECALC:-0}`; no tier's `overrides.env` sets it). The reward is
   `hard_no_recalc` (all SB tiers set `SB_SCORING=hard`). `compare_workbooks` loads gold and output with
   `openpyxl.load_workbook(data_only=True)`; a formula cell the agent wrote through openpyxl has no cached value, so it
   reads `None` and never matches.
2. **Historical scorer under-scores formula outputs: confirmed, measured.** Correct formula outputs with no cached values:
   as-saved scorer 0/30 pass; recalculating scorers 25/30 (LO 7.1.8.1) to 29-30/30 (LO 25.8.7.3). In the verified-400 gold, **282 of 400 tasks
   (70.5%) have formula cells inside `answer_position`**. Through the real `Adapter.score()` on task 58687: the same
   correct formula workbook gets `hard_no_recalc = 0.0` but `hard_restriction = 1.0`. This is by design (matches SkillOpt;
   CapEvolve's README quotes 43.5 as-saved vs 58.3 recalculated for Gemma-4-31B on a full_verified run) but it means every
   historical SpreadsheetBench number rewards "write literals, not formulas".
3. **The recalculation path is not a clean fix with the host LibreOffice.** The recalc path (`*_restriction` metrics,
   `SB_REWARD_RECALC=1`) recalculates the candidate output only; gold is used as shipped (Excel-cached values). LibreOffice
   7.1.8.1 (RHEL 9, the runner version named in the adapter docstring; upstream asks for >= 7.5) mis-evaluates some
   array/dynamic formulas (`#NAME?`), so even **the official gold file used as the output fails**: 32/400 tasks (28 beyond the 4 unscorable ones; 8 train, 2 val, 18 test of the SkillOpt split) with 7.1.8.1,
   19/400 (15 beyond) with LibreOffice 25.8.7.3. Under the recalc reward those tasks are unwinnable.
4. **4 of 400 verified tasks (1%) are unscorable under ANY path** (gold-as-output fails the official comparator because of
   unparseable or malformed `answer_position` strings): `130-9`, `283-32`, `45944`, `49300` (all four are in the SkillOpt TEST split). In the 912 set 11 tasks
   fail the same check: `283-32 118-8 130-9 147-7 532-3 CF_25745 49300 52763 37456 45944 56637`. Max attainable on verified-400 test = 276/280 = 98.6%.
5. **Scoring is deterministic**: every (output, path, engine) was scored twice with fresh LibreOffice profiles; 0 of 333 records
   differed (both engines).
6. **Malformed outputs score 0 on every path**, no exception escapes `score()`. A failed LibreOffice run is only *recorded*
   (`recalc_failed`) and is invisible when the as-saved reward is used; when LibreOffice is missing the adapter silently skips
   recalculation (the CI preflight only warns).
7. **The gold answer workbooks sit inside the directory bind-mounted read-write into the agent's container** (`/mnt/data`),
   next to the inputs. Verified with the real sandbox: `os.listdir` shows `1_<id>_golden.xlsx`. Agent code can read the answer
   (and, depending on host uid mapping, overwrite it). Fix prototyped: `patches/adapter_gold_dir.patch` +
   `local/make_agent_view.py` (section 6).

## 2. What the CapEvolve scorer does, exactly (code references)

`adapter.py::score` (about lines 1523-1670):
* For each graded case index (`_case_indices`, read from disk: 1 for verified-400, 3 for the 912 set, fewer for 4 defective
  912 tasks) it resolves the gold (`_resolve_case_file(..., "answer")`) and the agent output
  `outputs/<run_tag>/<idx>_<id>_output.xlsx`.
* **No-recalc comparison first**: `vendor["compare_workbooks"](gold, output, instruction_type, answer_position)` on the file as
  saved (becomes `*_no_recalc`).
* If `KEEP_OUTPUTS`, copies the output to `*.norecalc.xlsx`.
* **Then, if a LibreOffice binary was found**, `_reclaim_container_file` (the container-uid-owned output is replaced by a copy
  owned by the harness uid) and `_recalc_workbook(output, soffice)`: `soffice --headless --calc -env:UserInstallation=file://<fresh tmp profile> --convert-to "xlsx:Calc MS Excel 2007 XML"`, timeout 120 s (`SPREADSHEETBENCH_LIBREOFFICE_TIMEOUT`), result moved over the original in place. Any non-zero exit, timeout, OSError or missing converted file returns `False`.
  A `False` appends the case to `recalc_failed` and **the comparison simply proceeds on whatever is cached** (no retry, no error).
* The recalculated file is compared again (becomes `*_restriction`). Gold is **never** recalculated or modified.
* Applies identically to every rollout: baseline/seed and candidates go through the same code, there is no per-capability branch.
* Reward = `hard_no_recalc` or `soft_no_recalc` when `REWARD_RECALC=0` (default) else `hard_restriction`/`soft_restriction`. All four are always emitted as metrics (one marked primary).
* Feedback: when recalc is the reward, recalc failures are reported; in the default mode a case that would pass only after
  recalculation is reported to the optimizer as "formula-only" so it learns to write literals. `_localize_failure` additionally feeds
  per-range counts/types of mismatches (not values) to the optimizer.
* Engine/locale: whatever `soffice` the host has. Not recorded in any artifact. Host: LibreOffice 7.1.8.1 (RHEL 9 AppStream), `LANG=C.UTF-8`; a fresh profile per call, so the user locale does not leak in.

## 3. Comparison with the official evaluation (RUCKBReasoning/SpreadsheetBench@49b73a94775fb489063f60ca1865e3a650079a79)

| aspect | official | CapEvolve |
|---|---|---|
| comparator | `evaluation/evaluation.py::compare_workbooks` | **identical bytes** (vendored copy equals upstream main; `evaluation.py` sha256 `4ae77cee8df01d1f3468…`) |
| value read | `openpyxl data_only=True` for both | same |
| cell equality | `transform_value` (floats rounded to 2 dp, numeric strings -> float, datetimes -> serial rounded to 0 dp, `time` -> `HH:MM`), `""` == `None`, then **strict type equality** then `==` | same |
| scope | only cells inside `answer_position` (comma-separated ranges, optional `'Sheet'!` prefix); formatting/colours not compared (commented out) | same |
| recalculation | README: before evaluating, run `open_spreadsheet.py` over **the whole spreadsheet directory** (inputs, outputs, gold), LibreOffice >= 7.5 or Excel, which rewrites each file as xlsx so cached values exist | recalculation of the **candidate output only**, never gold; ALSO the as-saved comparison exists and is the default reward |
| recalc failure | prints and counts `failed`; no scoring change | recorded, ignored |
| `evaluation.py` main loop | hard-codes 3 cases, and in main the `proc_path` points at `_input.xlsx` (the outputs line is commented out) i.e. the shipped main script does not even read agent outputs | CapEvolve uses its own loop (`score`) around the shared comparator |
| hard / soft | `hard = 0 if any case fails`; soft = fraction | same |

So the *comparator* is exactly official; the *pipeline around it* (which files get recalculated, with which engine, and which
variant is the reward) is CapEvolve's own. The as-saved default follows SkillOpt's evaluator, not the official README
instructions (which recalculate first).

Data defects found by running gold through the official comparator (section 4.4): they exist upstream and affect official numbers too.

## 4. Diagnostic results

### 4.1 Design
Official gold (case 1) of sampled verified-400 tasks is used to synthesise "agent outputs":

| output variant | meaning |
|---|---|
| `good_gold_asis` | the gold workbook bytes (known-good, has Excel-cached values) |
| `good_gold_formulas_nocache` | openpyxl round-trip of gold keeping formulas, which drops all cached values (what an agent writing formulas with openpyxl produces) |
| `good_gold_values_only` | gold saved with `data_only=True` (literal values) |
| `bad_input_unchanged` | the task's input workbook |
| `bad_one_cell_corrupted` | gold values with the first answer cell replaced |
| `malformed_empty` / `malformed_text` / `malformed_truncated` | 0-byte file / text with `.xlsx` name / half of the gold zip |
| `missing_file` | path absent |

Scorer paths (all use the vendored comparator and the **adapter's own `_recalc_workbook`**):
* **A as_saved**: no recalculation (CapEvolve default reward).
* **B recalc_out_only**: recalculate output, compare to gold as shipped (CapEvolve `*_restriction` / `REWARD_RECALC=1`).
* **C recalc_both**: recalculate output and a copy of gold with the same engine, compare (what "recalculate everything" in the official README implies).
* **D fill_missing_only** (proposed): keep every cached value as shipped; take LibreOffice's value **only for formula cells that have no cached value**; compare to gold as shipped.

Sample: 30 tasks whose gold answer range contains formula cells + 7 with none (seed 11), 37 tasks x 9 variants x 2 repetitions per engine.
A "formula cell" is any cell with `data_type == 'f'` (includes array formulas; an earlier survey that only counted `=` strings under-counted: 176 vs 282 tasks).

### 4.2 Results: number of outputs scored as PASS (fresh LibreOffice profile each call)

Formula-gold tasks (n = 30 per row):

| output | A as-saved | B 7.1.8.1 | C 7.1.8.1 | D 7.1.8.1 | B 25.8.7.3 | C 25.8.7.3 | D 25.8.7.3 |
|---|---|---|---|---|---|---|---|
| good_gold_asis (should pass) | 30 | 25 | 30 | 30 | 29 | 30 | 29 |
| good_gold_formulas_nocache (should pass) | **0** | 25 | 30 | 25 | 29 | 30 | 29 |
| good_gold_values_only (should pass) | 30 | 30 | 25 | 30 | 30 | 29 | 30 |
| bad_input_unchanged (should fail) | 0 | 0 | **2** | 0 | 0 | 0 | 0 |
| bad_one_cell_corrupted (should fail) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| malformed_empty (should fail) | 0 | 0 | **1** | 0 | 0 | 0 | 0 |
| malformed_text / truncated / missing (should fail) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Plain-gold tasks (n = 7): all rows give the expected outcome on every path and engine (good = 7, bad/malformed = 0), including
`good_gold_formulas_nocache` = 7 under A, i.e. the penalty is specific to answers that are formulas.

Reading:
* A fails all 30 correct formula outputs; recalculation recovers 25-29.
* B (CapEvolve's recalc reward) **fails the gold file itself** on 5/30 tasks with LO 7.1.8.1 (50683, 50971, 48608, 59884, 45896) and 1/30 with 25.8 (59884). Cause (task 39903 inspected; it fails the gold-as-output check under both engines): the gold cells are dynamic-array formulas, `=LET(t,TEXTSPLIT(B2,", "),ft,FILTER(...),SUM(IF(ft="",0,1)))`; LibreOffice 7.1.8.1 recomputes all five cells to `#NAME?` (no LET/TEXTSPLIT/FILTER), LibreOffice 25.8.7.3 gets four of five right and returns `#VALUE!` for C2, while Excel's cached values (1, 1, 0, 0, 6) are the reference.
* C removes B's gold mismatch but **accepts bad outputs** on LO 7.1.8.1 (2 unchanged inputs, 1 empty file) because both sides collapse to the same error values, and rejects correct literal answers (25/30). C is unsafe with an old engine and should not be used.
* D never accepts a bad/malformed output in this sample and never penalises cached values; its only misses are formulas the engine cannot evaluate (5/30 on 7.1.8.1) and, on 25.8.7.3, task 59884 whose *gold itself* has formula cells with no cached value (D fills them from LibreOffice, gold keeps `None`, so even the gold file mismatches; B fails the same way). Probably a gold-data artefact (gold cells without cached values) rather than an engine fault; not investigated further.
* Engine matters: 5 vs 1 failures out of 30 formula-gold tasks.

Through the real `Adapter.score()` (no LLM, synthetic rollout, output dirs written by the test):

| task | engine | gold_as_shipped (reward / restriction) | gold_formulas_no_cache (reward / restriction) | input_unchanged | malformed |
|---|---|---|---|---|---|
| 58687 | 7.1.8.1 | 1.0 / 1.0 | **0.0 / 1.0** | 0.0 / 0.0 | 0.0 / 0.0 |
| 58687 | 25.8.7.3 | 1.0 / 1.0 | **0.0 / 1.0** | 0.0 / 0.0 | 0.0 / 0.0 |
| 50683 | 7.1.8.1 | 1.0 / **0.0** | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| 50683 | 25.8.7.3 | 1.0 / 1.0 | 0.0 / 1.0 | 0.0 / 0.0 | 0.0 / 0.0 |

("reward" = default `hard_no_recalc`; "restriction" = `hard_restriction`.) Files: `out/e2e/*.json`.

### 4.3 Determinism
Each record scored twice (fresh profile per `soffice` call, independent output copies): **0 nondeterministic records of 333 on 7.1.8.1 and 0 of 333 on 25.8.7.3** for all of A, B, C, D. Same bytes in, same verdict out. (Wall time differs; the verdict does not.) Caveat: LibreOffice and openpyxl versions are pinned only by this host; a different engine version changes B/C/D (section 4.2).

### 4.4 Population ceiling check (whole dataset, gold used as the output)
| data | cases | unscorable with as-saved comparator (A) | extra unscorable under recalc reward, LO 7.1.8.1 | extra, LO 25.8.7.3 |
|---|---|---|---|---|
| verified-400 | 400 | 4 tasks (`130-9`, `283-32`, `45944`, `49300`) | 28 tasks | 15 tasks |
| of which SkillOpt split | | test 4 | test 18, train 8, val 2 | test 9, train 5, val 1 |
| 912 set | 2,729 | 11 tasks (listed above) | not completed at time of writing (`out/pop/AB_912_lo71.json` appears if the background job finished) | not run |
| sample_200 (smoke dataset) | 600 | 1 task (`56637`) | not run | not run |

Extra-unwinnable-under-recalc ids, LO 7.1.8.1: `13284 31011 32023 33722 45300 45896 48608 50526 50683 50768 50971 535-20 54085` are
the ones that LO 25.8 fixes; the remaining 15 fail on both. No recalculation failure (process level) occurred on any of 800 gold files.

Why the four A-failures: `283-32` (`'Sheet3'!A:G,'Sheet4'!A:G`, whole-column range, parser raises), `130-9` (sheet name `b2b, sez, de`
contains commas, the comma split breaks it), `45944` (`G4:G6, G11:G13` space after the comma -> AttributeError), `49300` (the dataset's `answer_position` is `"\u00a0'Sheet1'!C2:C3"`, i.e. starts with a non-breaking space, so the sheet name `\xa0'Sheet1'` is not found: "worksheet not found").

### 4.5 Failure modes of the recalculation step (observed)
* `soffice` returns success on a 0-byte or non-zip text file with an `.xlsx` name: it opens it as text and writes a valid workbook,
  and `_recalc_workbook` overwrites the malformed output with that conversion (recalc_ok = True for 74 of 111 malformed samples; the truncated zip fails, 37 of 111). The comparison still fails on content, but a CSV-like file with correct values in the right cells would be "repaired" into a pass under B/C/D and fail under A.
* Concurrency: every call uses a fresh `-env:UserInstallation` profile, so parallel calls do not conflict (the 24-way runs completed with 0 process-level failures).
* A cold first start can take ~20 s under load (observed 19.9 s on a busy host); the 120 s timeout is not hit in practice, but a timeout would be a silent `recalc_failed` under the default reward.

## 5. Recommendation for the campaign

1. Decide one reward and state it: **keep A (as-saved) as the primary, comparable to SkillOpt/WikiSkill**; report D with
   LibreOffice >= 24.8 (25.8.7.3 tested here) as the secondary "recalculation-correct" metric. Do not use C. Do not use B with LO 7.1.8.1.
2. Record in every run: LibreOffice `--version` string, `SPREADSHEETBENCH_REWARD_RECALC`, the hash of the vendored `evaluation.py`, and the data tree hash (`benchmarks.md`). None is recorded today.
3. Exclude or flag the 4 unscorable verified tasks (and report the 276/280 ceiling), or fix `answer_position` parsing and say so.
4. Treat a `recalc_failed` case as an infrastructure error, not as a score of 0, when recalculation is part of the reward.
5. Use the isolated layout (section 6) so the agent cannot read or overwrite gold.

## 6. Isolation-relevant scorer facts (see also `setup_log.md`)
* Real-sandbox probe (`local/sandbox_probe.py`, no LLM): with the repo adapter, container code sees
  `['1_58687_golden.xlsx', '1_58687_init.xlsx', 'prompt.txt']` in `/mnt/data/spreadsheet/58687` (gold visible). With the
  gold-free agent view it sees `['1_58687_init.xlsx', 'prompt.txt']`; output writes still work.
* `patches/adapter_gold_dir.patch` (47 lines, applies cleanly to HEAD `e3cb51309`, **not applied to the repo**) adds `SPREADSHEETBENCH_GOLD_DIR`: gold is read from there for
  scoring (default = DATA_DIR, so behaviour is unchanged when unset). Verified: scores through the patched adapter with separated gold dir are identical to the unpatched adapter on the 4 e2e outputs above.
* The data dir is also where per-rollout outputs are created (`outputs/<run_tag>/`), so a read-only evaluator tree must be paired with a writable `outputs/` (the agent view provides it).

## Reproduction
```bash
BENCH=/home/dev/projects2/campaign-scratch/bench; cd $BENCH
# diagnostic matrix (no LLM). LO 7.1.8.1 = /bin/soffice (default); LO 25.8 via SPREADSHEETBENCH_LIBREOFFICE_BIN
DIAG_WORKERS=24 ./venv/bin/python -W ignore scorer_diag/scorer_diag.py $REPO data/extracted/spreadsheetbench_verified_400 verified_400 out/diag2 30 11
SPREADSHEETBENCH_LIBREOFFICE_BIN=$BENCH/lo258/root/opt/libreoffice25.8/program/soffice DIAG_WORKERS=24 ./venv/bin/python -W ignore scorer_diag/scorer_diag.py $REPO data/extracted/spreadsheetbench_verified_400 verified_400 out/diag3_lo258 30 11
# population ceiling
POP_WORKERS=32 ./venv/bin/python -W ignore scorer_diag/pop_check.py $REPO data/extracted/spreadsheetbench_verified_400 out/pop/AB_verified_lo71.json /bin/soffice
# adapter-level end-to-end score() test
./venv/bin/python -W ignore local/adapter_score_e2e.py patches/orig/adapter.py data/extracted/spreadsheetbench_verified_400 - 58687 out/e2e/x.json
```

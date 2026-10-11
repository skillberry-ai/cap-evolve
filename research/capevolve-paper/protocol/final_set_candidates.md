# Final-set candidates for Suite A (SpreadsheetBench): manifests, hashes, scorer readiness

Prepared 2026-10-11 by the benchmark/scorer steward. **Zero LLM calls. No final sample was drawn**; everything below is a candidate pool or a
feasibility measurement. Freeze the sample later with a seed over the manifests named here.
Inputs: `audit/fresh_test_candidates.md`, `audit/sb912_residual_exposure.csv` (provenance auditor); scripts in `experiments/tooling/final_set/`;
machine-readable manifests in `protocol/final_set/` (`sb912_residual_pool.json`, `sb2_candidates.json`).

Recommendation in one paragraph: use **SpreadsheetBench 2 Template + Financial_Model (197 tasks, 36 task families)** as the independent claim,
treat **Debugging (93 scorable tasks, only 10 workbook families)** as optional, and use the **912 residual pool (294 ids, 334 if the as-saved reward is primary)** for continuity with every
earlier SpreadsheetBench number. SB2 needs a new adapter (the current one cannot load it); partition SB2 **by family**, never by task.

## 1. SpreadsheetBench-912 residual pool (continuity candidate)

**Build rule** (all inputs are committed or in `audit/`; script `experiments/tooling/final_set/build_912_pool.py`, run on 2026-10-11, zero LLM):
start from the provenance auditor's 512 ids (`audit/sb912_residual_exposure.csv` = the 912 set minus verified-400) and keep an id only if all hold:

| step | rule | removes |
|---|---|---|
| 1 | top exposure role is `finalize-score-only` (scored at finalize in at most 2 `full` runs, nothing else) or `train-assigned-only` (never evaluated in a completed run) | 87 (optimization role: selection in `full`, pilot or smoke) |
| 2 | not in the public `sample_data_200` | 83 |
| 3 | no smoke-FIT, pilot or other design use in `roles`/`smoke_runs`/`pilot_val_runs` | 3 (`118-8`, `203-16`, `57448`) |
| 4 | the dataset must ship exactly 3 graded cases (the upstream defects 43026, 46444, 4714, 52964 ship 1 or 2; only `43026` and `46444` are in this 512) | 2 |
| 5 | scorable with the gold file as the output under the official comparator (as saved) | 3 (`147-7`, `52763`, `CF_25745`; the other 8 of the 11 failing ids are verified-400, sample_200 or were removed earlier) |
| 6 | scorable with the gold file as the output after LibreOffice 25.8.7.3 recalculation of the output (the recalc reward) | 40 |

Result: **294 eligible ids** (254 score-only, 40 train-only). `sorted-ids sha256 = 2f9163a019cfa40bb1f97f20a73826cdea2a169b11976d68fd9e23bcbc3d2da7`.
Step 6 is the strictest and only matters for the recalculated metric. If the primary metric is the as-saved score, the pool is **334 ids**
(`sorted-ids sha256 = d476edf70ef13cb79b37cbe1a5db3ab1ab5a140935a52167d4f206062d60405e`); the 40 ids are listed with reasons under `excluded` in the manifest.
Note the gold-as-output check was run on all 2,729 graded cases of the 912 set: 11 tasks fail under the as-saved comparator, 104 under LO 25.8.7.3 recalculation, 131 under LO 7.1.8.1; one gold file failed to convert at all with 25.8.7.3.

Manifest: `protocol/final_set/sb912_residual_pool.json` (summary, one record per eligible id, `excluded` list). Per-id fields:
`id`, `id_type` (int/str: half the ids are ints in `dataset.json`), `family` (the prefix N of an `N-M` id; `CF_*` -> `CF`; numeric ids are their own family),
`family_size_in_912`, `family_dev_exposed_members` (members of the same family that are in verified-400, sample_200 or an optimization role), `instruction_type`,
`n_cases` (3 for all), `exposure`, `full_split` (the CapEvolve `full` split they were in), `answer_cells`, `answer_cells_with_formula_in_gold`, `gold_has_formula_in_range`,
`instruction_chars`, `max_jaccard_to_verified400_instruction`, and the gold-as-output flags under both LibreOffice versions. The dataset carries no richer family/instruction metadata
than `instruction_type`, `answer_position`, `answer_sheet`, `data_position`.

**What the pool looks like (stratification-relevant):**
* instruction type: 165 Cell-Level, 129 Sheet-Level.
* **Type and formula answers are almost the same variable:** 162 of 165 Cell-Level tasks have formula cells in the gold answer range, and only 9 of 129 Sheet-Level ones. Under the as-saved reward formula answers are penalised, so stratify by `gold_has_formula_in_range` (171 True / 123 False), not only by instruction type.
* answer size: quartiles of `answer_cells` 5 / 18 / 80; instruction length quartiles 270 / 430 / 651 characters.
* 255 distinct families (8 with more than one member in the pool). **55 pool ids share a family prefix with a dev-exposed task** (verified-400, sample_200 or optimization role); 239 have no such sibling. If sibling leakage matters, use the `family_dev_exposed_members == 0` subset (n = 239); I did not check whether same-family `N-M` tasks actually share a workbook or instruction, only the id prefix.
* No instruction in the pool has token-Jaccard >= 0.6 with any verified-400 instruction (max 0.367), so no near-duplicates by that measure.

**Caveats, repeating the auditor's and adding mine:** these are the 512 tasks the expert verification did not retain (unvetted quality, original instruction text, 3-case hard scoring); public since 2025-04; local development runs are not visible; same forum family as the exposed 400. Excluding the 40 recalc-failing tasks removes mostly formula-heavy Cell-Level ones, which shifts the pool toward literal-valued answers; use the 334-id variant if the as-saved reward is primary.

## 2. SpreadsheetBench 2 (independent candidate)

### 2.1 What was pinned
| item | value |
|---|---|
| dataset | HF `KAKA22/SpreadsheetBench-v2`, revision `5a2215ed4121945ab09d8723df2995602090b042` (2026-09-10), MIT, ungated |
| file | `spreadsheetbench-v2-09-10.zip`, 134,232,213 bytes, sha256 `52699c974c30aced7125f3d12cdaabbbcbba8db804373d7397a5d3bdf68e5b3e` (equals the LFS oid on the Hub; downloaded with parallel ranges). The 2026-06-03 `spreadsheetbench-v2.zip` (sha `17147ef9...`) is a different file: do not mix. |
| extracted tree | 479 files, tree sha256 `3fc3988e2c61c7d5478a5de90d3162663c92c6c3481f93e35aff3bbf8c6934cb` (sorted `path\0sha256`) |
| scorer code | `RUCKBReasoning/SpreadsheetBench-2@5842db8f` (`main`, 2026-10-08), `evaluation/evaluation.py` used **unmodified** (585 lines, header "DO NOT EDIT"), `open_spreadsheet.py` 356 lines |
| LibreOffice used | 25.8.7.3 (rootless extract; the host 7.1.8.1 was not used for SB2) |

Categories (per-category `dataset.json` sha256, sorted-ids sha256, in `sb2_candidates.json`):

| category | tasks | families | tasks/family | scoring | in scope |
|---|---|---|---|---|---|
| Debugging | 100 | **10** (one workbook, 10 injected-error variants each; same golden and same `answer_position` within a family) | 10 | deterministic cell compare; 10 tasks compare formulas ("Embedded"), 10 compare font colour ("Color") | yes (optional) |
| Financial_Model | 100 | **20** (5 input variants per project, one golden) | 5 | deterministic cell compare | yes |
| Template | 97 | **16** (1 to 24 tasks per group, each task has its own input and golden) | uneven | deterministic cell compare | yes |
| Visualization | 24 | 24 | 1 | **VLM checklist (`glm-4.6v`), Windows chart export** | **no**: not deterministic, needs another model and credentials |

Ids are only unique **within a category** (`01_01` exists in all four), so use `<Category>/<id>` as the key. Total deterministic: 297 tasks in 46 families. No official split exists.

### 2.2 The official scorer in one paragraph
`compare_workbooks_with_regression(input, golden, output, answer_position)`: cells in `answer_position` (many sheets, ranges such as `'Ex 1 - LBO'!B1:AK95,...`) are split by comparing input against golden into
**modification cells** (golden differs from input) and **regression cells** (must stay the same). A task scores **1.0 only if the modification ratio is exactly 1.0 and the regression ratio is >= 0.998**, else 0.0;
numeric cells match within a 1% relative tolerance (absolute 0.01 when one side is 0); "not meaningful" placeholders (`N/A`, `#DIV/0!`, `-`, ...) are equivalent; None equals 0. It reads cached values (`data_only=True`), so the README
orders: recalculate the **inputs, the goldens and the outputs** with `open_spreadsheet.py` (LibreOffice) before use. That is path **C** below, and it is the only path whose result is "official".

### 2.3 Gold-as-output check (official scorer, 297 tasks, LibreOffice 25.8.7.3, zero LLM)
Same method as the verified-400 audit: the golden file used as the output, a copy with formulas kept but cached values dropped (what an agent writing formulas with openpyxl produces), and the unchanged input.
A = files as shipped, no recalculation; B = recalculate the output only; C = recalculate input, golden and output (the README path).

| category (n) | golden as output: A / B / C | formula-stripped golden: A / B / C | unchanged input passes (any path) |
|---|---|---|---|
| Debugging (100) | 93 / 84 / 93 | 10 / 55 / 60 | 0 |
| Financial_Model (100) | 95 / 90 / **100** | **0** / 75 / 85 | 0 |
| Template (97) | 97 / 97 / 97 | 12 / 96 / 96 | 0 |

* **No false positives**: the unchanged input never passes on any path.
* **12 structurally unwinnable tasks as shipped.** Debugging `05_01, 05_05, 05_06, 05_07, 05_08, 05_09, 05_10`: after classification there are zero modification cells (modification ratio is 0 by construction), so no output can score; they remain unwinnable on every path (7). Financial_Model `06_01..06_05`: the shipped golden/input cannot be opened by openpyxl (`unbound prefix` XML error), so path A cannot score even the golden; the README recalculation (LibreOffice rewrite) repairs the file and path C scores them 100/100. Under the official path C: **290 of 297 tasks are winnable** (Debugging 93, Financial_Model 100, Template 97).
* **As-saved scoring (A) is not viable for SB2**: a correct formula-bearing output scores 0 on all 100 Financial_Model tasks and 90 of 100 Debugging tasks, and the golden of one whole family cannot be opened. The recalculated path is required, which makes the engine part of the benchmark: record the LibreOffice version in every run, as with SpreadsheetBench 1.
* Path B (recalculate only the output) fails more correct answers than C (Debugging 16 and Financial_Model 10 golden-as-output failures vs 7 and 0), because the golden keeps Excel's cached values while the output gets LibreOffice's. Use C: recalculate input and golden once, offline, then each output the same way.
* The formula-stripped proxy still loses 15 to 40 percent under C (Debugging 60, Financial_Model 85, Template 96): LibreOffice 25.8 does not reproduce every Excel result and the 10 formula-compare and 10 font-colour Debugging tasks are sensitive to how the output was written. It is a proxy for a formula-writing agent, not a measurement of one.
* LibreOffice 7.1.8.1 (the host version) was not run on SB2; given the verified-400 result (5 vs 1 failures out of 30), expect more failures. Do not use it.

### 2.4 Can the current CapEvolve agent run it? No, not as is.
Probe (`sb2_adapter_probe.py`, real adapter code, `SPREADSHEETBENCH_DATA_DIR` pointed at each category): `Adapter.tasks()` raises `KeyError: 'instruction_type'` for all three. What the adapter needs:

1. a loader for the SB2 schema: `spreadsheet_path` is a **file** (not a task directory with `<n>_<id>_input.xlsx`), `golden_response_path` names the golden, no `instruction_type`, no `answer_sheet`/`data_position`, and ids need the category prefix;
2. the SB2 scorer (above) instead of `compare_workbooks`: needs the **input** workbook at scoring time (to classify cells), 1% tolerance, the font-colour and formula modes for the 20 special Debugging tasks, and a multi-sheet `answer_position` parser (sheet names with commas and spaces occur; the v1 parser already fails on such strings);
3. the recalculation pipeline of 2.3 path C, with the input/golden recalculation done once per family and cached;
4. an agent view that withholds the golden (it sits next to the inputs, e.g. `spreadsheet/01_Debugging/01_golden.xlsx` beside `input_files/`). The gold-name regex already matches every SB2 golden name (`*_golden.xlsx`), but the v1 input **allowlist** does not match SB2 input names such as `Double Counting_input.xlsx` or files inside `input_files/`, so the startup assertion would refuse an SB2 view until the allowlist is extended;
5. a prompt builder that survives many sheets: the v1 five-row preview of every sheet gives a first message of median **4.4k tokens (p90 38k) for Debugging, 10k (p90 21k) for Financial_Model, 0.7k (p90 1.0k) for Template** (characters/4; 5 Financial_Model previews failed to render), so a row/sheet cap is needed;
6. a larger turn budget and per-task container memory (input workbooks reach 8 MB; the scorer alone needed 4-7 GB RSS per worker on the largest Debugging family).

### 2.5 Cost and turns (no LLM; measured from the benchmark's own published trajectories and our files)
The authors' `trajectory_example.zip` (HF, sha256 `73217eb9...`) holds 5 SWE-agent trajectories per (model, category) for 8 frontier models, 160 files, with `api_calls` and `tokens_sent`. This is a **small, hand-picked sample, not a distribution** and the scaffold differs from CapEvolve's CodeAct loop; use it for order of magnitude only.

| category | API calls per task: median / p90 / max (cap 50) | input tokens per task (sum over calls): median / p90 | tasks that hit the cap |
|---|---|---|---|
| Debugging | 28.5 / 51 / 51 | 653k / 1.37M | 4 of 40 |
| Financial_Model | 29.5 / 51 / 51 | 904k / 1.88M | 5 of 40 |
| Template | 15 / 28 / 51 | 108k / 469k | 2 of 40 |

Reading: a Template rollout costs roughly one eighth of a Financial_Model rollout in input tokens. For planning, tokens per evaluation = tasks x trials x the median above: e.g. 40 Template tasks x 3 trials = about 13M input tokens; 40 Financial_Model tasks x 3 trials = about 108M. Dollar cost is not given because the gateway price of the agent models is unknown (`protocol/pricing.json` lists it as such). Scoring cost on this host: Template 12 s per task for all three paths, Debugging median 150 s and Financial_Model 213 s (largest Debugging workbooks several minutes), so evaluation wall clock is dominated by LibreOffice and openpyxl, not by the model.
For comparison, the frontier results quoted in the paper are 34.89 percent overall and 12 percent on Debugging, so headroom exists but a weak agent such as `gpt-oss-120b` or Gemma may sit near 0 on Debugging and Financial_Model (the same "no signal at baseline" risk as before); a pilot with the agent model on Template is cheap and tells you first.

### 2.6 Statistics that follow from the family structure
The 297 tasks are **46 clusters** (10 + 20 + 16). Debugging's 10 tasks per family share one golden and one `answer_position`; Financial_Model's 5 share a golden. A task-level sample overstates the effective n and leaks a family between dev and test. Draw the final sample **by family** (whole families to dev or to test), and use a family-clustered bootstrap for intervals. With Template + Financial_Model that is 36 families; with Debugging 46.

## 3. Ranking for Suite A

| rank | set | n (tasks / clusters) | independence | cost | readiness | main risk |
|---|---|---|---|---|---|---|
| 1 | **SB2 Template + Financial_Model** | 197 / 36 | never run, scored or discussed by CapEvolve (provenance audit) | Template cheap, Financial_Model about 8x a Template rollout | **needs a new adapter and scorer wiring (2.4)** | different task shape from every earlier number; weak-agent floor; LibreOffice dependence |
| 2 | 912 residual pool (294 / 334 ids; 239 with no dev-exposed sibling) | 294 / 255 families | weakly exposed (score-only in at most two `full` finalize runs, or never evaluated) | same as the existing runs | **works today** (agent view merged in #783) | unvetted tasks, formula/type confound, same forum family as the exposed 400 |
| 3 | SB2 Debugging (93 scorable) | 93 / 10 | as rank 1 | highest tokens, slowest scoring | needs the same adapter | 7 unwinnable tasks, only 10 independent workbooks |
| - | SB2 Visualization (24) | | | | VLM judge, Windows | not deterministic: exclude |

Open items before freezing: (a) decide the primary SB2 scoring path (recommend README path C on LibreOffice >= 25.8) and the LibreOffice pin; (b) pilot the agent on Template to see if the floor is above 0; (c) decide whether the 40 recalc-failing 912 ids stay excluded (depends on the 912 primary reward); (d) check whether same-family `N-M` ids in the 912 pool really share a workbook (only the prefix was compared); (e) ask the provenance auditor to log any use of these manifests in the exposure ledger from now on.

## 4. Reproduction
```bash
BENCH=/home/dev/projects2/campaign-scratch/bench; cd $BENCH
POP_WORKERS=48 ./venv/bin/python scorer_diag/pop_check.py $REPO data/extracted/all_data_912_v0.1 out/pop/AB_912_lo258.json $BENCH/lo258/root/opt/libreoffice25.8/program/soffice
./venv/bin/python scorer_diag/build_912_pool.py out/final_set/sb912_pool.json
SB2_WORKERS=40 ./venv/bin/python scorer_diag/sb2_check.py data/sb2/x/spreadsheetbench-v2 src/sb2_upstream/evaluation/evaluation.py out/sb2/check_lo258.json $BENCH/lo258/root/opt/libreoffice25.8/program/soffice
./venv/bin/python scorer_diag/sb2_adapter_probe.py data/sb2/x/spreadsheetbench-v2 out/sb2/adapter_probe.json
```

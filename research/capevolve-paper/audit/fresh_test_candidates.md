# Fresh final-evaluation candidates: exposure audit

Follow-up to `historical_results.md`. No commits, no LLM calls. Evidence: repo branches/history, issues, `benchmark-history` records, GitHub Actions artifacts, upstream GitHub/HF metadata. Supporting files: `artifact_manifest.json` (sha256 of everything downloaded), `sb912_residual_exposure.csv` (per-id roles for the 512 ids).

Scope of "exposure" below = what is recorded in the repo, its 200+ remote branches, issues/PRs, docs and the `benchmarks.yml` history. Local/off-CI development runs and internal (IBM/Red Hat) use cannot be seen from here; every label inherits that limit. All benchmarks here are public, so model pre-training contamination is separate and unmeasured.

## 1. Artifact manifest
`audit/artifact_manifest.json`: 6.6k+ files under `campaign-scratch/artifacts/history/` with sha256, size, run id, artifact name and GitHub expiry. Earliest GitHub expiries: `31331458168` 2026-11-07; the two SpreadsheetBench-912 `full` runs `30714307266` 2026-10-30 and `30762167950` 2026-10-31 (I downloaded both now; they were not in the first batch). Everything else expires 2026-12-24 or later. Non-run files (issues, PRs, upstream splits, datasets) carry `expires_at: null`.

## 2. tau2 retail, telecom, mock: exposure and versions

**Exposure: none recorded.** Evidence:
- `templates/adapters/tau2_bench/adapter.py:48` hard-codes `DOMAIN = "airline"`. Every CI task list (`ci/benchmarks/tau2/{smoke,integration,full}/tasks.json`, 50 airline ids 0-49), `tau2_custom` (`airline` and `airline_skillberry`), all `examples/tau2_*` splits and every `RESULTS.md`/`TAU2_SUMMARY.md` run are airline.
- Case-insensitive search of `origin/main` and all remote branches for `retail`/`telecom`: only (a) `docs/HOLDOUT_PROTOCOL.md:55` proposing them as the untouched option, (b) a registry log line in `examples/tau2_airline/run_full/demo.cast` listing installed domains (`mock, airline, retail, telecom, telecom-workflow, banking_knowledge`), copied into three branches, (c) one generic sentence on pass^k in a skill reference. No config, split, run record or result mentions them. `gh search` over issues and PRs for `telecom`/`retail`: no hits. Git history: only commit c0660c7cd/970c317ae (the HOLDOUT_PROTOCOL doc) and a demo-cast re-record add the words.
- `mock`: the only hits for "mock" near tau2 are the `mock` *optimizer skill* option, not the tau2 mock domain. Never used.

**Official splits** (`data/tau2/domains/<d>/split_tasks.json`; copies in `artifacts/history/tau2/{pinned,main}/`):

| domain | train | test | base | other | notes |
|---|---|---|---|---|---|
| airline | 30 | 20 | 50 | | exposed (see `historical_results.md`) |
| retail | 74 | 40 | 114 | | tasks.json = 114 |
| telecom | 74 | 40 | 114 | `small` 20, `full` 2285 | `full` = generated task groupings; `small` ⊂ `full` |
| mock | | | 10 | | too small |

**Versions.** Pinned commit `8ebb7499` (2026-06-22) vs current `main` `4ce7c039` (2026-10-07, 62 commits ahead, repo now branded tau3-bench; release v1.0.0 "τ³-bench" 2026-03-18, v1.0.1 2026-07-22). Git blob SHAs of every top-level data file for airline, retail, telecom and mock are **identical** at `v1.0.0`, `8ebb7499` and `main`; the split files are byte-identical at pinned vs main. Of the 62 commits since pinning, the only `data/` changes are in `banking_knowledge` (v1.0.1 grading fixes); the rest is voice/leaderboard/website/runner code. Retail and telecom task ids and content therefore do not differ across versions. (Nested `task_issues/` directory in retail was not diffed; the top-level `tasks.json` and `split_tasks.json` are the evaluation inputs.) The pinned version already carries the v1.0.0 "task quality" corrections.

## 3. SpreadsheetBench-912 minus verified-400 (512 ids)

Method: ids from the public 912 archive (`spreadsheetbench_912_v0.1`, 912 ids; note ~half are ints in `dataset.json`, strings in CapEvolve's lists). Roles from `full/split_ids.json` (verified inside the artifacts of both `full` runs: `splits.json` equals the committed split), `pilot/split_ids.json`, and the `tasks` lists in every spreadsheetbench `benchmark-history` record (smoke rosters across time). Completed 912-set runs: only `30714307266` and `30762167950` (tier `full`, gpt-5.5 agent, 10 iterations, selection on val-91, test-639 scored at finalize for champion and seed), plus 7 pilots (all ids drawn from `full` train) and 14 smoke runs (10 ids each, FIT metric). Cancelled/failed runs did not reach test.

Most intensive role per id (per-id table: `sb912_residual_exposure.csv`):

| top role | n | Cell-Level | Sheet-Level | meaning |
|---|---|---|---|---|
| optimization (val-91 selection in 2 full runs; pilot val-50; smoke FIT) | 87 | 61 | 26 | dev-exposed |
| finalize-score-only (`full` test; scored for seed and champion in 2 runs, 4 scorings) | 358 | 188 | 170 | outcomes recorded, never used for selection |
| train-assigned-only (`full` train; never evaluated in a completed run) | 67 | 37 | 30 | least exposed on record |
| never | 0 | | | |

Refinements: 66 of the 358 score-only ids are in the public `sample_data_200` (answers distributed); the two known 912-defect ids in this set (`43026`, `46444`; 1 test case instead of 3) are unwinnable at hard scoring; 17 of the train-only ids are also in sample_200. A conservative residual pool excluding sample_200 and the known-defective ids has **340 ids: 290 score-only + 50 train-only (183 Cell / 157 Sheet)**.

Answering the question asked: **358 ids are score-only exposed in ≤2 finalize runs and never used for design on record; 67 more were never evaluated in any completed run. Total clean-ish: 425 (340 after removing sample_200 and defects).** Caveats that stop this being an "untouched" label: (i) these are exactly the tasks the expert verification did *not* retain, so quality is unvetted (the verified re-release rewrote 226/400 instructions and changed 61 golden files; the 512 carry the original text and 3-case hard scoring); (ii) per-task outcome lists of the two full runs exist in `report.md` and history; (iii) local development on the adapter and the SkillOpt-comparison branches is unrecorded; (iv) the 912 have been public since 2025-04.

## 4. SpreadsheetBench 2 (arXiv 2606.29955)

- **Paper:** "SpreadsheetBench 2: Evaluating Agents on End-to-End Business Spreadsheet Workflows", submitted 2026-06-29; accepted NeurIPS 2026 (repo README). Best model 34.89% overall, debugging 12.00%.
- **Public and ungated:** code `RUCKBReasoning/SpreadsheetBench-2` (main `5842db8f`, 2026-10-08, evaluation/ + SWE-agent scaffold); data `KAKA22/SpreadsheetBench-v2` on HF (MIT, ungated, ~23k downloads). Latest dataset commit `5a2215ed` (2026-09-10, `spreadsheetbench-v2-09-10.zip`, 134 MB, sha in the manifest); the 2026-06-03 upload `spreadsheetbench-v2.zip` differs, so **pin the revision**. I downloaded the 09-10 zip.
- **Counts (from `dataset.json` in the zip):** Debugging 100, Financial_Model 100, Template 97, Visualization 24 = **321** (matches the paper). No official train/val/test split is shipped; ids are per category (`01_01` ...).
- **Deterministic scoring:** `evaluation/evaluation.py` (openpyxl cell comparison with 1% numeric tolerance, optional font color/formula checks) covers **Debugging, Financial_Model, Template = 297 tasks**. **Visualization (24) is scored by a VLM checklist (`glm-4.6v`)** through `run_visual_vlm_checklist_eval.py`, so it is neither deterministic nor credential-free. README warns every input/golden must be recalculated with `open_spreadsheet` before use (same cached-value pitfall as SpreadsheetBench v1). I did not verify whether the per-task metric is binary or a cell-fraction; check before choosing a pass criterion.
- **CapEvolve exposure: none.** No adapter, tier, split, run, issue or PR. The only occurrence in the repo is a related-work row on `site/skillsbench/proposals/cap-evolve-research-design.html` ("Optional stronger workflow transfer test"), copied into every branch. 
- **Practical cost:** tasks average 11.8 worksheets and ~594 cell modifications; needs a new adapter and probably a larger turn/token budget than the 30-turn v1 harness; Debugging/Financial_Model/Template are far harder (12-35% frontier accuracy), so headroom exists but baselines near zero would again make gains uninformative. 

## 5. SkillsBench

Upstream `benchflow-ai/skillsbench`: releases v1.0 (2026-06-12, "87-task snapshot") and v1.1 (2026-06-14, native `task.md` packages) are the only releases; no newer release. `tasks/` is 87 directories at v1.0, v1.1, CapEvolve's pinned commit `bf3793e9` and `main` (pushed 2026-07-23), and the 87 are exactly the 87 in `skillsbench-history/results.json` (0 added/removed). **However `tasks-extra/` holds 14 tasks present since the pinned commit that CapEvolve never ran** (zero mentions on main, `skillsbench-history`, `benchmark-history`): `cobol-gl-batch-reconcile, diff-transformer_impl, find-topk-similiar-chemicals, gh-repo-analytics, gpu-cluster-online-scheduling, mhc-layer-impl, nda-playbook-review, pedestrian-traffic-counting, pg-essay-to-audiobook, scheduling-email-assistant, speaker-diarization-subtitles, taxonomy-tree-merge, video-filler-word-remover, video-tutorial-indexer`. Upstream keeps them out of the default set because they are "credential-dependent or integration-incompatible" (e.g. Modal A100 for `mhc-layer-impl`). So: no newer *release*, but 14 never-touched tasks of unvetted runnability, too few to support a headline alone. (Families/categories of these 14 were not mapped.)

## 6. Ranked recommendation

### (A) Spreadsheet suite

| rank | set | n | exposure label (honest) | main risks |
|---|---|---|---|---|
| 1 | **SpreadsheetBench 2, Debugging + Financial_Model + Template** at HF rev `5a2215ed` (hold out a pre-registered test partition; develop on a separate partition) | 297 (partition e.g. 100/50/147 chosen once, digest committed) | **Never run, scored, discussed or used for design by CapEvolve** (verified across repo, 200+ branches, issues). Public since 2026-06 and re-uploaded 2026-09-10; model contamination unmeasured. Not a "sealed" set until we freeze a manifest | new adapter; different task shape from all previous results (cannot be compared with the v1 numbers); no official split; recalculation step; unknown metric granularity |
| 2 | **Residual 512 of SpreadsheetBench-912** | 340 conservative (290 score-only + 50 train-only), up to 425 | **Weakly exposed**: 358 score-only in 2 finalize runs (4 scorings, gpt-5.5, Aug 2026), 67 never evaluated in a completed run; no recorded design use; local dev unrecorded | not expert-verified; 3 graded cases (hard needs all 3); older instruction text; known defects (43026, 46444 test; 4714, 52964 in the 912 set per README); 66 ids in public sample_200; same task family as the exposed verified-400 (same forums), so the optimized prompt may transfer by construction rather than fresh generalisation |
| 3 | Fresh perturbed variants of verified-400 (HOLDOUT_PROTOCOL.md pattern) | any | Derived from exposed tasks: robustness test only, never "independent" | shares skill and failure modes with exposed set |
| 4 | SkillsBench `tasks-extra` 14 | 14 | Never run; but credential/GPU dependent | too small, heterogeneous |
| — | SpreadsheetBench verified-400 test 280 | | **Dev-exposed. Do not use** | |

Pair rank 1 and rank 2: rank 2 gives continuity with the existing agent/scorer and a same-benchmark generalisation claim; rank 1 gives the only clean independent claim. Report both scorers (as saved, recalculated) as in `historical_results.md`.

### (B) tau suite

| rank | set | n | exposure label | notes |
|---|---|---|---|---|
| 1 | **tau2 retail**, official split at pinned commit `8ebb7499` (task content identical on current main): develop on `train` (74); final = official `test` (40) scored once | 74 / 40 | **No recorded CapEvolve exposure** (never in any run, config, issue or doc beyond a proposal naming it). Public benchmark with public leaderboard; internal off-repo use unknowable | needs adapter domain parameterisation (`DOMAIN="airline"` hard-coded) and a retail seed capability (policy/tools); airline lessons (e.g. guard-code) may transfer so call it "new domain, same method family" |
| 2 | **tau2 telecom**, official `test` (40) with `train` (74); or `small` (20) for smoke only | 74 / 40 | Same label as retail. Different structure (user-side device troubleshooting) so a stronger independence argument; deterministic env-assertion reward | `full` (2285) is generated groupings; do not mix with `base`; adapter work larger |
| 3 | tau2 `banking_knowledge` (pin to v1.0.1 or later; data changed after the pinned commit) | | Never touched | retrieval-heavy, different surface; grading fixes make the commit pin essential |
| — | tau2 mock | 10 | never used, unusable (10 tasks) | |
| — | tau2 airline (all 50) | | **Dev-exposed. Do not use** | |

Note for both suites: the tau user simulator is an LLM, so even untouched tasks need ≥5-10 trials per task and a task-clustered CI; the airline instrument could not certify +0.02 effects (see `docs/TAU2_SUMMARY.md`), and retail/telecom will have similar noise. Freeze and commit the manifest digest (sha256 of sorted ids) of every final set before the first optimization run, and record every scoring of it in the exposure ledger.

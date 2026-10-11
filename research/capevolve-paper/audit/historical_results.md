# Historical results audit (CapEvolve)

Auditor: historical-result and provenance auditor. Scope: every number in the old draft (`paper_zip/paper.tex`, `numbers.json`, `CLAIMS_LEDGER.md`), the blog post, and the literature-review Appendix A/B disputed list. No LLM credentials were used and no benchmark was run. All recomputation is from downloaded GitHub Actions artifacts and committed records.

Companion files in this directory: `recomputed_numbers.csv` (40 claim rows), `exposure_ledger.csv` (17 rows), `provenance_issue_drafts/*.md` (12 drafts).
Scripts: `/home/dev/projects2/campaign-scratch/scripts/provenance/` (`sb_recompute.py`, `sb_pooled_ci.py`, `sk_recompute.py`, `make_*_csv.py`; run with `python3.12 -I`).
Raw downloads (not committed): `/home/dev/projects2/campaign-scratch/artifacts/history/`.

## 0. Method and the one fact that organises everything

Every SpreadsheetBench `benchmarks.yml` artifact cited by the draft was downloaded (`gh run download`, 20 runs, 176 MB). **None had expired.** Earliest expiry is the SWE-bench pilot `31331458168` on 2026-11-07, then `36175707483` on 2026-12-24; E-arm runs expire 2027-01-02..04. The 90-day clock is the largest preservation risk: archive these before 2026-11-07.

`metrics.jsonl` in each artifact carries per-task `reward_baseline`, `reward_opt` and, for later runs, **both** the as-saved metric (`hard_no_recalc`/`soft_no_recalc`) and the LibreOffice-recalculated metric (`hard_restriction`/`soft_restriction`) computed from the same output workbook. That is what makes the scorer sensitivity checkable.

Organising fact: the benchmark has **two scorers and two partitions**, and the draft, ledger, post and issues each mix them differently.

| era | runs | reward | split |
|---|---|---|---|
| A (pre #556/#568) | 36175707483, 36306060353 (and retracted 36261022325) | LibreOffice-recalculated | cap-evolve seed-42 80/40/280 |
| B | 36387149344 onward | as saved (no recalculation); recalc recorded as secondary | SkillOpt's released 80/40/280 |

The draft treats 63.2 -> 76.4 (era A) and 43.5 -> 76.5 (era B) as two views of one benchmark. They are not comparable.

## 1. Reproducible from artifacts (numbers confirmed to the decimal)

| claim | recomputed | note |
|---|---|---|
| Gemma+Opus 5: 43.5 -> 76.5, SD 1.5, Delta 33.0 [29.1, 36.8] | 43.53 -> 76.54, SD 1.46, 33.01 [29.1, 36.8] | draft derivation reproduces exactly; CI method is anti-conservative (below) |
| Post: 76.8 +/- 1.3, +33.0 +/- 1.5 | 76.76 +/- 1.28; Delta SD 1.45 | different denominator definition than the draft (post counts champion on all champion-scored tasks), same data |
| GPT-5.5+Opus 5: 38.5 -> 87.6 (SD 0.6), +49.1 [45.5, 52.8] | 38.50 -> 87.60, SD 0.57, 49.11 [45.5, 52.8] | 38.5 is an average of per-run paired baselines; the single seed measurement is 38.57 = 38.6 |
| GPT-5.5 recalculated baseline 77.5; optimized ~87.4 | 77.47; 87.37 | recalc gain +9.9, not +49 |
| Gemma no-skill 43.5 as saved / 58.3 recalculated | 43.5 / 58.3 (276 scored) | 119 pass under both, 42 only with recalc, 1 only as saved |
| Agent-mode 63.2 -> 76.4, 54/17/209 | 63.21 -> 76.43, 54/17/209 | era A, recalculated scorer, other split |
| E0..E4 finals and deltas (59.9/16.1, 73.0/29.6, 66.7/23.2, 65.1/21.5, 61.1/17.5) with CIs | all ten CIs match | per-arm n=1 |
| SkillsBench 50.8 -> 84.2; 71.3% (62/87); 73.6% (64/87) | 50.80 -> 84.22; 62/87; 64/87 | arithmetic only; it is a selection/fit metric |
| RH-SWE 58.0 -> 76.5, 24 up / 2 down | 58.0 -> 76.47; 24/2 | from the per-task graph in `benchmark-history` UI snapshot |
| SWE-bench pilot 68.0 / 72.0 rejected / 70.5; 6 infra of 50 | same | the same seed scored 63.6 and 70.5 on the same 44 tasks |

Seed integrity check: in all three Gemma champion runs the reused seed's per-task as-saved result equals the no-skill run's on every scored task (0/276, 0/275, 0/276 mismatches). The two GPT-5.5 no-skill measurements on two gateways agree on 260/280 tasks and both give 38.6.

## 2. Conflicts (numbers disagree, or the draft's framing is contradicted)

1. **SpreadsheetBench scorer (largest).** Under recalculation Gemma goes 58.3 -> 75.4/77.5/78.6 (+17 to +20), not +33; GPT-5.5 goes 77.5 -> 87.4 (+10), not +49. Roughly 14 (Gemma) and 39 (GPT-5.5) of the as-saved points are formula-to-literal compliance. Baseline and optimized were scored identically (both metrics come from the same file, the as-saved comparison taken before recalculation), so the comparison is fair *within* a scorer, and the headline must name the scorer. The historical scorer reads cached values (`openpyxl data_only=True`) with no LibreOffice recalculation, matching SkillOpt/WikiSkill. See drafts 01.
2. **Which split.** Draft ledger and README say "committed `split_ids.json`, seed 42". The three Gemma and three GPT champion runs were on **SkillOpt's** partition (verified: sha256 of sorted ids matches `split_source.json`; per-run `splits.json` has 280/280 ids in the SkillOpt test). Era A runs used seed-42 (194/280 test ids shared). Draft text calling the split "a size-matched reconstruction" is stale for the headline runs. Draft 02.
3. **Unreported 85.6.** `36306060353`, cited by the draft only as the "no-capability control" (62.9), is a hill-climb-all run whose empty-seed champion `cand_0001` scored **85.6** on the same 280 test tasks and scorer, versus 76.4 for the 8-round agent-optimize run. It is absent from the draft, ledger, README and issue #538. n=1 each, different seed (empty vs pristine), but it undercuts the agent-optimize headline. Draft 04.
4. **GPT-5.5 excluded run 36711181652.** Draft says it was excluded for "different commit and proxy" with a "baseline 10 points below". Actual cause: 55 of 280 champion test rollouts failed with LiteLLM `Budget has been exceeded`; 28.9 is the seed on the 225 surviving, non-random tasks (seed scores 38.6 on all 280). Exclusion is right; stated reason is wrong. Draft 06.
5. **Small-optimizer ablation labelling.** Draft's "E0 none (control)" 37204406089 (59.9, +16.1) is the pre-experiment `baseline`; the actual E0 replicate of issue #652 is `37345961613` (56.9, +13.4) and is missing from the draft, while the ledger's top P0 gap is "control replicate needed". Control-to-control spread is 3.0 points. E1's +13 to +16 over controls is real in direction but n=1, and "output guard" is bundled with sub-agent removal. Draft 07.
6. **tau2 held-out runner identity.** `docs/RESULTS.md` (Qwen section) says the 30/20 held-out run used a Claude runner; `docs/TAU2_SUMMARY.md` row 2 says gpt-oss-120b. The draft calls it "the stronger Claude agent". Draft 10.
7. **RH-SWE.** `docs/RESULTS.md` says "no committed artifact"; a per-task UI snapshot **is** on `benchmark-history`. Conversely the chart bars (55.7 / 73.1 / Opus 63.3) exist in no record. The post pairs a 76.5 fit value with the chart's Opus 63.3. Draft 08.
8. **CLAIMS_LEDGER optimizer spend** for run 36175707483 says $15.84; the record says $57.85 (15.84 belongs to the control run). `numbers.json` is right.

## 3. Unverifiable (no artifact; do not cite as results)

| claim | status |
|---|---|
| tau2 held-out 30/20: Claude 30.0 -> 47.5 | RESULTS.md says artifact "committed separately... until it lands"; never landed |
| tau2 `agent-optimize` 0.460 -> 0.545 (20 tasks x 10 trials), val 0.589 -> 0.678 | docs only; no per-task files on main or any branch |
| tau2 Qwen2.5-14B 17.0 -> 24.0 (tools) and 12.0 -> 27.0 (all); the surface "comparison" | no artifacts; baselines of the same model/split differ by 5 points (noise on 20 tasks) |
| `c_win` full-val gate fail (docs/RESULTS.md 2042-2096) | arithmetic reproduces (pooled -0.0146, SE 0.0181, z -0.81); raw blocks not committed |
| GLM 5.3 SWE-bench 85.9 held-out and 96.4% (482/500) (post) | no record produces either; nearest are PR #673/#699 (open, unmerged): test 86.9 -> 95.9 on 122 of 125 scored, `recovered: true` |
| optimizer transcript anecdote (169 shell calls / 166 oversized outputs) | from `skillberry-1` transcripts; issue #651 reports 303 calls / 179 oversized for the baseline arm; neither is in a committed record |
| SkillsBench 87-task run `20260903001` provenance | `event: local`, `sha: null`, `branch: null` |
| external numbers (WikiSkill 48.3/58.5/56.4/63.1/68.0, SkillOpt 41.8/80.7, Codex 85.0) | read from issues, not from the PDF; reported-not-reproduced |

## 4. Per-family: what the evidence supports, what is quarantined, minimal re-run

### 4.1 SpreadsheetBench Gemma-4-31B (Opus 5 optimizer)
- **Supports:** on SkillOpt's partition, as-saved scorer, hill-climb-all, 5 rounds, gate k_se 0.2, three optimizer runs raised the 280-test mean from a single seed measurement of 43.5 to 76.5 (SD 1.5). Under recalculation the gain is +18.7. Round 1 does most of the work (+18 to +21 val tasks).
- **Quarantine:** the cross-paper comparison with WikiSkill's 68.0 (their harness, tools, turns, decoding unknown; their scorer inferred, not stated); the "7 points ahead" language; "sealed test" (see exposure: no clean task remains); pooled-observation CIs; SD 1.5 as pipeline variance (n=3, one baseline).
- **Minimal re-run:** a new, never-looked-at partition (candidate source: the 512 SpreadsheetBench-912 tasks outside verified_400, after excluding ids the `full`-tier runs optimized on; these have 3 graded cases and older text, so they are a different benchmark variant and must be labelled as such), both scorers reported, baseline re-measured in the same run window, >=3 pipeline seeds, task-clustered bootstrap.

### 4.2 SpreadsheetBench GPT-5.5
- **Supports:** 38.6 -> 87.6 as saved; 77.5 -> 87.4 recalculated. Most of the as-saved gain is "write values not formulas".
- **Quarantine:** +49 as a capability gain; comparison with SkillOpt 80.7 (different optimizer, harness); 36711181652 numbers except as an infra incident.
- **Minimal re-run:** none needed for the numbers; report recalculated gain as primary; for any optimizer comparison, GPT-5.5 as its own optimizer.

### 4.3 Agent-optimize SpreadsheetBench (36175707483, 63.2 -> 76.4)
- **Supports:** an 8-round agent-optimize run on the seed-42 split under the recalculated scorer.
- **Quarantine:** all use as evidence that agent-optimize beats a simpler baseline; the 36306060353 result (85.6) contradicts that. Do not put 63.2 -> 76.4 in the same table as 43.5 -> 76.5.
- **Minimal re-run:** one agent-optimize vs one hill-climb-all run from the same empty seed, same split, same scorer, >=3 seeds each.

### 4.4 Small-optimizer (Gemma optimizing itself; E0..E4)
- **Supports:** with Gemma as optimizer, `output_guard + no_subagents` (E1) gave 73.0 vs control runs 59.9 and 56.9 (paired CI vs the 59.9 champion [+8.1, +19.1]); E2/E3 smaller gains; E4 (all four) not better than controls. Transcript-level mechanism (oversized-output loop) is plausible but uncommitted.
- **Quarantine:** "16.1 -> 29.6" as a single effect of the output guard (two changes bundled; E0 mislabelled); causal language from per-arm n=1.
- **Minimal re-run:** E0 and E1 x3 each plus `output_guard` alone and `no_subagents` alone, or a 2x2; commit the transcript statistics.

### 4.5 tau2 airline
- **Supports:** `run_full` 0.536 -> 0.712 is a committed fit metric. The agent-optimize series (4 nulls, then one accepted guard edit, then `c_win` failing full-val) is documented honestly in RESULTS.md; the instrument cannot certify +0.02 effects (needs ~178 trials/task).
- **Quarantine:** every held-out tau2 number in the draft/post (30.0 -> 47.5, 0.460 -> 0.545, Qwen), and any claim that agent-optimize improves airline. All 50 tasks are dev-exposed.
- **Minimal re-run:** requires a new task set (e.g. another tau2 domain or freshly authored airline tasks); with n>=10 trials, committed per-task artifacts, and a 2x2 surface design with matched baselines for any surface-width claim.

### 4.6 SkillsBench
- **Supports:** 87-task numbers as a per-task selection/fit metric (50.8 -> 84.2; 62/87 = 71.3% mixing 34 test and 53 val outcomes). 3-task pilot arithmetic.
- **Quarantine:** 71.3% as a pass rate; 55.6 -> 66.7 as generalisation (one trial of one task). The 87 run lacks a commit.
- **Minimal re-run:** per-task skills evaluated on held-out trials (fresh trials, same task) plus a task-level holdout of >=20 tasks not used in any sweep.

### 4.7 RH-SWE-bench
- **Supports:** a local run, 119 tasks, fit metric, 58.0 -> 76.5, per-task data on `benchmark-history`.
- **Quarantine:** the chart numbers and the Opus 63.3 comparison; "357 tasks"/"validation".
- **Minimal re-run:** a held-out slice of the 357 with a single scoring pipeline that regenerates both table and chart.

### 4.8 SWE-bench (pilot and GLM)
- **Supports:** pilot is a gate-behaviour anecdote (same seed 63.6 vs 70.5). GLM PR #673: 86.9 -> 95.9 on 122 scored of 125 as a PR claim, finalize recovered after a crash.
- **Quarantine:** 85.9, 96.4 (482/500), any SOTA comparison. The optimizer had gold and test patches for all 500 tasks and the evolved prompt tells the agent to fetch the upstream fix.
- **Minimal re-run:** offline/network-isolated run with no upstream access, decontaminated tasks (e.g. post-cutoff SWE-bench-Live style), >=3 trials.

## 5. Exposure status of the three asked-about sets (details in `exposure_ledger.csv`)

- **SpreadsheetBench 280-test: development-exposed, no untouched task.** Observed in 16 completed SkillOpt-split runs and 3 seed-42 runs; per-task outcomes published and used for design. 100 of 280 are the probe subset used as the test for #606/#622 conclusions; 40 (disjoint) were used as the **validation set** for four optimization runs in #622, chosen from test outcomes; the remaining 140 are score-only exposed. 200+80 ids also overlap the 912-task `full` tier by id (older text).
- **tau2 airline test (20 official): development-exposed.** Sealed-scored >=6 times with different candidates; 15 of 20 were train/val in the 26/12/12 runs; all 50 tasks fit in `run_full`.
- **SkillsBench: all 87 tasks are optimization tasks.** The 3-task pilot test tasks are also members of the 87-task sweeps.

## 6. Recommendation (keep history intact)

Do not rewrite earlier results. Add new auditable records that supersede framing, not data: (1) archive the 20 artifacts; (2) add a scorer-labelled results table (as saved and recalculated) for every SpreadsheetBench row; (3) publish `recomputed_numbers.csv` alongside; (4) mark exposed sets in `docs/RESULTS.md` and use new holdouts for any future headline; (5) file the drafts in `provenance_issue_drafts/` as issues.

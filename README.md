# spreadsheet-history

Results, recipes, and artifacts from running cap-evolve and nine competitor optimizers on **SpreadsheetBench `verified_400`**,
per the experiment plan in issue [#895](https://github.com/skillberry-ai/cap-evolve/issues/895). An orphan branch, unrelated to
`main`'s commit history, following the pattern of `skillsbench-history` and `parsec-history`.

## Why this branch exists

cap-evolve produces library code (adapters, scoring, CI), which belongs on `main` as reviewed PRs, and a **result narrative**: what a
run found, which candidates it tried, what a number does and does not mean. The narrative has no home on `main` and none on
`benchmark-history` (machine-written and pruned). This branch is where it lives.

## The experiment

| | |
|---|---|
| benchmark | SpreadsheetBench `verified_400`: 80 train, 40 val, 280 official test tasks ([`recipes/split_ids.json`](recipes/split_ids.json)) |
| agent / optimizer | Gemma-4-31B (instruction-tuned) / GLM-5.3 |
| systems | CapEvolve v1, CapEvolve v2, GEPA, GEPA-full, MIPROv2, SkillOpt, EvoSkill, Trace2Skill, Meta-Harness, WikiSkill, ACE |
| search budget | R = 2,160 counted rollouts per search, k = 3 trials per task, 3 seeds per system (33 searches) |
| test | one window per search on the 280 test tasks: 1,680 episodes, the frozen champion (840) and the seed (840) scored **in the same window** |
| headline | paired per-task gain (champion − same-window seed), with a CR1 standard error clustered by task |

**Deviations from the plan in #895** (each recorded in [`docs/decisions.md`](docs/decisions.md)). The main ones:
- The seed is re-scored in every test window and the gain is paired within the window, rather than comparing against a single seed run.
- 14 of the 33 windows ran the champion's 840 episodes first and then the seed's (ACE, GEPA s0/s2, GEPA-full, MIPROv2, WikiSkill).
  The other 19 interleaved the two in one shuffled order. Both orders use the same registered task list and the same pairing.
- CapEvolve v2 is CapEvolve at a later `main` commit (optimizer instructions "Improvement 2", gate k_se 0.2); see
  [`docs/HANDOFF_capevolve_v2.md`](docs/HANDOFF_capevolve_v2.md).

## Result

Full tables (train, val, test, sorted by gain and by absolute score): [`reports/results_tables.md`](reports/results_tables.md).
Per-seed figures: [`results/full_table.json`](results/full_table.json).

| system | mean test gain | per seed (s0 / s1 / s2) | SD across seeds |
|---|---|---|---|
| GEPA-full | +0.129 | +0.145 / +0.090 / +0.152 | 0.034 |
| SkillOpt | +0.119 | +0.098 / +0.123 / +0.134 | 0.018 |
| GEPA | +0.118 | +0.179 / +0.100 / +0.075 | 0.054 |
| WikiSkill | +0.097 | +0.089 / +0.086 / +0.115 | 0.016 |
| MIPROv2 | +0.096 | +0.093 / +0.135 / +0.062 | 0.036 |
| CapEvolve v2 | +0.095 | +0.075 / +0.068 / +0.143 | 0.041 |
| CapEvolve v1 | +0.090 | +0.142 / +0.066 / +0.061 | 0.045 |
| EvoSkill | +0.087 | −0.006\* / +0.143 / +0.123 | 0.081 |
| Trace2Skill | +0.054 | 0.000\* / +0.069 / +0.093 | 0.048 |
| Meta-Harness | +0.052 | +0.041 / +0.060 / +0.055 | 0.010 |
| ACE | +0.040 | +0.015 / +0.105 / 0.000\* | 0.057 |

\* **Inert seed**: the search ended with the seed itself as its champion, so its window compares the seed with itself (Trace2Skill s0,
EvoSkill s0, ACE s2). They are counted as about 0. In ACE s2 every candidate playbook carried a helper script that the common
pre-rollout helper gate rejects, so all three of its validation evaluations scored 0.0 and the seed stayed champion.

**How to read it.**
- Use the paired gain. The seed's own test score ranged 0.592–0.657 across the 33 windows (SD 0.018), so absolute champion scores
  partly reflect which window they ran in.
- Only the ends are separated. Ranks 4–8 lie within 0.010 of each other in mean gain, while a single system's seeds differ by an SD of
  0.016–0.081. With 3 seeds that middle order is not a ranking.
- Validation figures are optimistic: each champion was selected on val.

## Layout

| directory | what's in it |
|---|---|
| [`results/<system>/s<seed>/search/`](results/) | per search: `run_summary.json` (stop reason, champion, budget used), `run_meta.txt` (host, code sha, settings), `budget_probe.json` (the R-counter check), `isolation_scan.json`, `val_evals.jsonl`, `train_ids.txt`, `val_ids.txt`. CapEvolve keeps its own run state, so its searches have `run_main/` instead (champion, baseline, history, eval index, journal, insights). |
| [`results/<system>/s<seed>/test/`](results/) | per test window: `summary.json` (paired gain), `summary_champion_only.json` (champion-first windows), `registry.json` (champion and seed file hashes, order hash, registered before the first episode), `per_task_test_scores.json` (per-task mean for champion and seed) |
| [`results/full_table.json`](results/full_table.json) | the per-seed train/val/test figures behind the tables |
| [`artifacts/seed/`](artifacts/seed/), [`artifacts/<system>/s<seed>/champion/`](artifacts/) | the seed capability and each frozen champion exactly as scored; the file hashes match `registry.json` |
| [`recipes/<system>/`](recipes/) | each system's arm code and LSF launcher, `BUILD_RECORD.json` and `deviations_<system>.json` (where our port differs from the published method); `recipes/common/` is the shared rollout and budget layer; CapEvolve's are its project templates |
| [`scripts/`](scripts/) | the test-window runner, the metering gateway, the automatic test launcher, the LSF wrappers, the table builder, and the script that staged this branch |
| [`docs/decisions.md`](docs/decisions.md) | the append-only decision log of the whole experiment, including every incident and relaunch |
| [`reports/`](reports/) | the final tables |
| [`ui/results.html`](ui/results.html) | a self-contained, sortable results page: one row per system, every seed, and a cost and time table (tokens and wall time from the gateway ledgers in [`results/usage.json`](results/usage.json)); built by `scripts/build_results_page.py` |

Every headline number can be re-derived from this branch alone: each `summary.json` gain equals the mean over tasks of
champion − seed in the matching `per_task_test_scores.json`.

## Not on this branch

The raw per-rollout and per-episode ledgers, the gateway call ledgers, the LSF logs and the full run folders are kept off-repo in
`cap-evolve-archive/spreadsheetbench-exp895/`. The benchmark data itself is not stored anywhere here, because it contains the gold answers.

## Caveats

- The competitor ports are ours, built from each published method; `recipes/<system>/deviations_<system>.json` lists the differences.
- Many searches and windows were resumed or relaunched (lost hosts, model-endpoint slowdowns, engine errors in WikiSkill and GEPA,
  a stalled window). Infra failures are retried and never scored 0; candidate errors score 0. Each case is in `docs/decisions.md`.
- `run_meta.txt` and the logs record CCC cluster host names and workarea paths; they identify where a run happened and carry no credentials.

# SpreadsheetBench `full_verified` — Gemma-4-31B-It, agent-optimize, seed 1 of 3

Complete record of run [36175707483](https://github.com/skillberry-ai/cap-evolve/actions/runs/36175707483):
the first cap-evolve result on a **held-out** SpreadsheetBench split that is a candidate for
comparison with WikiSkill / SkillOpt / EvoSkill.

Everything here is what you need to **audit**, **replicate**, or **continue** the run. The GitHub
Actions artifact expires ~90 days after the run; this directory does not.

---

## Result

| | val (40 tasks) | **sealed test (280 tasks)** |
|---|---|---|
| seed capability | 0.625 | **0.6321** |
| champion `r3_decide` | 0.8875 | **0.7643** |
| delta | +0.2625 | **+0.1321 (+21% rel)** |

Per-task on the sealed split: **54 improved · 17 regressed · 209 unchanged.**

`test` is disjoint from `train`/`val` — the optimizer never saw these 280 tasks. The val→test
drop (0.8875 → 0.7643) is the expected selection-optimism gap; the *seed* held steady across the
two splits (0.625 → 0.6321), which is the check that the partition behaves.

### Round trajectory

Candidate rewards are the booked values from `data/steps.jsonl`; controls are the two
byte-identical null replicates gated in the same round (`data/events.jsonl`, `split=val`).

| round | candidate | val | concurrent controls | verdict |
|---|---|---|---|---|
| — | `seed` | 0.6250 | — | baseline (also ran train: 0.5696) |
| 1 | `r1_contract` | 0.7750 | 0.6750 / 0.6250 | **accept** |
| 2 | `r2_numeric` | 0.8462 | 0.8421 / 0.7949 | reject |
| 3 | **`r3_decide`** | 0.8974 → grow 0.8750 → **0.8875** | 0.8462 / 0.8500 | **accept** |
| 4 | `r4_silent` | 0.8421 | 0.8205 / 0.8974 | reject |
| 5 | `r5_verdict` | 0.8000 | 0.9231 / 0.8718 | reject |
| 6 | `r6_scope` | 0.7692 | 0.8250 / 0.8718 | reject |
| 7 | `r7_path` | 0.8462 | 0.8974 / 0.8684 | reject |
| 8 | `r8_cut` | 0.8750 | 0.8718 / 0.8947 | reject |

The champion comes from **round 3**; rounds 4–8 found nothing better. Controls rise through the
run because a control is a null edit of the *current champion*, not the seed — so the bar moves up
after each accept, which is why later rounds keep failing.

### Cost and scale

| | |
|---|---|
| Suite wall clock | **18.5 h** (2026-09-25 18:49Z → 2026-09-26 13:21Z) |
| Rollouts actually spent | **1,943** |
| Agent tokens | **146.7 M** |
| Optimizer cost | **$57.85** (Opus 5) |
| Agent cost | **not metered** — litellm has no pricing table for a RITS-proxied model |

> The `>>> plan:` line printed **920** rollouts as an "upper bound". The real figure was **1,943**
> — 2.1×. In agent mode the projection models only `baseline + iterations × val + finalize`; it
> does not model the agent's concurrent **controls** (2 per round), its **cheap screens**, the
> **train-split diagnostic** eval, or **grow**. Treat it as a floor, not a bound, until fixed.

---

## Exact provenance

| | |
|---|---|
| Run | [36175707483](https://github.com/skillberry-ai/cap-evolve/actions/runs/36175707483) · `workflow_dispatch` |
| Commit | `da4781c8c51a48f2c2bd7fb0cfc779d3940bf05b` on `main` |
| Benchmark / tier | `spreadsheetbench` / `full_verified` |
| Dataset | **`verified_400`** — `SPREADSHEETBENCH_VARIANT=verified_400`, fetched by `ci/benchmarks/spreadsheetbench/fetch_data.sh` (log: `fetching SpreadsheetBench verified_400`) |
| Split | committed `ci/benchmarks/spreadsheetbench/full_verified/split_ids.json` — **80 train / 40 val / 280 test**, seed 42, ratios 2:1:7 |
| Agent model | `rits/google/gemma-4-31B-it` (lite-rits proxy on skillberry-1) |
| Optimizer | `aws/claude-opus-5` via `claude-code`, `--budget 1350` min |
| Algorithm | `agent-optimize` (`orchestration_mode: agent`) |
| `iterations` / `trials` | **8** / **1** |
| `gate_k_se` | 1.0 |
| Scoring | **`SB_SCORING=hard`** (`full_verified/overrides.env`). On this dataset hard **==** soft: the verified release grades ONE case per task, so this is a native hard score. |
| Agent turn budget | `SPREADSHEETBENCH_MAX_TURNS=30` (tier default, `run_suite.sh`) |
| Container concurrency | `SPREADSHEETBENCH_CONCURRENCY=8` (tier default) |
| Seed capability | **pristine** (`warm_seed: false`) — `templates/adapters/spreadsheetbench/seed_capability/` at the commit above |
| Rollout seeding | `SPLIT_SEED` from repo var `BENCH_SPLIT_SEED` (unset → `0`). The partition is fixed by the committed file, so this varies only per-trial rollout seeding. |

---

## What is in here

```
champion/            the accepted capability (r3_decide) — this IS the optimized artifact
  prompt.md            system prompt
  task_template.md     per-task user message
  PROCESS.md INSIGHTS.md JOURNAL.md LEDGER.md RUNMAP.md
  META_INSIGHTS.md FRAMEWORK_IMPROVEMENTS.md
  capability.diff      seed -> champion, unified diff
rounds/rN_name/      every round the agent attempted, accepted or not
  diff.patch           that round's edit
  PROCESS.md           the agent's own root-cause analysis for that round
data/
  report.md            rendered report incl. all 280 per-task test rows
  metrics.jsonl        280 per-task test records
  steps.jsonl          12 booked steps (baseline, 8 rounds, finalize, finalize_baseline)
  events.jsonl         142 events — every eval_start/evaluate/screen/gate decision with timings
  runmeta.json         run identity + dispatch config
host/
  driver_prompt.md     the briefing the optimizer agent was launched with (incl. stop_condition)
  launch_args.json     exact argv
  transcript.jsonl.gz  full optimizer transcript (152 KB gz) — every tool call and decision
```

The 9 MB interactive UI snapshot is not duplicated here; it is published at
`runs/36175707483__full_verified-spreadsheetbench/` on the `benchmark-history` branch.

---

## Replicate

```bash
# 1. same commit
git checkout da4781c8c51a48f2c2bd7fb0cfc779d3940bf05b

# 2. same dataset (15 MB; NOT a filter of the 912-task set — see fetch_data.sh)
SPREADSHEETBENCH_VARIANT=verified_400 ci/benchmarks/spreadsheetbench/fetch_data.sh

# 3. same dispatch
gh workflow run benchmarks.yml --ref main \
  -f benchmark=spreadsheetbench -f tier=full_verified \
  -f agent_model=rits/google/gemma-4-31B-it \
  -f optimizer_model=aws/claude-opus-5 \
  -f algorithm=agent-optimize -f iterations=8
# trials and optimizer_usd_per_iter left blank -> 1 and unlimited (tier defaults)
```

Expect ~18–21 h on the `ibm-vpc` runner. Exact reproduction is **not** guaranteed: the agent and
the optimizer are both sampled, and whether the RITS endpoint honours the per-rollout `seed` is
unverified. Treat this as one draw from the pipeline distribution.

## Continue from the champion

`champion/` is a complete capability directory. To start a new run from it instead of the
pristine seed, install it as a warm seed — the mechanism already exists and is used by the
`pilot` tier (`SB_WARM_SEED=1` + `templates/adapters/spreadsheetbench/seed_capability_warm/`,
which carries a `PROVENANCE.md` naming its origin run).

Doing so makes the run's `base→opt` delta **not** a from-scratch number, exactly as
`pilot/overrides.env` documents. Record the provenance if you do it.

---

## Fair comparison: what this number can and cannot be set against

WikiSkill (arXiv 2608.27454v1) Table 1, SpreadsheetBench column, **Gemma-4-31B**:

| | no skill | Trace2Skill | EvoSkill | SkillOpt | WikiSkill | **this run** |
|---|---|---|---|---|---|---|
| Gemma-4-31B | 48.3 | 58.5 | 56.4 | 63.1 | 68.0 | **76.4** |

**Comparable:** the absolute sealed-test score, the dataset (their 80/40/280 = the verified 400),
the metric (native hard score), the model, and a genuinely held-out test split.

**NOT comparable, and why:**

1. **Our baseline is not their "no skill".** Our seed scores **63.2** — essentially SkillOpt's
   63.1 and far above their no-skill 48.3 — because it is a tuned prompt plus a task template, not
   an empty context. So our **+13.2 delta cannot be set against their +19.7** (48.3 → 68.0). Only
   the absolute figures are candidates for comparison.
2. **One seed, not three.** The paper reports "the average test performance across three
   independent runs of the entire evolutionary pipeline". This is a single draw. Pipeline variance
   (which candidate gets accepted) is much larger than the ~0.03 measurement SE on 280 tasks.
3. **The split is a documented reconstruction, not their split.** Sizes match (80/40/280, seed 42,
   2:1:7) but the actual partition is ours. Different tasks are in test.
4. **Their baselines are reported, not reproduced.** We did not run Trace2Skill / EvoSkill /
   SkillOpt. This compares cap-evolve against their *published* numbers.
5. **Their iteration and turn budgets are never stated.** Ours are 8 rounds and 30 agent turns.
6. **No paired significance test.** They use paired bootstrap (1,000 resamples, p<0.05) over the
   test split. `data/metrics.jsonl` has the 280 per-task rewards needed to run one.

## Open finding: 17 regressions

Every regression sampled went **1.000 → 0.000** (`60-7`, `384-4`, `82-38`, `183-8`, `192-22`,
`387-16`, `524-31`, `560-12`, `45635`, `48643`, …). The champion trades whole solved tasks for
others: 54 gained, 17 lost. Net strongly positive, but a 40-task val split cannot see this, and
`rounds/r3_decide/PROCESS.md` plus the full per-task table in `data/metrics.jsonl` are the place to
start on it.

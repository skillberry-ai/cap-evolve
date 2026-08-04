# SpreadsheetBench tier configuration

Three tiers, with **different purposes and different honesty guarantees**.

| | `smoke` | `pilot` | `full` |
|---|---|---|---|
| Tasks | 10 | 60 (from `full`'s train split) | 912 (all of SpreadsheetBench original) |
| Split | **no-holdout FIT** | 5 / **50** / 5 — sized to measure | **held-out** — 182 / 91 / 639, disjoint |
| `finalize` number is | a FIT metric | **meaningless** | a real generalization number |
| Agent turns | 5 | **30** | **30** (SkillOpt parity) |
| Container concurrency | 4 | 8 | 8 |
| Runs on `tier=all`? | yes | **no — explicit only** | yes |
| Purpose | cheap, fast CI signal | cost/runtime measurement | paper comparison |

Only `full` produces a number that may be put next to a paper. The smoke report labels itself
`train==val==test (FIT metric, not a generalization/held-out claim)`.

## The `pilot` tier — a measurement rig, not a benchmark

`pilot` exists to answer three questions before a ~$450 full run is launched:

1. **What does a rollout cost and take at `MAX_TURNS=30`?** Every other anchor comes from
   smoke at 5 turns and does not transfer.
2. **Does `azure/gpt-5.5` work on the gateway at all?** Nothing has exercised it yet.
3. **Does the parallel LibreOffice recalc hold up at non-trivial volume?**

Its split is deliberately *not* 2:1:7. `val` is 50 because that is what every iteration
evaluates (full's is 91, so one pilot iteration extrapolates directly); `test` is 5 because
`finalize` evaluates it twice and teaches nothing new about per-rollout cost; `train` is 5
because with `algorithm_focus: all` the train split is never evaluated.

> **Pilot reward numbers are not comparable to anything** — not to SkillOpt, not to `full`, not
> across pilot runs. A 5-task test split is a cost probe, not a measurement of quality. This is
> why `pilot` is excluded from `tier=all`: the aggregate job publishes every leg to
> `benchmark-history`, and sweeping it in would put meaningless rows on the benchmarks page.

Pilot tasks are drawn **only from `full`'s train ids**, so `full`'s selection and test splits
stay untouched by any pilot run. Regenerate with:

```bash
python3 ci/benchmarks/spreadsheetbench/utils/make_pilot.py --write
```

Suggested dispatch — `tier=pilot`, `trials=1`, `iterations=2`, `agent_model=azure/gpt-5.5`.
At those settings it is `50 + 2×50 + 2×5` = **160 rollouts**.

## The held-out split

`full/split_ids.json` is committed, and `run_suite.sh` uses it instead of the default
no-holdout split because it exists. Regenerate with:

```bash
python3 ci/benchmarks/spreadsheetbench/utils/make_split.py --write
```

### What it reconstructs — and what it does not

It reconstructs **SkillOpt's stated default** (arXiv 2605.23904):

- `split_seed = 42` — stated globally in the paper.
- **2:1:7** train/selection/test — Appendix C's "default 2:1:7 split when no benchmark-specific
  split is stated", which the train-size ablation protocol repeats.

These are **our** choices, because the paper does not publish them:

- **No SpreadsheetBench-specific split is given**, so the 2:1:7 default is applied.
- **No SpreadsheetBench task count is given**, so all 912 tasks are used.
- Table 2's caption says **4:1:5**, but for an *ablation panel*; two other mentions say 2:1:7,
  so 2:1:7 is taken as the headline configuration. If that reading is wrong:
  `make_split.py --ratios 4,1,5 --write`.

> **Therefore: this is a documented reconstruction, not a reproduction of SkillOpt's split.**
> Any comparison must say so. Do not describe a result here as "on SkillOpt's split".

### Seeds

The partition is fixed by the committed file, so `SPLIT_SEED` varies only the **per-trial
rollout seeding** — which is what makes independent seeds possible on one split. For the
"≥3 seeds" requirement, set the repo variable `BENCH_SPLIT_SEED` to `42`, then `43`, then `44`
between dispatches. (`workflow_dispatch` caps inputs at 10 and that list is full, which is why
this is a repo variable rather than an input.)

## Editable scope — how "skill text only" is actually enforced

SkillOpt edits a **single natural-language skill document, skill text only**. Here:

- `capabilities: [system-prompt]`, and the seed capability is a **single `prompt.md`** with no
  scripts. There is nothing but text to edit.
- This is a *closer* match than `capabilities: [skill-package]` would be — skill packages also
  ship scripts, which is precisely the scope difference to avoid.
- **`actions: [edit]` is not a machine-enforced constraint.** It appears in some example specs
  but nothing in `core/` or `skills/` reads it. Scope comes from the capability selection above,
  which *is* passed to the optimizer. Do not cite `actions:` as a guarantee.

Our seed is ~190 tokens; SkillOpt's initial skill artifact was **224 tokens**, growing to 1,995
over 4 accepted edits — so seed-to-seed the starting points are comparable.

## Reading a result against the paper

SkillOpt's GPT-5.5 direct-chat column: **No skill 41.8 · human skill 72.9 · GEPA 73.6 ·
SkillOpt 80.7**.

- Compare our **sealed test %** against 80.7 / 73.6 / 72.9.
- **Do not equate our seed baseline with 41.8.** Their "No skill" is the frozen model run with
  *the benchmark's default system prompt* — not an empty context, and not our tuned seed. Their
  own optimization started from a 224-token seed skill whose score the paper does not report.
- Their harness rows use different baselines again (Codex 27.5, Claude Code 22.1), so pin one
  harness and say which.

## Cost and runtime, before you launch a full run

Per-iteration evaluation hits the **91-task selection split only** (with `algorithm_focus: all`
the train split is never evaluated; `finalize` evaluates test twice — best and baseline).

At `trials=1, iterations=10`: `91 + 10x91 + 2x639` = **2,279 rollouts**. Measured smoke rate was
~$0.048/rollout and ~13 s/rollout wall at concurrency 4, so roughly **$110–150 and ~10 h per
seed** — but that anchor predates `MAX_TURNS=30`, and more turns means more cost and more wall
clock per rollout.

**Run a ~50-task pilot at `iterations=2` first** and re-derive both numbers before committing
to 912 x 3 seeds. Also note the shared model gateway has a spend cap; a four-figure run will
start returning `429 budget_exceeded`, which zeroes every rollout.

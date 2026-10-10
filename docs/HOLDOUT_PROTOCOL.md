# Holdout protocol (tau2 airline)

Why this exists: a result is only as honest as the data it was never allowed to influence. This page
says what we can and cannot claim on tau2 airline, and how every report must label it.

## The hazard: train == val, and a spent test split

- tau2 airline has **50 tasks**. Optimization uses tasks **0-29**; they are both the search signal
  (train) and the gate (val). Selecting the best of many edits on the same 30 tasks inflates the
  winner's val score ("winner's curse"), so val is a fit metric, not a generalization estimate.
- Tasks **30-49** (the old test split) were already scored in run `run_20261008_150326`: its
  `splits.json` has `"test_used": true` (20 test ids), `final.json` holds the test score of the
  optimized capability (0.733) and of the baseline (0.683), and `report.md` states the test was scored
  once for both. The artifacts show the *scoring*; they cannot show whether that number later steered
  design decisions, so we treat 30-49 as **development-exposed**: no longer untouched, even though no
  test trace was read.
- **There is no fresh, untouched holdout inside tau2 airline's 50 tasks.** We state this plainly;
  we do not fabricate one. Splitting the 30 optimization tasks further (for example 25 + 5) gives a
  validation set too small to resolve effects of the size we see (a +0.05 mean effect on 30 tasks
  is not resolvable below ~500 rollouts; see `research/design/eval_statistics.md`).

## Rules

1. **No test traces in edits.** The optimizer, the agent, clustering, digests and pre-gate fixtures
   read only rollouts of tasks 0-29. Test rollouts are aggregate-only artifacts; nothing derived from
   a test task (ids, failures, tool calls, feedback text) may enter a prompt, a fixture or a policy.
2. **Test is scored once, at the designated finalize step**, on the final champion only, and the
   score is recorded with its checkpoint name. No test number is used to pick between candidates,
   to decide whether to continue, or to tune a threshold. A second look at test creates a new
   exposure and must be logged as such in the report.
3. **Sentinels and probes come from val only** (`merge_n` already refuses test ids).
4. **Ablations and the simulator never touch test.** The simulator is built from val rollouts.
5. **Everything is seeded and ledgered**: evidence is pooled per capability hash and `env_fp`; a
   change of agent or user-sim model starts a new pool.

## How results must be labelled

| result | label it as |
|---|---|
| offline replay / simulator (`ablate.py replay`, `sim`) | "SIMULATED / REPLAYED OFFLINE - NOT EVIDENCE OF REAL AGENT PERFORMANCE" (the tools print this; keep it) |
| real run, val 0-29 | "optimization set (train == val), selection-biased" |
| real run, test 30-49, scored once | "development-exposed split, scored once at <checkpoint>" |
| any claim such as "90%" | "on a development-exposed split of tau2 airline" until a fresh benchmark confirms |

Every report states: the task ids used for optimization, whether test was scored and when, the
number of candidates tried (the selection pressure), and the seeds.

## What would give an untouched claim

Neither is built here; both are options for whoever needs an external claim:

- **Variants**: generate perturbed versions of tasks 30-49 (changed names, ids, dates, amounts,
  reworded user scripts) *before* any further design work, freeze them, and score once. They share
  the policy and tools with the exposed tasks, so this measures robustness, not full independence.
- **Another domain** (tau2 retail or telecom, or another benchmark): the only fully untouched
  option. Run the frozen champion on it exactly once.

## Real ablations

`ablate.py real` is a dry run: it writes one spec per arm (only an `optimizer.ablation` block is
added to the base spec) and prints `cap-evolve run` commands. A human or agent runs them, a few seeds
first on a smoke budget, on tasks 0-29 only. The simulator's ranking of arms must not be quoted as a
finding; only the real runs' numbers, labelled per the table above, may be.

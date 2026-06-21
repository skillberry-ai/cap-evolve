---
name: gepa
description: Runs the real GEPA optimization loop (arXiv:2507.19457) — sample-efficient reflective Pareto search. Use when rollouts are expensive and the scorer gives informative per-task feedback, and you want the most quality per evaluation. Each iteration samples a parent from a per-instance Pareto frontier, evaluates it on a cheap minibatch of train tasks with full traces, builds a reflective dataset over the failures, asks the optimizer for one targeted component edit, re-checks the child on the same minibatch (a cheap local gate), and only on pass pays for a full-val eval behind the honest significance gate. Adds round-robin component focus and a system-aware merge across complementary lineages. Prefer over hill-climb when feedback is rich and budget is tight; use hill-climb for the first baseline run or feedback-poor binary tasks.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer 'CMD {workdir} {prompt}' [--max-metric-calls N --minibatch-size 4 --component-selector round_robin|all --max-merges 2]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, reflective_dataset, candidate]
sources: [gepa]
---

# gepa — the real sample-efficient reflective Pareto loop

GEPA (Agrawal et al., 2025, arXiv:2507.19457) is the highest-ceiling member of the
family. Its power comes from a **two-stage economy** that spends cheap rollouts to
decide whether a candidate is worth an expensive honest evaluation, plus reflection
on **traces** (not scalars) and a **per-instance Pareto frontier** that keeps
specialists alive. This skill is a thin wrapper over `cap_evolve.gepa.gepa_loop`;
all honesty-critical machinery (splits, gate, seal, stats, cache) is the engine's.

## The loop

1. **Select a parent** by sampling the per-instance Pareto frontier *frequency-
   weighted* — each non-dominated candidate's weight is how many val instances it is
   best at, so a specialist that uniquely tops one task is kept (seeded RNG, logged).
2. **Sample a minibatch** of `--minibatch-size` (default 4) **train** ids.
3. **Eval the parent on the minibatch with traces** (cheap; eval-cached).
4. **Build a reflective dataset** over the parent's FAILING minibatch tasks — input
   + the agent's output/trajectory + feedback — written as `REFLECTION.md` in the
   optimizer workdir, plus a round-robin **component focus** as `FOCUS.md`. Invoke
   the optimizer.
5. **Eval the child on the SAME minibatch**; **local gate** `sum(child) >
   sum(parent)`. This is the economy: a proposal that doesn't even help the
   minibatch is rejected here, before any full-val cost.
6. **On local-gate pass only**, pay for a **full-val** eval and apply the honest
   significance gate (paired, val-only — the same gate hill-climb uses). On accept,
   the child joins the pool and the per-instance frontier.
7. **System-aware merge** (every `--merge-cadence` accepts, up to `--max-merges`):
   find two frontier dominators sharing a common ancestor both beat, recombine
   component-by-component (each component from whichever descendant changed it),
   minibatch-gate, then full-val + standard gate.

**Budget is in rollouts/metric-calls** (`--max-metric-calls`, primary) — both
minibatch and full-val evals count — with `--max-iterations` as a secondary cap.
The **test split is never touched**; minibatch/merge evals draw from train/val only.

## When to use vs. hill-climb / skillopt

| Situation | Use |
|---|---|
| Rich per-task feedback + expensive rollouts; want max quality/eval | **gepa** |
| First run / need a yardstick baseline | hill-climb (`--focus all`) |
| Binary pass/fail, no diagnosis in feedback | hill-climb (reflection has little to chew on) |
| Tiny task set (frontier collapses to 1–2 points) | hill-climb |
| Want a fixed edit-budget schedule + epoch slow-update | skillopt |
| Single global-best lineage is fine and merges add no value | hill-climb / skillopt |

GEPA's economy (minibatch gate + frontier) pays off precisely when evaluations are
costly and feedback is informative; otherwise the bookkeeping doesn't earn its keep.

## Focus modes

- **`--component-selector round_robin`** (default): each iteration focuses ONE
  component (cycled across the parent's editable files), so every proposal is a
  small, attributable change — the unit the merge later recombines.
- **`--component-selector all`**: list every component in `FOCUS.md`; the optimizer
  may edit anywhere. Use for monolithic capabilities or when changes must span files.

For a single-file / monolithic capability there is only one component; round-robin
and `all` coincide, and the system-aware merge skips gracefully (nothing independent
to recombine) rather than producing a degenerate child.

## Key hyperparameters

- `--max-metric-calls` (default 0 = unlimited): PRIMARY budget — total rollouts.
- `--max-iterations` (default 50): secondary cap on propose→gate iterations.
- `--minibatch-size` (default 4): train ids per cheap local gate.
- `--n-trials` (default 1): rollouts/task on the full-val eval (raise under noise so
  the significance gate is trustworthy).
- `--component-selector` (`round_robin` | `all`), `--selection-strategy`
  (default `pareto_per_instance`), `--max-merges` (default 2), `--merge-cadence`
  (default 3).
- `--gate-mode` / `--k-se`: the val acceptance bar (paired significance by default).
- `--no-regression`: reject a child that breaks any previously-passing val task.
- `--seed`: seeds the parent-sampling + minibatch RNG (logged for reproducibility).

## How to run

```bash
python scripts/check.py    # behavioral, offline (mock optimizer + synthetic adapter)
python scripts/run.py --run-dir .capevolve/run_X --project .capevolve/project \
  --optimizer 'python .../run-optimizer/scripts/run.py --name mock --workdir {workdir} --prompt {prompt}' \
  --max-metric-calls 400 --minibatch-size 4 --component-selector round_robin
```

Requires `baseline` first (reads the seed's full-val result from `baseline.json`).
Reports the frontier/pool, best candidate, accepts, merges, and metric-calls spent;
test stays sealed for `finalize`.

## References

- `references/concepts.md` — the GEPA economy, reflective dataset / actionable side
  information, per-instance frequency-weighted frontier, system-aware merge, the
  metric-call budget, and the relation to the hill-climb / skillopt siblings.
  Cites arXiv:2507.19457.

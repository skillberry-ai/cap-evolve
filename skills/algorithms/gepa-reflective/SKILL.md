---
name: gepa-reflective
description: The flagship optimization algorithm — GEPA-style reflective Pareto evolution. Use when you want sample-efficient, high-quality optimization that learns from full execution traces rather than scalar rewards. Each iteration reflects on a parent candidate's failing tasks (turning traces and feedback into natural-language "actionable side information" — the textual analogue of a gradient), proposes a targeted edit, and keeps a per-task Pareto frontier of complementary candidates instead of a single global best, so specialists and stepping-stones survive and the run resists overfitting. The best default for prompt/skill/tool text; same honest val-only gate and sealed test as the rest of the family.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer 'CMD {workdir} {prompt}'"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, reflective_dataset, candidate]
sources: [gepa, dspy]
---

# gepa-reflective

Reflective **Genetic-Pareto** evolution, after GEPA (Agrawal et al., 2025,
arXiv:2507.19457; also `dspy.GEPA`). Two ideas make it strong, and both depart from
the single-lineage hill-climb of `all-at-once` / `cyclic` / `hardest-first`:

### 1. Reflect on traces, not scalars

Each iteration builds a **reflective dataset** from the parent candidate's failing
val tasks — the input, the agent's actual output/trajectory, and the scorer's
feedback — and asks the optimizer to *diagnose the common root cause and fix the
general pattern*, not patch one task. GEPA's thesis is that natural language is a
far richer learning medium than a scalar reward: an English diagnosis of *why* a
rollout failed is the textual analogue of a gradient ("actionable side
information"). This is what makes it sample-efficient — GEPA reports matching or
beating RL (GRPO) with **up to ~35× fewer rollouts**, and +10% over MIPROv2.

### 2. Keep a Pareto frontier, not one champion

Candidates are kept on a **per-task Pareto frontier**: a candidate survives if it is
non-dominated — best on *some* task — even when its *mean* is lower than the
incumbent's. Each iteration's parent is **sampled from that frontier**, not fixed to
the global best. This preserves **specialists** (a candidate that uniquely solves
one hard task) and **stepping-stones** (a lower-mean candidate that opens a path to
a higher peak) that a greedy "keep only the best mean" rule would discard. The
result is more exploration and strong resistance to overfitting / premature
convergence — the same quality-diversity intuition behind MAP-Elites and AlphaEvolve.

### The loop

1. **Select a parent** from the Pareto frontier over per-task val scores (seeded
   with the baseline candidate).
2. **Build the reflective dataset** over that parent's failing val tasks and prompt
   the optimizer for a general fix.
3. **Evaluate on val** (`n_trials` rollouts/task) and **gate** on the val
   significance bar.
4. **On accept, add the candidate to the frontier** (it may be a new specialist,
   not necessarily the new best mean). Repeat until budget / `--max-iterations`.
5. Report the frontier and the best-mean candidate; the **test split stays sealed**
   for finalize.

## When to use

- **The default for optimizing text capabilities** — prompts, skills, tool docs —
  especially with informative per-task feedback (a good `score` feedback string).
- **When a global hill-climb overfits or plateaus.** The frontier keeps diversity a
  single lineage loses; trace reflection finds fixes a scalar-only loop misses.
- **When rollouts are expensive.** Its sample efficiency is the whole point — more
  quality per evaluation than reward-only search.

## When NOT to use

- **No informative feedback** (binary pass/fail with no diagnosis): reflection has
  little to work with — a hill-climb (`all-at-once`) is simpler and just as good.
- **Tiny task sets** where a per-task frontier collapses to one or two points — the
  Pareto machinery adds overhead without diversity to exploit.
- **As the very first run / baseline** — start with `all-at-once` so you have a
  yardstick to prove the extra machinery here is earning its keep.

## Selection / focus / acceptance behavior

- **Selection (parent):** sampled from the **per-task Pareto frontier** (a candidate
  dominates another only if it is ≥ on every task and > on at least one). This is the
  key difference from the hill-climb siblings, which always extend the single global
  best.
- **Focus:** a reflective dataset over the *parent's* failing val tasks — the
  diagnosis is parent-relative, so different frontier members get different fixes.
- **Acceptance:** the shared significance gate on **val** (never train). Accepted
  candidates join the frontier even if they don't beat the best mean — that is how
  specialists are retained.

## Hyperparameters

- `--max-iterations` (default 10): propose→gate steps. Each grows the frontier on
  accept; more iterations = more exploration of complementary candidates.
- `--n-trials` (default 1): rollouts per task per evaluation; raise under noise so
  both the frontier dominance checks and the gate are trustworthy.
- `--gate-mode` (default `significant`) / `--k-se` (default 1.0): the val acceptance
  bar; see `all-at-once` for all modes.
- `--no-regression`: reject candidates that break a previously-passing val task.
- `--store`: how accepted iterations are versioned.

(GEPA proper also includes a **system-aware merge** that crosses over complementary
lineages on the frontier; this skill implements the reflective proposal + Pareto
selection core. See `references/concepts.md`.)

## Trade-offs

- **Strengths:** the most sample-efficient and highest-ceiling member of the family;
  trace reflection extracts more signal per rollout; the frontier resists
  overfitting and local optima by keeping complementary specialists alive.
- **Limits:** needs informative feedback to shine; the frontier and reflective
  dataset add bookkeeping and prompt length; on tiny or feedback-poor tasks the
  machinery doesn't pay for itself — fall back to the hill-climb schedulers.

## How to run

```
python scripts/check.py
python scripts/run.py --run-dir .capevolve/run_XXXX --project .capevolve/project \
    --optimizer "python <skills>/optimizers/<opt>/scripts/run.py --workdir {workdir} --prompt {prompt}" \
    --max-iterations 12
```

Requires `baseline` first. Reports the frontier and best candidate; test stays
sealed for finalize. Routes through `core.harness.pareto_loop`, which overrides
parent selection (Pareto frontier) and the proposal prompt (reflective dataset)
versus the shared hill-climb loop.

## References

- `references/concepts.md` — GEPA's reflective evolution, actionable side
  information, the per-task Pareto frontier, system-aware merge, the relation to
  DSPy/MIPRO and AlphaEvolve/OpenEvolve, and cited sources.

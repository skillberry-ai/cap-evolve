---
name: skillopt
description: Runs the SkillOpt single-lineage optimization loop over epochs x mini-batches with a textual learning rate (an integer edit budget that decays on a constant|linear|cosine schedule), a within-epoch rejected-edit + failure-pattern buffer injected into the optimizer prompt, and a gated epoch-boundary slow/meta update that fixes longitudinal regressions. Parent is always the current best; acceptance is the val significance gate; the test split stays sealed. Use when a run benefits from disciplined annealing and per-epoch consolidation rather than hill-climb's one-shot whole-trainset proposals or gepa's Pareto frontier.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer CMD [--epochs 4] [--batch-size N] [--edit-budget 4] [--lr-schedule cosine] [--min-edit-budget 2] [--no-slow-update]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, candidate]
---

# skillopt — annealed single-lineage climb (epochs × mini-batches)

SkillOpt (arXiv:2605.23904) borrows the deep-learning training loop. It is a
strict single-lineage climber (parent is always the current best, like
hill-climb) but adds three things from the DL analogy:

- a **textual learning rate** — an integer **edit budget** `L` per step, large
  early (explore broadly) and shrinking later (consolidate), on a
  `constant | linear | cosine` schedule;
- a per-epoch **rejected-edit + failure-pattern buffer** injected into the next
  step's prompt (don't re-propose dead ends; these failures remain unsolved);
- an **epoch-boundary slow / meta update**: re-evaluate the epoch-start skill vs
  the current best on a small train sample, categorize improved / regressed /
  persistent / stable, then run ONE extra **gated** step to fix regressions
  without breaking stable successes.

Every step calls the shared `run_step` (materialize → optimize → eval-VAL →
significance gate → accept/reject → snapshot/best, with RejectedMemory/History);
this skill only owns the schedule, the buffer, and the slow update. Gated on val;
test stays sealed (that's `finalize`).

## The DL analogy

| deep learning | SkillOpt |
|---|---|
| epoch over the dataset | epoch over the **train** ids (shuffled, seeded by epoch) |
| mini-batch / gradient accumulation | `--batch-size` train tasks × `--accumulation` per step |
| learning-rate schedule | **edit-budget** `L` schedule (`--lr-schedule`, decays `--edit-budget` → `--min-edit-budget`) |
| gradient step | one `run_step` (a bounded edit, gated on val) |
| momentum / replay | the per-epoch rejected-edit + failure-pattern buffer |
| LR warm-restart / fine-tune | the epoch-boundary **gated** slow/meta update |

`L` is communicated to the optimizer in **natural language only** ("make at most
L bounded edits") — the LLM is not mechanically clipped — so the loop logs
*requested-vs-applied* edits to surface an optimizer that ignores its budget.

## When to use vs hill-climb / gepa

| algorithm | parent | proposal unit | best when |
|---|---|---|---|
| `hill-climb` | current best | whole train set, one-shot each iter | broad gaps; you want the simplest loop |
| `skillopt` | current best (single lineage) | mini-batch under a shrinking edit budget, epochs + gated slow update | you want disciplined annealing + per-epoch consolidation; a moderately sized train set |
| `gepa` | sampled from a per-instance **Pareto frontier** | minibatch with a cheap local gate before full val | many specialists the mean hides; merge across lineages |

## Inputs / outputs (manifest tokens)
- **needs:** `scores` + `traces` (per-task val results to reflect on) and
  `candidate` (the parent to extend).
- **provides:** `candidate` (the accepted best).

## Standalone use

```bash
python scripts/run.py --run-dir .capevolve/run_X --project .capevolve/project \
  --optimizer 'python .../run-optimizer/scripts/run.py --name mock --workdir {workdir} --prompt {prompt}' \
  --epochs 4 --batch-size 8 --edit-budget 4 --lr-schedule cosine --min-edit-budget 2 \
  --n-trials 4
```

Requires `baseline.json` first (like its sibling algorithms). `--resume`
continues from the run's current best. `--no-slow-update` disables the
epoch-boundary meta step; `--no-regression` adds a SWE-bench-style dual gate.

## Pitfall: small val sets

The default gate is `significant`/`paired` (NOT naive strict-greater) so a tiny
val set does not reject every edit on noise. With a small val set, raise
`--n-trials` (real per-trial variance) or use a **graded** reward so the paired
significance test has signal. Only the slow update is a "meta" step — it is still
**gated on val**, never force-accepted, and its train sample is small + counted in
budget (toggle with `--no-slow-update`).

## References
- `references/concepts.md` — the SkillOpt loop in detail, the textual-LR schedule,
  the buffer/slow-update mechanics, and citations (arXiv:2605.23904).

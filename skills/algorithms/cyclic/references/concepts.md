# Concepts — cyclic (round-robin per-task focus)

> Same honest hill-climb core as `all-at-once`, but the reflection narrows to one
> training task per iteration and cycles through them. This file explains why
> per-task focus helps when failures are heterogeneous, how it relates to
> coordinate ascent and curriculum scheduling, and cites the relevant literature.

## The loop, precisely

```
best ← seed
for i in 0 .. max_iterations-1:
    parent  ← best                           # greedy, one lineage (like all-at-once)
    t       ← train[i mod N]                  # round-robin focus
    offspring ← optimizer(parent, reflection_focused_on(t))
    s       ← evaluate(offspring, val, n_trials)
    if gate(s, best_val):                     # Δ > k_se · combined_SE, on VAL
        best ← offspring
```

Only the **focus** changes versus `all-at-once`: the reflection emphasizes the
single task `t` and its failure feedback, instead of listing all failures and
asking for one averaged improvement. Parent selection, the val-only significance
gate, multi-trial scoring, and the sealed test split are identical.

## Why per-task focus (coordinate ascent)

When different tasks fail for different reasons, a single global edit must satisfy
all of them at once. The optimizer is effectively asked to move along the *average*
of conflicting directions, and the averaged move often improves nothing decisively —
the run plateaus. Focusing one task at a time is the prompt-optimization analogue of
**coordinate ascent / round-robin (Gauss–Seidel) descent**: optimize one coordinate
while holding the rest fixed, then rotate. Each optimizer call gets a clean,
concrete signal ("this specific task fails like *this* — fix it") instead of a
diffuse one.

The acceptance gate is what keeps coordinate ascent honest here. A per-task fix is
the move most likely to **regress a sibling task**, so:

- acceptance is still gated on the **held-out val aggregate**, not on the focus task
  — a fix that helps `t` but hurts the mean is rejected; and
- `--no-regression` upgrades this to a hard constraint (reject if any
  previously-passing val task breaks), the same dual-gate idea SWE-bench-style
  evaluations use ("fix the target without breaking what passed").

## Skipping solved tasks

A task that already passes contributes no failing feedback, so when the cursor lands
on it the reflection has nothing to focus and the step naturally seeks robustness or
moves on. The *effective* schedule is therefore a round-robin over the **unsolved**
tasks, which is what you want: budget flows to open problems, and a full cycle still
guarantees every task is revisited (a previously-solved task that later regresses
re-enters the rotation).

## Lineage in the literature

- **Per-example / error-focused feedback.** ProTeGi/APO (Pryzant et al., 2023)
  forms natural-language critiques ("textual gradients") from the prompt's mistakes
  on a *minibatch* and revises against them; OPRO (Yang et al., 2023) feeds the
  optimizer a trajectory of past attempts and scores. cyclic is the extreme of
  shrinking that minibatch to **one task**, then rotating — maximizing the
  specificity of each critique.
- **Coordinate / block-coordinate optimization.** Round-robin updates of one
  coordinate at a time are a standard alternative to full-gradient steps when the
  full step is hard to satisfy jointly; cyclic applies the same scheduling idea to
  tasks.
- **Curriculum and pacing.** Curriculum learning (Bengio et al., 2009; survey by
  Soviany et al., 2021) studies the *order* in which examples are presented to a
  learner. cyclic's order is uniform round-robin (no easy→hard pacing); its sibling
  `hardest-first` is the anti-curriculum / hard-example-mining variant. Both are
  schedule choices over the same loop.
- **Multi-module program optimization.** In DSPy's MIPRO (Opsahl-Ong et al., 2024),
  optimizing a multi-stage program means improving *each module's* instruction; the
  per-component attention there is analogous to cyclic's per-task attention — narrow
  the unit of optimization to get a cleaner signal.

## Practical guidance

- Give it **at least one full cycle** (`max_iterations ≥ N`) so every task gets a
  turn; otherwise the tail of the task list never gets focus.
- Turn on `--no-regression` — single-task fixes are the most prone to breaking
  siblings, and the loop has no other defense against "rob Peter to pay Paul."
- If a few tasks clearly dominate the loss, `hardest-first` will reach a better mean
  faster by triaging worst-first rather than giving every task an equal slot.
- If cyclic also stalls, the failures may need a kept population / stepping-stones —
  move to `gepa-reflective`.

## Sources

- Automatic Prompt Optimization with "Gradient Descent" and Beam Search (ProTeGi /
  APO). Pryzant et al., EMNLP 2023. arXiv:2305.03495 — https://arxiv.org/abs/2305.03495
- Large Language Models as Optimizers (OPRO). Yang et al., 2023. arXiv:2309.03409 —
  https://arxiv.org/abs/2309.03409
- Curriculum Learning. Bengio, Louradour, Collobert, Weston, ICML 2009. —
  https://dl.acm.org/doi/10.1145/1553374.1553380
- Curriculum Learning: A Survey. Soviany, Ionescu, Rota, Sebe, IJCV 2022.
  arXiv:2101.10382 — https://arxiv.org/abs/2101.10382
- Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs
  (MIPRO). Opsahl-Ong et al., EMNLP 2024. arXiv:2406.11695 —
  https://arxiv.org/abs/2406.11695
- GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning. Agrawal
  et al., 2025. arXiv:2507.19457 — https://arxiv.org/abs/2507.19457

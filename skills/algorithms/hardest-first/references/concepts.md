# Concepts — hardest-first (worst-first hard-example mining)

> The same hill-climb core as `cyclic`, but the focus cursor is ordered by
> difficulty: rank the seed's train tasks worst-first and attack the hardest first.
> This file explains the hard-example-mining / anti-curriculum rationale, the
> important train-ranking vs val-gate separation, the failure modes, and sources.

## The loop, precisely

```
best ← seed
train_scores ← evaluate(seed, train, n_trials)        # one-time ranking pass
ranked ← train_ids sorted by ascending reward          # hardest (lowest) first
for i in 0 .. max_iterations-1:
    parent  ← best                                     # greedy, single lineage
    t       ← ranked[i mod N]                           # worst-first, then cycle
    offspring ← optimizer(parent, reflection_focused_on(t))
    s       ← evaluate(offspring, val, n_trials)
    if gate(s, best_val):                               # Δ > k_se · combined_SE, on VAL
        best ← offspring
```

It is `cyclic` with a difficulty-ordered cursor. Parent selection, multi-trial
scoring, the val-only significance gate, and the sealed test split are unchanged.

## Why worst-first (hard-example mining / anti-curriculum)

Two well-studied ideas motivate attacking the hardest tasks first:

- **Hard-example mining.** Most data is "easy" and contributes little gradient;
  the model improves fastest when training concentrates on the **high-loss**
  examples. Online Hard Example Mining (Shrivastava et al., CVPR 2016) made this
  automatic — select the highest-loss samples each step — and showed the largest
  gains came on the hardest, biggest datasets. hardest-first applies the same
  principle: a task at reward 0.1 has ~0.9 of headroom; one already at 0.95 has
  almost none, so the marginal value of an optimizer call is far higher on the
  former.
- **Anti-curriculum.** Curriculum learning orders examples easy→hard (Bengio et al.,
  2009); the *reverse* ordering (hard→easy, "anti-curriculum") is a recognized and
  sometimes superior schedule in the curriculum literature (Soviany et al., 2021),
  particularly when the hard tail is where the achievable improvement lives.
  hardest-first is the anti-curriculum schedule for capability optimization.

The payoff is **aggregate gain per iteration**: when difficulty is heavy-tailed,
lifting the worst tasks moves the mean the most. Under a fixed budget, that is the
allocation that maximizes expected improvement.

## The train-ranking vs val-gate separation (why it stays honest)

There are two distinct uses of scores here, and they deliberately use different
splits:

- **Ranking effort** uses the seed's **train** scores. This is allowed and cheap —
  it only decides the *order* in which tasks get attention, never whether an edit is
  kept. Using train here cannot overfit, because no acceptance decision rides on it.
- **Accepting candidates** uses the held-out **val** significance gate, exactly as
  in every sibling algorithm. So even though the loop spends its budget on the
  hard train tail, an edit survives only if it improves the *held-out* aggregate —
  the test split remains sealed for finalize.

Keeping these separate is what lets hardest-first prioritize aggressively without
compromising the honesty guarantee.

The ranking is computed **once**, from the seed, and not refreshed as candidates
improve. That keeps the schedule stable and the cost bounded (one train pass), at
the price of the order possibly going stale if the difficulty profile shifts a lot
during the run. Add `--no-regression` so that pouring budget into the hard tail does
not silently break the easy tasks the seed already passed.

## Failure modes to watch

- **Noisy ranking.** The worst-first order is estimated from the seed's train scores;
  under a high-variance scorer the "hardest" task is unstable and the loop may chase
  noise. Raise `--n-trials` to stabilize the ranking, or fall back to `all-at-once`.
- **The intractable hardest task.** Worst-first can sink the whole budget into a task
  no edit can fix, starving easier wins. The cyclic cursor mitigates this (it moves
  on after a turn), but on very hard tails consider `cyclic` for even coverage.
- **Uniform difficulty.** If tasks are equally hard, the ordering buys nothing and
  the upfront train pass is wasted — use `all-at-once`.

## Lineage in the literature

- **Online Hard Example Mining (OHEM)** — Shrivastava, Gupta, Girshick, CVPR 2016:
  prioritize the highest-loss examples; the direct ancestor of "attack the hardest
  first."
- **Curriculum Learning** — Bengio et al., ICML 2009; **survey** — Soviany et al.,
  IJCV 2022: the study of example ordering and pacing, including the anti-curriculum
  (hard-first) regime hardest-first instantiates.
- **Quality-diversity / population schedulers** (MAP-Elites in OpenEvolve, the GEPA
  Pareto frontier) take the complementary view — keep *diverse* specialists rather
  than triaging a single lineage. hardest-first is the lightweight, single-lineage
  alternative when you simply want budget aimed at the worst tasks.

## Sources

- Training Region-based Object Detectors with Online Hard Example Mining (OHEM).
  Shrivastava, Gupta, Girshick, CVPR 2016. arXiv:1604.03540 —
  https://arxiv.org/abs/1604.03540
- Curriculum Learning. Bengio, Louradour, Collobert, Weston, ICML 2009. —
  https://dl.acm.org/doi/10.1145/1553374.1553380
- Curriculum Learning: A Survey (covers anti-curriculum / hard-first). Soviany,
  Ionescu, Rota, Sebe, IJCV 2022. arXiv:2101.10382 — https://arxiv.org/abs/2101.10382
- GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning. Agrawal
  et al., 2025. arXiv:2507.19457 — https://arxiv.org/abs/2507.19457
- OpenEvolve (MAP-Elites quality-diversity, evolutionary coding agent) —
  https://github.com/codelion/openevolve

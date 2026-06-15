# Concepts — all-at-once (global hill-climb)

> The simplest member of the algorithm family. It schedules nothing: one parent
> (the current best), one offspring per iteration, proposed against the whole
> training set, accepted only on a held-out improvement. This file places that
> loop in the optimization literature and explains why it is the right default and
> the right baseline.

## The loop, precisely

all-at-once is a **steepest-ascent / (1+1) hill-climb** over the space of candidate
texts (a prompt, skill, or tool description):

```
best ← seed                                  # from baseline
repeat until budget / max_iterations / stall:
    parent   ← best                          # greedy: always the incumbent
    offspring ← optimizer(parent, reflection_over_all_failing_val_tasks)
    s        ← evaluate(offspring, val, n_trials)   # mean reward ± SE
    if gate(s, best_val):                    # Δ > k_se · combined_SE
        best ← offspring
```

Two design choices make it "honest":

- **Acceptance is gated on a held-out val split, never on train.** The optimizer
  edits against train-derived feedback, so accepting on train would reward
  memorization. Gating on a disjoint val set means only generalizing edits survive.
- **The gate is statistical, not a raw comparison.** With noisy scorers, a raw
  "did the mean go up?" test accepts noise. The default `significant` gate requires
  the improvement to exceed `k_se` standard errors of the combined estimate, so
  accepted gains are unlikely to be sampling noise. The `test` split is touched
  exactly once, at finalize, so the reported number is a true held-out estimate.

## Why "all-at-once" (no scheduling)

The reflection presented to the optimizer each step lists **all** currently-failing
val tasks and asks for a single edit that raises the aggregate. There is no
per-task focus, no ordering, no clustering. This is deliberate:

- When failures are **correlated** (tasks fail for the same underlying reason), one
  general edit fixes many at once — the most sample-efficient possible move.
- It introduces **no scheduling hyperparameters or assumptions** that could be
  wrong for a given task set. Specialized schedulers (`cyclic`, `hardest-first`,
  `gepa-reflective`) only help if their assumption about the failure structure
  holds; all-at-once makes none.

## Lineage in the literature

The "LLM proposes a new candidate, we keep it only if a held-out metric improves"
pattern is the common skeleton of modern automatic prompt optimization. all-at-once
is its minimal form:

- **APE — Automatic Prompt Engineer** (Zhou et al., 2022): an LLM proposes
  instruction candidates and a selection step keeps the best by score; iterative
  resampling refines around high scorers. all-at-once is the single-lineage,
  one-proposal-per-step specialization.
- **OPRO — Large Language Models as Optimizers** (Yang et al., 2023): the optimizer
  prompt carries a trajectory of past (solution → score) pairs and the LLM proposes
  the next solution. all-at-once carries the same history (accepted/rejected memory)
  but commits greedily to the best.
- **ProTeGi / APO — Automatic Prompt Optimization with "Gradient Descent" and Beam
  Search** (Pryzant et al., 2023): natural-language critiques act as "textual
  gradients"; beam search keeps several candidates. all-at-once is the **beam width
  = 1** case — one incumbent, steepest ascent — which is the standard baseline beam
  search and Pareto methods are measured against.
- **Evolutionary search / (1+1)-ES:** classic hill-climbing keeps one parent,
  generates one offspring, and replaces the parent only on improvement. all-at-once
  is exactly this with an LLM as the (informed, non-random) mutation operator and a
  significance test as the replacement rule.

## Why it is the right baseline

Fancier schedulers add machinery — task ordering (`hardest-first`), per-task
rotation (`cyclic`), a kept population / Pareto frontier and trace reflection
(`gepa-reflective`, after GEPA). Each is justified *only* if it beats this loop on
the same budget, splits, and gate. Running all-at-once first gives an honest
yardstick: if a complex method can't clear it, the complexity is not paying for
itself on your task. GEPA itself reports its gains relative to strong optimizers
(e.g. +10% over MIPROv2) — the discipline of "beat the simple baseline" is how those
numbers stay meaningful.

## Practical guidance

- Start with `--max-iterations 10`, `--n-trials 1`, `--k-se 1.0`. Raise `--n-trials`
  first if accepts look like noise (the gate can't resolve real gains under a large
  SE); raise `--k-se` if you suspect overfitting accepts.
- If it **plateaus** (several rejected steps in a row) the failures are probably
  heterogeneous — a single edit is being pulled in conflicting directions. Switch to
  a per-task scheduler (`cyclic` / `hardest-first`) or to `gepa-reflective`.
- Add `--no-regression` when you must not break already-passing tasks (e.g. a
  capability already in production).

## Sources

- GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning. Agrawal
  et al., 2025. arXiv:2507.19457 — https://arxiv.org/abs/2507.19457
- Large Language Models Are Human-Level Prompt Engineers (APE). Zhou et al., 2022.
  arXiv:2211.01910 — https://arxiv.org/abs/2211.01910
- Large Language Models as Optimizers (OPRO). Yang et al., 2023. arXiv:2309.03409 —
  https://arxiv.org/abs/2309.03409
- Automatic Prompt Optimization with "Gradient Descent" and Beam Search (ProTeGi /
  APO). Pryzant et al., EMNLP 2023. arXiv:2305.03495 — https://arxiv.org/abs/2305.03495
- Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs
  (MIPRO). Opsahl-Ong et al., EMNLP 2024. arXiv:2406.11695 —
  https://arxiv.org/abs/2406.11695
- Evolution Strategies / (1+1) hill-climbing background — Beyer & Schwefel,
  "Evolution strategies – A comprehensive introduction," 2002. —
  https://link.springer.com/article/10.1023/A:1015059928466

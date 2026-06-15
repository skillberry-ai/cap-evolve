# Concepts — gepa-reflective (reflective genetic-Pareto evolution)

> The flagship algorithm. Unlike the single-lineage hill-climbers, it reflects on
> full execution traces (not scalar rewards) and keeps a per-task Pareto frontier of
> complementary candidates. This file explains GEPA's two core ideas, the loop,
> where it sits relative to DSPy/MIPRO and AlphaEvolve/OpenEvolve, and the sources.

## What GEPA is

**GEPA = "Genetic-Pareto."** From the paper (Agrawal et al., 2025, ICLR 2026 Oral):
*"GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning."* Its
central claim is that *"the interpretable nature of language often provides a much
richer learning medium for LLMs, compared to policy gradients derived from sparse,
scalar rewards."* GEPA *"samples trajectories (e.g., reasoning, tool calls, and tool
outputs) and reflects on them in natural language to diagnose problems, propose and
test prompt updates,"* and *"combine[s] complementary lessons from the Pareto
frontier of its own attempts."* It reports up to **35× fewer rollouts** than GRPO
(RL), +6% (up to +20%) over GRPO, and **+10% over MIPROv2**.

## Idea 1 — reflect on traces, not scalars (actionable side information)

A scalar reward says *how much* a rollout failed; it does not say *why*. GEPA
instead constructs a **reflective dataset** from a candidate's failing tasks — the
input, the agent's actual output / trajectory, and the evaluator's textual
feedback — and asks an LLM to **diagnose the common root cause and rewrite the
general pattern**. The natural-language diagnosis is the textual analogue of a
gradient: it points the proposal in a concrete direction. GEPA calls this signal
**actionable side information**.

This is the same lineage as **textual-gradient** prompt optimization — ProTeGi/APO
(Pryzant et al., 2023) generates NL critiques ("gradients") of a prompt's mistakes
and moves opposite them; OPRO (Yang et al., 2023) feeds the optimizer a trajectory
of past (solution → score) pairs. GEPA generalizes this from a single prompt's error
critiques to **full agent trajectories** (reasoning + tool calls + outputs), which is
why it is so sample-efficient: each expensive rollout yields a rich English lesson,
not just a number.

## Idea 2 — keep a per-task Pareto frontier (quality-diversity)

The hill-climb siblings keep exactly one candidate: the best mean. GEPA keeps a
**Pareto frontier over per-task scores**. Candidate A *dominates* B iff A ≥ B on
**every** task and A > B on **at least one**; the frontier is the set of
non-dominated candidates. A candidate that solves one uniquely-hard task survives
even if its mean is lower than the incumbent's.

Why this matters:

- **Specialists are retained.** A candidate that is the only one solving task *t*
  is on the frontier regardless of mean — the genuine fix for *t* is not thrown away
  just because it slightly hurt the average.
- **Stepping-stones survive.** A lower-mean candidate can be the doorway to a higher
  peak. Greedy "keep best mean" closes that door; the frontier keeps it open.
- **Anti-overfitting / anti-premature-convergence.** Sampling parents from a diverse
  frontier (rather than always extending one champion) keeps exploration alive.

This is the **quality-diversity** principle shared with MAP-Elites and the
program databases of FunSearch / AlphaEvolve / OpenEvolve, where evolution keeps an
*archive* of diverse high-performers and selects future parents from it, instead of
collapsing to a single best.

## The loop in this skill

```
frontier ← [ seed ]                                   # per-task val scores
for _ in range(max_iterations):
    parent  ← sample(pareto_frontier(frontier))        # diversity-preserving select
    dataset ← reflective_dataset(parent.failing_val_tasks)   # inputs + outputs + feedback
    offspring ← optimizer(parent, dataset)             # diagnose root cause, fix pattern
    s       ← evaluate(offspring, val, n_trials)
    if gate(s, parent_val):                            # Δ > k_se · combined_SE, on VAL
        frontier.append(offspring)                     # may be a specialist, not best-mean
best ← argmax_mean(frontier)                           # finalize on SEALED test
```

The honesty contract is identical to the other algorithms: acceptance is gated on a
held-out **val** split (never train), scoring is multi-trial with a standard error,
and the **test** split is touched exactly once at finalize.

## System-aware merge (the part this skill approximates)

GEPA proper adds a **system-aware merge** step: because different frontier lineages
often improve *different* modules / components of a compound system, GEPA can cross
over two complementary candidates — taking the better version of each component — to
produce an offspring that inherits both lineages' wins. This skill implements the
**reflective proposal + Pareto parent selection** core; merge-style crossover across
the frontier is the natural extension (and is what the multi-component DSPy GEPA
implementation does). The per-task frontier is exactly the structure a merge step
needs.

## Relation to DSPy / MIPRO

GEPA ships as `dspy.GEPA`. Its predecessor in DSPy, **MIPRO/MIPROv2** (Opsahl-Ong et
al., 2024), optimizes *both* instructions and few-shot demonstrations for every
module of a multi-stage program using program- and data-aware instruction proposal
plus a Bayesian/surrogate search over the joint space. GEPA's reported +10% over
MIPROv2 comes from (a) reflecting on traces rather than searching demonstrations,
and (b) the Pareto frontier. The two are complementary: MIPRO optimizes *what
examples and instructions* each module gets; GEPA evolves the instruction text via
reflective diagnosis. Both descend from **DSPy** (Khattab et al., 2023), which framed
LM pipelines as compilable, self-improving programs with bootstrapped demonstrations.

## Practical guidance

- Provide **informative feedback** in the scorer — GEPA's edge is the quality of the
  English diagnosis it reflects on. Binary pass/fail with no explanation wastes the
  method; use `all-at-once` there.
- Give it enough iterations for the frontier to accumulate complementary candidates
  (the diversity is the point). On tiny or feedback-poor task sets, the frontier
  collapses and the hill-climb schedulers are simpler.
- Use `all-at-once` as the baseline first — GEPA's value is precisely that it should
  beat the simple loop on the same budget and splits.

## Sources

- GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning. Agrawal,
  Tan, Soylu, Ziems, Khare, Opsahl-Ong, Singhvi, Shandilya, Ryan, Jiang, Potts, Sen,
  Dimakis, Stoica, Klein, Zaharia, Khattab. 2025 (ICLR 2026 Oral). arXiv:2507.19457 —
  https://arxiv.org/abs/2507.19457
- DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines.
  Khattab et al., 2023. arXiv:2310.03714 — https://arxiv.org/abs/2310.03714
- Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs
  (MIPRO / MIPROv2). Opsahl-Ong et al., EMNLP 2024. arXiv:2406.11695 —
  https://arxiv.org/abs/2406.11695
- Automatic Prompt Optimization with "Gradient Descent" and Beam Search (ProTeGi /
  textual gradients). Pryzant et al., EMNLP 2023. arXiv:2305.03495 —
  https://arxiv.org/abs/2305.03495
- Large Language Models as Optimizers (OPRO). Yang et al., 2023. arXiv:2309.03409 —
  https://arxiv.org/abs/2309.03409
- AlphaEvolve: a Gemini-powered coding agent for designing advanced algorithms.
  Google DeepMind, 2025 (program database + evolutionary selection) —
  https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- OpenEvolve: open-source evolutionary coding agent (MAP-Elites quality-diversity,
  island populations) — https://github.com/codelion/openevolve

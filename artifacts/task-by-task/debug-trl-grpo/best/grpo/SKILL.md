---
name: grpo
description: Reference for the GRPO (Group Relative Policy Optimization) algorithm. Use when implementing, debugging, or verifying a GRPO training pipeline — covers the mathematical formulation (group-relative advantages, clipped surrogate loss, KL penalty), the training loop (generate → score → advantage → loss), log-probability computation, advantage estimation, and relationship to PPO/REINFORCE.
---

# GRPO Algorithm Reference

## Overview

Group Relative Policy Optimization (GRPO) is a policy gradient method that eliminates the need for a learned critic by computing advantages from group statistics. For each prompt, multiple completions are sampled and their rewards are normalized within the group to produce advantages.

**Key insight:** Instead of training a value function to estimate `V(s)`, GRPO uses the mean reward of the group as the baseline. This removes the critic entirely, reducing memory and avoiding value function approximation errors.

## Training Loop

Each step follows this pipeline:

```
1. Sample G completions per prompt from current policy
2. Decode completions to text
3. Score completions with reward function
4. Compute group-relative advantages
5. Compute per-token log-probs (current policy + reference policy)
6. Compute clipped surrogate loss with KL penalty
7. Backpropagate and update
```

## Advantage Estimation

Rewards are normalized within each group of `G` completions for the same prompt:

```
mu   = mean(r_1, ..., r_G)
sigma = std(r_1, ..., r_G)
A_i  = (r_i - mu) / (sigma + epsilon)
```

**`epsilon`** is a small constant (typically 1e-4 to 1e-8) for numerical stability only. It prevents division by zero when all rewards in a group are identical.

**Properties:**
- Advantages within each group sum to approximately zero;
- High-reward completions get positive advantages, low-reward get negative;
- The learning signal vanishes if epsilon is too large (dominates denominator) or if rewards are constant. For example, if all rewards in a group are identical (or nearly identical), then causing all advantages to collapse to 0;

## Log-Probability Computation

Per-token log probabilities via log-softmax:
```
log_prob(token_i) = logit(token_i) - logsumexp(logits)
```

**Critical invariant:** `log_prob <= 0` always, since it's the log of a probability in (0, 1].

Sequence-level log probability: `log_pi(y|x) = sum_t log_pi(t_j | x, t_<j)`

## Loss Function

The GRPO loss combines a clipped surrogate objective with a KL divergence penalty:

```
ratio = exp(log_pi_theta(y|x) - log_pi_old(y|x))
L_clip = min(ratio * A, clip(ratio, 1-eps, 1+eps) * A)
L_kl = beta * KL(pi_theta || pi_ref)
loss = -E[L_clip] + L_kl
```

| Component | Purpose |
|-----------|---------|
| `ratio` | How much the policy has changed from the generation policy |
| Clipping | Prevents destructively large policy updates |
| `beta * KL` | Keeps the policy close to the reference (prevents degeneration) |

## Key Hyperparameters

| Parameter | Typical Range | Effect |
|-----------|--------------|--------|
| `num_generations` (G) | 4–16 | More = lower variance advantages, higher compute cost |
| `beta` | 0.01–0.1 | Higher = more conservative updates (closer to reference) |
| `epsilon` (clip) | 0.1–0.2 | Narrower = more conservative updates |
| `epsilon` (advantage) | 1e-8–1e-4 | Must be small; only for numerical stability |
| `learning_rate` | 1e-7–5e-6 | Much lower than SFT; RL is sensitive to LR |

## Debugging a GRPO pipeline that shows no improvement

"No improvement" is rarely one bug. A corrupted GRPO run usually has **several independent
defects across different stages**, and each stage can silently zero or invert the learning
signal on its own. The most common failure when debugging is **stopping after the first one
or two fixes** — verify EVERY stage of the training loop before concluding.

Also load the **`rl-post-training`** skill and run its `scripts/verify_pipeline.py` diagnostic:
it round-trips each stage and hard-fails the exact broken one, so treat a clean run of that
probe — not "I found a bug" — as the bar for declaring the pipeline fixed.

Check each stage against its invariant (a violation is a bug, even if you already found others):

| Stage | Invariant to verify |
|-------|---------------------|
| Log-prob (`selective_log_softmax`) | Every returned log-prob is `<= 0`; the formula is `selected_logit - logsumexp(logits)`, NOT the reverse. A sign flip yields positive log-probs and inverts the ratio/KL — check the operand order explicitly. |
| Advantage normalization | The stability `epsilon` in `(r - mu)/(sigma + eps)` is *tiny* (≈1e-4 to 1e-8). A large value (e.g. `1e4`) crushes every advantage to ~0. |
| Decode / completion extraction | Text passed to the reward function is correct for all completion shapes (plain, complete reasoning block, incomplete block). A bug here is a narrow error in ONE branch. |
| Loss / clipping | Ratio, clip, and KL terms use the corrected log-probs. |

**A diff against another library version LOCATES anomalies; it is not the ORACLE for what the
code should do.** Do not "restore upstream" or delete intentional custom logic (e.g. a decode
step that extracts answers from `<think>...</think>` reasoning blocks) merely because a stock
version lacks it — that trades one bug for several. Fix the offending branch in place and keep
the intended behavior; correctness is defined by this repo's own contracts and tests.

## Available References

| File | Contents                                                                                                                                          | When to load |
|------|---------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| `references/grpo-algorithm.md` | Full mathematical formulation with notation table, step-by-step derivations, comparison to PPO and REINFORCE                                      | When you need to verify whether a specific implementation detail matches the algorithm specification |
| `references/grpo-trainer-internals.md` | GRPOTrainer implementation from popular frameworks (TRL): method-by-method breakdown, data flow diagram, and how each algorithm step maps to code | When tracing bugs through a GRPOTrainer implementation or understanding how the algorithm maps to specific code paths |

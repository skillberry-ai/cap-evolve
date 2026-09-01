---
name: rl-post-training
description: Diagnostic guide for RL-based post-training of language models (GRPO, PPO, REINFORCE, DPO). Use proactively when debugging a training pipeline that shows no improvement, loss anomalies, reward stagnation, NaN gradients, or other unexpected behavior during reinforcement learning fine-tuning. Work through all pipeline stages — reward, advantages, log-probs, loss, generation/decoding — before concluding the diagnosis is complete; stopping after one or two fixes is a common failure mode. Covers log-probability math, advantage estimation, numerical stability, reward processing, and generation/decoding pipeline issues.
---

# RL Post-Training — Concepts & Diagnostic Guide

## Core Concepts

RL post-training optimizes a language model's policy using reward signals. The standard pipeline:

```
prompt → generate completions → score with reward → compute advantages → policy gradient update
```

Each stage has distinct failure modes. When a model "shows no improvement," the bug could be anywhere in this pipeline.

## Diagnostic Methodology

When RL training produces no improvement, work through these stages in order. Each stage depends on the previous one being correct.

### Stage 1: Verify Reward Signal
- Are rewards non-constant? If all rewards are identical, there is no learning signal.
- Do rewards correlate with completion quality? Spot-check decoded completions against their scores.
- Is the reward function being called on the correct text? Check that decoding/stripping preserves the content the reward function needs to evaluate.

### Stage 2: Verify Advantage Computation
- Are advantages non-zero when rewards vary? If they collapse to ~0, the policy gradient vanishes.
- Check the magnitude and dtype of every numerical-stability constant in the advantage path (additive epsilons, clipping bounds). Compare each to what the math requires.
- Check the group size `G`. `G ≤ 2` makes `std` either undefined or extremely noisy.

### Stage 3: Verify Log-Probability Computation
- Verify bounds: log-probs of valid tokens must be non-positive.
- Compare your implementation against `F.log_softmax` on a small deterministic input — a numerical match rules out sign errors, wrong gathering axis, and off-by-one subtraction.
- On a near-one-hot input, confirm the dominant token's log-prob is close to 0 (not close to the min).

### Stage 4: Verify Loss Computation
- Is the loss changing across steps? Flat loss suggests zero gradients upstream.
- Log the KL term and the policy-gradient term separately. Either dominating the other is diagnostic.
- Check the fraction of clipped samples. Near-100% clipping means the clip range is starving the signal.

### Stage 5: Verify Generation and Decoding
- Are padding and decoder artefacts stripped from the text the reward function sees?
- Does every completion shape your model can emit survive the decoding path with non-empty output where a human would expect non-empty output? Include degenerate cases (no formatting markers, only a prefix, only a suffix) in the round-trip test.
- A decoder that handles reasoning-block markers (e.g. `<think>...</think>`) has a **three-branch contract**, and each branch is a separate requirement: (1) *complete* reasoning (marker opened and closed) → return only the content after the close; (2) *incomplete* reasoning (opened, never closed) → treat as unusable (empty); (3) *plain* completion (no markers at all) → return it **verbatim**. The classic bug is branch (3): a catch-all `else` that blanks anything lacking a closing marker also blanks plain completions, zeroing their reward. Fix the ONE offending branch — do NOT delete the marker-extraction logic to "simplify", because that just moves the bug to branch (1). `scripts/verify_pipeline.py` round-trips all three shapes and flags each violation separately.
- Print or log a sample of the actual strings handed to the reward function — mismatches between "what the model generated" and "what the reward saw" are often visible at a glance.

## Before You Conclude — Completion Gate

A pipeline that "shows no improvement" almost always has **more than one** independent bug (a broken reward, a collapsed advantage, a sign-flipped log-prob, and a decoding bug can all coexist and each independently kill learning). Finding one or two and stopping is the single most common way this task is failed. Do not declare the diagnosis done until you have positively checked **every** stage's invariant, not just the ones where you already found a bug.

Make this concrete by RUNNING the bundled diagnostic instead of only reasoning about it:

```
python scripts/verify_pipeline.py
```

- It exercises `selective_log_softmax`, `decode_and_strip_padding`, and the advantage path on small fixed inputs and checks the invariants for you.
- It **hard-fails** (`!!`) on a sign-flipped or mis-gathered log-prob (any positive log-probability, or divergence from `F.log_softmax`) and on any decode-contract violation — a plain completion that gets blanked, a complete `<think>…</think>` whose markers are left in or whose answer is dropped, or an incomplete `<think>` left non-empty. Treat any `!!` as an unfixed bug (the decode probe is deterministic and offline — run it even if the reward already looks non-zero).
- Inspect every line marked `?` too — a soft flag is still a lead.
- The script **self-locates** the real `trl` package, so if `import trl` errors from the checkout directory, that is a path/namespace-shadowing artefact, **not a code bug** — do not spend turns debugging the import; just run the script (it handles it) and keep looking for real bugs.

You are not done while the diagnostic reports any `!!` failure. Only conclude after a clean run plus a deliberate pass over each stage below.

## Fixing, Not Rewriting

A bug in a branched function is a bug in one branch, not a verdict on the whole function. Before editing:

- Enumerate the input shapes the function handles today and the output each branch produces. The branches exist because callers rely on them.
- Identify which input-output pairs violate the intended contract. Those are the only branches you need to change.
- If your diff collapses a multi-branch function to a one-liner, you have almost certainly broken a contract a different caller depends on. Re-read the call sites before committing.
- Diffing against a pip-installed or upstream version of the library is fine for *locating* an anomaly, but the upstream code is NOT the oracle for what this repo should do. A project often carries intentional custom logic (e.g. reasoning-block extraction in a decoder) that upstream lacks; "restoring upstream" then deletes required behavior and breaks the project's own tests. Verify each branch against this repo's contract/tests, and fix the narrow error in place rather than reverting the whole function.

The same principle applies to epsilon values, sign conventions, and clipping bounds — if a constant looks wrong, replace it with a correct constant; don't remove the surrounding numerical-stability logic.

## Key Mathematical Invariants

These invariants should always hold. If any is violated, there is a bug.

| Invariant | What it means | How to check |
|-----------|--------------|-------------|
| `log_prob <= 0` | Log of a probability is non-positive | `assert (log_probs <= 1e-6).all()` |
| log-probs match `F.log_softmax` | Manual implementation equals the reference | `torch.allclose(manual, F.log_softmax(...).gather(...))` |
| `sum(softmax(logits)) == 1` | Probabilities sum to 1 | `assert torch.allclose(softmax.sum(-1), ones)` |
| `0 < epsilon << 1` | Additive epsilons exist for numerical stability only | `assert 0 < epsilon < 1` |
| `advantages != 0` when rewards vary | Non-constant rewards yield non-zero advantages | `assert advantages.abs().max() > 0.1` |
| Decoding preserves content | Every generation shape the model emits survives the decode path with the content a human reader would expect | Round-trip representative samples; confirm non-empty where non-empty is expected |

## Common Pitfall Categories

Detailed pitfall catalog with examples is in `references/common-pitfalls.md`. Summary:

1. **Sign errors in log-space** — log-softmax, KL divergence, DPO log-ratio
2. **Numerical stability constants out of range** — additive epsilons, clip bounds, temperature
3. **String processing in decoding** — cleanup that blanks shapes the rules didn't anticipate
4. **Reward / decoding format mismatch** — reward function sees text with the shape it needs removed
5. **Reference model drift** — reference model not frozen, or gradients flowing through it
6. **Gradient flow breakage** — detached tensors, in-place ops, `.item()`/numpy round-trips in the loss path
7. **Configuration misuse** — SFT-scale LR, KL coefficient dominating, clip range too tight, `G` too small

## Available References

| File | Contents | When to load |
|------|----------|-------------|
| `references/common-pitfalls.md` | Catalog of pitfall categories with symptoms and detection strategies | When you have a suspicious area and want to match it against known pattern shapes |
| `references/diagnostic-workflow.md` | Stage-by-stage diagnostic procedures with verification snippets | When you need guidance on which invariant to check in which order |
| `scripts/verify_pipeline.py` | Runnable diagnostic that checks log-prob / advantage / decoding invariants on small fixed inputs; self-locates the `trl` package so it works even when a checkout dir shadows the import | **Execute it** (`python scripts/verify_pipeline.py`), do not reimplement. Run before declaring any fix done; treat every `!!` as an unfixed bug and inspect every `?` |

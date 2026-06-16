# tau2 airline — real end-to-end results (watsonx/RITS `openai/gpt-oss-120b`)

This example optimizes the **airline policy** (a `system-prompt`-style capability)
against real [tau2-bench](https://github.com/sierra-research/tau2-bench) airline
tasks, with **both the agent and the user simulator** running `openai/gpt-oss-120b`
through IBM RITS / watsonx (credentials read from the repo `.env`).

It is set up as a recoverable-degradation study: we delete the policy's
**Cancel-flight eligibility section** (the rules for when a cancellation is
allowed) to create a weak seed, then optimization restores it. This gives a clean,
measurable target.

## Pipeline runs (real tau2 rollouts)

Driven by the AgentCapTune skills end to end: `acapo check` → `baseline` →
`all-at-once` (optimizer edits the policy) → `finalize` (sealed test) → `report`.

| Run | split | baseline val | optimized val | gate | test (sealed) |
|-----|-------|--------------|---------------|------|----------------|
| eligibility-removed, 1 trial | 4/2/2 | 0.00 | **1.00** | accepted (Δ=1.0) | 0.00¹ |
| full-section-removed, 2 trials | 3/2/1 | 0.50 | **1.00** | accepted | 0.00¹ |

¹ The held-out test split (1–2 tasks) happened to contain the *hardest* adversarial
refusal tasks (e.g. task 0), which remain hard even with the correct policy. With
such a tiny test set, generalization is all-or-nothing — and the framework
**honestly reports the low test number instead of the inflated val number.** This
is the honest-eval guarantee doing its job, not a bug.

## A/B aggregate (the real, generalizing gain)

To measure the true effect of the optimization independent of split luck, we score
the **degraded** vs **restored** policy head-to-head on the SAME 10 cancellation
tasks (`ab_compare.py`):

```
tasks: 0,1,26,39,41,43,45,47,48,49
degraded_mean = 0.20   (2/10 pass)
restored_mean = 0.60   (6/10 pass)
delta         = +0.40
```

Restoring the cancellation-eligibility rules fixed tasks **26, 41, 43, 47, 48**
(0 → 1). A few tasks stay hard (0, 45, 39 — adversarial pressure / other factors)
and one flipped on single-trial noise (task 1) — which is exactly why AgentCapTune
defaults to **multi-trial, variance-aware** evaluation and a significance gate.

## Lessons this example encodes
- Real agent benchmarks are **noisy**: prefer `num_trials ≥ 2` and enough val/test
  tasks; the significance gate will (correctly) refuse marginal, noisy gains.
- The **sealed test set** prevents over-claiming — a val win is not a result until
  it survives held-out test.
- gpt-oss reasoning models sometimes emit an empty turn; `tau2_runtime.py` re-requests
  that single call (no fabricated content) so tau2 doesn't abort.

## Reproduce
```bash
# from the repo root, with .env containing RITS_API_KEY/WATSONX_* :
export AGENT_CAPO_CORE="$PWD/core"
export PYTHONPATH="$AGENT_CAPO_CORE:$PWD/examples/tau2_airline"
export ACAPO_TAU2_DATA="$PWD/examples/tau2_airline/data"
export TAU2_MAX_CONCURRENCY=20

# head-to-head A/B (degraded vs restored policy):
AB_TASK_IDS="0,1,26,39,41,43,45,47,48,49" python3 examples/tau2_airline/ab_compare.py

# full skill pipeline (intake/check/baseline/optimize/finalize/report) — see README.md
```

---

## Composite run (policy + tools, claude-opus-4-6) — full 50-task result

The headline composite run: optimize the airline **policy + tools together** with
`all-at-once`, the **claude-code optimizer @ claude-opus-4-6**, agent+user
`gpt-oss-120b` (watsonx/RITS), **all 50 tasks** (no-holdout fit), **num_trials 4**,
tau **concurrency 7**, **git** iteration store + optimizer memory. Reproduce:
[run_full/](run_full/) and [../../docs/REPRODUCE_tau2.md](../../docs/REPRODUCE_tau2.md).

| metric | value |
|---|---|
| baseline (seed) | **0.46** ± 0.058 |
| **final (cand_0007)** | **test reward 0.80** · pass^1 0.80 · pass^2 0.73 · pass@2 0.87 |
| tasks fully solved | 31 / 50 |
| improvement | **+0.34** (0.46 → 0.80) |

The optimization process (one git commit per iteration):
```
baseline 0.46
iter1 ACCEPT cand_0001  0.68  (Δ+0.22, significant)
iter2 reject 0.59 · iter3 0.715(TAKEN) · iter4–6 0.71/0.72/0.685
iter7 cand_0007 0.75 (TAKEN, best) · iter8 0.735
final test on cand_0007 = 0.80
```
iter1 raised val 0.46→0.68 by clarifying the policy AND fixing tool docstrings
(e.g. `update_reservation_flights` + the "basic economy" rule); later iterations
plateaued, and the highest candidates (0.715, 0.75) were adopted. `cand_0007`
changed both `policy/policy.md` and `tools/tools.py`. The whole process — every
candidate, the accept/reject reasons, the optimizer's `STATE.md`/`rejected.jsonl`
memory — is in the run dir's git history and the `dashboard.html`.

> Note: train=val=test=all 50 (a deliberate no-holdout fit on the full benchmark,
> per the run request); the test number is a fit metric, not held out.

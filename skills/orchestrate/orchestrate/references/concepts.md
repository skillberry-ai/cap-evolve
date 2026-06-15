# Concepts — orchestrating the pipeline honestly

> orchestrate adds no measurement logic; it sequences the phases and enforces,
> automatically, the guardrails that keep a run honest. This note maps the
> pipeline as a dependency graph and shows where each guardrail lives.
> Implementation: this skill's `scripts/run.py` (`needs`/`provides` resolution).

## The pipeline is a needs/provides DAG

Each phase declares what tokens it `needs` and `provides`. orchestrate orders the
phases so every `needs` is satisfied by an upstream `provides`, which is also how a
misordered or incompatible pipeline is caught *before* it runs:

```
intake            provides: project, tasks
  → implement-and-check   needs: project        provides: checked
    → baseline            needs: project, tasks  provides: splits, baseline, candidate
      → <algorithm>       needs: candidate, ...  (propose → evaluate → diagnose → gate)
        → finalize        needs: candidate       provides: report (sealed test)
          → report        reads run dir          provides: report (human summary)
```

The edges are not cosmetic: `baseline` cannot run until `implement-and-check`
emits `checked`, so the hard gate cannot be skipped; `finalize` consumes the best
candidate chosen on val, so selection happens before the test seal.

## Where each honesty guardrail lives

The pipeline's honesty is the sum of per-phase invariants, applied in order:

1. **ask-if-missing (intake)** — a missing NEEDED input is a question for the user,
   never a fabrication. Wrong here and everything downstream measures nothing.
2. **hard gate (implement-and-check)** — `acapo check` must be green; the adapter
   must be implemented and the scorer deterministic before any budget is spent.
3. **freeze-once split + headroom (baseline)** — the split is written once and
   seeded; if the seed already saturates val, stop.
4. **val-only significance gate (the loop)** — acceptance is decided on val, by
   Δ > k·SE, never on train (overfit) and never on test (leak).
5. **sealed test, scored once (finalize)** — `test_used` makes re-scoring an error,
   so the headline number is unbiased.
6. **honest reading (report)** — test vs baseline, the val-test gap as overfitting,
   pass^k as reliability, uncertainty always shown.

orchestrate's contribution is that these are applied *automatically and in order*,
rather than depending on an operator to remember each one under time pressure.

## Stop rules — and why each exists

- **budget exhausted** (`max_iterations` / `max_metric_calls` / `max_usd`): the
  hard ceiling.
- **stall** (N consecutive rejects): the search has plateaued. Because the gate
  rejects non-significant gains, a run of rejects means remaining proposals are
  not clearing the noise floor — more tries mostly burn budget. Stalling early
  also limits the multiple-comparisons exposure (every extra candidate is another
  chance for a noise spike to look like a win).
- **no headroom**: the baseline already saturates val; there is nothing to gain.

Whatever the reason, the run **always ends with finalize + report**. A run that
stops without scoring the sealed test has produced edits but no result — and a
result is the only deliverable.

## Sources
- GEPA: Reflective Prompt Evolution (Agrawal et al., 2025) — the
  propose → reflect → evaluate → select loop orchestrate sequences:
  https://arxiv.org/abs/2507.19457
- τ-bench (Yao et al., 2024) — reliability (pass^k) as the end-of-run signal:
  https://arxiv.org/abs/2406.12045
- Koehn, "Statistical Significance Tests for MT Evaluation" (EMNLP 2004) — the
  significance discipline the acceptance loop enforces:
  https://aclanthology.org/W04-3250/
- Hastie, Tibshirani, Friedman, *Elements of Statistical Learning* — train/val/test
  roles the DAG encodes: https://hastie.su.domains/ElemStatLearn/

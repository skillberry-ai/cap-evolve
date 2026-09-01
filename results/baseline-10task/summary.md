# Baseline — 10-task Sonnet 4.6 (validation-only)

**Date:** 2026-07-29
**Model (agent):** claude-sonnet-4-6 (via ETE LiteLLM)
**Optimizer:** none (baseline-only — `--max-iterations 0`)
**Task set:** 10 authored "shared-office" tasks from SkillsBench (7 val + 3 test), the intake-example set inherited from parent HANDOFF.
**Baseline JSON:** `baseline_all.json` (cap-evolve `run_baseline/baseline.json`)
**Run dir:** `.capevolve/run_baseline/`

## What this run was for

Validate the end-to-end pipeline (cap-evolve → bench → podman → agent → verifier) on
the 10-task setup the parent HANDOFF describes. **Not** a scientific baseline; just a
plumbing smoke.

## Aggregate

| Metric | Value |
|---|---|
| Mean reward | 0.1429 |
| Stderr | 0.1429 |
| pass_at_1 | 0.1429 (1/7 val tasks) |
| pass_at_2 | 0.1429 |
| Wall clock | ~57 min |
| Infra errors | 0 (after workarounds) |
| Cost (recorded) | $0.00 (bench telemetry gap) |

## Per-task (val split, 7 tasks × 3 trials)

| task | reward | trials | note |
|---|---|---|---|
| invoice-fraud-detection | 1.000 | [1.0, 1.0, 1.0] | 3/3 |
| offer-letter-generator | 0.000 | [0.0, 0.0, 0.0] | real verifier fail |
| exceltable-in-ppt | 0.000 | [0.0, 0.0, 0.0] | real verifier fail |
| xlsx-recover-data | 0.000 | [0.0, 0.0, 0.0] | 1 trial timed out at 600s |
| sales-pivot-analysis | 0.000 | [0.0, 0.0, 0.0] | real verifier fail |
| weighted-gdp-calc | 0.000 | [0.0, 0.0, 0.0] | **all 3 errored at container build** (libreoffice postinst, before dpkg-statoverride wrapper) |
| financial-modeling-qa | 0.000 | [0.0, 0.0, 0.0] | real verifier fail |

## Notes

- `weighted-gdp-calc` errored at image build during this run — every "0.0" for that task
  was actually an infra error, not a real skill defect. Re-ran once workarounds landed
  and it still failed the verifier, so the number is right by accident.
- Only `invoice-fraud-detection` passes reliably. This is our starting point.
- `run_baseline_FIRST_TRY_all_zero/` and `run_baseline_SECOND_TRY_dpkg_chown/` under
  `.capevolve/` are earlier attempts that hit infra errors on every task; kept for
  reference but no useful numeric data.

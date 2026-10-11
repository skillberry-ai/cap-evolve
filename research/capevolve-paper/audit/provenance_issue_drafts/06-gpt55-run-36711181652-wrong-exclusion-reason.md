# GPT-5.5 run 36711181652 is excluded for the wrong stated reason

## Problem
`CLAIMS_LEDGER.md`: excluded because "different commit and proxy ... and a baseline 10 points below the others", values reported apart as 28.9 -> 89.8.

## Evidence
`metrics.jsonl` for 36711181652: 55 of 280 rows `opt_infra`; issue #538 shows all 55 are `litellm.RateLimitError: Budget has been exceeded` on `ibm-ete-int`. The 28.9 baseline is the seed on the 225 surviving tasks; the same seed scores 38.6 on all 280 (two gateways). Recomputed paired 28.89 -> 89.78 (CI [54.2, 67.1] on delta), recalculated 76.0 -> 90.2. With infra as failures: 72.1.

## Impact
The exclusion is correct, but reporting 28.9 as a "baseline" or 89.8 as a result is wrong; the 55 failed tasks are non-random.

## Correction
Describe it as an incomplete run (budget exhaustion), not a lower baseline; do not tabulate 89.8.

## Acceptance
Ledger and paper text corrected; run appears in an "incident/excluded runs" table with reason.

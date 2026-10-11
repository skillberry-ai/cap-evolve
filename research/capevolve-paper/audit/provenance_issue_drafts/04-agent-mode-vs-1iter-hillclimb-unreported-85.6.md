# A 1-iteration hill-climb from an empty seed (85.6 test) is unreported and exceeds the 8-round agent-optimize headline (76.4)

## Problem
Run 36306060353 is described everywhere as the "no-capability control" with test 62.9. It is actually a `hill-climb-all` run (1 iteration, Opus 5) whose champion `cand_0001` scored **85.6** on the same 280 test tasks and scorer as the 8-round agent-optimize champion (76.4).

## Evidence
`36306060353/.../steps.jsonl`: baseline val 0.60, iterate cand_0001 val 0.85 accepted ($15.84), finalize test 0.8536, finalize_baseline 0.6295. `metrics.jsonl`: paired 62.9 -> 85.6 (72 up / 9 down, 2 infra). Same split (seed-42) and recalculated scorer as 36175707483 (63.2 -> 76.4, $57.85). Neither README nor issue #538 mention the optimized side; the draft's `nSBnoskill` uses only the baseline.

## Impact
Undercuts any claim that agent-optimize is the better algorithm on this benchmark, and shows an empty seed is a better starting point than the pristine seed (which adds nothing over no skill: 177 vs 175 of 280). n=1 each, different seeds, so it is a flag, not a ranking.

## Correction
Report both sides of 36306060353 in the history table; do not cite agent-optimize SpreadsheetBench as evidence of superiority without a matched comparison.

## Acceptance
Table row for 36306060353 shows 62.9 -> 85.6 with scorer; matched agent-optimize vs hill-climb-all experiment (>=3 seeds each, same empty seed, same split/scorer) is scheduled.

# run_20260909_092628 — rfe-creator (local, informal)

This is a **dashboard-only publish**, not a benchmark-history record: there is
no matching entry in `../../records/` and no row in `benchmarks.json`. It will
not appear in the main benchmarks table, filters, or the "Running now" panel.
It is reachable only via its direct URL:

  `https://skillberry-ai.github.io/cap-evolve/benchmark-ui/runs/run_20260909_092628__local-rfe-creator/ui/`

## Why no record

This run predates `rfe-creator`'s addition as a dispatched CI benchmark
(`ci/benchmarks/rfe-creator/`, PR #492). It was run directly against a local
checkout with `store: git`/`dashboard: auto`, not through `run_suite.sh`, so
it has no `final.json` and its test split is identical to train/val by
design — not a sealed, held-out result. Per `ci/benchmarks/PUBLISHING.md`,
a `benchmark-history` record requires `final.json` to exist and
`runmeta.json.conclusion == "success"`; neither is true here, and forcing an
entry would put a null/misleading reward on the public table.

## What it actually is

Hill-climb optimization of the RFE-Creator skill pipeline — Claude Code
Haiku 4.5 as agent, Opus 5 as optimizer, 25 tasks x 3 trials,
`train == val == test == all 25 tasks` (no-holdout FIT). **Not finished**:
3 of 10 budgeted iterations ran; the 4th was abandoned mid-rollout.

| stage | val reward |
|---|---|
| baseline (seed) | 0.897 +/- 0.017 |
| cand_0001 (rejected) | 0.906 |
| cand_0002 (accepted) | 0.913 |
| cand_0003 (accepted, champion) | 0.925 +/- 0.011 |

Full artifacts (JOURNAL, events, candidates, rollouts) are in the private
`cap-evolve-internal` repo.

## Getting a real, published result

Dispatch `Actions -> Benchmarks -> rfe-creator` (`smoke` or `full`) on the
`ibm-vpc` runner. A completed dispatch produces `final.json`, and the
existing `aggregate` job publishes the benchmark-history row and this same
kind of dashboard snapshot automatically — no manual steps needed.

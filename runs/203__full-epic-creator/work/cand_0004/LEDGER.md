# LEDGER — factual run record (framework-maintained; READ-ONLY)

The measured record of every iteration: which candidate, its parent, whether the gate ACCEPTED it, the val reward + Δ, and the tasks it broke / fixed. Facts only — your own narrative, lessons, and refuted hypotheses go in JOURNAL.md. Use this to never re-introduce a change that broke a task, and to see which approaches the gate accepted vs rejected.

`broke` / `fixed` list only tasks whose move EXCEEDED 2·SE of its own per-task measurement error, so they are claims the measurement can support. A task that moved by less is in `unresolved`: it is NOT evidence the edit did anything to that task, in either direction, and must not be reasoned about as a regression or a win. Do not redesign an edit because a task appears there — re-measure it, or ignore it.

## Iterations
| iter | candidate | parent | outcome | val | Δ vs parent | broke (were passing) | fixed | unresolved (moved < 2·SE) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | cand_0001 | seed | ACCEPT | 0.982 | +0.064 | {} | {case-015-redundant-hlrs} | {case-013-human-process-gates, case-014-tech-preview-foundation, case-018-cross-strategy-dependency, case-020-hardware-dependent-investigation, case-024-real-default-vector-store} |
| 2 | cand_0002 | cand_0001 | ACCEPT | 0.992 | +0.011 | {} | {} | {case-013-human-process-gates, case-014-tech-preview-foundation, case-020-hardware-dependent-investigation, case-030-real-operator-structured-logging} |
| 3 | cand_0003 | cand_0002 | reject | 0.958 | -0.034 | {} | {} | {case-013-human-process-gates, case-024-real-default-vector-store, case-030-real-operator-structured-logging} |

## Current best: cand_0002

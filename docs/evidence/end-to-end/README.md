# End-to-end run from scratch — `agent-optimize`, agent mode

A full pipeline run on a fresh project, used to validate the changes in this PR and to shake out
bugs. It found **three**, all fixed here. Artifacts in this directory are the real outputs.

## What was run

`cap-evolve init` → `doctor` → `estimate` → baseline → one `agent-optimize` round (fan-out of 1 +
**two byte-identical null controls**) → gate → `commit` → `finalize` (sealed) → `report` + dashboard.

**Capability:** a system prompt. **Task:** normalise a date mentioned in a sentence to ISO 8601,
scored by exact match (`tasks.jsonl`, 48 tasks, deterministic and committed here).
**Splits:** train 24 / val 12 / test 12, seed 0 (`splits.json`), test sealed.
**Agent:** `gpt-oss-120b` through an OpenAI-compatible gateway, 3 trials per task.

The seed prompt is deliberately underspecified — it never states an output contract — so the model
answers in prose (*"The date referred to is **January 19, 2018**."*) and exact match scores 0. That
is the headroom the optimizer has to find, and it is a realistic defect rather than a staged one.

## Result

| | val | sealed test |
|---|--:|--:|
| baseline (seed prompt) | **0.000** | — |
| `cand_contract` (accepted) | **1.000** | **1.000** |

Two null control replicates both measured **0.000**, so this round's null delta is exactly **0.0** —
the task is deterministic, so unlike τ²-bench there is genuinely no measurement noise to clear. One
candidate, one accept, no regressions. 58,627 tokens, **$0.0174**, 308s wall.

The edit was a stated output contract: ISO 8601, date only, zero-padded, one example. Full diff in
`dashboard-lower.png`; `report.md` and `final.json` are the run's own output.

Note the gate's own warning, visible in `cli.png`: **"combined/paired SE is 0"** — with a
deterministic task the significance test is degenerate, and the harness says so rather than
accepting on a divide-by-zero.

## Three bugs this run found, all fixed in this PR

1. **`doctor` misdiagnosed a missing optimizer registry.** With no `optimizers/registry.yaml` under
   the skills dir it reported *"claude-code is not in optimizers/registry.yaml"* and advised picking
   a different optimizer — sending the user to edit a spec that was already correct. It now
   distinguishes "no registry" (fix: install / set `CAPEVOLVE_SKILLS_DIR`) from "name not in
   registry" (fix: pick a registered name).

2. **`doctor` demanded optimizer credentials in agent mode.** In `orchestration_mode: agent` the
   driving agent *is* the optimizer and no optimizer process is spawned, so its API key is never
   read. The check now reports that explicitly instead of warning about a key that cannot matter.

3. **The test seal could be re-scored after a crashed finalize.** The most serious of the three.
   Seal-on-success deliberately lets a finalize that dies mid-scoring be retried — but it cannot
   tell "crashed *before* scoring test" from "crashed *after*". In this run a finalize killed by a
   foreground timeout had already scored the test split; the retry scored it again, and the reported
   number came from a **second look at held-out data**. The run's own cost ledger shows it: three
   `evaluate` events on `test` against a single `finalize`.

   Fixed with `RunDir.begin_test_attempt()`, called once per finalize: a retry is refused when test
   rollouts already exist, while a genuine crash-before-scoring retry still works. The guard is at
   *attempt* granularity on purpose — one honest finalize scores test twice by design (`FINAL` for
   the best, `FINAL_seed` for the baseline), and putting the check in `reserve_test` broke exactly
   that, in seven core tests. Pinned by `core/tests/test_test_seal_rescore_guard.py`, including a
   regression test for the granularity mistake.

## Files

| file | what it is |
|---|---|
| `cli.png` | `cap-evolve doctor` (all green) and `report --terminal` |
| `dashboard-top.png` | summary tiles, run status, pipeline phases, score curve, per-task matrix |
| `dashboard-lower.png` | prompt diff, lineage, evaluations table, cost ledger |
| `report.md`, `final.json` | the run's own report and sealed-test summary |
| `tasks.jsonl`, `splits.json` | the task set and the frozen splits, so the run is reproducible |

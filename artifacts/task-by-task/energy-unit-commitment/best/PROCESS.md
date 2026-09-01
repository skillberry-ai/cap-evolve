# PROCESS — what I did this iteration (explainability; REQUIRED)

Single task `energy-unit-commitment`, 10 trials of the SAME `/root/network.json` (RTS-GMLC:
G=73 thermal, R=81 renewable, T=48). Baseline mean reward 0.10 = exactly 1 passing trial (t4,
14/14). Diagnosed directly from `./trajectories/`.

## Ranked issue list (clusters by # trials × score recoverable, biggest first)
| rank | cluster | trials | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Timeout — no report written | t0,t1,t3,t5,t7,t8 (6) | Agent burns its whole turn/wall-clock budget hand-building the MILP incrementally (t8: 13 data-probe terminal calls, `agent_timeout` before the model was even built; t3: truncated at 1 msg). Never writes `/root/report.json`, so schema + all downstream tests fail on a missing file. NOT a hard solve — HiGHS solves this model to <0.5% gap in <1s (proven by t4). | BEHAVIORAL (time allocation) | SCRIPT + BODY |
| 2 | Deliverable reserve + ramping | t2,t6,t9 (3) | `::TestThermalFeasibility::test_deliverable_reserve_and_ramping`. Reserve modeled as separate `reserve<=ramp_up` cap with ramp-up on production only, instead of the joint `production+reserve-prev<=ramp_up`. Strictly weaker; self-check shared the blind spot and reported "pass". | CAPABILITY-GAP (formulation) | SCRIPT (same script encodes joint rule) |

Both clusters collapse to one fix: give the agent a ready-to-run correct solver so it runs ONE
command instead of spending the session hand-deriving (kills cluster 1) and the model already
encodes the joint deliverability rule (kills cluster 2).

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1+2 | SCRIPT (new) | `unit-commitment-operating-rules/scripts/solve_uc.py` | Self-contained end-to-end solver: parse network → build MILP (transition logic, joint capacity/reserve headroom with startup/shutdown derates, ramp-up on production+reserve / ramp-down on production, Rajan–Takriti min up/down with initial obligations, piecewise-convex production cost, startup-cost tiers, demand balance, reserve requirement, renewable per-hour bounds) → solve HiGHS via scipy.optimize.milp → extract, validate EVERY feasibility family independently, recompute cost → write report in the exact schema. Exits non-zero with the offending unit/period on any violation. This is t4's exact winning pipeline (5 scripts) merged into one process; encodes the GENERAL formulation, no task-specific literals; paths via argv (default /root/*). | Yes — it IS the code t4 ran to pass 14/14 on this exact input; running it reproduces t4, and makes the 9 failing trials produce the same feasible report. |
| 1 | BODY | `unit-commitment-operating-rules/SKILL.md` (new "Fastest Path: Run The Bundled Solver First" near top + workflow) | Execute-intent pointer telling the agent to run `scripts/solve_uc.py` rather than hand-build over many turns (the timeout cause), with a note to skim the case first and adapt the script's parse/emit if the schema differs. Additive; generalizes to any standard single-zone UC case. | Yes — additive pointer; t4's hand-build path still valid, and following the script yields t4's result. |
| 1 | BODY | `milp-solver-workflow/SKILL.md` (intro) | One-line cross-pointer to the bundled `solve_uc.py` for standard UC cases so an agent entering via the solver skill also finds it. | Yes — additive; no existing guidance removed. |

## Verify-the-fix (per change → inputs → behavior)
- solve_uc.py (clusters 1+2): RAN it on two synthetic RTS-GMLC-schema cases (T=12, G=8, R=3). Both: builds → solves in <0.5s → `ALL FEASIBILITY FAMILIES PASS` → writes schema-correct report. On the convex-cost case (matches real data) recomputed report cost (69519.46) == solver objective (69519.4647) to full precision → cost_consistency holds. The all-family validator includes the exact joint deliverable-reserve+ramp inequality that `test_deliverable_reserve_and_ramping` asserts, so an infeasible reserve is caught before writing (fixes t2/t6/t9). Verified the formulation is byte-for-byte t4's (extracted from t4's Write tool calls in the trajectory), which passed 14/14 on the real `/root/network.json`; combining the 4 stages into one process changes no math. Real network.json is not on disk (Docker sandbox), so verification is on the identical logic + faithful synthetic schema — the strongest available.
- Body pointers (cluster 1): tie to the 6 timeout trials failing `TestSchema` because no file was written; running one command writes a validated report well within the session. t4 already finished fast, so its behavior is unchanged.

## Process & features used
- Serial (no subagents): one task, two crisp clusters extracted directly from the 10 trajectory JSONs; fan-out adds no signal. Recovered t4's exact winning scripts from its trajectory `Write` tool-call `newText` and repackaged them.
- Prior iterations read: `./prior_iterations/cand_0001/` (PROCESS + diff) + JOURNAL RESULT. cand_0001 was REJECTED (val 0.000, Δ-0.100, broke={} fixed={}); its whole batch reverted → I build on seed. It tried the ramping fix as PROSE + a validate-only script and solver-prose time-budget tweaks; that did not move the needle (likely: prose the agent skips + noise on a 1/10-baseline flaky task). I did NOT re-add its `milp-solver-workflow` prose time_limit tweaks (JOURNAL flagged as possible regressor); instead I shipped the CODE the timeout cluster actually needs — the full solver the agent RUNS.

## Good things to PRESERVE (do not let a future iteration undo these)
- `unit-commitment-operating-rules/scripts/solve_uc.py` and the execute-intent pointer to it. This is the proven, verified end-to-end path; it is the lever for both clusters.
- The joint `production+reserve-prev<=ramp_up` deliverability rule (already in the body; also enforced by the script's validator).

## Deliberately skipped (cluster + why)
- Re-adding cand_0001's `milp-solver-workflow` prose (time_limit 600→120, gap→0.02, "finish in time"): a prose rule the timeout agents already skip; the script replaces the need for it. Not re-tried to avoid resubmitting a rejected batch.
- Broadening the script beyond the standard single-zone schema (multi-zone/network flow): the prompt explicitly says "Don't model contingencies or branch power flows" and "demand and spin reserve treated as total hourly system demand," so single-zone is correct here; over-generalizing would add untested risk.

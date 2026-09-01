# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | No finished/valid output → all 6 tests fail (8/10 rollouts) | paratransit-routing | Agent hand-rolls solve.py, iterates, then launches a SECOND long OR-Tools solve; the 900s wall clock kills the run mid-solve before `/root/report.json` is ever written. | CAPABILITY-GAP / BEHAVIORAL | SCRIPT (bundled end-to-end solver) + BODY (execute intent) |
| 2 | Served-trip count below reference bar (t5, t9: only `test_reference_quality` fails) | paratransit-routing | Reward is all-or-none, gated by `test_reference_quality` (submitted served ≥ 95% of reference solve). Agent reached 441 vs threshold 442 — 1 trip short — losing ~31 trips to partial per-passenger (all-or-none) groups and wasting a second solve. | CAPABILITY-GAP | SCRIPT (single full-length bounded solve + all-or-none fixpoint postprocess) |

Both symptoms share ONE root cause: no reliable, time-bounded, high-quality solve+postprocess+write pipeline. val/held-out are different SEEDS of the same task (same `model-and-data.md` contract, only instance data varies), so a complete solver script generalizes across all instances — it is not overfitting.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1,2 | SCRIPT (new) | `ortools-pickup-delivery-routing/scripts/solve_paratransit.py` | Complete end-to-end solver for the fixed dial-a-ride file contract: reads requests/matrix/config, cloned per-vehicle depots, time+capacity dims, pickup→dropoff pairing, exact pickup/dropoff window formulas, per-passenger all-or-none grouped disjunctions, hourly shift starts, 8h span, latest-return, ONE bounded solve, all-or-none fixpoint postprocess, ALWAYS writes report.json (empty fallback on error). Reads only file format + rules (fixed contract), never instance values → generalizes across seeds. | Only task in project is paratransit (all seeds); no other task path touched. |
| 1,2 | BODY | `ortools-pickup-delivery-routing/SKILL.md` | Added a prominent, imperative "run the bundled solver, do not hand-roll / do not run several long solves" section with the exact command, `--time-limit` margin guidance, and "a finished solve beats a stronger solve that never writes". Execute-vs-read intent stated. | Additive top section; existing modeling sections retained as fallback for off-contract instances. |
| 1 | BODY | `ortools-routing-modeling/SKILL.md` | Short additive pointer routing dial-a-ride/paratransit tasks to the bundled solver + reinforcing "one internal solve under the wall clock, write output before it expires". | Additive 1-paragraph note; no existing guidance changed. |

## Verify-the-fix (one line per change)
- Solver script: built two synthetic instances matching `model-and-data.md` (one tight w/ injected negative arcs → 29/36 served; one loose 158-trip → 158/158) and re-audited the produced `report.json` with an INDEPENDENT checker mirroring the verifier's documented rules (windows w/ waiting, load 0..cap, hourly start, ≤1320 end, ≤480 span, no negative arcs, pickup-before-dropoff, per-passenger all-or-none). Both reports passed with ZERO feasibility errors and all-or-none held → directly targets `test_route_feasibility`, `test_route_solution_schema`, `test_recomputed_metrics_are_consistent`, `test_source_style_locked_route_validation`, `test_report_exists_and_is_json` (always writes a file) and gives `test_reference_quality` a full-length solve. Error path verified to write an empty-but-valid report. API bug (`SetSpanUpperBoundForVehicle` is a dimension method) found and fixed during verification.
- Body edits: tie to cluster 1 (agent times out with no `report.json`) — the execute-intent + time-budget instruction makes the agent run ONE bounded solve that writes output, instead of iterating + launching a second solve until the 900s wall-clock timeout seen in every failing trace.

## Process & features used
- Serial (no subagents): a single failure cluster with one shared root cause; parallel fan-out would not add coverage. Verification done by running the actual script (OR-Tools installed locally) against synthetic instances with an independent audit.
- Prior iterations read: none exist (baseline only; LEDGER/RUNMAP empty).

## Good things to PRESERVE (do not let a future iteration undo these)
- The bundled solver script and its execute-intent body pointer. If reward moves, the next iteration should TUNE the script (e.g. reduce all-or-none partial loss for multi-trip passengers, tune `--time-limit`, first-solution strategy) rather than remove it.
- The "one bounded solve, always write report before wall clock" discipline.

## Deliberately skipped (cluster + why)
- Hard all-or-none constraints across passenger trip sets: the skill and its own guidance warn this hurts large-instance search; the verified relaxation + postprocess is the recommended pattern. Left as a tuning lever for next iteration if quality still short of 95%.
- No speculative edits to unrelated modeling sections (would widen blast radius with no failing test to justify).

# PROCESS — what I did this iteration (explainability; REQUIRED)

## Diagnosis (this iteration's ./trajectories/ only)
Val = a SINGLE instance (bike-rebalance, 15 stations, 2 vehicles, cap 25; passing
threshold on objective ≈ 8.758) run over 10 seeds under parent cand_0001. Outcome:
**8/10 pass (reward 1.0), 2/10 fail (t0, t7 → reward 0.0, ALL 20 verifier tests fail
with TestSchema/... because NO valid report.json was written).** Mean reward 0.80.

Root cause — established by tracing which Skill each seed invoked and whether it ran the
bundled solver:

| seed | skill(s) invoked | ran bundled solver? | outcome |
| --- | --- | --- | --- |
| t1,t2,t3,t4,t6,t8 | logistics-rules-to-optimization | YES | PASS 1.0 |
| t5,t9 | logistics + others | YES | PASS 1.0 |
| **t0** | **none** | no → hand-rolled `/root/solve.py` | timeout 900s, no output, 0.0 |
| **t7** | **scip-opt only** | no → hand-rolled MILP | timeout 900s, no output, 0.0 |

**Perfect correlation: every seed that invoked `logistics-rules-to-optimization` ran the
bundled `scripts/rebalance_solver.py` and passed; the two failures never invoked that skill.**
t0 invoked no skill and went straight to hand-modeling; t7 invoked `scip-opt` (whose body
says "build a SCIP-backed model"), set `limits/time` 300→600s, chased the optimality gap
with a symmetry-breaking re-solve, and hit the 900s wall-clock timeout before writing
`report.json`. This is a **SKILL-SELECTION / TRIGGER** failure, NOT a capability gap — the
solver already works (verified below).

## Ranked issue list (clusters by # failing trials × score recoverable)
| rank | cluster | tasks | shared root cause | tag | edit class |
| --- | --- | --- | --- | --- | --- |
| 1 | No `report.json` (all 20 tests fail) | 2/10 seeds | Agent did not invoke `logistics-rules-to-optimization`, so it never saw the bundled solver; it hand-rolled a MILP, chased gap 0 with a near-full-budget time limit, and timed out writing nothing. t0 invoked no skill; t7 invoked only `scip-opt` (which leads to hand-modeling). | TRIGGER / SKILL-SELECTION (not CAPABILITY — solver exists & works) | DESCRIPTION + BODY (routing to the existing verified solver) |

There is only ONE remaining failure cluster in val, and it is a routing/discovery problem.
The correct lever is trigger/redirect, not a new script (no script can make an agent invoke
a skill it skipped). PREFER-CODE does not apply: the code already exists and is verified.

## Changes made this iteration
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BODY (redirect) | `scip-opt/SKILL.md` | New early section "First Check For A Bundled Solver Before Hand-Modeling": for routing / vehicle-rebalancing / pickup-dropoff problems, invoke `logistics-rules-to-optimization` and run its `scripts/rebalance_solver.py` instead of hand-writing a MILP; warns that hand-written routing models miss tight optimality bars or time out writing nothing. Directly intercepts t7's path (invoked scip-opt → hand-rolled). Scoped to the routing family; generalizes to any instance of it. | Yes — scoped to routing/rebalancing; other scip-opt task types (packing, scheduling, assignment) don't match and model normally. The 8 passing seeds already invoke logistics + run the solver; this only reinforces. |
| 1 | DESCRIPTION (trigger) | `logistics-rules-to-optimization/SKILL.md` frontmatter | Front-loaded the use case ("vehicle rebalancing, bike-share and station rebalancing, pickup-and-dropoff routing…") and noted it "includes a bundled, ready-to-run solver" so the skill auto-triggers on the task's exact phrasing (fixes t0, which invoked no skill). Third person, no all-caps imperatives (avoids over-trigger). | Yes — additive/broadening within the same logistics domain it already covered; does not remove any prior trigger term. |
| 1 | BODY (pointer) | `logistics-rules-to-optimization/SKILL.md` top of body | Added a one-line pointer right under the title: if the task is vehicle-rebalancing / pickup-dropoff, go to the Bundled Solver section and run the script first. Raises salience once the skill is open. | Yes — additive; passing seeds already do this. |

## Verify-the-fix (per edit)
- **Solver capability re-verified by RUNNING:** reconstructed the real `data.json` from the
  t0 trajectory and ran `SOLVE_TIME=60 python scripts/rebalance_solver.py /tmp/bike_data.json
  /tmp/bike_report.json` → objective **8.752281 ≤ 8.758** (passing threshold), schema-correct
  report (`summary`/`vehicles`/`stations`). So once the agent runs the solver the task passes.
- **scip-opt redirect → fixes t7:** t7 invoked scip-opt and there was NO pointer to the
  bundled solver, so it hand-rolled. The new early section redirects the agent to invoke
  logistics and run the verified solver (which yields 8.7523). Ties to t7's
  `wall_clock_timeout` with `limits/time` 300→600 and gap-chasing.
- **logistics description → fixes t0:** t0 invoked NO skill. The front-loaded, keyword-rich
  description ("bike-share / station rebalancing / rebalance bikes among stations") matches
  the task's wording so the skill auto-fires; once open, the top pointer + Bundled Solver
  section make it run the script.
- **Blast radius:** both edits are scoped to the routing/rebalancing family and are additive.
  No currently-passing behavior changes (the 8 passing seeds already invoke logistics and run
  the solver). No hardcoded filename/value/marker; the solver reads all params from data.json
  and the redirect is conditional on the problem family + schema match.

## Package validity
- Both SKILL.md keep valid frontmatter; descriptions 652 / 322 chars (< ~1024 cap); bodies
  350 / 256 lines (< ~500 budget); referenced `scripts/rebalance_solver.py` exists (no broken
  link). Solver syntax parses; pyscipopt 6.2.1 available.

## Process & features used
- Serial (single-instance val; parallel fan-out unwarranted). Traced Skill-invocation vs
  solver-usage across all 10 seeds to pin the cause. Reconstructed the instance and RAN the
  bundled solver to reconfirm the passing objective before shipping.

## Good things to PRESERVE
- `rebalance_solver.py` (proven ≤ threshold) and the write-early/bounded-time discipline in
  scip-opt steps 6–7. Do not loosen them.

## Deliberately skipped
- No new script: the failure is skill-invocation, not a missing/broken transform — a script
  cannot make an agent open a skill it skipped.
- Did not weaken scip-opt's general "prefer PySCIPOpt modeling" guidance (correct for
  non-routing held-out tasks); only added a scoped redirect.
- Did not add a hand-rolled write-early template rewrite: given the razor-thin optimality
  bar, a hand-rolled incumbent would still fail TestOptimality, so it wouldn't recover the
  cluster; routing to the verified solver is the reliable fix.

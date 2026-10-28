# FRAMEWORK-IMPROVEMENTS — suggestions for cap-evolve itself (cross-run)

NOT about this capability or this run's result — about what cap-evolve the FRAMEWORK should change so FUTURE runs (any capability, any project) go better: a confusing prompt section, a missing tool, a file you wished existed, a gate that felt wrong. Optional most iterations; add an entry whenever something about the framework itself (not the task) got in your way or surprised you.

<!-- cap-evolve:framework-improvements-append-below -->

## Iteration cand_0001
- The trajectory rollout JSONs contain the full produced-artifact file map (`rollout.output.files`), but the task-summary feedback lines are truncated mid-sentence (~200 chars). Diagnosing "which judge failed and on which file" required re-reading the raw JSONs; a per-trial structured field (`failed_judges: [{name, message}]`) would save every iteration that first re-parsing pass.
- The rollout artifacts do NOT include `.context/rhai-components.txt` (provisioned input, not collected output), so a validator designed against the traces must fetch the canonical list from the eval cases dir — fine here because it's readable, but a future run with an opaque dataset would not be able to verify component-vocabulary edits at proposal time. Mirroring the per-case component list into the rollout record (like annotations do) would make that class of edit verifiable offline.
- Grader inconsistency observed: case-018's identical priority-inheritance defect scored 5/5 in t0 and 4/5 in t2. Nothing to fix in the framework, but per-task SE on the gate comparison should absorb it — worth remembering when a "regression" of one dq point on one trial may be noise.


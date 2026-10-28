# FRAMEWORK-IMPROVEMENTS — suggestions for cap-evolve itself (cross-run)

NOT about this capability or this run's result — about what cap-evolve the FRAMEWORK should change so FUTURE runs (any capability, any project) go better: a confusing prompt section, a missing tool, a file you wished existed, a gate that felt wrong. Optional most iterations; add an entry whenever something about the framework itself (not the task) got in your way or surprised you.

## Iteration cand_0001
- The trajectory rollout JSONs contain the full produced-artifact file map (`rollout.output.files`), but the task-summary feedback lines are truncated mid-sentence (~200 chars). Diagnosing "which judge failed and on which file" required re-reading the raw JSONs; a per-trial structured field (`failed_judges: [{name, message}]`) would save every iteration that first re-parsing pass.
- The rollout artifacts do NOT include `.context/rhai-components.txt` (provisioned input, not collected output), so a validator designed against the traces must fetch the canonical list from the eval cases dir — fine here because it's readable, but a future run with an opaque dataset would not be able to verify component-vocabulary edits at proposal time. Mirroring the per-case component list into the rollout record (like annotations do) would make that class of edit verifiable offline.
- Grader inconsistency observed: case-018's identical priority-inheritance defect scored 5/5 in t0 and 4/5 in t2. Nothing to fix in the framework, but per-task SE on the gate comparison should absorb it — worth remembering when a "regression" of one dq point on one trial may be noise.

<!-- cap-evolve:framework-improvements-append-below -->

## Iteration cand_0002
- The flaky-task framing ("pass sometimes; make the good behavior consistent") is accurate, but the iteration prompt's inline summary interleaves task feedback snippets mid-instruction (the "(b) 3 FLAKY task(s)" block pastes grader rationale fragments into the directive text, truncated mid-sentence). A compact per-trial table (task, trial rewards, failing judge, one-line gap) would state the target set more reliably than pasted rationale prose — I had to rebuild exactly that table from the rollout JSONs anyway.
- The trajectories again paid for themselves as the verification surface (extracted artifacts → corpus-run the new validator check), but each iteration re-derives the same extraction script. A small tool in the work dir (`extract_trial_artifacts.py <trajectory.json> <dir>`) would make corpus blast-radius verification a one-liner and more likely to actually happen in iterations with tighter budgets.
- Observed grader-behavior fact worth surfacing to future runs of this benchmark: the dq judge and the mechanical implementation_type_rules judge can DISAGREE on the same edge (dq praised the konflux→general edge as a genuine artifact dependency while the soft gate failed it). When two judges conflict, the optimizer needs the judge priority explicit — here the mechanical gate's −0.1 dominates — otherwise an iteration can "fix" toward the LLM judge's preference and lose score.


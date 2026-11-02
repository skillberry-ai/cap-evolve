# FRAMEWORK-IMPROVEMENTS — suggestions for cap-evolve itself (cross-run)

NOT about this capability or this run's result — about what cap-evolve the FRAMEWORK should change so FUTURE runs (any capability, any project) go better: a confusing prompt section, a missing tool, a file you wished existed, a gate that felt wrong. Optional most iterations; add an entry whenever something about the framework itself (not the task) got in your way or surprised you.

- A harness-side translator that converts `<|tool_call>call:python_interpreter {code: "..."}`-style
  replies into a fenced code block (or at least a retry with the format rule re-asserted) would
  deterministically fix ~11 zero-score tasks that no prompt edit can reliably reach; the corrective
  "No python code block was found" message was ignored 3x in a row within single episodes.
- Rejecting byte-identical code resubmissions (hash per episode, force a "change approach or
  finalize" message) would break the 30-round degenerate loops; the model has no other stop signal
  when its code prints nothing.
- Several val tasks are dominated by litellm timeouts (7 of 120); retry/backoff at the rollout
  layer would recover more reward than any capability edit on those tasks.

## From iteration cand_0002
- When a candidate is rejected, record WHY it scored 0 (lint failure? smoke failure? placeholder?
  rollouts ran but behaviorally zero?). cand_0001 was rejected at val=0.000 with no error string,
  and its stored diff.patch is truncated mid-hunk ("... (truncated)" at 90 lines), making the root
  cause unrecoverable — the next iteration cannot distinguish "the idea was wrong" from "the
  packaging was broken". Storing the validator's output and the FULL diff would fix this.
- Per-task rollout traces of a rejected candidate are not copied into prior_iterations/ — only
  PROCESS.md + diff.patch. For a candidate that ran, its trajectories would show exactly which
  edit broke which task; consider copying them (or a failure histogram) on rejection.

## cand_0003 (iteration 3)
- The gate records REJECTED at val=0.000 with no machine-readable REASON (lint failure? smoke
  failure? placeholder? out-of-surface file?). Both prior candidates died this way and their
  stored diff.patch files are truncated at ~90 lines / line width, so the optimizer cannot
  identify the failing element. Please stamp the rejection reason (which check, which file) into
  the RESULT line or rejected.jsonl — it would convert a 1-bit rejection into a diagnosis.
- The SpreadsheetBench rules say helper scripts "cannot be run as a CLI: there is no __main__"
  while the skill-package guidance requires a `--self-check` CLI entry point "because validation
  RUNS it". These two requirements conflict; state which one the lint/smoke actually enforces.
- INSTRUCTIONS recommends writing a root-level DIAGNOSIS.json while the surface contract says
  "three surfaces and nothing else" — ambiguous whether a root-level file invalidates a candidate.

## cand_0004
- Store the FULL diff.patch of rejected candidates, not a 90-line truncation: the journal shows two
  iterations lost because the mechanical-zero cause was unrecoverable from a truncated diff.
- Surface the lint/smoke-test RESULT (pass/fail + reason) to the optimizer immediately after
  candidate submission, or at least in the RESULT line — a 0.000 with "lint failed: ImportError:
  openpyxl" would have saved two full iterations of guessing.
- Consider running the helper lint in an environment that matches the agent kernel (which has
  openpyxl); if the lint env intentionally differs, document which imports are available there.
- The scorer feedback text sometimes misleads ("check where the data actually ends" on 48983, whose
  real issue was None-vs-0 blank semantics). A per-cell expected-vs-got sample (3 cells max, no full
  gold leak) would make diagnosis much faster.

## cand_0005
- With rollout budget enforced (1800/2160 at iteration 5 of 1000), the iteration count is
  misleading — the run ends at ~6 candidates, not 1000. Surface remaining-budget/rollouts in the
  INSTRUCTIONS header so the optimizer can plan (it currently must infer it from the budget line).
- A mechanical 0.000 wastes a full evaluation AND erases the behavioral information of otherwise
  good text edits in the same batch (cand_0004). Consider running lint/smoke BEFORE deducting
  rollout budget, or scoring the text surface separately when the script surface fails validation.

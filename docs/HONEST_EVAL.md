# Honest evaluation in cap-evolve

cap-evolve's one differentiator is that its numbers mean something. Optimizing a
prompt/skill/tool against a metric is trivially gameable — you can hill-climb on
the same data you report. The substrate (`cap_evolve`) makes that hard *by
construction*, and the rules below are enforced in code, not just documented.

## The five guarantees

1. **Seeded, frozen splits.** `make_splits(task_ids, seed, ratios)` partitions
   tasks deterministically. The split is written to the run dir once
   (`splits.json`) and every skill reads it back — no skill re-splits or peeks.

2. **The test set is sealed.** `RunDir.consume_test()` flips a `test_used` flag
   and raises `TestSealError` on any second access. The held-out number is
   produced exactly once, at `finalize`. (See `splits.py`, `rundir.py`.)

3. **Acceptance is gated on val, with significance.** `gate.decide(...)` refuses
   any split but `val` (`TrainGateError`) and, by default, accepts a candidate
   only when the improvement exceeds `k · SE` — so noise is not mistaken for
   progress (`mode="significant"`). Other modes (`strict`, `threshold`,
   `simplicity_tiebreak`) exist but never relax the val-only rule. The gate reads
   only the **primary** metric (the scalar `reward`); any shown-only secondary
   metrics a scorer emits (`Score.metrics`) are for display and cannot move the
   decision.

4. **Variance is measured, not assumed.** With `num_trials > 1`, each task gets a
   mean and stderr; `combined_stderr` mixes between-task and within-task error;
   `pass_k` reports the probability all k i.i.d. trials succeed (tau-bench style).

5. **The grader is tamper-evident.** Guarantees 1–4 make the *evaluation* honest, but
   when the capability is tool code or a skill package the optimizer is a coding
   agent with write tools — it could "improve" by editing `score()` instead of the
   target. `protect.py` SHA-256s the **protected paths** (by default `adapters/`,
   `capevolve.yaml`, the spec's `dataset_source` / `split_ids_file`, and `*gold*`
   data files) at `baseline` into `protected.json`, and re-verifies them **both before
   and after** every scoring pass — inside `evaluate_candidate` (the chokepoint every
   fresh score goes through), inside GEPA's `_eval_minibatch`, and once more
   immediately before `finalize` burns the seal. Any difference logs a
   `tamper_detected` event and raises `TamperError`, so the score is discarded rather
   than recorded and the test split is not sealed. A content hash, not mtime:
   `os.utime` is a one-liner. Declare a different grader location with
   `protected_paths` in `capevolve.yaml` (a malformed `protected_paths` is a hard
   error, never a silent fallback to the defaults).

   **Exactly what is guaranteed — and what is not.** This is *detection, not
   prevention*: nothing stops a write, and a hacked grader can execute. What is
   guaranteed is that a **byte-level change to a declared protected file, made at any
   point between `baseline` and `finalize`, is detected and aborts the run before the
   affected score is recorded, made best, or sealed** — and that the evidence
   (`protected.json` plus the `tamper_detected` event's expected/actual hashes) is
   left on disk. Concretely covered: source edits, deletions, newly-added protected
   files, a same-length edit with the mtime restored, a planted `.pyc` (`load_adapter`
   sets `sys.dont_write_bytecode` and clears the cache dir, so bytecode is hashed like
   any other file instead of being excluded), a protected file replaced by a symlink,
   a destroyed or rewritten `protected.json` (which hard-fails against the digest
   logged in `events.jsonl` rather than re-recording from the current tree), and a
   writer that lands *during* scoring (the post-scoring check).

   Residual gaps, stated plainly:
   - **A narrow race remains.** The post-check brackets the scoring window; it does
     not lock it. A writer that changes a protected file after the scorer's last read
     and restores it before the post-check hash is not detected. Closing that would
     require the scorer to hash the bytes it reads.
   - **Ground truth outside the project dir is not protected** — only paths under
     `.capevolve/project` can be hashed. A declared glob that matches nothing there
     logs `protected_paths_unmatched`, so the omission is visible, but it is still an
     omission.
   - **A project with no `adapters/adapter.py` gets no protection at all**, logged as
     `protected_manifest_skipped`.
   - **Detection is per-run.** The manifest records the tree as it was at *this* run's
     baseline; it does not attest that the checkout was clean to begin with.
     `--reuse-baseline` inherits the prior run's manifest and refuses a prior run that
     logged a tamper, but a grader hacked *before* baseline is recorded as pristine.
   - **The `PreToolUse` hook is the advisory half, not the enforcement.** It blocks a
     model's `Edit`/`Write` to a protected path, `protected.json`, `events.jsonl`,
     `state.json` and `best.txt` with exit 2, but it fails open on internal error and
     only sees Claude Code's own tools — a shell command or a subprocess bypasses it
     entirely. Core's hash check is the guarantee.

## Why no central engine?

prior agent-optimization work proved the design with a six-axis engine. cap-evolve keeps the *discipline*
but moves the orchestration into skills, so the pipeline runs on any host with no
framework lock-in. The discipline can't drift because the only place rewards are
aggregated, splits are made, the gate is applied, and test is sealed is
`cap_evolve` — every algorithm skill calls it and physically cannot gate on
train or re-score test.

## What this costs you

Honest eval needs enough tasks to split three ways and (ideally) multiple trials.
For tiny task sets, expect wide error bars and a conservative gate that rejects
marginal edits — that is the point.

## Sources
- prior agent-optimization work: `gates.py` (`val_improvement_significant`), `eval/base.py` (combined_stderr, pass^k), `splits.py`.
- tau2-bench: pass^k and reward-on-correct-action evaluation.

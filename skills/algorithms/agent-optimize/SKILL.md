---
name: agent-optimize
description: Fully-agentic, free-form optimization algorithm. Use in agent orchestration mode when you want the conversational agent to own the whole search — understand the benchmark/inputs first, run the baseline, then freely propose capability edits, triage on cheap task subsets, and accept only on a full-val significance gate, all bounded by a free-text stop_condition it re-reads with the run-dir spend. Agent-mode only (orchestration_mode: agent); for a deterministic loop use hill-climb | gepa | skillopt.
component: algorithm
argument-hint: "agent-mode only — set orchestration_mode: agent + algorithm_skill: agent-optimize"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: [scores, traces, candidate]
---

# agent-optimize — the free-form loop you own

This is the one algorithm with **no deterministic subprocess** and **no per-iteration
optimizer**. You — the conversational agent that ran intake — are the optimizer, the
scheduler, and the stopping rule. `cap-evolve run` (with `orchestration_mode: agent`)
does check → baseline, prints a handoff with the `run_dir`, and returns. From there the
search is yours: what to edit, what to evaluate, when to evaluate it, when to call it
done. Your freedom is bounded by exactly two things — the **honesty invariants** below
(most of which core enforces whether you cooperate or not) and the project's free-text
**`stop_condition`**.

Nothing new lives in core for this. You drive the *existing* cap-evolve primitives (the
phase scripts + the `RunDir` API), so `events.jsonl` / rollouts / results / snapshots stay
populated and the dashboard renders unchanged.

## Phase 0 — understand before you optimize

Do this once, before any edit, and **ask the user any blocking question here** (mirror
intake's ask-if-missing discipline) so the loop then runs unattended:

- Read `PROJECT.md`, `capevolve.yaml`, the adapter (`adapters/adapter.py`), and every file
  under `capability_path` (the seed capability you'll edit).
- Understand what **one evaluation** does: what a task is, what `run_target` produces, what
  `score()` rewards, and what the per-task **feedback** says (that is your learning signal).
- Note the **val and test sizes**, `num_trials`, `gate_mode`/`gate_k_se`, and the capabilities
  under optimization (the allowed edit surface, e.g. `system-prompt`, `tools`).
- Read the free-text **`stop_condition`** and restate it to yourself as concrete checks
  (score goal on full val, cost ceilings, time). This is what tells you when to finish.

## Agent-mode loop

Everything below runs against the handed-off `run_dir` (call it `$R`) and project (`$P`).
`$S` is the skills dir (`$CAPEVOLVE_SKILLS_DIR`). Baseline has already scored the seed on
val and set `best_id = seed`; read its val mean/stderr from `$R/baseline.json`.

Each round:

1. **Read the signal.** Look at the current best candidate's per-task val rollouts under
   `$R/rollouts/val/` (and the diagnose skill if you want them clustered) to see which tasks
   fail and *why*. This is free — no new evaluation.
2. **Propose ONE coherent edit yourself.** Copy the current best into a fresh candidate dir
   and edit it (you may consult the `system-prompt` / `tools` capability skills for guidance,
   and spawn helper subagents for parallel sub-tasks — but you make the edit):
   ```bash
   cp -r "$R/candidates/$(python -c "from cap_evolve import RunDir;print(RunDir.open('$R').best_id)")" "$R/work/cand_N"
   # …edit $R/work/cand_N/policy/policy.md and/or tools/tools.py …
   ```
   Every edit must encode a **general rule** — never hardcode a task's id, gold value, or answer.
3. **(Optional) Cheap triage.** To decide if an edit is even worth a full-val eval, you may
   informally sample a **subset** of tasks. Triage is *informational only* — it may **never**
   be the accept/reject decision (see honesty invariant 1).
4. **Honest gate on FULL val.** Evaluate the candidate on the whole val split — this writes
   rollouts+results into the run dir:
   ```bash
   python "$S/phases/evaluate/scripts/run.py" --run-dir "$R" --project "$P" \
          --candidate "$R/work/cand_N" --split val --n-trials <num_trials>
   ```
   Then apply the significance gate against the current best's val mean:
   ```bash
   python "$S/phases/gate/scripts/run.py" --mode paired --k-se <gate_k_se> \
          --current <best_mean> --candidate <cand_mean> \
          --current-stderr <best_se> --candidate-stderr <cand_se>
   ```
   Accept **only** if the gate says Δ > k·SE. Also apply **no-regression**: reject if the
   candidate breaks any val task the current best passed, even when the mean rises.
5. **Commit the decision through the run dir** (so the dashboard + `best_id` stay real):
   ```bash
   python - <<'PY'
   from cap_evolve import RunDir
   rd = RunDir.open("$R")
   rd.snapshot("cand_N", "$R/work/cand_N")   # persist as a candidate
   rd.set_best("cand_N")                       # ACCEPT: make it the new parent
   rd.log_event("accept", candidate="cand_N", val=<cand_mean>, note="<one-line why>")
   rd.update_spent(iterations=1)
   PY
   ```
   On **reject**: `log_event("reject", …)` + `update_spent(iterations=1)` and keep the old best.

## See your constraints every few steps

There is no `cap-evolve status` command — you read what already exists. **Every 2–3 rounds**,
re-read both:

- the free-text `stop_condition` from `capevolve.yaml` (score goal, cost ceilings, time), and
- the run-dir spend:
  ```bash
  python -c "from cap_evolve import RunDir; import json; print(json.dumps(RunDir.open('$R').spent.to_dict(), indent=2))"
  ```

Compare spend and the latest **full-val** mean against the `stop_condition`, then decide:
keep optimizing, or stop and seal. (The Stop hook also re-nudges you across turns so you
keep driving until the run is finalized.)

## Stop & seal (exactly once)

Stop when the `stop_condition` is met (e.g. full-val mean ≥ the score goal) or the budget/
stall is hit. Then seal the held-out **test** split exactly once and write the report:
```bash
python "$S/phases/finalize/scripts/run.py" --run-dir "$R" --project "$P" --n-trials <num_trials>
python "$S/phases/report/scripts/run.py"   --run-dir "$R"
```
(There is **no `cap-evolve finalize` subcommand** — the orchestrate/host prose uses that as
shorthand; the real seal is the finalize *phase script* above, which scores the best on test
once and burns the seal. A second finalize raises `TestSealError`.) A run with no finalize
has no result.

## Honesty invariants (non-negotiable; core enforces most of these)

1. **Accept/reject and the score-goal check are ALWAYS on FULL val through the gate.** Cheap
   subset triage is informational only and may never gate.
2. **The test split stays sealed until the single finalize.** You never score test during the
   loop — the evaluate phase physically restricts `--split` to `train|val`; only finalize
   touches test, once.
3. **Never edit** `splits.json`, anything under `rollouts/test/`, or gold/test files (a
   PreToolUse hook blocks it and core owns the seal).
4. **Generalize, don't overfit** — every edit is a general rule, never a task-specific answer.
5. **Drive through cap-evolve primitives, never around them** — every val eval via the
   evaluate phase, every accept via `snapshot` + `set_best` + `log_event`. A round that
   produced no run-dir artifacts is a bug: fix it before continuing.
6. **Always finish with finalize + report.**

## What good vs bad looks like

- **Good:** Phase 0 done and blocking questions asked up front; each accepted candidate has
  rollouts + a `set_best`/`accept` event; the score goal is confirmed on full val; the run
  ends with a single sealed-test number — even if the honest answer is "no significant gain".
- **Bad:** gating on a triage subset; accepting a mean gain that regresses a passing task;
  peeking at test mid-run; declaring success on val without ever finalizing.

## References
- `references/algorithm.md` — why free-form + how honesty survives full agent autonomy, with sources.

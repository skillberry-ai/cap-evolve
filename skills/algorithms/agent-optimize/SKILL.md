---
name: agent-optimize
description: Fully-agentic, free-form optimization algorithm. Use in agent orchestration mode when you want the conversational agent to own the whole search — understand the benchmark/inputs first, run the baseline, then freely propose capability edits (serially, or several siblings in parallel working copies), triage on cheap task subsets, and accept only on a full-val paired significance gate plus no-regression, all bounded by a free-text stop_condition it re-reads with the run-dir spend. Agent-mode only (orchestration_mode: agent); for a deterministic loop use hill-climb | gepa | skillopt.
component: algorithm
argument-hint: "agent-mode only — set orchestration_mode: agent + algorithm_skill: agent-optimize"
allowed-tools: Read, Write, Edit, Bash, Task
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
phase scripts, this skill's `scripts/`, and the `RunDir` API), so `events.jsonl` /
rollouts / results / snapshots stay populated and the dashboard renders unchanged.

## Shell variables used by every command below

```bash
R="<run_dir from the agent-mode handoff>"      # e.g. .capevolve/run_20250101_120000
P="<project dir>"                              # the dir holding capevolve.yaml + adapters/
S="${CAPEVOLVE_SKILLS_DIR:?set CAPEVOLVE_SKILLS_DIR to the skills/ dir}"
A="$S/algorithms/agent-optimize/scripts"       # this skill's helpers
mkdir -p "$R/work"                             # working copies live here (RunDir does NOT create it)
```

Every script here (and every phase script) does its own `import _bootstrap`, so it finds
`cap_evolve` without you exporting `PYTHONPATH`. All of them print JSON on stdout.

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

Baseline has already scored the seed on val and set `best_id = seed`; read its val
mean/stderr from `$R/baseline.json`, or from the readout in step 0 below.

Each round:

**0. Check you can afford the round.** Budget and stall live in the run dir; read them
*before* spending, not after:

```bash
python "$A/spend.py" --run-dir "$R" --project "$P"
```

Stop and seal if `stop` is `true` (its `stop_reason` is `budget_exhausted()`'s), or if the
free-text `stop_condition` it echoes is already satisfied by `best_val`.

**1. Read the signal.** This is free — no new evaluation. Cluster the current best's
failing val rollouts:

```bash
python "$S/phases/diagnose/scripts/run.py" --run-dir "$R" --tag "$(python "$A/spend.py" --run-dir "$R" | python -c 'import json,sys;print(json.load(sys.stdin)["best_id"])')"
```

Read `clusters` for what to fix and **`kept_good`** for what you must not break — those
are exactly the tasks the no-regression check in step 4 protects.

**2. Propose ONE coherent edit per candidate.** Copy the current best into a fresh working
copy, then edit it (consult the `system-prompt` / `tools` capability skills for guidance —
but *you* make the edit):

```bash
BEST="$(python "$A/spend.py" --run-dir "$R" | python -c 'import json,sys;print(json.load(sys.stdin)["best_id"])')"
TAG="cand_1"                                   # unique per candidate — it IS the rollout tag
cp -r "$R/candidates/$BEST" "$R/work/$TAG"
# …now edit the files under $R/work/$TAG that your capability actually owns.
# (Example only — a system-prompt project might have policy/policy.md, a tools project
#  tools/tools.py; read capability_path in Phase 0 for the real layout.)
```

Every edit must encode a **general rule** — never hardcode a task's id, gold value, or answer.

**3. (Optional) Cheap triage.** To decide if an edit is even worth a full-val eval, you may
informally sample a **subset** of tasks. Triage is *informational only* — it may **never**
be the accept/reject decision (see honesty invariant 1).

**4. Honest gate on FULL val.** Evaluate on the whole val split (this writes
rollouts + results into the run dir under tag `$TAG`, because the evaluate phase tags by
the candidate **dir name**):

```bash
python "$S/phases/evaluate/scripts/run.py" --run-dir "$R" --project "$P" \
       --candidate "$R/work/$TAG" --split val --n-trials <num_trials>
```

Then take the decision — the **paired** significance gate plus **no-regression**, read
straight off the persisted rollouts:

```bash
python "$A/gate_check.py" --run-dir "$R" --candidate "$TAG" --k-se <gate_k_se>
```

It prints `gate` (`accept`, `reason`, `delta`, `threshold`), `paired_n`, `regressions`, and
a combined `verdict`. Accept **only** on `"verdict": "accept"` — i.e. Δ̄ > k·SE over the
paired per-task deltas **and** no val task the current best measured-and-passed got worse.
A `"verdict": "indecisive"` is not a rejection: too little of val actually ran, so fix the
runner before spending more budget.

> `phases/gate/scripts/run.py` is the human-inspection front-end. In **rollout mode** it
> reaches the same paired gate off the same files, so it is a faithful way to re-derive
> just the significance half of a decision:
> ```bash
> python "$S/phases/gate/scripts/run.py" --mode paired --k-se <gate_k_se> \
>        --run-dir "$R" --current-tag <best_id> --candidate-tag "$TAG"
> ```
> It is still **not** the round's gate: it applies significance only and knows nothing
> about no-regression, so a candidate that lifts the mean while breaking a task the
> parent passed looks like an `accept` here and is a `reject` under `gate_check.py`.
> Decide with `gate_check.py`; use this to inspect. (Passing scalar `--current`/
> `--candidate` instead of a run dir cannot do a paired test — two means carry no
> per-task deltas — so that combination is refused rather than quietly downgraded.)

**5. Commit the decision through the run dir** (so the dashboard, `best_id`, the stall
counter and the audit log all stay real):

```bash
python "$A/commit.py" --run-dir "$R" --candidate-id "$TAG" --from-dir "$R/work/$TAG" \
       --decision accept --val <cand_mean> --note "<one line: the general rule you added>"
```

Use `--decision reject` to keep the old best. Either way it snapshots the candidate,
logs the event, and advances `iterations` + the stall counter. Add
`--optimizer-usd/--optimizer-tokens/--optimizer-seconds` for **your own** proposal cost —
the runner's `metric_calls`/`usd`/`seconds` are already recorded by the evaluate phase, but
nothing else records the proposer's, so cost-based stop conditions under-count without it.

## Parallel round (optional, and only as described)

You have the `Task` tool. Fan-out buys real wall-clock, and costs real budget, so it is
bounded by five invariants — state them to yourself before every fan-out:

1. **Diagnosis fans out freely.** It is read-only and costs zero rollouts. Dispatch one
   `cap-evolve-diagnoser` subagent per failure cluster / rollout shard, then merge their
   JSON. No limit worth enforcing.
2. **Proposal fans out across distinct working copies with distinct tags.** N siblings from
   the same parent, each `cp -r`'d to its own `$R/work/<tag>` (a git worktree if the
   capability lives in a repo), each dispatched to its own `cap-evolve-proposer`. **The tag
   must be unique per sibling**: rollout files are `<task>__<tag>__t<k>.json`, so two
   concurrent evals sharing a tag interleave into the same filenames and silently corrupt
   both candidates' scores. Never two proposers on the *same* candidate dir.
3. **The gate stays serial.** `set_best` mutates run state, and paired deltas are computed
   against whatever the baseline is *right now*. So: gate + commit siblings **one at a
   time**, and after any accept, **re-run `gate_check.py` for every remaining sibling
   against the new best** before committing it. Skipping the re-gate double-counts the same
   gain and admits an edit that never actually beat the candidate it is now stacked on.
4. **Never fan out across the test split.** The seal is single-use; only finalize touches
   test, once, serially.
5. **Pay before you fan out.** Every sibling's full-val eval is a real charge. Run
   `spend.py` and check `stop` / the remaining budget for **N** evals *before* dispatching
   N, not after — N candidates can blow a budget that had room for one.

Shape of a parallel round:

```
spend.py                      → can I afford N evals?
diagnose  ──fan out──►  M read-only diagnosers ──► merge clusters      (free)
propose   ──fan out──►  N proposers, N distinct $R/work/<tag> dirs     (costs proposer time)
evaluate  ──fan out──►  N full-val evals, one per unique tag           (costs rollouts)
gate+commit ─ SERIAL ─►  gate_check → commit; on accept, re-gate the rest
```

If in doubt, run the serial loop. A correct serial round beats a fast wrong one — and a
double-counted gain is invisible in the val number that produced it.

## See your constraints every few steps

There is no `cap-evolve status` command. **Every 2–3 rounds** (and always before a fan-out)
run the readout and compare it to the goal:

```bash
python "$A/spend.py" --run-dir "$R" --project "$P"
```

It prints the current `best_id` + full-val mean, all recorded `spent` fields
(`iterations`, `metric_calls`, `usd`, `optimizer_usd`, tokens, seconds), the `budget`,
`budget_exhausted()` as `stop`/`stop_reason`, the free-text `stop_condition`, and
`test_sealed`. Then decide: keep optimizing, or stop and seal. (The Stop hook also
re-nudges you across turns so you keep driving until the run is finalized.)

## Stop & seal (exactly once)

Stop when the `stop_condition` is met (e.g. full-val mean ≥ the score goal) or when
`spend.py` reports `stop: true`. Then seal the held-out **test** split exactly once and
write the report:

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
2. **No-regression is part of acceptance, not a nicety.** A mean gain that strictly drops a
   val task the current best measured and passed is a **reject** — `gate_check.py` folds this
   into `verdict`, and diagnose's `kept_good` is the list it protects.
3. **The test split stays sealed until the single finalize.** You never score test during the
   loop — the evaluate phase physically restricts `--split` to `train|val`; only finalize
   touches test, once. Never in parallel.
4. **Never edit** `splits.json`, anything under `rollouts/test/`, or gold/test files (a
   PreToolUse hook blocks it and core owns the seal).
5. **Generalize, don't overfit** — every edit is a general rule, never a task-specific answer.
6. **Drive through cap-evolve primitives, never around them** — every val eval via the
   evaluate phase, every decision via `gate_check.py`, every commit via `commit.py`
   (`snapshot` + `set_best` + `log_event` + `update_spent`). A round that produced no run-dir
   artifacts is a bug: fix it before continuing.
7. **One tag per candidate, one gate at a time.** Unique tags keep concurrent evals from
   overwriting each other's rollouts; a serial gate keeps a moved baseline from letting two
   siblings claim the same gain.
8. **Record what you spent.** `iterations` + stall via `commit.py` every round, and your own
   proposal cost via `--optimizer-*`; otherwise a cost-based `stop_condition` is unenforceable.
9. **Always finish with finalize + report.**

## What good vs bad looks like

- **Good:** Phase 0 done and blocking questions asked up front; each accepted candidate has
  rollouts under its own tag plus a `set_best`/`accept` event; the score goal is confirmed on
  full val with no regressions; parallel siblings gated one at a time with a re-gate after
  each accept; the run ends with a single sealed-test number — even if the honest answer is
  "no significant gain".
- **Bad:** gating on a triage subset; accepting a mean gain that regresses a passing task;
  two concurrent evals sharing a tag; committing two parallel siblings without re-gating the
  second; fanning out N evals with budget for one; peeking at test mid-run; declaring success
  on val without ever finalizing.

## References
- `references/algorithm.md` — why free-form + how honesty survives full agent autonomy, with sources.

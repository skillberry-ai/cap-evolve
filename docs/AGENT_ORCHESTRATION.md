# Agent orchestration mode

cap-evolve can run an optimization in one of two **orchestration modes**, chosen by a single
key in `capevolve.yaml`:

```yaml
orchestration_mode: deterministic   # default — cap-evolve sequences the loop in core
orchestration_mode: agent           # the conversational agent drives the loop itself
```

Both modes share the same honesty guarantees, because those live in `core/` — the seeded
train/val/test split, the val-only significance gate, and the once-only sealed test score
are enforced by `core/cap_evolve/{splits,gate,rundir}.py` and cannot be bypassed by any
skill, prompt, or CLI flag in either mode.

## Deterministic mode (default)

`cap-evolve run` sequences the phases itself: `intake → implement-and-check → baseline →
<algorithm> → finalize → report`. A per-iteration **optimizer** subprocess (e.g. `claude-code`,
`codex`, or `mock`) proposes each edit; the engine evaluates on val, applies the gate, and
accepts/rejects. This is the right choice when the schedule is known and you want a hands-off,
reproducible run. Algorithms: `hill-climb`, `gepa`, `skillopt`.

## Agent mode

`cap-evolve run` does `check → baseline`, prints a handoff (`run_dir`, `algorithm`,
`stop_condition`), and **returns** — no algorithm subprocess, no auto-finalize. From there the
**same conversational agent that ran intake drives the optimization itself**, following the
selected algorithm's *Agent-mode loop* section. It is *not* a new spawned agent and it does *not*
delegate edits to an optimizer subprocess — in agent mode the agent is the optimizer. The user
stays in the loop and can steer or halt at any round. A Stop hook re-nudges the agent so it keeps
driving across turns until the run is finalized.

Every algorithm has an Agent-mode loop, so `hill-climb` / `gepa` / `skillopt` can all be driven
by the agent. One algorithm is built for this mode and runs *only* here: **`agent-optimize`**
(free-form, below). A second, `evograph`, is **deprecated** — it fanned the same per-cluster work
out but accepted merges on a self-reported train delta instead of the val significance gate, so
`agent-optimize` supersedes it.

### `agent-optimize` — the fully-agentic, free-form algorithm

`agent-optimize` (`skills/algorithms/agent-optimize/`) has no fixed schedule and no delegated
optimizer. The agent owns the whole search:

1. **Phase 0 — understand first.** Read the project, adapter, seed capability, and `score()`/
   feedback; note val/test sizes; restate the free-text `stop_condition` as concrete checks.
   Ask the user any blocking questions here so the loop then runs unattended.
2. **Free loop.** Read the failing-task feedback (free signal); propose one coherent, *general*
   edit itself; optionally triage on a cheap task subset; then evaluate on **full val** and accept
   only on the paired significance gate (Δ > k·SE) with no regression; snapshot + `set_best` +
   log the round.
3. **See constraints every few rounds.** Re-read `stop_condition` and the run-dir spend
   (`RunDir.spent`) — score goal, eval cost, optimization cost, and time all fit in one line.
4. **Stop & seal once.** When the stop condition is met, seal the held-out test split exactly
   once and write the report.

**When to choose it:** when the best next move is judgment — which failure cluster is worth a
targeted edit, when a subset eval is enough to kill a bad idea, when the score goal is already
met — rather than a fixed round schedule. Prefer a deterministic algorithm when rollouts are cheap
and you want a fully hands-off, reproducible run.

## How to select it

```yaml
# capevolve.yaml
orchestration_mode: agent
algorithm_skill:    agent-optimize
stop_condition:     "stop when the FULL val mean reward >= 0.78; keep eval + optimization cost modest; you decide which tasks to evaluate and when; no fixed round count"
```

Then:

```bash
cap-evolve run --spec .capevolve/project/capevolve.yaml --project .capevolve/project --run-ts myrun
# -> prints {"mode":"agent","run_dir":".capevolve/run_myrun","algorithm":"agent-optimize", ...}
```

If a run is interrupted, add `--resume` (with the same `--run-ts`) to reopen the run dir
and hand the agent back the existing `run_dir` + current best instead of re-running the
baseline:

```bash
cap-evolve run --spec .capevolve/project/capevolve.yaml --project .capevolve/project --run-ts myrun --resume
```

The agent then drives the loop against `run_dir`, using the phase scripts directly:

```bash
S="$CAPEVOLVE_SKILLS_DIR"; R=.capevolve/run_myrun; P=.capevolve/project
# honest full-val eval of a candidate dir/id (writes rollouts+results):
python "$S/phases/evaluate/scripts/run.py" --run-dir "$R" --project "$P" --candidate "$R/work/cand_1" --split val --n-trials 1
# the significance gate:
python "$S/phases/gate/scripts/run.py" --mode paired --k-se 1.0 --current <best_mean> --candidate <cand_mean> --current-stderr <s> --candidate-stderr <s>
# spend snapshot (the "see your constraints" step — no new command needed):
python -c "from cap_evolve import RunDir; import json; print(json.dumps(RunDir.open('$R').spent.to_dict(), indent=2))"
# seal test ONCE + report:
python "$S/phases/finalize/scripts/run.py" --run-dir "$R" --project "$P" --n-trials 1
python "$S/phases/report/scripts/run.py"   --run-dir "$R"
```

> **Note — finalize is not a `cap-evolve` subcommand.** Where prose says "finalize", it means
> the finalize *phase script* above (`skills/phases/finalize/scripts/run.py`), which scores the
> best candidate on test once and burns the seal. A second finalize raises `TestSealError`.
> `cap-evolve --help` lists the real subcommands.

## Unattended agent mode — the headless host

Agent mode assumes a conversational agent is present to pick up the handoff. Where none is —
CI, cron, a script — the handoff would simply go unread: `cap-evolve run` prints it, returns 0,
and nothing drives the loop. `skills/algorithms/agent-optimize/scripts/host.py` is the host for
that case:

```bash
S="$CAPEVOLVE_SKILLS_DIR"
python "$S/algorithms/agent-optimize/scripts/host.py" \
       --run-dir "$R" --project "$P" \
       --agent claude-code --model claude-opus-4-8 \
       --budget 240 --usd-budget 30
```

It renders a driver briefing from the spec + handoff (paths, `num_trials`, `gate_k_se`, the
`stop_condition`, and an instruction not to ask questions), then hands it to the named agent CLI
through the existing **`optimizers/run-optimizer`** runner — so the registry row, `{model}`
substitution, budget-flag mapping, cost capture and CLI-present hard-fail are the same ones the
deterministic path uses, not a second copy. `--agent` accepts any row in
`skills/optimizers/registry.yaml`.

Three things are the host's own:

- **Whole-loop budgets.** Agent mode runs the entire search in ONE agent process, so `--budget`
  (turns) and `--usd-budget` bound the whole loop, not one round. CI derives them by multiplying
  the per-iteration caps by the round count.
- **A raised Bash-tool ceiling.** Claude Code caps one Bash call at `BASH_MAX_TIMEOUT_MS`
  (default 10 min). A full-val eval on a real benchmark runs far longer, so the host raises both
  `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` — the effective ceiling is the larger of
  the two. Left at the default, every eval is killed mid-flight and a healthy run reads as a
  broken runner.
- **A guaranteed seal.** An agent that exhausts its turns leaves no `final.json`, and there is
  then no honest number and no way to tell "stopped early" from "crashed". If the agent did not
  seal, the host does — through the same `measure.py` — and reports `seal: host` so it is never
  mistaken for the agent's own judgement that it was finished. Already-sealed runs report
  `seal: agent` rather than raising `TestSealError`.

`--prompt-only` renders the briefing and spends nothing (it lands at `$R/host/driver_prompt.md`,
so a finished run carries a record of exactly what the host asked for). `--seal-only` seals a run
a previous host left open.

## Honesty invariants (both modes)

- Acceptance and the score-goal check are always on **full val** through the gate; cheap subset
  triage is informational only and never gates.
- The **test split is sealed** until a single finalize — the evaluate phase physically restricts
  `--split` to `train|val`; only finalize touches test, once.
- Never edit `splits.json`, `rollouts/test/*`, or gold/test files.
- Every edit encodes a **general rule** — never a task-specific answer.
- Every val eval goes through the evaluate phase and every accept through `set_best` + `log_event`,
  so the dashboard renders and `best_id` is real.
- Always finish with finalize + report.

See [`REPRODUCE_tau2.md`](REPRODUCE_tau2.md) for a worked agent-mode run on τ²-Bench airline and
[`RESULTS.md`](RESULTS.md) for the numbers.

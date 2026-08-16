---
name: agent-optimize
description: 'Fully-agentic, free-form optimization algorithm. Use in agent orchestration mode when you want the conversational agent to own the whole search — understand the benchmark/inputs first, run the baseline, then freely propose capability edits (serially, or several siblings in parallel working copies), kill bad ones cheaply on a deterministic informative SUBSET of val (a promotion ladder that never accepts), accept only on a full-val paired significance gate plus no-regression, all bounded by a free-text stop_condition parsed into re-checkable predicates and re-read from the run dir every round, and finished with one honest train/val/sealed-test measurement. Agent-mode only (orchestration_mode: agent); for a deterministic loop use hill-climb | gepa | skillopt.'
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
- Read the free-text **`stop_condition`** — then let `spend.py` parse it for you rather than
  restating it from memory. It prints `constraints.predicates`: each concrete check
  (`target_val_score`, `max_usd`, `max_wallclock_seconds`, `max_iterations`, `max_stall`,
  `max_metric_calls`, `protect_task`) with its measured actual, plus the prose verbatim.
  **If `constraints.ambiguous` is non-empty, ASK THE USER before the loop starts** — a
  vague clause ("don't spend too much", a bare number with no unit) is reported, never
  guessed at, and this is the one moment where asking is cheap.

## Agent-mode loop

Baseline has already scored the seed on val and set `best_id = seed`; read its val
mean/stderr from `$R/baseline.json`, or from the readout in step 0 below.

Each round:

**0. Check you can afford the round — for the number of candidates you actually intend
to run.** Budget, stall, wallclock and the parsed constraints all live in / are derived
from the run dir; read them *before* spending, not after. Pass `--n-siblings N` whenever
you plan N candidates this round (N=1 for a serial round):

```bash
python "$A/spend.py" --run-dir "$R" --project "$P" --n-siblings 3
```

Act on the single `recommendation`:

| `recommendation` | what it means | what you do |
| --- | --- | --- |
| `stop` | a ceiling is breached (or `budget_exhausted()` is true), or the score goal is met on FULL val | go to **Stop & seal** |
| `narrow_scope` | ≥80% of some ceiling consumed, goal unmet | ONE cheap candidate, screened at tier 1; no fan-out |
| `continue` | room left, goal unmet | run the round you planned |

`afford.affordable: false` (with `afford.blockers` naming the ceiling) means **do not
fan out N** — drop to a smaller N, or to a subset-screened single candidate. The $ figure
uses this run's own **measured** `usd_per_rollout` (`spent.usd / spent.metric_calls`), and
is honestly `null` before the first rollout is paid for. Check this BEFORE dispatching
proposers: N candidates can blow a budget that had room for one.

**Read `afford.runner_spend_metered`.** Some serving paths return no cost at all (an
OpenAI-compatible litellm proxy typically does: litellm logs "model isn't mapped yet" and
reports `0.0`). A measured rate of exactly $0 after real rollouts is *unmetered*, not
free — treating it as 0.0 would make `usd_needed` 0.0, so a `max_usd` ceiling could never
block anything and every fan-out would come back `affordable: true`. When
`runner_spend_metered` is `false`, bound the run with `max_metric_calls` /
`max_iterations`, and report **rollout counts, not dollars**.

**1. Read the signal.** This is free — no new evaluation. Cluster the current best's
failing rollouts:

```bash
BEST="$(python "$A/spend.py" --run-dir "$R" | python -c 'import json,sys;print(json.load(sys.stdin)["best_id"])')"
python "$S/phases/diagnose/scripts/run.py" --run-dir "$R" --tag "$BEST" --split train
python "$S/phases/diagnose/scripts/run.py" --run-dir "$R" --tag "$BEST" --split val
```

Read `clusters` for what to fix and **`kept_good`** for what you must not break — those
are exactly the tasks the no-regression check in step 4 protects.

**Diagnose TRAIN when the spec has a disjoint train split, and compare its clusters to
val's.** Val is what the gate scores, so reading the learning signal off val and then
gating on val fits the split you are judged on; train is the honest surface. It only
works if the two share failure modes, and that is a **free** thing to check before you
spend: if train's cluster signatures and val's are disjoint, no train-driven edit can
ever move the val mean and every candidate will be correctly rejected for a reason that
looks exactly like a null result. Say which it is, in the report, either way. (Train
rollouts have to exist first — baseline only scores val, so pay one
`evaluate --split train` for the seed if you want this signal.)

**2. Propose an edit per candidate — and address EVERY cluster the round can afford.**
One round should not fix one thing. Take the ranked clusters from step 1 and cover as many
as the budget allows, either as **sibling candidates** (one cluster each, gated
independently — the safe default) or as **one bold multi-part edit** (several clusters in
one candidate — higher variance, but it is the only way a fix that needs a prompt change
*and* a tool change lands together).

The failure mode to design against is **churn**, and it is measured, not hypothetical: in
a real run two of three candidates had an *identical* mean to their parent while a
different set of tasks passed — each fixed 2 tasks and broke 2. A mean-only gate calls
that a tie; the **no-regression veto in step 5 is what rejects it**, and it is the reason
a multi-part edit is safe to attempt at all. So when you bundle, keep the parts
*independent* (different files or different rules) so that if the bundle is vetoed you can
resubmit the surviving part alone next round — and read `regressed` out of the screen and
the gate to know which part to drop.

Copy the current best into a fresh working copy, then edit it (consult the `system-prompt`
/ `tools` capability skills for guidance — but *you* make the edit):

```bash
BEST="$(python "$A/spend.py" --run-dir "$R" | python -c 'import json,sys;print(json.load(sys.stdin)["best_id"])')"
TAG="cand_1"                                   # unique per candidate — it IS the rollout tag
cp -r "$R/candidates/$BEST" "$R/work/$TAG"
# …now edit the files under $R/work/$TAG that your capability actually owns.
# (Example only — a system-prompt project might have policy/policy.md, a tools project
#  tools/tools.py; read capability_path in Phase 0 for the real layout.)
```

Every edit must encode a **general rule** — never hardcode a task's id, gold value, or answer.

**3. Cheap SUBSET screen — the promotion ladder.** Do not pay full val to learn that an
edit is bad. Screen it on a small, deterministically chosen, informative subset of val
first:

```bash
python "$A/screen.py" --run-dir "$R" --project "$P" \
       --candidate "$R/work/$TAG" --tier 1 --k-se 1.0
```

What it does, and why each part is there:

- **The parent side is free.** The current best already has full-val rollouts on disk, so
  the screen re-reads its per-task rewards. Only the candidate pays, and only for the
  subset — that is the entire saving.
- **The subset is deterministic and recorded.** Seeded from the frozen splits seed + tier,
  and written verbatim (ids, seed, deltas, decision, measured rollout economics) to
  `$R/screens/<tag>__tier<N>.json`, so any kill is reproducible and auditable later.
- **The subset is informative, not random**: tasks a previous edit broke first (pass them
  with `--broken t3,t7`), then the most informative remaining tasks (currently failing /
  high per-task variance), plus a **random holdout** (`--holdout-frac`, default 0.34) drawn
  from tasks the parent *passes* — that holdout is the only part of a screen that can see a
  regression. Honest about the tension: selecting on currently-failing tasks makes the
  screen much more informative per rollout **and biased toward the tasks the edit targeted**
  — fine for triage, fatal for acceptance, which is exactly why acceptance stays on full val.
- **Rungs are cumulative.** `--tier 2` (~50% of val) does not re-run tier 1's tasks; the
  candidate's screen rollouts are merged across `<tag>__screen*` tags so each rung only
  pays for the ids it adds. Screen rollouts use their own tag, so they never mix into the
  full-val rollouts the gate reads.
- **`decision` is `kill` or `promote`. Never `accept`.** It kills only on evidence of
  significant *harm* (`Δ̄ + k·SE < 0`, or a unanimous negative where SE legitimately
  collapses to 0); everything else — including a flat Δ̄ and "no signal at all" — promotes
  with `inconclusive: true`. The bias is deliberate and asymmetric: a **false kill** throws
  away a good edit and leaves no trace, while a **false promote** costs exactly one
  full-val eval after which the honest gate reaches the right answer anyway.
- **The saving is measured, not estimated.** `savings.net_rollouts` is `+ (full_val −
  fired)` on a kill and `− fired` on a promote, so a run's ledger sums to the truth.

Ladder: `tier 1` (~25% of val, but never fewer than **6** tasks) → on `promote`, either
`tier 2` (~50%) for a second cheap look, or straight to full val. On `kill`:
`commit.py --decision reject` and move on.

**Check the screen's own economics before you rely on it.** `savings.breakeven_kill_rate`
is `fired / full_val_rollouts` — the fraction of candidates the screen must kill just to
pay for itself. On a small val that number is brutal: at `val_n 12` the tier-1 floor of 6
gives a breakeven of **0.5**, so screening only pays if it kills half of everything you
propose, and a measured run killed **0 of 4**. The floor is 6 rather than 3 because 3 was
measured to be worse than useless — a 3-task tier-1 screen reported `fixed: ["44"]` for a
candidate that full val showed never fixed task 44. So: on a small val, either skip the
ladder and pay full val directly, or screen and then read the outcome as *direct
evidence about the tasks the edit targeted* rather than as a statistical test. A tier-1
subset that contains **every** failing val task and comes back 0-for-N on them is a
sound reason to stop spending on that candidate — that is not "killing on noise", the
edit simply missed everything it aimed at. Say in the commit note that the reject was a
budget decision on screen evidence, not a gate decision.

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
logs the event, and advances `iterations` + the stall counter.

**On a reject, pass `--reject-basis` — it says what the reject rests on.** The screen's
`decision` and the driver's disposition are two different facts, and conflating them made
one run's artifacts contradict themselves: `screen.py` recorded `promote` for two
candidates while the commit notes said "rejected on the tier-1 screen, not promoted to
full val". Both were true. `screen.py`'s `decision` is authoritative *only* as the
**screen's own statistical verdict**, which by invariant 1 can only ever be `kill` or
`promote` — "promote" means "could not prove harm", never "was then evaluated on full
val". What actually happened next is `--reject-basis`:

| basis | meaning |
| --- | --- |
| `gate` | a full-val paired gate ran and said reject — the only basis that asserts this |
| `screen_kill` | the screen proved significant harm |
| `ceiling` | arithmetic proved no accept was reachable, so full val was never paid |
| `budget` | screen evidence plus a budget call; not a gate decision |
| `infra` | missing data, not a judgement |

So `screen: promote` + `reject_basis: ceiling` is one coherent story, and a reader never
has to guess whether a promoted candidate reached the gate.

`commit.py` **refuses a `--candidate-id` that already carries an accept/reject event** in
`events.jsonl` (pass `--force` only to repair a record deliberately). That is invariant 7
made mechanical rather than aspirational: a real run had two concurrent drivers both tag a
candidate `cand_r2`, producing two reject events but ONE set of rollouts, so one edit was
judged on the other's evidence and the second snapshot overwrote the first. The check
reads the log, not memory, so it holds across processes.

Add
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
   `spend.py --n-siblings N` and require `afford.affordable: true` **before** dispatching
   N, not after — N candidates can blow a budget that had room for one.

Shape of a parallel round:

```
spend.py --n-siblings N       → afford.affordable? recommendation != stop?
diagnose  ──fan out──►  M read-only diagnosers ──► merge clusters      (free)
propose   ──fan out──►  N proposers, N distinct $R/work/<tag> dirs     (costs proposer time)
screen    ──fan out──►  N tier-1 subset screens, one per unique tag    (costs ~25% of an eval)
evaluate  ──fan out──►  full-val evals for SURVIVORS only              (costs rollouts)
gate+commit ─ SERIAL ─►  gate_check → commit; on accept, re-gate the rest
```

Three independent sources of concurrency — use all three, they compose:

1. **Inside one evaluation**, if the adapter has `run_batch`/`run_trials` it already runs
   the whole task grid at its own concurrency (tau2's airline adapter does, via
   `TAU2_MAX_CONCURRENCY`). Otherwise `screen.py --workers N` — or `CAPEVOLVE_WORKERS=N`
   in the environment, which every phase script honours since none of them take a
   `--workers` flag — pools rollout *generation* through `trials.run_trials_pool`.
   Scoring and persistence stay serial and in task order, so pass^k, SE and the gate see
   byte-identical numbers to a serial run. Opt in only when `run_target` is thread-safe
   (no shared scratch dir, no single live container, no module-global client):

   ```bash
   CAPEVOLVE_WORKERS=4 python "$S/phases/evaluate/scripts/run.py" \
          --run-dir "$R" --project "$P" --candidate "$R/work/$TAG" --split val --n-trials 1
   ```
2. **Across candidates**, one evaluate/screen process per sibling, each with its **own
   unique tag**.
3. **Across diagnosers**, freely — read-only, zero rollouts.

The gate is the one thing that never parallelizes (invariant 3).

If in doubt, run the serial loop. A correct serial round beats a fast wrong one — and a
double-counted gain is invisible in the val number that produced it.

## See your constraints every few steps

There is no `cap-evolve status` command. **Every 2–3 rounds** (and always before a fan-out)
run the readout and compare it to the goal:

```bash
python "$A/spend.py" --run-dir "$R" --project "$P"
```

It prints the current `best_id` + full-val mean, all recorded `spent` fields
(`iterations`, `metric_calls`, `usd`, `optimizer_usd`, tokens, seconds), the measured
`wallclock_seconds`, the `budget`, `budget_exhausted()` as `stop`/`stop_reason`, the
free-text `stop_condition` **parsed into per-predicate satisfied/violated rows with their
measured actuals**, the `remaining` headroom per ceiling, anything `ambiguous`, and
`test_sealed`. Everything comes from the run dir on each call — never from a total you are
carrying in your head. Then act on `recommendation`. (The Stop hook also re-nudges you
across turns so you keep driving until the run is finalized.)

## Stop & seal, then MEASURE (exactly once)

Stop when `spend.py`'s `recommendation` is `stop`. Then produce the run's one honest
result table — seed vs best on **val**, on **train** when the spec defines a train split
worth reporting, and on the **sealed test** split scored exactly once:

```bash
python "$A/measure.py" --run-dir "$R" --project "$P" --train auto
python "$S/phases/report/scripts/run.py" --run-dir "$R"
```

`measure.py` reads val straight off the rollouts the gate used (free), evaluates train
only when it adds information (`--train auto` skips it when the train ids equal the val
ids, because the numbers would be a copy), and seals test through the same
`harness.finalize` the finalize phase calls — so it is interchangeable with:

```bash
python "$S/phases/finalize/scripts/run.py" --run-dir "$R" --project "$P" --n-trials <num_trials>
```

For every split it prints mean, stderr, n (scored / in split), the paired per-task delta
vector's mean + SE + n, the recomputed gate decision (val only — `gate.decide` refuses any
other split), the per-task `fixed` / `broke` / `unchanged` movement, a `screen_ledger`
totalling every recorded screen's MEASURED rollout economics (a negative `net_rollouts`
honestly says screening was pure overhead because nothing was killed), and a `holdout`
verdict. It refuses to flatter the run: an **empty** split says `empty` instead of
reporting 0.0; a **no-holdout** spec (test overlapping train/val, e.g. tau2's default
`split_ids.json` where all three are the same 50 ids) is labelled a **FIT metric, not
generalisation**, with the overlap counted; and `best_id == "seed"` prints a `warning` that
every delta is 0 by construction and must be reported as a **null result with a diagnosed
cause**, not as a 0.000 improvement.

(There is **no `cap-evolve finalize` subcommand** — the orchestrate/host prose uses that as
shorthand; the real seal is the finalize phase script / `measure.py`, which scores the best
on test once and burns the seal. A second finalize raises `TestSealError`.) A run with no
finalize has no result.

## Honesty invariants (non-negotiable; core enforces most of these)

1. **Accept/reject and the score-goal check are ALWAYS on FULL val through the gate.** A
   subset screen may **kill** a candidate; it may **never accept** one. `screen.py` prints
   only `kill`/`promote` and has no code path to `accept`; `spend.py` checks
   `target_val_score` against the full-val mean only. A subset result's `coverage` looks
   like 1.0 (its denominator *is* the subset), so never hand one to `gate_check.py`.
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
9. **Constraints are re-read, never remembered.** Every round's affordability decision comes
   from `spend.py` reading the run dir (spend, wallclock, splits, rollouts). A budget carried
   in an agent's context is how a $6.00 cap becomes $6.01. Where the prose is ambiguous, say
   so (`constraints.ambiguous`) and ask — never invent a ceiling.
10. **Always finish with `measure.py` (or finalize) + report** — the full train/val/sealed-test
    table, with the `holdout` verdict stated. A val number alone is the training signal, not
    a result.

## What good vs bad looks like

- **Good:** Phase 0 done, `constraints.ambiguous` cleared with the user up front; every
  round covers as many diagnosed clusters as it can afford; obviously-bad candidates killed
  at tier 1 for a quarter of an eval with the subset + seed recorded in `$R/screens/`; each
  accepted candidate has full-val rollouts under its own tag plus a `set_best`/`accept`
  event; parallel siblings gated one at a time with a re-gate after each accept; the run
  ends with `measure.py`'s train/val/sealed-test table and an explicit `holdout` verdict —
  even when the honest answer is "no significant gain".
- **Bad:** gating on a triage subset, or letting a screen `promote` stand in for an accept;
  killing a candidate on 3 noisy tasks (the screen is built to refuse this — do not lower
  `--k-se` to make it decisive); accepting a mean gain that regresses a passing task, or
  accepting a churn bundle whose gains and losses cancel; two concurrent evals sharing a tag;
  committing two parallel siblings without re-gating the second; fanning out N evals with
  budget for one; re-deriving the budget from memory instead of `spend.py`; peeking at test
  mid-run; quoting a val number as the result without ever measuring the sealed test.

## References
- `references/algorithm.md` — why free-form + how honesty survives full agent autonomy, with sources.

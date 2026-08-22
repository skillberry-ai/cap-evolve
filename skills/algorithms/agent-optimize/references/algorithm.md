# agent-optimize — rationale, and how honesty survives full autonomy

## Why a free-form agentic algorithm

The deterministic algorithms (hill-climb, gepa, skillopt) fix the *schedule* of the
search: which tasks each round reflects on, when the optimizer is called, how the parent
is selected. That is exactly right when rollouts are cheap and the schedule is known. It
is a poor fit when the best move is judgment: *this* failure cluster is worth a targeted
policy edit, *that* one is uncontrollable infra noise to ignore; a subset eval is enough to
kill a bad idea before paying for full val; the score goal is already met so stop now.

agent-optimize hands that judgment to the conversational agent. There is no fixed round
count and no delegated per-iteration optimizer subprocess — the agent decides what to edit,
what to evaluate, when, and when to stop, bounded by a free-text `stop_condition`.

## How honesty survives handing the agent the wheel

Full autonomy is only safe because the honesty guarantees are **not** the agent's to keep —
they live in `core/cap_evolve/{gate,rundir,splits,check}.py` and hold no matter what the
agent does:

- **Test is sealed by code.** The evaluate phase only accepts `--split train|val`; the test
  split is scored solely by the finalize phase, once, after which `RunDir.commit_test()`
  burns the seal and a second finalize raises `TestSealError`. The agent cannot peek at test
  mid-run even if it tries.
- **Acceptance is a code gate on val.** `gate.decide` applies Δ > k·SE; the agent's subset
  triage can only *kill*, never accept — `scripts/screen.py` emits `kill`/`promote` and has
  no accept path at all. The agent reaches the *same* gate the
  deterministic loops use — the **paired** test — through `scripts/gate_check.py`, which
  rebuilds both sides' `SplitResult` from the persisted rollouts
  (`harness.split_result_from_rollouts`), builds the aligned per-task delta vector
  (`harness._paired_deltas`) and calls `gate.decide(mode="paired", …)`. The `phases/gate`
  CLI takes only two scalar means, so it can express only the weaker *unpaired*
  `significant` test; it stays the human-inspection front-end.
- **No-regression is enforced, not advised.** `gate_check.py` also vetoes a mean gain that
  strictly drops any val task the current best measured and passed — the same rule, and the
  same "tasks with no valid trial are missing data" exclusion, that `hill_climb_loop`
  applies. It is what diagnose's `kept_good` list exists to protect.
- **Edits are audited.** Every candidate is snapshotted in the git-backed store and every
  round is appended to `events.jsonl`, so the search is fully reconstructable.

So the "free" in free-form is freedom of *strategy*, not freedom to fake a result. The
headline number is still produced once, on data the search never saw.

## Subset screening: where the cost actually goes, and why a screen may not accept

The unit of cost in a run is one full-val evaluation — `val_n × num_trials` rollouts, paid
once per candidate per round. Most candidate edits are not close calls, so most of that
spend buys a conclusion a fraction of it would have reached. GEPA already exploits this on
train (`gepa._eval_minibatch` plus its `sum(child) > sum(parent)` local gate); agent-optimize
ports the same economy to val and makes it **variance-aware**, which is the part Arbor's
structure lacks: Arbor's `merge_threshold` is log-only, never blocks, and there is no
repeated-trial, standard-error or significance machinery behind it at all.

Three design choices carry the honesty:

1. **The parent side is free.** The current best already has full-val rollouts persisted, so
   `screen.py` re-reads its per-task rewards instead of re-running it. Only the candidate
   pays, and only for the subset. That is the whole saving; there is no cleverer trick.
2. **A screen may kill, never accept.** `cap_evolve.subsample.screen_decision` returns
   `kill`/`promote` only. Acceptance needs the full split, because a subset chosen from the
   parent's failing tasks is *deliberately biased toward the tasks the edit targeted* — an
   excellent triage signal and an invalid basis for a decision. A subset `SplitResult`'s
   `coverage` is also 1.0 by construction (its denominator *is* the subset), so it would sail
   past the gate's low-coverage guard if it were ever handed over.
3. **The bias runs toward promote, deliberately.** With k≈4 and one trial the delta vector is
   coarse and the SE is large. A **false kill** discards a good edit and leaves no trace — the
   run simply fails to improve and nothing says why. A **false promote** costs exactly one
   full-val eval, after which the honest gate is correct anyway. So `screen_decision` kills
   only on `Δ̄ + k·SE < 0` or a unanimous negative (SE legitimately 0), and everything else —
   flat Δ̄ included — promotes with `inconclusive: true`. Lowering `--k-se` to make the screen
   "decisive" is the one tuning knob that makes the algorithm worse.

Subset composition is `broken_ids` (tasks a previous edit is known to have broken) → most
informative remaining (`(1-reward) + stderr`: headroom plus instability) → a seeded **random
holdout** drawn from tasks the parent *passes*. The holdout is the only part of a screen that
can see a regression, and it is why the classic churn candidate (fixes 2, breaks 2, identical
mean) at least surfaces its `regressed` list at tier 1 instead of looking like a tie. It is a
partial correction, not a complete one: with small k, a regression outside the holdout screens
clean and only shows up in the full-val gate's `regressions` list (which is diagnosis — it names
which part of a bundle to drop — and blocks an accept only under `--veto-regressions`). Selection
is deterministic given
the seed, and the whole record (ids, seed, holdout fraction, deltas, decision, measured
rollout economics) is written to `$R/screens/<tag>__tier<N>.json`, so a kill is auditable
after the fact rather than a decision that happened once inside an agent's context.

Rungs are cumulative — tier 2 merges tier 1's rollouts across `<tag>__screen*` tags and pays
only for the ids it adds — and savings are reported as measured integers
(`+ (full_val − fired)` on a kill, `− fired` on a promote) so a run's ledger sums to the truth
instead of to a flattering estimate.

### The break-even, and when the ladder cannot pay for itself

Screening is an economic bet, not a free improvement, and the arithmetic is one division:
`savings.breakeven_kill_rate = fired / full_val_rollouts` — the fraction of candidates the screen
must **kill** just to recover what its own rollouts cost. Screen only when that number sits below
the kill rate you have actually observed on this project.

The floor is what makes it unreachable on a small val. `screen.py` never fires a rung below an
absolute minimum number of tasks (currently 6), because a rung decided on two or three tasks is a
coin flip dressed as evidence. So on a 12-task val the tier-1 subset is half the split and the
break-even is **0.5** — every second candidate must be provably harmful. Measured across four real
runs on that project: the screen killed **0 of 8** promoted candidates while producing one
documented false positive (a 3-task tier-1 reported `fixed: ["44"]` for a candidate that full val
showed never fixed 44 — which is why the floor is 6, not 3). A ladder that cannot pay for itself and
mis-reports is worse than no ladder: pay full val directly.

Where the screen *is* worth paying for (large val, cheap tier), read it as **direct evidence about
the tasks the edit targeted**, not as a statistical test: a tier-1 subset containing every failing
val task that comes back 0-for-N on them is a sound reason to stop spending on that candidate. Book
that as a budget decision on screen evidence (`--reject-basis budget`), never as a gate decision.

### `phases/gate` is an inspection front-end, not the round's gate

`phases/gate/scripts/run.py --mode paired` reaches the *same* paired gate off the *same* persisted
rollouts, so it is a faithful way to re-derive the significance half of a decision by hand — but
only in **rollout mode** (`--run-dir` plus `--current-tag`/`--candidate-tag`). Passing scalar
`--current`/`--candidate` means cannot do a paired test at all, since two means carry no per-task
delta vector, so that combination is refused rather than quietly downgraded to an unpaired test
whose number would look the same and mean something else.

It is still not the round's gate, for two reasons that matter to the audit trail: it does not read
`regressions`, so it cannot tell you which part of a bundled edit to drop, and it does not book the
decision into the run dir. Decide with `gate_check.py`; use this to inspect.

## The constraint surface: free-text stop_condition, parsed and re-read

Per the design, agent-optimize adds **no** new budget fields and no status command: the
project's free-text `stop_condition` plus the already-tracked run-dir spend is the whole
surface. What it *does* add is a normalizer, because prose is the right input and a terrible
thing for a loop to enforce. `cap_evolve.constraints.parse_constraints` turns

> "reach val mean >= 0.75, or stop after $40 / 90 minutes; don't regress task 12"

into `target_val_score >= 0.75`, `max_usd <= 40`, `max_wallclock_seconds <= 5400`,
`protect_task == "12"` — keeping the prose verbatim alongside — and
`check_constraints` re-checks each predicate against **measured** actuals every round,
emitting one `stop | continue | narrow_scope` recommendation. The tightest ceiling wins when
one is stated twice; the score goal is checked against the **full-val** mean only.

Two properties matter more than the parsing:

- **Ambiguity is reported, never guessed.** "don't spend too much", or a bare number with no
  unit, lands in `constraints.ambiguous` with the offending span and a reason, and an
  unparseable condition is explicitly *not* treated as "no constraint". SKILL.md's Phase 0
  says to clear that list with the user before the loop runs unattended — the one moment when
  asking is free.
- **Nothing is remembered.** Spend comes from `state.json`, wallclock from the first entry in
  `events.jsonl`, the val mean from the persisted rollouts, regressions from a seed-vs-best
  per-task comparison. A running total carried in an agent's context is how a $6.00
  per-iteration cap became $6.01 in a previous real run.

`spend.py --n-siblings N` closes the last gap: it prices N full-val evaluations at this run's
own **measured** `usd / metric_calls` and answers `afford.affordable` *before* the fan-out.
Before the first rollout is paid for it honestly answers `null` rather than "yes".

The recording half matters
just as much: the evaluate phase already books `metric_calls`/`usd`/`runner_seconds`, but in
agent mode *the agent is the proposer*, so `scripts/commit.py` takes `--optimizer-usd` /
`--optimizer-tokens` / `--optimizer-seconds` alongside `iterations` and the accepted flag
(which drives the stall counter). Without those, a cost- or stall-based `stop_condition` is
unenforceable no matter how carefully it is written.

## Parallelism: fan out on the cheap steps, stay serial where state moves

Arbor's discipline — dispatch independent workers into separate worktrees, evaluate each on
a dev signal, merge only what clears a held-out margin — ports cleanly, with the boundaries
cap-evolve's own state model dictates (see `docs/SUBAGENT_PATTERNS.md`):

- **Diagnosis** is read-only and costs no rollouts, so it fans out without limit.
- **Proposal** fans out across *different* parents/working copies only, never two proposers
  on one candidate dir. Each sibling needs a **unique tag**, because rollouts are written as
  `<task>__<tag>__t<k>.json` and the evaluate phase derives the tag from the candidate dir
  name: two concurrent evals sharing a tag interleave into the same filenames and corrupt
  both scores.
- **The gate is serial.** `set_best` mutates run state and paired deltas are computed against
  the *current* baseline, so admitting sibling A invalidates sibling B's deltas. B must be
  re-gated against the new best before it is committed; skipping that double-counts one gain.
- **Test is never parallel.** The seal is single-use.
- **Budget is checked before the fan-out**, for N evals rather than one: N siblings can
  exhaust a budget that had room for a single round (`spend.py --n-siblings N`).
- **Screening is where fan-out pays best.** N tier-1 screens cost roughly one full-val eval
  between them, so the expensive stage runs only for survivors.

Inside a single evaluation there are two further, composable sources of concurrency: an
adapter's own `run_batch`/`run_trials` fast path (some adapters run their whole task
grid at their own concurrency setting), and framework-level pooling via `trials.run_trials_pool`
(`screen.py --workers N`). The pool only parallelizes rollout *generation* — scoring and
persistence stay serial and in task order — so pass^k, SE and the gate see exactly the numbers
a serial run produces. It is opt-in because `adapter.run_target` is not required to be
thread-safe.

## The final measurement: one table, and the things it refuses to pretend

A val number is the signal the gate optimized against, so quoting it as *the* result quotes
the training signal. `scripts/measure.py` produces the run's one reportable table — seed vs
best on val (free, off the rollouts the gate used), on train when that adds information, and
on the sealed test split via the same `harness.finalize` the finalize phase calls — with
mean, stderr, n scored / n in split, the paired delta vector's mean + SE + n, the recomputed
gate decision (val only; `gate.decide` raises `TrainGateError` for anything else), and the
per-task fixed/broke/unchanged movement.

Three refusals are the point of it: an **empty** split reports `empty` rather than a 0.0 that
reads like a measured failure; a **no-holdout** spec (test overlapping train/val — some benchmarks ship a
default split file that makes all three the same ids) is labelled a **FIT metric, not
generalisation**, with the overlap counted; and `best_id == "seed"` emits a warning that every
delta is 0 *by construction* and must be reported as a null result with a diagnosed cause.
`--train auto` also declines to pay for a train evaluation whose ids equal val's, because the
numbers would be a copy.

## Caveats

- With `train == val` the val gate is a *fit*, not a held-out check — only the sealed test
  number generalizes. Label val a fit metric in any report.
- At `num_trials: 1` on a stochastic benchmark, single-trial val means carry real variance;
  the paired k·SE gate curbs false accepts, but consider a re-eval before sealing if the
  score goal is only just met.

## Sources

- GEPA: reflective prompt evolution with a Pareto frontier (arXiv:2507.19457) — the
  deterministic sibling this loop's "read the feedback, propose one targeted edit" step echoes,
  and the prior art for the minibatch economy `subsample.py` ports to val.
- Arbor (github.com/RUC-NLPIR/Arbor) — the source of the *structure* here: independent workers
  in separate worktrees, a cheap dev-signal screen, merge only what clears a bar. Its looseness
  is deliberately **not** ported: Arbor has no repeated trials, no standard error, no
  significance test, and its `merge_threshold` is log-only and never blocks. Every idea taken
  from it is re-expressed as a variance-aware decision (`screen_decision`'s `Δ̄ + k·SE < 0`) that
  can only kill, with acceptance left to the paired val gate.
- cap-evolve honesty model: `docs/HONEST_EVAL.md`, `docs/ARCHITECTURE.md` (splits/gate/seal in core).

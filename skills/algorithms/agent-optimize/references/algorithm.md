# agent-optimize — rationale, and how honesty survives full autonomy

## Contents

- [Why a free-form agentic algorithm](#why-a-free-form-agentic-algorithm)
- [How honesty survives handing the agent the wheel](#how-honesty-survives-handing-the-agent-the-wheel)
- [Subset screening](#subset-screening-where-the-cost-actually-goes-and-why-a-screen-may-not-accept)
- [The constraint surface](#the-constraint-surface-free-text-stop_condition-parsed-and-re-read)
- [Sibling candidates by default](#why-n3-sibling-candidates-is-the-default-not-one-candidate-at-a-time)
- [Provisional candidates](#provisional-candidates-sequential-evidence-not-compounded-edits)
- [JOURNAL.md write protocol](#journalmd--the-append-only-handover-and-its-write-protocol)
- [Parallelism](#parallelism-fan-out-on-the-cheap-steps-stay-serial-where-state-moves)
- [The final measurement](#the-final-measurement-one-table-and-the-things-it-refuses-to-pretend)
- [Gate as evidence, not a verdict](#gate-as-evidence-not-a-verdict)
- [Measuring only what the edit reaches](#measuring-only-what-the-edit-reaches)
- [Caveats](#caveats)
- [Sources](#sources)

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
- **A broken framework file stops the round, it does not get hand-worked-around.** On run
  33492876620 round 3, `_gate()` swallowed a `gate_check.py` crash into `{"error": ...}` and
  the caller `.get()`'d the missing verdict keys into `null`s in the round table; the agent
  noticed, recomputed the verdicts itself from `gate_check.py`'s raw output, booked the round
  `inconclusive` by hand, and said so in `JOURNAL.md`. That specific case is now closed by
  code: `_gate()` raises `GateCheckFailed` on a non-zero exit or unparsable stdout,
  `assert_rows_were_judged` refuses to publish any row whose reward is `null` when its own
  eval succeeded, and `round.py` exits non-zero with nothing written to the table — so there
  is no broken table left standing to work around. The **general** rule survives that fix and
  covers every other framework artifact (a malformed `screen.py`/`measure.py`/`diagnose`
  output, a torn JSON file on disk): treat it the same way `GateCheckFailed` is treated,
  never the way the old `_gate()` did. Stop, report the malformed file and what it should have
  contained, and let the caller re-run it — the underlying rollouts are already on disk, so
  re-deriving the verdict is free. Do **not** recompute a substitute number by hand and keep
  going, even when the hand-computed number turns out right, because the run is no longer
  telling anyone when this happens.

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

### Targeted screening: draw the collateral-damage holdout from outside the cluster

`--broken <ids>` biases a screen toward the tasks an edit is meant to fix — the right bias for
"did the targeted tasks improve", the wrong one for "did anything else break", because those
targeted ids crowd out the holdout that would otherwise catch a regression elsewhere. Two
separate calls answer the two questions cleanly: `--broken <cluster-ids> --k <n> --holdout-frac
0` for a pure read on the cluster, and a second call with no `--broken` and a normal
`--holdout-frac` for collateral damage — its holdout draws from tasks the parent already
*passes* (`select_screen_subset`'s `passing` set), which a diagnosed failure cluster is not, so
it checks the untouched surface without having to name it. One `--k`-sized draw that mixes both
either drowns the targeted signal in noise or lets the same tasks stand for both target and
holdout at once.

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

Those per-round figures **attribute** cost inside the total the host already meters for your
whole process; they do not add to it. The host books the residual (`host.optimizer_spend_to_book`),
so passing them moves spend from the run-level `unattributed` row onto the round that caused it
and never double-counts — which is exactly what it used to do: the host booked its metered total
*on top of* whatever the agent had booked, so an agent following this instruction made the run
report up to twice the optimizer spend it used, and a `max_usd` stop then fired on money nobody
spent. Pass them when you can estimate your own cost for a round; a round you cannot price is
better left unattributed than guessed, since the run total is right either way.

## Why N≥3 sibling candidates is the default, not one candidate at a time

A round pays fixed overhead regardless of how many candidates it gates: the null-control
replicates (`--control-replicates 2` by default) plus, on the deterministic path, a baseline
re-check. That overhead is paid ONCE whether the round proposes one candidate or several, so a
round that proposes exactly one candidate spends nearly all of it on a single shot at the gate —
observed directly in a live run, where two consecutive rounds each proposed one candidate and
both were rejected, at the same fixed cost as three or more addressed in parallel would have
been. `round.py` already supports evaluating N candidates as parallel *processes* (each with its
own adapter `apply()`), gating them serially — the mechanism was already there; only the default
behavior of proposing one at a time was the gap. Default to N≥3, one failure cluster each, and
drop to fewer only when `spend.py --n-siblings N` says the remaining budget cannot afford it.

## Provisional candidates: sequential evidence, not compounded edits

A candidate that clears `Δ>0` but not `Δ > k·SE` is not the same as one at `Δ<=0`: the first is
a real positive direction the gate could not yet resolve at this `n`; the second has no
direction to chase. Discarding both alike wastes the first kind of evidence — three real rounds
on one benchmark each proposed a single candidate, paid the round's full fixed overhead, and
bounced off the noise floor with nothing carried forward, even though at least one of those
candidates' `Δ` was positive and simply under-measured.

The fix is a THIRD decision, `commit.py --decision provisional`, for exactly that case
(`gate_check.py` flags it as `directionally_positive_but_inconclusive`). It is deliberately
narrow: the only thing that happens next is buying more trials on the **same, unmodified**
candidate (`scripts/grow.py`) — never a new edit stacked on top of it. This is the line that
keeps sequential evidence-gathering from becoming the failure mode this project's own
post-mortems already named — "fewer mechanisms beat more", i.e. compounding edits on
unconfirmed ground. A provisional candidate buys precision on ONE measurement; it never becomes
the base a sibling edit builds from until it has actually been accepted.

**The pooling has to be real pooling, not two verdicts averaged.** `grow.py` runs the additional
trials under a throwaway tag, then `loop.pool_split_results` concatenates each shared task's
`trial_rewards` (not its mean) before re-aggregating — so the pooled `SplitResult` is what a
single evaluation at `n = n_old + n_new` would have produced, and the paired significance test
that follows sees the honest combined variance. Averaging the two rounds' *deltas* instead would
silently discard the fact that more trials narrow the SE; averaging their *verdicts* would treat
a 60%-confidence read and a 40%-confidence read as one vote each. `grow.py` then merges the new
rollout files onto the candidate's own tag (renumbered past its existing trial indices), so every
later reader — `gate_check.py`, `commit.py`, the dashboard — sees one candidate at the pooled
`n` with no special-casing for having been grown.

**The honest risk, and its cap.** Could a provisional lineage get stuck accumulating trials on a
false positive for many rounds, burning budget chasing noise that looked promising once? Yes —
that is exactly the failure mode a gate without a stopping rule invites, and it is why growth is
capped at **`--max-growth-rounds 2`** (`grow.py`'s default): at most two extra rounds of added
trials before the candidate must be finally promoted or abandoned, never grown a third time.
Two rounds is enough to roughly double or triple `n` on a candidate that started with a small
val, which is where most of the SE reduction from added trials actually lives (diminishing
returns set in well before a fourth round would). A candidate that still has not cleared the bar
after two growth rounds is abandoned (`commit.py --decision reject --reject-basis gate`) — the
cap turns "maybe next round" into a bounded, auditable cost rather than an open-ended one.

## JOURNAL.md — the append-only handover, and its write protocol

`$R/work/$TAG/JOURNAL.md` exists in your working copy from the moment you `cp -r
"$R/candidates/$BEST" "$R/work/$TAG"` — the framework seeds it (`harness._seed_journal`) onto
the seed candidate before round 1, and re-seeds it onto whichever candidate is `$BEST` after
every `commit.py` call, so it is always present at the start of a round regardless of how many
rounds came before. It is YOUR file (append-only, never reset): the run-level copy at
`$R/JOURNAL.md` accumulates one entry per iteration, accepted and rejected alike.

The write protocol:

1. Read the WHOLE file before proposing — not just the last entry — so you build on every prior
   attempt and never re-test a refuted idea.
2. Append your new entry BELOW the marker line
   `<!-- cap-evolve:journal-append-below — add your Iteration entry under this line; do not edit
   anything above it -->`. Never edit or delete anything above the marker.
3. Use the heading `## Iteration <candidate id> — <one-line headline of what you tried>`,
   followed by: the changes you made, the expected effect of each, which prior RESULTS you built
   on (or explicitly avoided because a prior RESULT proved it regressed), refuted hypotheses, and
   your focus for the next iteration. You cannot know your own gate result while you write it —
   `commit.py` stamps a `**RESULT (framework, objective):**` line right below your entry
   afterward (accept/reject, Δ, and the exact tasks fixed/broken vs the parent), which is the
   authoritative record of what actually worked — read it, don't guess at it.

This is a general convention for ANY continuous-session algorithm (one long-running optimizer
subprocess spanning many rounds, as opposed to the deterministic loops' fresh per-iteration
optimizer workdir): the framework re-seeds the same file at the same two points
(`harness._seed_journal` called once before the session starts, and once per `commit.py` call
afterward) so a session that never gets a fresh workdir per iteration still gets a fresh append
target every round.

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

## Gate as evidence, not a verdict

The statistics come from two scripts, and it matters which one prints what: `gate_check.py` prints
`delta`, `stderr`, `resolvable_effect_size` and its own `"verdict"` for ONE candidate; `round.py` prints
the round-scoped numbers no single-candidate gate can see — `noise_floor_from_control` and
`verdict_by_reference`/`verdict_stable`, the sign-agreement check across the round's null-control
replicates. Neither decides for you. Nothing in `commit.py` or `round.py` checks that field against the `--decision` you pass: `set_best()`
is an unconditional setter, and `--reject-basis driver_judgement` exists precisely so you can log a
considered disagreement. Treat the printed numbers the way a careful researcher reads a stats printout,
not the way code reads a boolean:

- Read `resolvable_effect_size` first. It is the smallest true effect this round could have detected at
  all — a `delta` at or below it is not evidence either way, whatever the printed verdict says.
- Does `delta` clear the noise floor measured for THIS round (`round.py`'s
  `noise_floor_from_control`), not just the a priori `k_se` threshold baked into the printed verdict?
- Does the verdict survive the choice of control replicate (`round.py`'s `verdict_by_reference` /
  `verdict_stable`, always computed once there is more than one control block)? A round where they
  disagree is telling you the noise floor itself is unstable this round, not just that one candidate is
  borderline.
- Before any accept, or any decision that disagrees with the printed verdict, write one sentence in
  `commit.py`'s `--note` citing the actual numbers (delta vs resolvable effect size vs noise floor). This
  is not optional ceremony — it is the audit trail a human reviewer uses afterward to check your judgment,
  the same way a rigorous post-mortem checks the numbers behind every claim.

**Why this doesn't regress to the coin-flip-accept failure a significance bar this loose already produced
on a real benchmark**: the arithmetic that caused that failure — banking `delta > 0` as progress when the
significance bar sat below the measured noise floor — is untouched. `gate_check.py` still computes the same
rigorous statistics and prints them prominently; what changes is only that you must engage with those
numbers in your own reasoning rather than pattern-matching a boolean field. The historical failure mode was
"the bar sat below the noise floor and nobody could see it" — with `resolvable_effect_size` and
`noise_floor_from_control` printed first, that is now structurally hard to miss.

**The new risk this introduces, honestly stated**: a strong optimizer can rationalize accepting something
the numbers don't support, dressing noise-chasing in confident-sounding prose — the failure mode moves from
bad math to motivated reasoning, which is harder to catch mechanically than a wrong formula was. The only
mitigation available is the audit trail above: every override gets a human-readable justification citing
real numbers, reviewable after the fact, the same way this repo's own run post-mortems already work.

## Measuring only what the edit reaches

Two things a round prints are claims about *causality*, and both were being made at a precision the
measurement did not have. The evidence is run_finalrun6 — 7 candidates, 30 val tasks, 10 trials.

### The footprint: which tasks could the edit have moved at all?

An edit touches a handful of named surfaces. The gate, though, used to measure its delta across every val
task. The tasks the edit cannot reach do not sit at zero — they wobble, because measuring a task twice is
not the same as measuring it once — and that wobble goes straight into the SE of the mean. On
run_finalrun6, `SE(paired Δ)` ran **0.022-0.035** while the real per-edit effects were **0.011-0.05**: the
bar was as wide as the thing it was measuring. The same run's 7-way null-control replicate spread
(0.567-0.603) was statistically indistinguishable from its 7-way across-candidate spread (0.570-0.607) —
the round could not tell an edit from a re-measurement of the same code.

The fix is to measure over the tasks the edit can causally reach. `gate_check.py` diffs the candidate
against its reference, reads the identifier-like names off the changed lines, and asks which tasks'
persisted rollouts mention any of them (`cap_evolve.footprint` — deliberately a flat substring search over
the whole rollout record, so it works for any adapter's trace shape and any capability). Tasks outside that
set enter the delta vector as **0.0 rather than as their measured wobble**: an edit that cannot reach a
task has no effect on it by construction. The vector keeps its full LENGTH, so `Δ̄` stays on the same SCALE
as the val reward, and every threshold, ledger row and val-curve point derived from it stays comparable.

It changes **both** halves of the test, not just the variance: `Δ̄` moves too, because the out-of-footprint
deltas that used to be averaged in are now zeros. That is the mechanism, not a side effect — and it is why
the footprint must never UNDER-include. Zeroing a task that really regressed raises `Δ̄` *and* lowers the SE
together, both pushing toward accept, so a net-harmful candidate could be accepted on a fabricated gain.
Two rules prevent it: the enclosing definition is **always** part of the footprint (an edit inside a body
reaches everything that calls the body, not just the rare helper it happens to call), and a surface that
reaches ≥80% of tasks makes the edit **unlocalizable** — abandon and measure the full split — rather than
being dropped so the rarer surfaces beside it can define a confident, narrow, wrong footprint.

A third rule guards the other end. On a SMALL footprint the paired SE, which is estimated from the
cross-task spread of the vector, understates the real uncertainty: 4 tasks whose deltas are
{0, +0.1, 0, +0.1} have a small spread, so the gate reads SE 0.0046 and accepts — on two moves of one
flipped rollout each, the very moves `broke`/`fixed` below refuses to call real. So a restricted vector's
SE is floored by `harness.paired_se_floor`, the SE those tasks' own per-trial noise implies. Unrestricted
vectors keep the SE they always had, so no pre-existing verdict moves.

On the worked case in `core/tests/`, a real +0.1 on 3 of 30 tasks goes from unresolvable to accepted with
the bar falling roughly 4x. On run_finalrun6's real rollouts the mechanism is far more conservative: five
of seven edits reach the split too broadly to restrict at all, and neither restricted verdict changes
(cand_5 17/30, SE 0.0318 → 0.0268; cand_7 4/30, SE 0.0346 → 0.0113 floored). Its value on that run is that
it ABSTAINS rather than manufacturing confidence — an earlier revision without the three rules narrowed
cand_7 to 4 tasks at SE 0.0046 and accepted a docstring-only edit.

Read the `footprint` block in each row before the delta:

- `restricted: true` — `n_in_footprint` of `n_tasks` were in play. The SE describes those tasks.
- `restricted: false` — the surface could not be localized: no diff, a rewrite-sized diff (more distinct
  symbols than a targeted edit would name), no rollouts on disk, a footprint that covers every task
  anyway, or one of the edit's own surfaces reaching ≥80% of tasks. The measurement fell back to the whole
  split, so it carries every task's noise. **A null result here is weak evidence about the edit, not
  evidence against it.** `--no-footprint` forces this mode.
- `paired_se_floor` — the bar the restricted SE was floored at. When it equals `gate_threshold / k_se`, the
  verdict rests on per-task trial noise rather than on the cross-task spread.

The over-inclusion is deliberate: a symbol mentioned only in prose still counts as a hit. Over-including
gives back some of the noise the restriction removes; under-including would zero out a task the edit really
did move and manufacture a gain. Every unknowable case degrades to `restricted: false`, never to a crash
and never to a restriction invented from nothing.

This is also the mechanical argument for **sibling candidates over bundles**: a bundle's footprint is the
union of its parts', so a two-surface bundle is measured at close to full-split noise while each part
measured alone would have been resolvable.

**Not built, and why**: the round does not yet spend the freed budget on more trials over the smaller
in-footprint task set. That needs subset-scoped evaluation plumbed through `round.py`, and `grow.py`
already buys more `n` on an unresolved candidate — footprint-scoped growth is the natural next step, not a
prerequisite for the restriction being correct.

Free on the reference side, and already done: `gate_check.py --current` accepts a comma-separated list of
tags and **pools their trials per task**. `round.py` passes every one of the round's byte-identical
null-control replicates, so the control-relative comparison is against a pooled estimate rather than
whichever replicate happened to carry the round-scoped tag — which was a coin flip (the same candidate read
+0.0867 against one replicate and +0.0067 against the other). No new rollouts: those files are on disk.

### broke / fixed: is this task's move a claim the measurement supports?

`broke` and `fixed` used to be thresholded at `1e-9`, i.e. at nothing. At 10 trials a task that goes
`1.0 → 0.9` has had **one rollout out of ten** flip, and that was being stamped as a task the candidate
broke. It is not a hypothetical failure: on run_finalrun6, byte-identical code measured twice — `cand_2`
and its own fresh-tag re-measurement `cand_4` — got *different* `broke`/`fixed` labels, and the optimizer
reasoned from them for three rounds, including asserting a regression on a docstring-only edit that cannot
change behaviour at all.

Every such claim now has to clear **2·SE of its own per-task measurement** — the two sides' per-task SEs in
quadrature, the same "smallest resolvable effect" the gate reports for the split mean, applied per task.
One function, `harness.move_is_resolved`, is the single bar behind every place the framework makes the
claim: `LEDGER.md` + the journal RESULT stamp (`_candidate_task_impact`); the `no_regression` veto in both
the hill-climb and gepa loops, which is the strongest consequence of the set since it turns a
gate-PASSING candidate into a rejection; the round table's diagnosis list (`gate_check.regressions`);
skillopt's within-epoch improved/regressed buffer (`_categorize`); the sealed report's seed→best movement
and its improved/regressed counts (`measure.py`); and the "don't regress task X" constraint check
(`spend.py`). Seven copies of a bar is how six of them stay at `1e-9` while one gets fixed.

A sub-threshold move is reported as **`unresolved`**, which is neither "broke" nor "unchanged": the reward
moved, and the measurement cannot say the edit did it. Do not redesign an edit because a task appears
there, and do not cite one as a regression — re-measure it, or ignore it. At one trial per task every
per-task SE is 0, the bar collapses to `eps`, and the classification is exactly what it always was.

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

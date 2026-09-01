---
name: agent-optimize
description: 'Free-form optimization algorithm for agent orchestration mode: the conversational agent owns the whole search — proposing capability edits itself, screening them cheaply, gating each on full val, and sealing test once. Use when orchestration_mode is agent and algorithm_skill is agent-optimize. For a deterministic loop use hill-climb, gepa or skillopt instead.'
component: algorithm
argument-hint: "agent-mode only — set orchestration_mode: agent + algorithm_skill: agent-optimize"
allowed-tools: Read, Write, Edit, Bash, Task
provides: [candidate]
needs: [scores, traces, candidate]
---

# agent-optimize — the free-form loop you own

The one algorithm with **no deterministic subprocess** and **no per-iteration optimizer**: you — the agent
that ran intake — are the optimizer, the scheduler and the stopping rule. `cap-evolve run` (with
`orchestration_mode: agent`) does check → baseline, prints a handoff with the `run_dir`, and returns. From
there the search is yours, bounded by the invariants core enforces and the free-text **`stop_condition`**.
Drive the *existing* primitives so the run dir and dashboard stay populated as in a deterministic run.

## Shell variables used below

```bash
R="<run_dir from the agent-mode handoff>"      # e.g. .capevolve/run_20250101_120000
P="<project dir>"                              # the dir holding capevolve.yaml + adapters/
S="${CAPEVOLVE_SKILLS_DIR:?set CAPEVOLVE_SKILLS_DIR to the skills/ dir}"
A="$S/algorithms/agent-optimize/scripts"       # this skill's helpers
mkdir -p "$R/work"                             # working copies live here (RunDir does NOT create it)
```

Every script imports `_bootstrap` itself (no `PYTHONPATH`) and prints JSON on stdout.

## Phase 0 — understand before you optimize

Once, before any edit, and **ask the user any blocking question here** so the loop then runs unattended.
Read `PROJECT.md`, `capevolve.yaml`, the adapter and every file under `capability_path`, and understand what
**one evaluation** does: what a task is, what `run_target` produces, what `score()` rewards, and what the
per-task **feedback** says — that is your learning signal. Note the val/test sizes, `num_trials`,
`gate_mode`/`gate_k_se` and the allowed edit surface.

Then let `spend.py` parse the free-text **`stop_condition`** rather than restating it from memory: it prints
`constraints.predicates`, every concrete check it could extract, with its measured actual. **If
`constraints.ambiguous` is non-empty, ASK THE USER before the loop starts** — a vague clause is reported,
never guessed at, and this is the one moment where asking is cheap.

## Agent-mode loop

Baseline has scored the seed on val and set `best_id = seed`. Each round:

**0. Check you can afford the round — for the number of candidates you actually intend to run**, with
`--n-siblings N` whenever you plan N of them, *before* spending:

```bash
python "$A/spend.py" --run-dir "$R" --project "$P" --n-siblings 3
```

Act on the single `recommendation`: **`stop`** (a ceiling breached, `budget_exhausted()` true, or the score
goal met on FULL val) → **Stop & seal**; **`narrow_scope`** (≥80% of a ceiling consumed, goal unmet) → ONE
cheap candidate at tier 1, no fan-out; **`continue`** → run the round you planned.

`afford.affordable: false` (with `afford.blockers` naming the ceiling) means **do not fan out N** — check
BEFORE dispatching proposers, since N candidates can blow a budget with room for one.
`afford.runner_spend_metered: false` means $0 is *unmetered*, not free — bound such a run with
`max_metric_calls` and report **rollout counts, not dollars**.

**1. Read the signal.** Free — no new evaluation:

```bash
BEST="$(python "$A/spend.py" --run-dir "$R" | python -c 'import json,sys;print(json.load(sys.stdin)["best_id"])')"
python "$S/phases/diagnose/scripts/run.py" --run-dir "$R" --tag "$BEST" --split train
python "$S/phases/diagnose/scripts/run.py" --run-dir "$R" --tag "$BEST" --split val
```

Read `clusters` for what to fix and `kept_good` for what not to break. **With a disjoint train split,
diagnose it too and compare its cluster signatures to val's** — free, and it decides whether the round can
work at all: if the signatures are disjoint, no train-driven edit can move the val mean, and every candidate
is rejected for a reason that looks exactly like a null result. Say which, in the report. (Baseline
scores val only, so pay one `evaluate --split train` first.)

**Read the per-task pass rate, not the per-task pass/fail.** At `num_trials: n` a task's reward is
`k/n`, and that fraction is what separates defects from noise:

| per-task rate | what it is | what to do |
| --- | --- | --- |
| `0/n` – `3/10` | a real, reproducible defect | this is where every edit should aim |
| `4/10` – `7/10` | genuinely unstable behaviour | fix by *removing* ambiguity, not adding rules |
| `8/10` – `9/10` | noise around a working path | **leave it alone**; "fixing" it is how churn starts |

A task that "regressed" from `10/10` to `9/10` between rounds is a re-measurement, not damage.

**Audit the MEASUREMENT before you credit a failure**, in round 1 while it is still free (scoring
re-derives on persisted rollouts): a failing task is a claim by the scorer, and an optimizer that skips
this optimizes against its own instrumentation. Does the feedback name the **defect** or only the tool;
does any helper fail **silently**; is *silent* distinguished from *wrong*; did the rollout **run**, or is
this missing data wearing a 0.0; which components actually **gate**? The failure behind each item:
`references/edit-design-lessons.md`.

**After two rejected rounds, read the candidate's TRACE before writing a third** — not "was the rule
right" but "did the agent follow it at all". Never exercised ⇒ the **form** is wrong; exercised and
still wrong ⇒ the content is.

**2. Propose an edit per candidate — and address EVERY cluster the round can afford**, either as
**sibling candidates, default N≥3** (one cluster each, gated independently — the safe default) or as **one bold
multi-part edit** (higher variance, but the only way a fix needing a prompt change *and* a tool change
lands together). Bundle only *independent* parts — different files, different rules — so a rejected bundle
can be resubmitted as its surviving part; read `regressed` (screen) and `regressions` (gate) to know which
to drop. That is also what stops **churn** — a candidate whose mean matches its parent while a *different*
set of tasks passes — from reading as a tie.

```bash
TAG="cand_1"                                   # unique per candidate — it IS the rollout tag
cp -r "$R/candidates/$BEST" "$R/work/$TAG"
# …now edit the files under $R/work/$TAG that your capability owns. Example only:
# read capability_path in Phase 0 for the real layout.
```

Every edit encodes a **general rule** — never a task's id, gold value, or answer.

**Choose the edit FORM from the failure TYPE — before you write a word.** The form matters more than the
wording, because the form that repairs one failure type measurably backfires on another:

| the failure you observed | the form that fixes it | the form that makes it worse |
| --- | --- | --- |
| the rule is stated and the agent skips it under pressure | a prohibition plus the symptom that precedes it ("if you are about to X, you have already failed") | restating the rule — a mid-tier model gets *less* compliant |
| the agent complies but the call has the wrong shape | a **positive recipe**: what the correct call IS, its parts, in order | a list of things not to do — it produced *more* unwanted output than no guidance |
| a required element is missing | a **structural REQUIRED slot**, or a code-level precondition | a prose reminder mid-document |
| behaviour should differ by situation | a conditional on an **observable predicate** the agent can evaluate from tool output | an unconditional rule plus exemptions |

Then: **no nuance clauses**; **exemption clauses do not scope** (still suppresses X); **prefer an in-code
guard to a prose rule where the capability owns its tools** — prose when the agent lacks a decision
criterion, code when it has one and violates it. Costs, and the guard-closure trap: `edit-design-lessons.md`.

**Every round evaluates a null control**: copy the current best byte-for-byte into `$R/work/ctl_null`
and evaluate it like any candidate — first, not after a surprising result. That eval is the round's own
noise floor, and a candidate inside that band is not evidence of anything. And **read
`$R/rejected.jsonl` and make each proposal STRUCTURALLY different from what is in it**: a different
form, surface, or cluster — never a narrower version of a rejected rule.

**3. Cheap SUBSET screen — the promotion ladder.** Do not pay full val to learn an edit is bad:

```bash
python "$A/screen.py" --run-dir "$R" --project "$P" \
       --candidate "$R/work/$TAG" --tier 1 --k-se 1.0
```

Only the candidate pays, and only for the subset. `decision` is `kill` or `promote` — **never accept** — and
it kills only on proven harm. **Check the arithmetic before trusting a screen:**
`savings.breakeven_kill_rate` (`fired / full_val_rollouts`) is the fraction it must kill to pay for itself;
`savings.net_rollouts` books what it cost. Screen only when that break-even sits below your observed kill
rate — on a small val the tier-1 floor makes it unreachable, so pay full val directly — and read a screen as
evidence about the tasks the edit targeted, never as a gate decision.

**4. Honest gate on FULL val.** Evaluate the whole split (this writes rollouts + results under tag
`$TAG` — the evaluate phase tags by the candidate **dir name**), then decide off those rollouts:

```bash
python "$S/phases/evaluate/scripts/run.py" --run-dir "$R" --project "$P" \
       --candidate "$R/work/$TAG" --split val --n-trials <num_trials>
python "$A/gate_check.py" --run-dir "$R" --candidate "$TAG" --k-se <gate_k_se>
```

`"verdict"` is evidence, not a command — decide accept/reject yourself, citing the numbers in
`commit.py --note` (`references/algorithm.md`, "Gate as evidence"). `"indecisive"` means too little of val
ran, not a rejection. **`regressions` is diagnosis, not a veto** — a per-task drop at `n` trials is an
estimate, not proof, and the old no-regression veto rejected byte-identical seed copies often enough to dominate false
rejects (`--veto-regressions` restores it, at that rate). `phases/gate/scripts/run.py` inspects the same
gate but books no decision.

**5. Commit the decision through the run dir**, so `best_id`, the stall counter, the dashboard and the
audit log stay real. `--decision reject` keeps the old best; either way it snapshots the candidate, logs
the event and advances `iterations` + stall:

```bash
python "$A/commit.py" --run-dir "$R" --candidate-id "$TAG" --from-dir "$R/work/$TAG" \
       --decision accept --val <cand_mean> --note "<one line: the general rule you added>"
```

**On a reject, pass `--reject-basis`** — `screen.py`'s "promote" means "could not prove harm", never "was
evaluated on full val", so conflating the two makes the run's artifacts contradict themselves. `gate` (a
full-val paired gate ran and said reject), `screen_kill` (the screen proved harm), `ceiling` (arithmetic
proved no accept reachable, full val never paid), `budget` (screen evidence plus a budget call, not a
gate decision), `infra` (missing data). So `screen: promote` + `reject_basis: ceiling` is coherent.

`commit.py` **refuses a `--candidate-id` that already carries a decision event** (`--force` only to
repair a record deliberately): two drivers tagging a candidate alike otherwise produce two decision
events over ONE set of rollouts. Pass `--optimizer-usd/--optimizer-tokens/--optimizer-seconds` for
**your own** proposal cost — the evaluate phase records the runner's, nothing records the proposer's.

**Two decisions that are NOT rejects** (a reject advances **stall**): `--decision inconclusive` for an
unresolved round (`verdict_stable: false`), re-measured under a FRESH tag; `--decision provisional` for a
Δ>0 round under the bar (`directionally_positive_but_inconclusive`), after which `grow.py` buys trials on
the SAME candidate and re-gates at the pooled n, capped at 2 rounds. `references/algorithm.md`.

**6. Write the handover before ending this round** — append one `## Iteration <cid>` entry below
`JOURNAL.md`'s marker: what you tried, why, what the numbers said. The only thing the NEXT round reads,
and `commit.py` folds in only what you wrote (`references/algorithm.md`).

## Parallel round (optional)

**The whole of steps 3–4 for a round is one command.** `round.py` builds the null control, evaluates
every tag in parallel *processes* (each runs its own adapter `apply()`, which mutates a process-global
registry and must never be shared), gates them serially, and prints one table:

```bash
python "$A/round.py" --run-dir "$R" --project "$P" \
       --candidates cand_1,cand_2,cand_3 \
       --n-trials <num_trials> --k-se <gate_k_se> --concurrency 8 --max-parallel 2
```

`--concurrency` is the gate's *measurement* concurrency and defaults deliberately low; `round.py` warns
once you raise it past what a gate can resolve, so never raise it to buy wall clock. Read
`noise_floor_from_control` FIRST — a candidate inside that band is not evidence, whatever its verdict.
`round.py` never commits: which part of a bundle to keep is your judgement.

Four invariants, to state before every fan-out (the reasoning, and where fan-out pays best, are under
*Parallelism* in [`references/algorithm.md`](references/algorithm.md)):

1. **Diagnosis fans out freely** — read-only, zero rollouts: one `cap-evolve-diagnoser` per failure
   cluster or rollout shard, then merge their JSON.
2. **Proposal fans out across distinct working copies, one `cp -r` per sibling, tag unique per sibling** —
   rollouts are `<task>__<tag>__t<k>.json`, so a shared tag interleaves two evals into the same filenames
   and corrupts both scores.
3. **The gate stays serial** — gate + commit one sibling at a time, and after any accept **re-run
   `gate_check.py` for every remaining sibling against the new best**. Skipping that re-gate
   double-counts a gain and admits an edit that never beat what it now stacks on.
4. **Never fan out across the test split, and pay before you fan out** — `spend.py --n-siblings N`
   must say `affordable: true` first.

Concurrency also composes *inside* one evaluation (`screen.py --workers N` / `CAPEVOLVE_WORKERS=N`, pooling
rollout generation only — numbers stay byte-identical to serial). Opt in only when `run_target` is
thread-safe: no shared scratch dir, single live container, or module-global client.

### Per-task fan-out — the cheap gradient

Reach for this only when the baseline's `k/n` bands show the loss **concentrated in a few named tasks**: one
task at `n_trials` then buys the same bit as a `val_n × n_trials` full-val round, about a failure that
demonstrably exists. Helpers, in order — `taskeval.py` (run **detached**: a per-task eval can outlive a
harness timeout while healthy), `mechanisms.py` (the shared ledger; `list` BEFORE you diagnose, or two
optimisers implement one fix and collide at merge with only one measured), `integrate.py`, `funcmerge.py`,
`merge_taskopt.py` — then gate the artifact once on full val via `round.py`. Economics, briefing contract,
canary selection, every flag: [`references/per-task-fanout.md`](references/per-task-fanout.md). Two rules
decide whether the shape is safe at all, so they live here:

**A parallel optimiser's deliverable is a MECHANISM WITH TRACE PROOF, not a rate.** A fan-out is a
high-load regime by construction — where a per-task rate cannot resolve the effect — so ask for
load-independent evidence (the guard fired, the next action changed), then gate the survivors serially.

**A multi-branch artifact is assembled with `integrate.py`, never by one merge**, one branch at a time with
a measurement after each: fewer mechanisms routinely beat more, and one number for N simultaneous changes
cannot tell you that. `funcmerge` merging cleanly is **not** evidence the branches compose — Clean merge is
a syntactic property; composition is an empirical one.

## Measurement discipline

**Measure step 2's null control twice**: the gap between two byte-identical parents is the round's bar, and a
bar smaller than that is not a gate. Two more rules; the rest — ceiling arithmetic, the binomial floor,
mechanism-vs-artifact designs, gating the sum not each addend, the sign test below the floor — is in
[`references/measured-lessons.md`](references/measured-lessons.md).

1. **Explore fast, gate slow, gate ALONE.** The load knob is *total in-flight requests* (K processes at
   concurrency C is K·C), not any per-process flag, and oversubscription fails silently as latency, not an
   error. Pause the fan-out, run both gate arms in one batch alone; if you cannot quiet the machine, say
   so next to the verdict.
2. **Two independently-seeded blocks, agreeing in sign, before a small effect is a result.** A paired
   run's SE is over *tasks*, so it cannot see run-to-run nondeterminism; `multirep.py` takes the error
   across whole runs (`--base-seed` picks the block — raising `--n` extends the same one, not a
   replication). Several full runs unaffordable ⇒ "not resolvable at this budget" is the honest output.

## Stop & seal, then MEASURE (once)

Spend is not a CLI subcommand: **every 2–3 rounds** (and always before a fan-out) run `spend.py`.
Everything it reports is re-read from the run dir, never a total in your head — which keeps a `$6.00`
cap from becoming `$6.01`. (The Stop hook re-nudges you until finalized; a `PostToolUse` hook
re-injects the same predicates on a cadence even if you skip `spend.py` — `goal_reminder.py`.)
Stop when `recommendation` is `stop`, then produce the run's one honest table — seed vs best on
**val**, on **train** when the spec defines one worth reporting, and on the **sealed test** split
scored once:

```bash
python "$A/measure.py" --run-dir "$R" --project "$P" --train auto
python "$S/phases/report/scripts/run.py" --run-dir "$R"
```

`measure.py` reads val off the rollouts the gate already used (free), evaluates train only when it adds
information, and seals test through the same `harness.finalize` the finalize phase calls — so it is
interchangeable with `phases/finalize/scripts/run.py`. Report its four refusals unsoftened: an **empty** split is `empty`, not 0.0; a **no-holdout** spec is a **FIT metric, not
generalisation**, with the overlap counted; a negative `screen_ledger.net_rollouts` says screening was
pure overhead; `best_id == "seed"` is a **null result with a diagnosed cause**, not a 0.000 gain.
(Sealing is that phase script, **not a CLI subcommand**; a second finalize raises `TestSealError`.)
No finalize, no result.

## Honesty invariants that are yours by hand

Core enforces the split seal, the val-only gate and the tamper guard whether you cooperate or not
(`skills/phases/{evaluate,gate,finalize}` document them). Two are yours, because no script can do them
for you: **never hand a subset result to `gate_check.py`** — its `coverage` reads 1.0 because its
denominator *is* the subset; and **a round that produced no run-dir artifacts is a bug**, so fix it
rather than driving around the primitives.

## References

One level deep — each is read on its own, and none points at another.

- [`references/algorithm.md`](references/algorithm.md) — why free-form, how the honesty invariants
  survive full autonomy, the screening break-even (incl. targeted-cluster holdouts), which steps
  parallelise safely, the constraint surface, provisional candidates. **Load** before relying on a
  screen, growing a candidate, or skipping a rule.
- [`references/measured-lessons.md`](references/measured-lessons.md) — every measurement rule with the
  number that bought it: binomial floor, full val vs a hard subset, the load-vs-noise tables, the sign
  test, the across-runs estimator. **Load** before your first gate decision on a new benchmark, or
  when a result surprises you.
- [`references/per-task-fanout.md`](references/per-task-fanout.md) — the fan-out's economics, the
  subagent briefing contract, canary selection, every helper's flags. **Load** when the loss is
  concentrated in a few named tasks.
- [`references/edit-design-lessons.md`](references/edit-design-lessons.md) — the scorer audit, guard
  closure, and the measured backfires behind the edit-form table. **Load** before editing a surface
  for the first time, or after two rejects.

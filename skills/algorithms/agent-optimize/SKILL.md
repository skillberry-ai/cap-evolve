---
name: agent-optimize
description: 'Fully-agentic, free-form optimization algorithm. Use in agent orchestration mode when you want the conversational agent to own the whole search — understand the benchmark/inputs first, run the baseline, then freely propose capability edits (serially, or several siblings in parallel working copies), diagnose per task from TRACES rather than from rates, accept only on a full-val paired gate measured against byte-identical control replicates in the same batch and repeated across seed blocks (one paired run cannot resolve a sub-0.10 effect here), all bounded by a free-text stop_condition parsed into re-checkable predicates and re-read from the run dir every round, and finished with one honest train/val/sealed-test measurement. Agent-mode only (orchestration_mode: agent); for a deterministic loop use hill-climb | gepa | skillopt.'
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

**Read the per-task pass rate, not the per-task pass/fail.** At `num_trials: n` a task's
reward is `k/n`, and that fraction *is* the learning signal — it separates the defects from
the noise, which is the distinction four consecutive null runs on one benchmark failed
to make:

| per-task rate | what it is | what to do |
| --- | --- | --- |
| `0/n` – `3/10` | a real, reproducible defect | this is where every edit should aim |
| `4/10` – `7/10` | genuinely unstable behaviour | fix by *removing* ambiguity, not adding rules |
| `8/10` – `9/10` | noise around a working path | **leave it alone**; "fixing" it is how churn starts |

A task that "regressed" from `10/10` to `9/10` between two rounds is a re-measurement of
the same capability, not damage. Chasing it is the single most expensive mistake available
here: `gate_check.py`'s old no-regression veto did exactly that and rejected a
byte-identical copy of the seed 43% of the time at 5 trials.

**Audit the MEASUREMENT before you credit a failure.** A failing task is a claim by the
scorer, and a scorer can be wrong in ways that look exactly like a capability gap. Spend the
first minutes of round 1 on this, because it is free and because every optimizer that skipped
it optimized against its own instrumentation:

- **Does the feedback name the actual defect, or only the tool?** If it says "Failed action(s):
  a write tool" when the real defect is a wrong *argument value*, no edit can be
  localized. (Measured on this benchmark: argument-value errors are the majority of failed
  gold actions. A predecessor read the wrong field name for the action check, reported "0
  actions missed" for every task, and stayed blind to the dominant failure mode for an entire
  effort.) Fix the adapter's feedback, then re-derive — scoring is deterministic on persisted
  rollouts, so this costs zero rollouts.
- **Does any feedback helper fail SILENTLY?** Grep the adapter for bare `except` around signal
  construction and make each one loud. On this benchmark a localizer called a helper method
  that did not exist; the `AttributeError` was swallowed, so every failed numeric check
  degraded to the generic *"1 required piece(s) of information were not clearly
  communicated"*. An optimiser read that as "the checker is unsatisfiable" and spent **seven
  rounds** instructing the agent to state a value it was already stating. The repaired signal
  distinguishes *never stated a figure* from *stated one and it was wrong* — and re-deriving
  it over 125 already-persisted rollouts cost nothing.
- **Distinguish "silent" from "wrong" for every value-bearing check.** They are different
  defects needing opposite edits (add a REQUIRED slot vs. fix arithmetic/scope), and a message
  that conflates them sends the round in the wrong direction. Report the value the AGENT
  stated, never the expected one — a check's `info` field often *is* the expected value
  (one benchmark stores a bare `"1628"`), so use its SHAPE and never echo it.
- **Did the rollout run, or did the infrastructure fail?** A wallclock timeout, a starved
  endpoint or a dropped connection is missing data, not a zero. If it lands in the mean as
  0.0, a whole evaluation can read as a catastrophic capability with no error anywhere.
  Check `termination_reason` and the coverage the gate reports — a low-coverage split must be
  `indecisive`, never a score.
- **Would a clearly-wrong candidate score worse?** If not, the metric is not discriminating
  and no gate built on it can work.

**When two rounds of edits are rejected, read the candidate's TRACE before writing a third.**
The question is not "was the rule right" but "did the agent follow it at all". If the trace
shows the new rule was never exercised, the content is not the problem — the **form** is, so
take a different row of the table below. If it was exercised and the outcome was still wrong,
the content is wrong and the rule needs different substance. Guessing between those two is
how a budget disappears into variants of one idea.

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

**Choose the edit FORM from the failure TYPE — before you write a word.** Which form you
reach for matters more than how well you word it, because the form that repairs one failure
type measurably backfires on another. Classify the cluster first, then take its row:

| the failure you observed | the form that fixes it | the form that makes it worse |
| --- | --- | --- |
| the rule is stated and the agent skips it under pressure | a prohibition plus the symptom that precedes it ("if you are about to X, you have already failed") | another restatement of the rule — this is the case where a mid-tier model gets *less* compliant, measured |
| the agent complies but the output/call has the wrong shape | a **positive recipe**: state what the correct call IS, its parts, in order | a list of things not to do — on shaping problems this produced *more* unwanted output than no guidance at all |
| a required element is simply missing | a **structural REQUIRED slot** the agent has to fill, or a code-level precondition | a prose reminder somewhere in the middle of the document |
| behaviour should differ by situation | a conditional on an **observable predicate** the agent can actually evaluate from tool output | an unconditional rule plus exemptions |

Two findings that cost other runs real budget:

- **No nuance clauses.** Appending one qualifying clause to an otherwise-winning recipe
  degraded it from consistent to noisy. If a rule needs a caveat, restructure the rule.
- **Exemption clauses do not scope.** "This limit does not apply to X" still suppresses X.
  Restructure so the rule cannot reach the exempt case in the first place.

**Prefer an in-code guard to a prose rule when the capability owns its tools.** The only
edit that has ever carried a large accepted gain on this benchmark was tool-level
(`tools.py` 593 → 832 lines, +0.176 val): a precondition that refuses the illegal write and
returns a recovery-oriented error changes behaviour deterministically, where a policy
sentence changes it only probabilistically. Prose is the right form when the agent *lacks*
a decision criterion; code is the right form when it has one and violates it.

**Every round evaluates a null control alongside the candidates.** Copy the current best
byte-for-byte into `$R/work/ctl_null` and evaluate it like any candidate. It costs one eval
and buys the round's own noise floor: whatever `ctl_null` measures away from its parent is
what *zero change* looks like today, so a candidate inside that band is not evidence of
anything. Three of the four null runs discovered this reactively, after the fact — do it
first. (Skill authoring calls this the mandatory-simultaneous-baseline rule; it is the same
discipline, applied to an optimizer.)

**Read `$R/rejected.jsonl` and make each proposal STRUCTURALLY different from what is in
it.** Not a narrower version of a rejected rule, not the same rule with a caveat — a
different form from the table above, a different surface (policy vs tools), or a different
failure cluster. Re-proposing a variant of a rejected edit is how a run burns its whole
budget re-measuring one idea.

**3. Cheap SUBSET screen — the promotion ladder.** Do not pay full val to learn that an
edit is bad. Screen it on a small, deterministically chosen, informative subset of val
first:

```bash
python "$A/screen.py" --run-dir "$R" --project "$P" \
       --candidate "$R/work/$TAG" --tier 1 --k-se 1.0
```

In one paragraph: the parent side is free (its full-val rollouts are already on disk, so only
the candidate pays, and only for the subset); the subset is seeded, recorded to
`$R/screens/<tag>__tier<N>.json`, and deliberately informative rather than random — currently-
failing and high-variance tasks, plus a random `holdout` drawn from tasks the parent passes,
which is the only part that can see a regression; rungs are cumulative, so `tier 2` pays only
for the ids it adds; `savings.net_rollouts` books the real cost (`+ (full_val − fired)` on a
kill, `− fired` on a promote). `decision` is `kill` or `promote` — **never accept** — and it
kills only on proven harm, because a false kill discards a good edit silently while a false
promote costs one eval the honest gate then decides correctly. Full detail:
[`references/algorithm.md`](references/algorithm.md#subset-screening-where-the-cost-actually-goes-and-why-a-screen-may-not-accept).

**At `val_n <= 30`, skip the ladder and pay full val directly.** Check the arithmetic before
you rely on a screen: `savings.breakeven_kill_rate` is `fired / full_val_rollouts` — the
fraction of candidates the screen must kill just to pay for itself. At `val_n 12` the tier-1
floor of 6 makes that **0.5**, and across four real runs the screen killed **0 of 8**
promoted candidates while producing one documented false positive (a 3-task tier-1 reported
`fixed: ["44"]` for a candidate that full val showed never fixed 44 — which is why the floor
is 6, not 3). A ladder that cannot pay for itself and mis-reports is worse than no ladder.

Where a screen *is* worth paying for (large val, cheap tier), read it as **direct evidence
about the tasks the edit targeted**, not as a statistical test: a tier-1 subset containing
every failing val task that comes back 0-for-N on them is a sound reason to stop spending on
that candidate. Commit that as a budget decision on screen evidence, not a gate decision.

**4. Honest gate on FULL val.** Evaluate on the whole val split (this writes
rollouts + results into the run dir under tag `$TAG`, because the evaluate phase tags by
the candidate **dir name**):

```bash
python "$S/phases/evaluate/scripts/run.py" --run-dir "$R" --project "$P" \
       --candidate "$R/work/$TAG" --split val --n-trials <num_trials>
```

Then take the decision — the **paired** significance gate, read straight off the persisted
rollouts:

```bash
python "$A/gate_check.py" --run-dir "$R" --candidate "$TAG" --k-se <gate_k_se>
```

It prints `gate` (`accept`, `reason`, `delta`, `threshold`), `paired_n`, `regressions`, and a
combined `verdict`. Accept **only** on `"verdict": "accept"` — Δ̄ > k·SE over the paired
per-task deltas. A `"verdict": "indecisive"` is not a rejection: too little of val actually
ran, so fix the runner before spending more budget.

**`regressions` is diagnosis, not a veto.** It lists val tasks the parent measured-and-passed
that dropped, and it is the most actionable line in the output — it names which part of a
bundled edit to drop next round. It does **not** block an accept. The old no-regression veto
did, and it was the measured cause of four consecutive null results: it fires on a
byte-identical copy of the seed 42.8% of the time at 5 trials, and in one run it vetoed
*both* candidates that had passed the significance test. The paired test already accounts for
per-task movement in both directions, so churn (fix 2 / break 2 at an unchanged mean)
correctly fails it for the right reason. `--veto-regressions` restores the old behaviour if
you specifically want a zero-regression guarantee and are willing to pay that false-veto rate.

> `phases/gate/scripts/run.py` is the human-inspection front-end. In **rollout mode** it
> reaches the same paired gate off the same files, so it is a faithful way to re-derive
> just the significance half of a decision:
> ```bash
> python "$S/phases/gate/scripts/run.py" --mode paired --k-se <gate_k_se> \
>        --run-dir "$R" --current-tag <best_id> --candidate-tag "$TAG"
> ```
> It is still **not** the round's gate: it does not read `regressions`, so it cannot tell
> you which part of a bundled edit to drop, and it does not book the decision.
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
`decision` and the driver's disposition are two different facts; conflating them made one
run's artifacts contradict themselves. `screen.py`'s `decision` is the screen's own
statistical verdict only, so "promote" means "could not prove harm", never "was evaluated on
full val". What happened next is `--reject-basis`:

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
`events.jsonl` (`--force` only to repair a record deliberately). A real run had two concurrent
drivers both tag a candidate `cand_r2`: two reject events, ONE set of rollouts, so one edit
was judged on the other's evidence. The check reads the log, not memory, so it holds across
processes.

Add
`--optimizer-usd/--optimizer-tokens/--optimizer-seconds` for **your own** proposal cost —
the runner's `metric_calls`/`usd`/`seconds` are already recorded by the evaluate phase, but
nothing else records the proposer's, so cost-based stop conditions under-count without it.

## Parallel round (optional, and only as described)

**The whole of steps 3–4 for a round is one command.** Once the working copies exist,
`round.py` builds the null control, evaluates every tag in parallel processes (safe: each
process does its own adapter `apply()`, which mutates a *process-global* registry and so
must never be shared), then gates them serially and prints one table:

```bash
python "$A/round.py" --run-dir "$R" --project "$P" \
       --candidates cand_1,cand_2,cand_3 \
       --n-trials <num_trials> --k-se <gate_k_se> --concurrency 300 --max-parallel 4
```

Read `noise_floor_from_control` FIRST. It is what zero change measured today; a candidate
whose `delta_vs_parent` sits inside that band is not evidence, whatever its verdict says.
`round.py` deliberately does not commit — deciding which part of a bundled edit to keep is
yours, and `regressions` is the input to it.

Everything below is why those defaults are what they are. Fan-out buys real wall-clock, and
costs real budget, so it is bounded by five invariants — state them before every fan-out:

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
round.py  ──fan out──►  ctl_null + N full-val evals in parallel        (costs rollouts)
             SERIAL ──►  gate_check per candidate, table with the noise floor
commit      SERIAL ──►  commit.py per candidate; on accept, re-gate the rest
```

(`screen` sits between propose and evaluate only when its `breakeven_kill_rate` can actually
pay — at `val_n <= 30` it cannot; see step 3.)

Three independent sources of concurrency — use all three, they compose:

1. **Inside one evaluation**, if the adapter has `run_batch`/`run_trials` it already runs
   the whole task grid at its own concurrency (some adapters do, via their own
   concurrency env var). Otherwise `screen.py --workers N` — or `CAPEVOLVE_WORKERS=N`
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

**But concurrency composes only up to the endpoint's sustainable rate, and past it the failure
is silent.** These three sources multiply: K optimisers x C concurrency each is K*C in flight,
and the serving endpoint does not know about your fan-out. Measured on this run: nine per-task
optimisers at concurrency 8 put ~72 requests in flight against a proxy whose sustainable band
is 24-90, and a single per-task eval went from ~4 minutes to ~50. Nothing errored — latency
just grew, so it read as "the model got slower" rather than "I oversubscribed". An earlier
incident on the same proxy is the extreme version: concurrency 300 pushed 292 of 300 rollouts
into wallclock timeouts and the evaluation reported **0.0067** as capability. So: measure the
sustainable band once, divide it by the number of concurrent optimisers, and treat a sudden
wall-clock blowout as an oversubscription symptom before you treat it as anything else.

If in doubt, run the serial loop. A correct serial round beats a fast wrong one — and a
double-counted gain is invisible in the val number that produced it.

## Per-task fan-out — the cheap gradient

Use this when the baseline's `k/n` bands show the loss is **concentrated in a few named
tasks** rather than spread thin. It is the highest-leverage shape in this skill, and the one
the first five rounds of one long run failed to use.

**Why.** A full-val gate round costs `val_n × n_trials` rollouts and returns *one bit per
candidate*: accept or reject. A single task at `n_trials` costs `n_trials` rollouts and
returns the same bit — about the failure that actually exists. At `val_n = 30, n_trials = 10`
that is 300 rollouts per learning step versus 10: **a 30× cheaper gradient**, on the unit the
defect lives in. Measured on one long run: five classic rounds spent ~1500 rollouts to
produce **10 learning steps and 1 accept**. The same budget under this shape buys **nine
optimisers × six iterations = ~54 steps**, each aimed at one measured defect, and the
per-task evals run concurrently so the wall-clock cost is one round's.

**A screening band is not a baseline.** Per-task rates from a small trial count tell you where
to *look*; they do not tell you where you *are*. In one run, ten tasks whose 3-trial
bands summed to 2.33 measured **4.04** at n=10 — the screen understated the artifact by 1.71
task-equivalents (0.057 of val), and one task went the other way (0.33 → 0.10). Every "0.0
DEFECT" label was suspect: three of them measured 0.30, 0.444 and 0.60. So: screen at low `n`,
but re-measure at the gate's `n` before you quote a number, compute headroom, or tell an
optimiser what its starting point is — and never let a low-`n` band be the thing a delta is
computed against. This is the same error as the canary bands, one level up.

**First compute the BINOMIAL floor. Most of what looks like mysterious nondeterminism is n.**
Each rollout is pass/fail, so a task's rate is a binomial proportion and an arm mean over `m` tasks
at `n` trials has

    SE(arm difference) = sqrt( sum_over_tasks 2·p(1-p)/n ) / m

Do that arithmetic BEFORE blaming the provider, the seeds, or the load. Measured here on 10 tasks
at n=10 with p≈0.35: predicted SE **0.0615**, observed gap between two byte-identical arms
**0.0778** — a ratio of **1.27**, i.e. plain sampling. Mean per-task movement was 0.0978 against a
binomial prediction of 0.1445, so the observed movement was *smaller* than chance requires. There
was nothing left to explain.

One precision about what this is and is not. At temperature 0 with identical seeds a fully
deterministic system would return *identical* arms, so this is not sampling error in the textbook
sense — there is no sample being drawn. What the arithmetic shows is that the observed variation is
**statistically indistinguishable in magnitude from independent per-rollout coin flips**. That
matters because it means no further mechanism needs to be posited to explain it, and — whatever its
physical cause — the remedy is the same one that works for binomial noise: more trials. Do not
report it as "sampling noise" without that caveat, and do not go hunting for a cause you have no
evidence for.

That reframes the concurrency result rather than cancelling it: at conc 25 per-task movement was
0.250, genuinely **above** the 0.1445 floor, and dropping to conc 8 removed that excess and exposed
the floor underneath. Lowering concurrency fixes what it can; the rest is n.

The consequence is uncomfortable and worth stating plainly: **an aggregate mean over a dozen HARD
tasks at n=10 cannot resolve any realistic edit.** Reaching 2 SE on a +0.05 effect on that subset
needs ~60 trials per task.

But be careful about the obvious inference, which is wrong. Narrowing to the hard tasks makes the
measurement *worse*, not better, for judging an artifact — because a task sitting at 1.00
contributes signal to the mean with almost no variance, so dropping it removes a free denominator.
Computed from this benchmark's own per-task rates:

| arm | rollouts/arm | SE of paired difference |
|---|--:|--:|
| 12 hard tasks, n=10 | 120 | **0.0496** |
| full val 30 tasks, n=10 | 300 | **0.0262** |
| full val 30 tasks, n=20 | 600 | 0.0185 |

Full val at n=10 is nearly twice as precise as the hard subset, and the four prior gate rounds here
were run at full val n=5 (SE 0.0371) — so their problem was never the task set. It was that they
ran at a concurrency carrying excess noise on top of that, and chased effects smaller than the sum.

So the two questions need opposite designs, and conflating them is the actual error:

| you want to know | measure | why |
|---|---|---|
| does this mechanism work | ONLY the tasks where it fires, at high n, per-task test | a mechanism firing on 2 tasks is diluted to nothing in a 30-task mean |
| does it break anything | canaries, cheap precisely because they sit at 1.00 | zero variance means a single drop is real |
| what is the artifact worth | FULL val, both arms in one batch | the 1.00 tasks are free precision for the mean |

A mechanism that fires on two tasks and lifts them 0.15 → 0.45 is resolvable at n=40 on those two
tasks (≈3 SE) and invisible in a 12-task mean at n=10 (≈0.5 SE). Same edit, same rollout budget,
one design answers the question and the other cannot.

**Run the GATE at low concurrency — most of the re-measurement noise is load-induced.** This is the
one lever that makes everything else measurable, and it is cheap to verify: measure the same bytes
on the same seeds twice at your search concurrency, then twice again at a low one.

| identical bytes and seeds, 12 tasks | conc 25 | conc 8 |
|---|--:|--:|
| arm-level \|delta\| between the two runs | **0.1167** | **0.0333** |
| mean \|per-task\| movement | **0.250** | **0.100** |
| tasks that moved at all | 10 / 12 | 5 / 12 |

Five of the twelve tasks became perfectly repeatable at conc 8 having each moved 0.20-0.40 at conc
25. So the practical split is: **search fast, gate slow.** Per-task exploration can run at high
concurrency because its output is a mechanism you verify from a trace, not a rate; the accept
decision must run at a concurrency where the null actually reproduces, which costs roughly 3x wall
clock for the one evaluation that matters.

Two caveats to state whenever you quote this, both real: the low-concurrency runs here were
sequential, so load and elapsed-time drift are confounded; and 12 tasks x 2 runs makes the variance
comparison thin. The direction was consistent across all three metrics, which is why it is worth
acting on, but it is not settled.

**A guard that forbids the harmless option can force the harmful one. Ask what the agent does
INSTEAD.** Measured: a guard refusing an itinerary change that changes nothing ("this call would
change nothing, so do not quote a price") is locally correct — an unchanged record genuinely
cannot produce a refund. On the task where the right answer was *make no change at all*, it cost
0.288. Removing that one guard, policy byte-identical, halved the damage (−0.288 → −0.147, no longer
resolvable) while the paired task kept its +0.498.

The failure is not the guard's logic, it is the guard's *closure*. Refusing the no-op left the agent
with only real changes to choose from, and it chose one. So before adding a refusal, name the action
set it leaves behind, and check that "do nothing" is still reachable — a refusal that removes the
correct answer converts a pass into a fail while looking like a safety improvement.

This is also why the first ablation was worth running even though it refuted its own hypothesis:
the paragraph I suspected turned out mildly *helpful* (removing it cost the paired task 0.141), and
without that null I would have shipped the wrong fix and kept the real cause.

**Auto-repair can accelerate a wrong action — a rejected call is sometimes a brake.** When a tool
bounces a recoverable argument slip, the agent spends a turn recovering, and turns are scarce, so
repairing the slip inside the tool looks like a free win. Measured counter-example: a booking whose
payment id used an unrecognised alias and omitted the amount was rejected by the parent and repaired
by the candidate — but that booking was itself premature, made with a defaulted payment method the
customer had never been asked about, and the customer then asked for a different one, forcing a
undo-and-redo that left an extra stale row in the database. The rejection had been
holding back a wrong write.

So before shipping a repair, ask what the rejected call would have DONE had it succeeded. If it
would have written the right thing a turn later, repair it. If it would have written the wrong
thing immediately, the repair needs to be paired with the precondition that makes the call correct
— not shipped alone, and not abandoned either.

**Draw canaries from the WHOLE suite, not from the neighbourhood of your mechanisms.** This is the
mistake that sank an artifact whose individual mechanisms all measured positive. The canary set was
nine tasks picked near the targets; the artifact then damaged four high scorers that nobody was
watching — two at 1.00, one at 0.90, one at 0.80 — and the gate failed on exactly that collateral.
**A canary set that only covers what you aimed at cannot catch what you hit by accident.**

`integrate.py --canary-auto BASELINE.json` selects them mechanically: every task at or above
`--canary-floor` (default 0.90) that is not a target, lowest-rate-first so the most fragile high
scorers are the ones kept. Run against this round's own baseline it recovers three of the four
tasks that were actually damaged.

The fourth is the honest limit and worth stating: it sat at **0.80**, under the floor. Lowering the
floor catches it and admits a noisier guard — a task at 0.80 moves about ±0.13 at n=10 by chance, so
it will veto good work at random. There is no floor that is both complete and quiet. Pick it
deliberately: 0.90 for a wide sweep where false vetoes are expensive, lower when you are integrating
one mechanism and can afford to investigate every flag.

**And a per-task effect that clears 2 SE once can still be wrong.** Measured this round: a task
regression of −0.288 at n=40 (z −2.61, resolvable) read −0.80 in one full-val block and **+0.30** in
the next. A single powered reading is not the floor for a per-task claim — agreement across
separately-seeded occasions is.

**A canary needs two separately-launched readings, not 20 trials in one.** Measured: a task read
1.00 in 20/20 rollouts and then 2/5 the next day on byte-identical code at the same seeds. It had
been promoted to canary on the strength of that 20/20 — evidence which does not support the claim,
because repeats launched inside one occasion share whatever makes the task come out the way it
does. Two separate readings caught it; more trials in the first reading never would have.

The consequence cuts both ways, and both matter:

* a task that disagrees between occasions must be dropped from the canary set, **and** must not be
  used to judge a candidate either — two of twelve target tasks here moved +0.45 between
  occasions, so a per-task delta on them is uninterpretable;
* the discipline itself survives — the other eight canaries read exactly 1.00 on both occasions —
  so the fix is the selection criterion, not the idea.

Cross-occasion drift on a hosted gateway turned out NOT to be the dominant term: mean per-task
movement was 0.123 across a day at low load versus 0.100 within a day, against 0.250 at high load.
Load dominates elapsed time. Check it rather than assuming either way.

**A multi-branch artifact is assembled with `integrate.py`, never by one merge.** Stated as a rule
because the author of that script skipped it on the very round it was written: six branches were
merged in one step, and the resulting artifact gated at **−0.0146** with seven replicated per-task
losses against two replicated gains — while the same round's *single*-mechanism artifact gated at
**+0.0115**. Fewer mechanisms beat more mechanisms, and a one-shot merge cannot tell you that,
because it yields one number for N simultaneous changes.

    python integrate.py --base BEST --branches B1 B2 B3 --tasks <targets> \
        --canary-auto BASELINE.json --n 10 --conc 8 --floor <measured null>

`funcmerge` merging cleanly is **not** evidence the branches compose — every branch retained cleanly
in that failed artifact, with zero conflicts and no undefined attributes. Clean merge is a syntactic
property; composition is an empirical one.

**Gate the SUM, not each addend.** Measured here: one tool-level mechanism is worth roughly
0.04–0.13 on the one or two tasks it touches, and resolving an effect that size at 2 SE needs about
**n=100 trials on that task**. Certifying seven mechanisms that way is ~1400 rollouts to establish
by rate what a deterministic replay establishes for free. So the economical order is:

1. **Prove it engages** — replay a real failing payload against the edited tool and show the guard
   fires; replay the passing payload and show it does not. Costs zero rollouts, and it is a
   stronger statement about the mechanism than any rate.
2. **Establish incidence from rollouts you already have** — how often does the condition occur, and
   is it skewed toward failures? Also free. One guard here fired on 8 of 76 matching calls, 8 in
   failures and 0 in passes.
3. **Confirm the sign at modest n, with canaries** — you are checking for a regression and a
   direction, not measuring a size.
4. **Gate the accumulated artifact ONCE on full val**, where SE is 0.0262 at n=10 and several
   mechanisms can clear it together even though none clears it alone.

Expect the measured per-task effect to land well below the upper bound incidence implies — here
~40% of it — because the guard fires correctly and the agent then still fails for an unrelated
reason. That gap is not evidence the mechanism failed; check the task's other reward components
before concluding anything.

**A parallel optimiser's deliverable is a MECHANISM WITH TRACE PROOF, not a rate.** This follows
from the load fact above and it is the part that changes how you brief a fan-out. K optimisers each
evaluating is K processes, so a fan-out is BY CONSTRUCTION a high-load regime — the very regime in
which a per-task rate cannot resolve the effect anyone is looking for. Briefing K subagents to
"measure whether your edit helps" therefore asks them for the one thing their situation cannot
provide, and what comes back is K rate deltas drawn from a distribution whose width is larger than
the effect. Several prior rounds did exactly this and accepted edits on it.

Ask instead for evidence that does not depend on load:

| evidence | load-sensitive? | good for |
|---|---|---|
| the guard fired on the observed call | no | proving the mechanism engages |
| the agent's next action changed after it fired | no | proving the mechanism works |
| a direct call with the exact bad payload now succeeds / still refuses | no | proving repair logic, deterministically |
| the delivered docstring text contains the keys | no | proving the description reaches the model |
| count of clarification turns before the first write | barely | proving a behavioural prose change |
| per-task pass rate | **yes, heavily** | almost nothing, at fan-out load |

Then gate the surviving mechanisms yourself, serialised, on a quiet machine. The division of labour
is: **the fan-out finds falsifiable mechanisms and proves them structurally; the driver alone turns
mechanisms into numbers.** A subagent that reports "indistinguishable from noise" while showing its
guard firing correctly has done its job completely.

**The knob is TOTAL IN-FLIGHT REQUESTS, not the runner's per-process concurrency flag.** That is per-process,
so it does not bound load when several evaluations run at once — and running them at once is the
normal case, because a fan-out of K optimisers each evaluating is K processes. A gate launched at
`--conc 8` alongside four exploring optimisers at `--conc 12` puts about 56 requests in flight, so
it is a HIGH-load measurement wearing a low-load flag, and it will reproduce the wide null rather
than the narrow one. Serialise the gate: let the fan-out finish, or pause it, and run the gate arms
alone. Both arms still belong in the same batch as each other — pairing is what removes drift — but
that batch must be the only thing running. If you cannot quiet the machine, say so next to the
verdict instead of quoting a per-process number as though it were the load.

**Take the error ACROSS whole runs, not across tasks within one run.** A single paired run's SE is
computed over tasks, so it cannot see run-to-run nondeterminism at all — and on this benchmark that
is the dominant term. Repeat the entire paired comparison on distinct seed blocks and use the
spread of the per-run deltas:

| seed block | candidate | control | paired Δ |
|---|--:|--:|--:|
| 0-4 | 0.7333 | 0.6467 | +0.0867 |
| 100-104 | 0.6867 | 0.6667 | +0.0200 |
| **combined** | | | **+0.0533, SE 0.0333 across runs (t ~ 1.6) — NOT demonstrated** |

```bash
# one paired run per seed block, both arms in the SAME batch, then combine ACROSS runs
python "$A/taskeval.py" "$R/work/cand" <val ids> --n 5 --base-seed 0   --json /tmp/c0.json
python "$A/taskeval.py" "$R/work/ctl"  <val ids> --n 5 --base-seed 0   --json /tmp/k0.json
python "$A/taskeval.py" "$R/work/cand" <val ids> --n 5 --base-seed 100 --json /tmp/c1.json
python "$A/taskeval.py" "$R/work/ctl"  <val ids> --n 5 --base-seed 100 --json /tmp/k1.json
python "$A/multirep.py" /tmp/c0.json:/tmp/k0.json /tmp/c1.json:/tmp/k1.json
```

`multirep.py` refuses to return a verdict from a single paired run at all, because that is exactly
where the retracted accept came from. `--base-seed` matters: raising `--n` only extends the same
seed block, so a rerun at the same seeds is a determinism check.

The first run alone reported SE 0.0548 across tasks and an "accept". Two runs show the same
candidate at +0.0867 and +0.0200, and a byte-identical control re-run moved +0.0800 by itself. The
across-run estimator needs no assumption about where the noise comes from, which matters because on
this run its source was never identified: LLM sampling, seed assignment, concurrent batching,
timeouts, infra accounting and set-iteration order were each ruled out by direct measurement, and
the leading remaining hypothesis (transient errors below the `max_errors` threshold being fed back
into the conversation) stayed unverified.

Budget for it up front: a credible verdict on a sub-0.10 effect here is **several full paired runs**,
not one. If that is unaffordable, the honest output of the round is "not resolvable at this budget"
— which is a result, and is what the earlier single-run accept should have been.

### Running the fan-out, merging it, and remembering what it found

Each optimiser evaluates its own task at full trials **plus a canary of tasks measured 1.0 at
baseline**, in one call, and writes traces so the next edit aims at an observed decision:

```bash
python "$A/taskeval.py" "$R/work/$TAG" <its-tasks> --project "$P" --n <num_trials> \
       --canary <stable-task-ids> --canary-n 3 --conc <low> --traces /tmp/tr_$TAG.json
```

Run every eval **detached** (`nohup ... &`, then poll for the output file): under endpoint
contention a per-task eval can take 15-50 minutes, and a harness-level timeout has killed an eval
that was still healthy.

Findings go in a shared ledger, never in the coordinator's head — independent optimisers on
different tasks keep rediscovering one cause, and two of them implementing the same fix collide at
merge with only one of the two actually measured:

```bash
python "$A/mechanisms.py" list --run-dir "$R" --task "$TASK" --compact
python "$A/mechanisms.py" add --run-dir "$R" --owner "$TAG" --status proposed \
       --mechanism "<the cause, one sentence>" --evidence "<what you measured>" \
       --touches <function-the-fix-edits>
python "$A/mechanisms.py" add --run-dir "$R" --owner "$TAG" --status rejected \
       --supersedes <seq> --mechanism "<what turned out to be false>" --evidence "<the test>"
```

Assemble the result **one branch at a time**, measuring after each — never in a single merge:

```bash
python "$A/integrate.py" --base "$R/work/<parent>" --branches "$R/work/t7" "$R/work/t17" \
       --out "$R/work/cand_merged" --tasks <targets> --canary-auto "$R/<baseline-per-task>.json" \
       --n <num_trials> --conc <low> --floor <measured-null-delta>
python "$A/round.py" --run-dir "$R" --project "$P" --candidates cand_merged \
       --n-trials <num_trials> --k-se <gate_k_se>
```

`funcmerge.py` is the merge engine `integrate.py` drives per step; call it directly only to inspect
a single combination, and read its `dropped_additions` — a line a branch ADDED that the merge did
not carry is how a rejected subtraction gets silently re-applied:

```bash
python "$A/funcmerge.py" --base <parent>/<file> --out /tmp/try.py \
       --inputs <branchA>/<file> <branchB>/<file> --union-pure-insertions --json /tmp/fm.json
```

`merge_taskopt.py` remains for the whole-file case (a capability whose artifact is prose, where
per-function merging does not apply):

```bash
python "$A/merge_taskopt.py" --root "$R/work" --base "$R/work/<parent>" \
       --out "$R/work/cand_merged" --include t7 t17
```

### Measurement discipline — the contract

Full evidence, with the numbers that bought each rule: **`references/measured-lessons.md`**. The
non-negotiable core, because skipping any of these is how four consecutive rounds of this loop
produced nulls that nobody could interpret:

1. **Compute the binomial floor before blaming anything.** Each rollout is pass/fail, so an arm
   mean over `m` tasks at `n` trials has `SE = sqrt(Σ 2·p(1-p)/n) / m`. Do that arithmetic first.
   Measured: two byte-identical arms differed by 0.0778 against a predicted 0.0615 — **1.27×**,
   i.e. nothing to explain. Hunting a cause you have not shown exists is how rounds get spent.
2. **Measure the null, twice.** Two byte-identical copies of the parent, same seeds, same load.
   Their gap is the round's bar; a candidate inside it has shown nothing whatever its verdict says.
3. **Explore fast, gate slow, and gate ALONE.** The load variable is *total in-flight requests*,
   not any per-process flag — a fan-out is by construction the noisy regime. Serialise gate arms.
4. **Different questions need opposite designs.** A *mechanism* is judged only on the tasks where
   it fires, at high `n`, per task. An *artifact* is judged on the FULL task set, because tasks at
   1.00 add signal with almost no variance — full val at n=10 measured **2× more precise** than the
   hard subset at n=10.
5. **Two independently-seeded blocks, and they must agree in sign.** This is the single check that
   catches a null a one-block reading calls positive. It rejected an artifact at +0.0263 / −0.0032
   and refuted a per-task mechanism story of −0.50 that read +0.20 in the second block.
6. **Canaries from the WHOLE suite, chosen mechanically** (`integrate.py --canary-auto`), lowest
   rate first. A set picked near your mechanisms cannot catch what you hit by accident: four high
   scorers were damaged unguarded and the artifact failed on exactly that collateral.
7. **Assemble multi-branch artifacts with `integrate.py`, one branch at a time.** A clean
   `funcmerge` is a *syntactic* property; composition is an empirical one. Six individually-positive
   mechanisms gated at **−0.0146** while one alone gated at **+0.0115**.
8. **State the ceiling before you spend.** Sum `1 - rate` over val at the real trial count, subtract
   what each task's own reward components cap it at, and say whether the target is reachable. A
   target never costed against measured headroom is a wish.
9. **When effects sit below the floor, pre-register directional predictions and use a sign test.**
   9/10 positive gave **p = 0.0107** where no individual z reached 2. Write each prediction down
   *before* its arm runs, or the test is worthless.
10. **A per-task effect that clears 2 SE once can still be wrong.** A −0.288 at n=40 (z −2.61) read
    −0.80 and then **+0.30** across two full-val blocks. Agreement across occasions is the floor for
    a per-task claim, not a single powered reading.

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
reporting 0.0; a **no-holdout** spec (test overlapping train/val, as some benchmarks default to
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

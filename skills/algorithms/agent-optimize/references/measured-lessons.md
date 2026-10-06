# Measured lessons — what a number on this loop can and cannot resolve

## Contents

- [Three rules the numbers keep proving](#three-rules-the-numbers-keep-proving) — per-task rate is a
  search signal not evidence, re-measure the null before trusting a delta, and mechanism+trace beats
  rate under fan-out load. Each stated once, with every measured number that backs it.
- [Fan-out mechanics](#fan-out-mechanics) — the three phases, merge granularity, the ledger, and the
  edit-design findings (reward decomposition, docstring delivery, guard wording, turn budget) that
  came out of running this loop for real.
- [The binomial floor, and what an aggregate mean can resolve](#the-binomial-floor-and-what-an-aggregate-mean-can-resolve)
  — the SE formula against a measured null, the sign test for sub-floor effects, and why narrowing to
  the hard tasks makes an artifact measurement worse.
- [Gate the sum, not each addend](#gate-the-sum-not-each-addend) — the six-branch merge that gated
  negative, and the cost of certifying each mechanism by rate.
- [What a run reports vs. what it spent](#what-a-run-reports-vs-what-it-spent) — the cost-accounting
  holes that make a run's published spend a fraction of its real one.
- [Worked examples](#worked-examples) — WE-1: the two-seed-block cross-run estimate that forced a
  retraction.

Every rule here was paid for by a measurement on a real run, and each states the number that bought
it. They live outside SKILL.md because the loop has to stay readable: the body carries the contract,
this file carries the evidence behind it. Read it before your first gate decision on a new benchmark,
and again whenever a result surprises you. The figures come from a multi-turn tool-use benchmark with
a mid-tier agent model; the *shape* of each finding is what transfers, and where a number is likely
benchmark-specific the rule says so.

## Three rules the numbers keep proving

Three findings account for most of what follows, and every other section either produces evidence for
one of them or assumes it. State them once, here, with every number that backs each one; downstream
sections reference them by name instead of re-deriving them.

### Rule 1 — a per-task rate is a search signal, never evidence of a fix

The per-task fan-out rests on `k/n` per task being informative. Measure whether it is, by running the
*same bytes* twice and diffing per task, at several trial counts and readings:

| measurement (identical bytes, temperature 0) | value |
|---|--:|
| n=5: mean per-task \|difference\|, run 1 vs run 2 | **0.160** |
| n=5: tasks that moved at all | **19 / 30** |
| n=5: tasks that moved >= 0.40 | 3 |
| n=5: worst single-task swing | **0.60** |
| n=10: same floor | **~0.11** |
| n=10: SE of one task's rate near p=0.5 | ~0.16 |
| 3 independent byte-identical readings of one task | 0.6 / 0.9 / 0.5 |
| 4 independent byte-identical readings of another, vs. a solo reading of 0.70 | 0.5 / 0.4 / 0.4 / 0.4 |

That floor is larger than most per-task effects worth chasing, so at these trial counts the `k/n`
gradient is mostly noise and a per-task "improved / regressed" list is close to uninformative. A
"74% of the gain was retained by the merge" figure computed from one reading each side was reported
and then withdrawn once an optimiser re-measured the same bytes twice and found the giveback was
noise (the merge itself was structurally clean, verified by diff) — a single-reading per-task
comparison is a hypothesis, not a result, and this is the mechanism that makes it one.

One nuance rescues the canary discipline anyway: **the variance is concentrated in particular tasks,
not spread uniformly**. Across five byte-identical readings of one 12-task subset, two tasks read
1.00 in *every* run while three carried nearly all the movement. So a canary set drawn from
demonstrably stable tasks is trustworthy even though per-task rates in general are not — which is why
canaries must be chosen from REPEATED measurements at the real trial count, never a 3-trial screen.

The consequence is not "give up on per-task work"; it is **stop using rates as the per-task evidence
and use MECHANISM instead**. Everything from one run that survived scrutiny was established
structurally rather than by a rate delta: a crash found in live tool returns and confirmed by its
error string going 3 -> 0; a docstring section shown to reach the model 0% of the time by rendering
the schema and counting characters; a reward component shown non-gating because the tool it names was
invoked in 0 of 300 rollouts while the task still scored 0.8. Every finding that rested on a rate
difference at n=5 or n=10 was later retracted or downgraded.

So the per-task loop's real output is a *diagnosis you can verify without the metric* — a wrong
argument visible in a trace, a tool that raised, text that never arrived. Use the rate only to decide
whether to keep looking, never as the proof. And when you do want a per-task delta rather than a
diagnosis, pool runs — report `k/N` across every run of those bytes, not the last one — and treat any
single-reading comparison as a hypothesis until it is pooled.

### Rule 2 — re-measure the null ITSELF before trusting any delta

A single null-edit control tells you the noise floor only if that control is itself stable, and on
this benchmark it is not. Three full-val readings at n=5, all on **identical seeds** with temperature
0:

| arm | reading |
|---|--:|
| control, run 1 | 0.6467 |
| control, run 2 (**byte-identical, same seeds**) | 0.7267 |
| candidate | 0.7333 |

The two control runs are **+0.0800 apart, and that null "passes" a k_se=1.0 gate** (bar 0.0379). The
candidate reads +0.0867 against run 1 and **+0.0067** against run 2 — the verdict is decided by which
control reading you happened to take. Anything measured at that trial count and below ~0.08 is
unresolvable, which on this run included every panel comparison and the headline candidate.

Note what this is NOT: seeds were identical across all three runs and temperature is 0, and single
model calls are perfectly deterministic (six identical completions by hash). The variance enters
through the multi-turn conversation, so a determinism check cannot substitute for it, and neither can
more trials in the same block — you have to run the whole arm again. The cheap discipline that
follows: **evaluate the control twice before you believe any candidate**, and set the bar from the
null's own spread rather than from a formula. A gate whose bar is smaller than the null's re-run delta
is not a gate.

A per-task *regression list* built at this trial count is not exempt: in one gate the byte-identical
control reported **four** regressed tasks and the candidate reported **four** — identical counts,
disjoint sets, and one of the two artifacts provably unchanged. That is the whole case for
`--veto-regressions` being off by default: with the veto on, a copy of the parent would have been
rejected for the same reason as the candidate. The old veto fired on a byte-identical copy of the seed
**42.8%** of the time at 5 trials, and in one run it vetoed *both* candidates that had passed the
significance test. Read `regressions` as a pointer to look at, never as a verdict, and always next to
the control's own list.

Even one paired run of the control against itself is not enough to settle a sub-0.10 effect — that
needs the error taken **across whole runs**, not across tasks within one run, because a single run's
SE cannot see run-to-run nondeterminism at all. See **Worked Example WE-1** for the full two-seed-block
calculation and `multirep.py`, the script that runs and combines it; budget for several full paired
runs when the effect is this small, and if that is unaffordable the honest output of the round is
"not resolvable at this budget."

**"Not resolvable" is a decision you can book, and booking it as a reject costs the run.** `round.py`
marks a candidate `verdict: inconclusive` when `verdict_stable: false` — its verdict changed depending
on which byte-identical control replicate happened to be the reference. Measured on a smoke run:
cand_2 at Δ +0.0433 against a threshold of 0.0492, `verdict_by_reference:
{ctl_null_i1: reject, ctl_null_i1r1: accept}`. Book it with `commit.py --decision inconclusive`, not
`reject`: a reject advances the stall counter (and stall ends the run at the tier cap, here 3) for a
reason that never happened, and it files the edit in `rejected.jsonl`, which later rounds read as
*tried, did not work* — teaching you to avoid your own untested idea. `inconclusive` charges
`iterations` (the budget really was spent), skips both files, and logs `step_indecisive`. The
`JOURNAL.md` RESULT line follows the same rule: an unresolved round is stamped `UNRESOLVED (not
judged)`, because the correct next move is to **re-measure**, not to redesign.

**To re-measure, use a FRESH tag.** Rollouts are written `<task>__<tag>__t{k}.json` for `k in
range(n_trials)`, so re-running a tag **replaces** `t0..t9` rather than adding `t10..t19` — it swaps
one reading for another and buys no evidence. Told to "re-run with more trials," one run re-measured
its own control under the same tag, spent 100 metric calls, replaced a 0.4967 replicate with a 0.5067
one, and *widened* the round's replicate spread. `harness` now logs a `rollout_overwrite_warning`
naming the destroyed reading. The same bug hit a re-gate's own control tags: `round.py` gave its
*table* a `.r<k>` suffix on a same-iteration re-run but reused the control *rollouts'* original tags,
so the one operation meant to add evidence deleted the measurements it was comparing against —
`ctl_null_i1` moved 0.4967 → 0.5067 and `ctl_null_i1r1` moved 0.4800 → 0.4367, the replicate spread
went 0.0167 → 0.0700 (the bar grew 4.2x), and `round_i1.json` was left quoting an `evidence_bar`
computed from numbers that no longer existed on disk. Control tags are now `ctl_null_i<N>a<k>` from
the second attempt on, and a re-gate is accumulative: `prior_attempt_controls` pools every replicate
the round has paid for into `null_delta_between_control_replicates`.

**An UNCHANGED parent's noise floor is measured once, not once per round.** Across six real runs the
mandatory two null-control replicates consumed roughly **40% of every rollout spent** — nearly as much
as all candidates combined — and most of that bought nothing once `best_id` stopped moving: the
control is the same bytes the previous round already measured. `round.py` now reuses those replicates
(`control_reuse` in the table) whenever `best_id` is unchanged, the measurement context matches (split,
trials, concurrency), and the rollouts are still on disk; an accept, `--gate-against control`, or a
re-gate all still pay for a fresh measurement. Pass `--no-reuse-control` to force one anyway.

`evidence_bar` (the noise floor to compare a delta against) is necessary but not sufficient:
`gate_threshold` (k·SE on the paired per-task differences) is what each `verdict` is actually computed
from, and it is usually stricter — one candidate cleared 0.0167 against an evidence bar and still
missed a 0.0492 gate_threshold. And a reject is not always a regression: the stamp that used to read
unconditionally *"re-introduce only the edits that did NOT break a task, dropping the ones that did"*
now branches on whether the reject actually carried any per-task regressions, since a reject with
none (fixed two tasks, broke none, lost to threshold on a +0.047 effect) was being told to redesign
edits that had just measured as helping.

### Rule 3 — at fan-out load, a per-task rate cannot resolve an effect; get mechanism+trace proof instead

K optimisers each evaluating is K processes, so a fan-out is BY CONSTRUCTION a high-load regime — the
very regime in which a per-task rate is least trustworthy. Measure it directly: the same bytes and
seeds, run twice at search concurrency and twice again at a low one.

| identical bytes and seeds, 12 tasks | conc 25 | conc 8 |
|---|--:|--:|
| arm-level \|delta\| between the two runs | **0.1167** | **0.0333** |
| mean \|per-task\| movement | **0.250** | **0.100** |
| tasks that moved at all | 10 / 12 | 5 / 12 |

Five of the twelve tasks became perfectly repeatable at conc 8 having each moved 0.20-0.40 at conc 25.
Two caveats when quoting this: the low-concurrency runs were sequential, so load and elapsed-time
drift are confounded, and 12 tasks x 2 runs makes the variance comparison thin — the direction was
consistent across all three metrics, which is why it is worth acting on, but it is not settled.

Concurrency composes only up to the endpoint's sustainable rate, and past it the failure is silent.
Measured: nine per-task optimisers at concurrency 8 put ~72 requests in flight against a proxy whose
sustainable band is 24-90, and a single per-task eval went from ~4 minutes to ~50 — nothing errored,
latency just grew, so it read as "the model got slower" rather than "I oversubscribed." An earlier
incident on the same proxy is the extreme version: concurrency 300 pushed 292 of 300 rollouts into
wallclock timeouts and the evaluation reported **0.0067** as capability. The knob is TOTAL IN-FLIGHT
REQUESTS, not the runner's per-process concurrency flag — that flag is per-process, so a gate launched
at `--conc 8` alongside four exploring optimisers at `--conc 12` puts ~56 requests in flight, a
HIGH-load measurement wearing a low-load flag. Serialise the gate: let the fan-out finish or pause it,
and run the gate arms alone, still paired in the same batch as each other.

So the practical split is: **search fast, gate slow.** Per-task exploration can run high concurrency,
because its output is a mechanism you verify from a trace, not a rate; the accept decision must run at
a concurrency where the null actually reproduces, which costs roughly 3x wall clock for the one
evaluation that matters. `per-task-fanout.md`'s evidence table lists exactly which kinds of proof stay
load-insensitive (a guard firing, a delivered docstring, a direct replay) and which do not (per-task
pass rate, "yes, heavily").

## Fan-out mechanics

**The three phases.**

1. **Fan out one optimiser per defect.** One subagent per `DEFECT` task; one per `UNSTABLE`
   *cluster* (unstable tasks share a mechanism more often than broken ones do). Each gets its own
   `cp -r` of the current best and edits only inside it.

2. **Merge.** `merge_taskopt.py` (git 3-way, one branch per optimiser). **Declare a rebased
   optimiser's parent** — `--include u67b t21 t17b:u67b` — or its diff re-applies everything the
   parent already did and collides with the parent's own branch. And **classify every conflict
   before resolving it**: a **semantic conflict** (two optimisers arbitrate the same decision
   differently) means **drop one bundle** on whichever side lacks a measurement — a union there ships
   contradictory instructions nobody measured (observed once: a bundle measuring 0.50 against its own
   0.60 baseline was excluded on its own author's recommendation). A **textual collision of distinct
   additions** (two new functions or dict keys landing on adjacent lines) means the union IS what both
   optimisers measured — resolve with `--union-on-conflict`, which names the union-resolved files so
   the claim stays checkable, then **render the live toolset** to catch what an import check won't
   (duplicate definitions, broken registration): one five-branch union gave 596 added lines, 14 tools
   registering, no duplicated methods, checked not assumed. The union is still a shape nobody measured
   in isolation, so the gate decides it — union to avoid losing gains, gate to find out whether you did.

   **The conflict may be an artifact of merging whole files.** Ten independently-verified branches in
   one round produced a whole-file merge that kept **four** of them; the "conflicts" were not
   disagreements — every optimiser had added one state field to the same `__init__` and one
   independent guard call to the same tool method, landing on adjacent lines of a shared insertion
   point. Line-level 3-way merge cannot tell *two people appended different things here* from *two
   people rewrote the same thing*, and diff3 conflicts on both; forcing it through with
   `--union-on-conflict` produced a file that **did not parse**, with five duplicated `def`s.

   So merge per FUNCTION, not per file — `funcmerge.py`, same git 3-way merge at a granularity where
   independent additions never interact, raising retention from 4/10 to the full set via three
   escalating, self-reporting steps: **pure insertions** (`--union-pure-insertions`, provably safe
   when no branch rewrites a base line — covers the shared `__init__` case); **priority trunk +
   insertions** (when branches *did* rewrite one function, pick the trunk by which branch changed
   that function MOST, not by whose task holds the most headroom — a branch owning a full
   task-equivalent had added exactly ONE line to the contested function, so ranking by headroom
   discarded the branch that had actually rewritten the return value; *what a function is worth is
   not what its author's task is worth*); and **forced trunk** (`--force-priority`, a last resort that
   drops losing branches' *rewrites* but keeps their *insertions* — dropping a whole branch because
   someone else rewrote the function is how a merge silently loses a measured fix, here it would have
   discarded task 42's guard call over a disagreement about a money string).

   **Audit what the merge failed to carry, against the ledger's rejected entries.** A forced-trunk
   resolution can silently RE-APPLY a subtraction a branch had already measured and reverted:
   observed live, one branch had added a sentence to a `payment_id` argument description and had
   separately logged, twice, that removing it was harmful; the merge dropped that branch's rewrite and
   re-performed exactly that subtraction, and nothing conflicted so nothing was reported. Trace
   evidence bore it out — of the correctly-written-but-still-0-scored rollouts on that task, four of
   seven charged a credit card when the customer had asked to pay by gift card, precisely the defect
   the deleted sentence addressed.

   **A merge that carries a function but not a CONSTANT it needs produces a crash that looks like a
   policy failure.** The most expensive single defect this run produced: `_check_bags_before_cabin_change`
   read `self.CABIN_LADDER` at four sites, and the merge carried the helper and its call site but left
   the class attribute behind. The live tool return, `Error: '<ToolsClass>' object has no attribute
   'SOME_CONSTANT'`, gets turned into a string by the tool layer, the agent abandons the write, and the
   reward records a **missing write** indistinguishable from the agent choosing not to act — it
   silently contaminated four measurements across two candidates and two ablations, found by a
   per-task optimiser reading a live trace, not by any aggregate. `funcmerge.py` now **refuses to
   write** a result in which any constant-shaped attribute read off `self` is undefined, collecting
   `ast.AnnAssign` as well as `ast.Assign` (six valid annotated fields were false positives without it)
   and hard-failing only on UPPER_CASE names (an inherited method reached through `self` isn't
   resolvable from one file, so refusing those would reject valid merges) — a hard check with false
   positives is worse than no check.

   `funcmerge.py` also reports `dropped_additions` — every non-trivial line a branch added that the
   result doesn't contain, advisory since some drops are deliberate but must be read before gating: run
   cold on seven branches it flagged lost work from **six of them**. Two things this exposed that no
   rate would have: a guard **helper** can survive a merge while its **call site** does not, so verify
   the call (`grep -c '_check_foo(record)'`), never the definition; and a ledger `touches` field can
   name a function no branch ever defined — the merged artifact must be checked against the code, not
   the ledger's own description of itself.

3. **Gate the merge once, on full val, against `ctl_null`.** Nothing from phase 1 or 2 is believed
   until this (Rule 2). Per-task fan-out changes where the search spends its rollouts; it does not
   change what counts as evidence.

   **A per-task gain is verified against ONE base and is not transitive to another.** The sharpest
   limit on the whole idea, so measure it rather than assume it. Seed-matched: adding an
   independently-verified task-14 edit to an artifact already carrying three other optimisers' work
   measured **-0.0617** overall, and **task 14 itself fell** 0.40 -> 0.20 despite the same edits having
   measured 0.50 -> 0.70 on the base they were developed against; two other tasks fell 0.80 -> 0.00 and
   0.80 -> 0.20. "Verified on my task, canaries intact" is necessary, not shippable — the only reliable
   check on which subset survives together is a seed-matched paired comparison of the composed artifact
   against the artifact without the addition. Budget for that; skipping it is how nine confirmed wins
   become a candidate that loses.

   **Select the merge on a headroom panel before you gate it.** A full-val gate answers one bit for 300
   rollouts, about a *sum*: one merged artifact scored +0.0126 and was rejected — correctly — while
   containing both real gains (task 40 `0.10->1.00`, task 21 `0.20->0.80`, +2.1 task-equivalents gross)
   and real losses (task 10 `0.80->0.10`, task 9 `0.80->0.40`, -1.6) the gate could not see; keeping only
   the gaining half would have measured ~0.78. Evaluate merge variants on the tasks below 1.0 — cheaper
   and more informative per rollout than full val for *selection*, though not a substitute for the gate
   that protects tasks already at 1.0 — and compute headroom (`sum(1-rate)` at the real trial count)
   before choosing a target: one run held 8.70 task-equivalents over 30 tasks, so 0.90 needed 5.7 of them
   (65% of everything left, 5.4 in six tasks). A target nobody has costed against measured headroom is a
   wish.

   **Regression attribution is free once rollouts are on disk.** Diff the stored failure feedback of the
   two arms per task before spending anything to explain a drop. In one run, regressed tasks had
   *identical* feedback strings in both arms at different frequencies — a tendency shift, not a bug,
   invisible from the means. The same pass rules out infrastructure for free: 5 of 2040 val rollouts
   (0.25%) died for infrastructure reasons and scored 0.0, concentrated on one task — measured small
   rather than assumed small.

**Each optimiser's loop** — target task at full `n_trials`, plus a canary of tasks measured **1.0** at
baseline, in the same call; after the fan-out, combine and gate the merge like any other candidate.
`per-task-fanout.md` has the exact `taskeval.py` / `merge_taskopt.py` / `round.py` commands and the
detached-run rationale (a per-task eval can take 15-50 minutes under contention, and a harness timeout
has killed one that was still healthy). Read the traces file — the agent's own tool calls, per failing
trial — and aim the next edit at an observed decision; for an UNSTABLE task, diff a failing trial
against a passing one, since the divergence point is the ambiguity and removing it beats adding a rule.

**The four things that keep the phase honest.** Skip any one and it manufactures a number:

- **A per-task rate is a training number by construction** (Rule 1) — quote it as a search signal,
  never a result.
- **No task-specific literals — and ENFORCE it with a script, not a promise.** No record identifiers,
  contact/PII fields, or other trace-specific literals from the specific rollout you're reading may
  appear in a line the edit ADDS (*e.g., in one such trace: a payment id, a confirmation code, an
  item number, a person's name, a date, a user id, or a location pair*). A ~40-line auditor diffing each
  candidate against the base and grepping the ADDED lines for your domain's id shapes makes `clean` a
  merge precondition, independent of the rate. Diff **added lines only** (a whole-file grep floods on
  the seed's own reference tables) and **skip literals the base already contains** (a reindented
  pristine docstring showed up as an addition and made three clean candidates look guilty until that
  filter went in). It caught one real case: a docstring enumerating that trace's own cities by name,
  dressed as a general rule — the underlying idea (match by city, not airport code) was fine; the
  enumeration is what made it memorisation.
- **Diagnose from behaviour, never from the target — but the COORDINATOR may audit the spec.** The
  task's `target`/`evaluation_criteria` belong to the grader; an optimiser's whole permitted input is
  the feedback string and the agent's own trace. The coordinator has one narrow extra,
  measurement-integrity permission: read the spec to answer "is this task winnable, and is the
  optimiser chasing the right criterion?", then relay only what the agent could already observe. This
  unblocked two dead tasks: one optimiser had called a check unsatisfiable when the real bug was the
  agent's own arithmetic, so the relay was *"your arithmetic or scope is wrong"* (no value echoed); a
  second had plateaued on a same-date-duplicate detector when the true criterion was the itinerary the
  customer stated in her own message, so the relay was *"cancel what conflicts with the trips she
  stated."* Relay a criterion the agent can evaluate from the conversation, never a value or an id — if
  the only way to state the fix is to name the answer, the task isn't winnable, and that's the finding.
- **A guard must fire on a DECISION, not on a tool.** A precondition refusing every call of a write
  tool derails tasks it was never aimed at — one such guard dropped a canary from 1.0 to 0.333 and its
  eval's wall time from 299s to 1493s (every extra refusal costs a turn). Key the guard to the specific
  contested situation, firing once per situation — re-keying one from per-user to per-contested-date was
  worth 0.0 -> 0.333 alone — and keep the refusal directive: softening "otherwise proceed" flipped
  over-writing into under-writing and gave the whole gain back.

**Measure the canary at the SAME `n` as the target, and never set the bar at 1.0.** A task reading 1.0
off a 3-trial baseline has a CI wide enough to hold 0.4. Measured cost of getting this wrong twice: one
canary read 1.0 at 3 trials and 0.67 at 10; a second read 1.0 at 3 trials and then 0.667/0.333/0.0/0.333
/0.333 across five independent 10-trial runs — `canary_mean == 1.0` was unreachable for reasons no
candidate caused. The bar is no canary below its own measured band, from the same `n` you judge at; the
same applies to the target — one "0.0 DEFECT" task measured 0.444 at n=10.

**Findings go in the ledger, not in the coordinator's head.** Independent optimisers keep rediscovering
one cause — four of nine independently found writes lost to turn starvation, and two independently
implemented the same tool enrichment, colliding at merge with only one actually measured. Every
optimiser lists before it diagnoses and appends when it finds (`mechanisms.py list`/`add`, commands in
`per-task-fanout.md`). **Filter the ledger per optimiser, never filter out the task-independent rows**:
one ledger hit 99 findings / 65 KB, and `--task N --compact` cuts it to 24 KB while keeping every row
about task N plus every row with no task attached — the cross-cutting facts (canary bands, variance
warnings) that apply to everyone. **Retire a wrong finding with `--supersedes <seq>`** rather than just
contradicting it with a newer row: three `verified` rows were disproved on one run and, without
supersession, a reader saw both the claim and its refutation with no way to tell which won. **A
disproved claim left in `verified` is worse than no ledger at all.** `--touches` is the collision key
and `--status` the point: `verified` means reuse it (rebase onto that copy), `proposed` means its owner
is already on it, `rejected` means a retry must be structurally different.

### Other findings from running this loop

**Decompose the reward before you fan out.** A composite metric (DB check + action check + communicate
check -> one *binary* task reward) scores a task that wrote the database right and only missed a
confirmation as 0.0, identical to a task that did nothing. `taskeval.py`'s `component_rates` turns
that one useless number into one per failure mode — in one run it showed all 14 failing tasks missing
the DB-state component and only 4 also missing COMMUNICATE, killing a plausible communicate-first plan
before a rollout was spent. Then tell each optimiser which components its own task even has: 25 of 30
val tasks have no communicate check, so on those nothing the agent *says* can move the score.

**Check which reward components actually GATE before reading the feedback as a to-do list.** A grader
that reports several component scores may not use all of them. One benchmark's `reward_basis` was
`["DB", "COMMUNICATE"]` — `ACTION` absent — yet the feedback led with "Action-level defects": task 12's
feedback named `calculate: was never called` on every failing rollout, `calculate` was invoked in **0
of 300** rollouts, and the task still scored 0.8. Label non-gating detail as diagnostic.

**Measure what the model actually RECEIVES before you write another word of it.** A tool docstring is
not delivered whole: one harness builds the schema `description` from the summary plus the prose
before `Args:` and drops `Returns:` entirely. Measured over a 14-tool set: **5469 of 12929 docstring
characters (42%) never reach the model** (94% on one tool). One "verified" mechanism worked only
because the **return VALUE** changed shape at call time — not because anything documented it.

| surface | reaches the model | use it for |
|---|---|---|
| docstring summary + prose before `Args:` | **yes**, in the tool schema | preconditions, scope, what not to do |
| `Args:` per-parameter descriptions | **yes** | argument-level constraints |
| the returned VALUE (a `next_step` key) | **yes**, at call time | what to do next, with its constraints |
| `Returns:` docstring section | **no — silently dropped** | human readers only |

Verify per candidate by rendering the toolset and summing delivered characters. Two hazards moving text
into the delivered region: a lifted line must not begin a recognised section (`Example:`, `Returns:`)
— a stray header can raise at REGISTRATION time and kill every rollout as `INFRASTRUCTURE_ERROR` — and
it must land *before* `Args:`, or it falls back into the dropped region.

**Ablate a read+enforce pair TOGETHER, or you will throw away the half that carries it.** The
strongest per-task result of one round was a two-part edit: a tool return printing the candidate
values, plus a write-side refusal ordering the agent to re-read them. Alone, the read moved
0.400 -> 0.500 (inside noise, looked worthless); removing it while keeping the refusal collapsed the
task from **0.625 to 0.200**. The same content as passive fields with no refusal was worth nothing too
— enforcement without the read is a dead end, the read without enforcement is decoration.

**A tool return that advertises a path must state that path's constraints in the same breath.** A
price table showing what one option would cost pulled the agent toward it, which then failed on that
option's payment rules three turns too late to pivot — cost 0.28. The same table with the rules printed
beside it recovered that and carried another task to 0.90.

**A numeric fix must not be phrased as an instruction to address the customer.** Telling the agent to
quote a figure after every write pushed the communicate component to 1.0 while the database component
collapsed (0.50 -> 0.11, a reliable canary to 0.667): "report this to the customer" fires *mid-flow*,
so a cancel-then-rebook spent the turn announcing a refund and never booked. Fix the value, not the
audience.

**Forcing a decision to be STATED is not forcing it to be CARRIED OUT.** A guard refusing a write until
the agent named which competing item it kept measured 0.2 -> 0.1: the blind retry disappeared, but the
agent treated *having named* a keep as resolving the situation and never issued the second write. If
the defect is a missing action, the guard must be satisfiable only by that action.

**"No nuance clauses" applies to refusal text too.** Two *correct* discrimination clauses added to a
working refusal took the same task 0.2 -> 0.1, all ten trials failing — the longer refusal traded
follow-through for precision.

**A traces file holding only FAILING trials is evidence about the passes.** If an action is absent from
every failing trial and the task sometimes passes, that action is what the passes are doing — a free
inference from an artifact you already have.

**A precondition can be misread as a platform limitation — say what it is.** A refusal the agent
apologised for ("the system won't let us do that") stopped reading that way once rewritten as *this is
not a limitation, here is the corrected value, retry now* — score-neutral, worth keeping anyway.

**A retryable refusal is safe when the retry leads to the CORRECT action, and poison when it's a free
choice among options.** A one-shot refusal naming *the* fix ("upgrade first, then add bags") took a task
0.60 -> 0.70. The same shape applied to a choice — refuse, list the valid ids, let the agent pick —
measured **0.70 -> 0.10**: the agent re-sent the same wrong id, treating the retry as a formality
because the refusal's own list read as permission. A menu turns a mistake into a sanctioned choice.

**In a turn-budgeted rollout, a fix that costs a turn can cost more than the bug.** Telling the agent to
*ask* for a missing piece of information measured 0.5 -> 0.3, scoped to one call site, because the user
simulator ends the conversation a few messages in — the question trades a write for an answer never
used. Count the turns a fix costs against the turns the failure costs; prefer a tool-return form. Two
corollaries: placing the same directive at four call sites read as self-contradictory (0.5 -> 0.3), and
telling the agent to defer eligibility reasoning to the tools was the single worst edit of the run
(0.5 -> 0.0, canary 1.0 -> 0.667) — the agent started attempting actions policy forbids.

**Elimination evidence is only as good as the classifier feeding it — verify by PRINTING, not by
measuring.** An elimination over 30 scored trials concluded a task was unwinnable without hardcoding;
the real bug was one inverted line in the helper matching items to the customer's stated requirement,
visible in five seconds by printing its output next to the raw data — instead it cost three eval
rounds. Print a derived label beside its input before spending rollouts on any hypothesis built from it.

**Find a task's own ceiling, then stop.** Two optimisers spent 13 rounds on one task without moving it
off 0.0. Its ceiling was structural: the user simulator ends the conversation a few messages in, and
3-4 of 10 rollouts died right after a *mandatory* question the opening message hadn't answered — with a
binary reward needing both components, ~0.6 was the ceiling whatever the edit. Say the ceiling out
loud, subtract it from headroom, and move the budget to a task that can move.

## The binomial floor, and what an aggregate mean can resolve

**First compute the BINOMIAL floor. Most of what looks like mysterious nondeterminism is n.** Each
rollout is pass/fail, so a task's rate is a binomial proportion and an arm mean over `m` tasks at `n`
trials has

    SE(arm difference) = sqrt( sum_over_tasks 2·p(1-p)/n ) / m

Do that arithmetic BEFORE blaming the provider, the seeds, or the load. Measured on 10 tasks at n=10
with p≈0.35: predicted SE **0.0615**, observed gap between two byte-identical arms **0.0778** — a
ratio of **1.27**, i.e. plain sampling. Mean per-task movement was 0.0978 against a binomial prediction
of 0.1445, so the observed movement was *smaller* than chance requires.

One precision about what this is and is not. At temperature 0 with identical seeds a fully
deterministic system would return *identical* arms, so this is not sampling error in the textbook
sense — there is no sample being drawn. What the arithmetic shows is that the observed variation is
statistically indistinguishable in magnitude from independent per-rollout coin flips, so no further
mechanism needs to be posited to explain it, and the remedy is the same one that works for binomial
noise: more trials. Do not report it as "sampling noise" without that caveat.

That reframes Rule 3's load result rather than cancelling it: at conc 25 per-task movement was 0.250,
genuinely **above** the 0.1445 floor, and dropping to conc 8 removed that excess and exposed the floor
underneath. Lowering concurrency fixes what it can; the rest is n. The consequence is uncomfortable:
**an aggregate mean over a dozen HARD tasks at n=10 cannot resolve any realistic edit** — reaching 2 SE
on a +0.05 effect there needs ~60 trials per task.

But narrowing to the hard tasks makes the measurement *worse*, not better, for judging an artifact —
because a task sitting at 1.00 contributes signal to the mean with almost no variance, so dropping it
removes a free denominator:

| arm | rollouts/arm | SE of paired difference |
|---|--:|--:|
| 12 hard tasks, n=10 | 120 | **0.0496** |
| full val 30 tasks, n=10 | 300 | **0.0262** |
| full val 30 tasks, n=20 | 600 | 0.0185 |

Full val at n=10 is nearly twice as precise as the hard subset, and four prior gate rounds run at full
val n=5 (SE 0.0371) had a concurrency problem, not a task-set one — they chased effects smaller than
the sum, on top of that excess noise. So the two questions need opposite designs:

| you want to know | measure | why |
|---|---|---|
| does this mechanism work | ONLY the tasks where it fires, at high n, per-task test | a mechanism firing on 2 tasks is diluted to nothing in a 30-task mean |
| does it break anything | canaries, cheap precisely because they sit at 1.00 | zero variance means a single drop is real |
| what is the artifact worth | FULL val, both arms in one batch | the 1.00 tasks are free precision for the mean |

A mechanism that fires on two tasks and lifts them 0.15 -> 0.45 is resolvable at n=40 on those two
tasks (≈3 SE) and invisible in a 12-task mean at n=10 (≈0.5 SE). Same edit, same rollout budget: one
design answers the question and the other cannot.

**When an effect sits below the floor, pre-register directional predictions and use a SIGN TEST.** The
floor bounds what a *mean* can resolve; it does not bound what a *pattern of directions* can. Write
down, before its arm runs, which way each prediction should go, then count. Measured: **9 of 10
predictions positive gave p = 0.0107** on a set where no individual z reached 2 — the effect was real
and every per-arm reading was individually inconclusive. Two conditions make it a test rather than a
story: the predictions are recorded *before* the arms run, and they are directions, not magnitudes. A
post-hoc count of which way things happened to go is worthless.

**A screening band is not a baseline (Rule 2, applied to screens specifically).** Per-task rates from a
small trial count tell you where to *look*; they do not tell you where you *are*. In one run, ten tasks
whose 3-trial bands summed to 2.33 measured **4.04** at n=10 — the screen understated the artifact by
1.71 task-equivalents (0.057 of val), and one task went the other way (0.33 -> 0.10). Every "0.0
DEFECT" label was suspect: three of them measured 0.30, 0.444 and 0.60. So screen at low `n`, but
re-measure at the gate's `n` before you quote a number, compute headroom, or tell an optimiser what its
starting point is.

## Gate the sum, not each addend

**A multi-branch artifact is assembled with `integrate.py`, never by one merge.** Stated as a rule
because the author of that script skipped it on the very round it was written: six branches were
merged in one step, and the resulting artifact gated at **−0.0146** with seven replicated per-task
losses against two replicated gains — while the same round's *single*-mechanism artifact gated at
**+0.0115**. Fewer mechanisms beat more mechanisms, and a one-shot merge cannot tell you that, because
it yields one number for N simultaneous changes. `funcmerge` merging cleanly is **not** evidence the
branches compose — every branch retained cleanly in that failed artifact, with zero conflicts and no
undefined attributes. Clean merge is a syntactic property; composition is an empirical one.

**Gate the SUM, not each addend.** Measured: one tool-level mechanism is worth roughly 0.04–0.13 on
the one or two tasks it touches, and resolving an effect that size at 2 SE needs about **n=100 trials
on that task**. Certifying seven mechanisms that way is ~1400 rollouts to establish by rate what a
deterministic replay establishes for free. So the economical order is:

1. **Prove it engages** — replay a real failing payload against the edited tool and show the guard
   fires; replay the passing payload and show it does not. Costs zero rollouts.
2. **Establish incidence from rollouts you already have** — how often does the condition occur, and is
   it skewed toward failures? Also free. One guard fired on 8 of 76 matching calls, 8 in failures and
   0 in passes.
3. **Confirm the sign at modest n, with canaries** — checking for a regression and a direction, not
   measuring a size.
4. **Gate the accumulated artifact ONCE on full val**, where SE was 0.0262 at n=10 and several
   mechanisms can clear it together even though none clears it alone.

Expect the measured per-task effect to land well below the upper bound incidence implies — there ~40%
of it — because the guard fires correctly and the agent then still fails for an unrelated reason. That
gap is not evidence the mechanism failed; check the task's other reward components before concluding
anything.

## What a run reports vs. what it spent

**A run published a quarter of what it spent, and the two causes pulled in opposite directions.** The
benchmark record's cost sums per-phase rows (baseline, each committed round, finalize), so metered
spend no phase owned was published as if it never happened: run 33046360451 went out as
`optimizer_usd: 0` / `eval_usd: 5.25` while its own state held `optimizer_usd 9.11` / `usd 12.55` — a
$21.66 run reported as $5.25, in the figure a full tier's budget gets projected from. Two holes fed
it: agent mode meters the optimizer once for the whole loop, so no round owns a share of it, and
control replicates / re-gates / abandoned rounds are real rollouts no committed step references. Both
are fixed by giving the residual its own row rather than inventing a per-round split. The opposite
error was live at the same time and worse: the host booked its metered process total *on top of* any
`commit.py --optimizer-usd` the agent had already booked for the same money, so a compliant agent made
the run report up to twice its optimizer spend, and a cost-based `stop_condition` could end a run that
still had budget. The host now books only the residual, bracketed to its own invocation, and books the
loop's wall time, which nothing recorded at all (`optimizer_seconds: 0.0` for a run that took hours).

## Worked examples

### WE-1 — take the error across whole runs (the retracted accept)

A single paired run's SE is computed over tasks, so it cannot see run-to-run nondeterminism at all —
and on the benchmark behind Rule 2 that was the dominant term. The fix: repeat the entire paired
comparison on distinct seed blocks and use the spread of the per-run deltas as the error.

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

`multirep.py`'s own docstring carries the mechanism and the motivating number (the byte-identical
control's 0.6467 -> 0.7267 re-run) — read it there rather than duplicating it here; this worked example
adds only the second seed block and the combined, still-inconclusive verdict the docstring's single
block cannot show. `multirep.py` refuses a verdict from one paired run at all, because that is exactly
where the retracted accept came from; `--base-seed` matters, since raising `--n` only extends the same
seed block, and a rerun at the same seeds is a determinism check, not a second run.

The first run alone reported SE 0.0548 across tasks and an "accept." Two runs show the same candidate
at +0.0867 and +0.0200, and a byte-identical control re-run moved +0.0800 by itself. The across-run
estimator needs no assumption about where the noise comes from, which matters because on that run its
source was never identified — LLM sampling, seed assignment, concurrent batching, timeouts, infra
accounting and set-iteration order were each ruled out by direct measurement, and the leading remaining
hypothesis (transient sub-threshold errors fed back into the conversation) stayed unverified. Budget for
it up front: a credible verdict on a sub-0.10 effect there is **several full paired runs**, not one.

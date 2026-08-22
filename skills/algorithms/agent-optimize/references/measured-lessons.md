# Measured lessons — what a number on this loop can and cannot resolve

## Contents

- [Measurement discipline — what a number here can and cannot resolve](#measurement-discipline--what-a-number-here-can-and-cannot-resolve)
  — per-task gradient noise, re-running the null, what the gate can resolve, the ceiling, the three
  phases of a fan-out, merge granularity and what a merge silently drops, and the four things that
  keep the phase honest.
- [The binomial floor, and what an aggregate mean can resolve](#the-binomial-floor-and-what-an-aggregate-mean-can-resolve)
  — the SE formula against a measured null, why temperature 0 does not make it "sampling error", and
  why narrowing to the hard tasks makes an artifact measurement worse.
- [Load is the other half of the noise](#load-is-the-other-half-of-the-noise) — the concurrency
  tables, the oversubscription incidents, and why total in-flight requests is the knob.
- [Gate the sum, not each addend](#gate-the-sum-not-each-addend) — the six-branch merge that gated
  negative, and the cost of certifying each mechanism by rate.
- [Take the error ACROSS whole runs](#take-the-error-across-whole-runs) — the two-seed-block table
  and the accept that had to be retracted.

Every rule here was paid for by a measurement on a real run, and each states the number that bought
it. They live outside SKILL.md because the loop has to stay readable: the body carries the contract,
this file carries the evidence behind it. Read it before your first gate decision on a new benchmark,
and again whenever a result surprises you. The figures come from a multi-turn tool-use benchmark with
a mid-tier agent model; the *shape* of each finding is what transfers, and where a number is likely
benchmark-specific the rule says so.

## Measurement discipline — what a number here can and cannot resolve

Everything below is about the instrument, not the edits. It is placed inside the fan-out section
because that is where it was learned, but it applies to every round: on this benchmark the
measurement floor turned out to be larger than most of the effects being chased, and four separate
conclusions in one round had to be retracted for ignoring it.

**Measure your per-task gradient's own noise before you trust it as a gradient.** The per-task
fan-out rests on `k/n` per task being informative. Measure whether it is, by running the *same
bytes* twice and diffing per task. Here, at n=5 on identical seeds with temperature 0:

| identical bytes, run 1 vs run 2 | value |
|---|--:|
| mean per-task \|difference\| | **0.160** |
| tasks that moved at all | **19 / 30** |
| tasks that moved >= 0.40 | 3 |
| worst single-task swing | **0.60** |

Task rates of 0.20 -> 0.80, 0.40 -> 0.80 and 0.60 -> 1.00 all occurred **with no change to the
code**. That floor is larger than most per-task effects worth chasing, so at this trial count the
`k/n` gradient is mostly noise, and a per-task "improved / regressed" list is close to
uninformative. At n=10 the floor is roughly 0.11 — still large against a claimed 0.20 step.

One nuance rescues the canary discipline: **the variance is concentrated in particular tasks, not
spread uniformly**. Across five byte-identical readings of one 12-task subset, two tasks read 1.00
in *every* run while three carried nearly all the movement. So a canary set drawn from
demonstrably stable tasks is trustworthy even though per-task rates in general are not — which is
why canaries must be chosen from REPEATED measurements at the real trial count, never from a
3-trial screen, and why "canaries intact" remained a meaningful statement all round even as the
target-task rates became unreadable.

The consequence is not "give up on per-task work"; it is **stop using rates as the per-task
evidence and use MECHANISM instead**. Everything from this run that survived scrutiny was
established structurally rather than by a rate delta: a crash found in live tool returns and
confirmed by its error string going 3 -> 0; a docstring section shown to reach the model 0% of the
time by rendering the schema and counting characters; a reward component shown to be non-gating
because the tool it names was invoked in 0 of 300 rollouts while the task still scored 0.8. Every
finding that rested on a rate difference at n=5 or n=10 was later retracted or downgraded.

So the per-task loop's real output is a *diagnosis you can verify without the metric* — a wrong
argument visible in a trace, a tool that raised, text that never arrived. Use the rate only to
decide whether to keep looking, never as the proof.

**Re-run the null ITSELF, not just once — the control's own run-to-run spread is the real bar.**
A single null-edit control tells you the noise floor only if that control is itself stable, and on
this benchmark it is not. Three full-val readings at n=5, all on **identical seeds** with
temperature 0:

| arm | reading |
|---|--:|
| control, run 1 | 0.6467 |
| control, run 2 (**byte-identical, same seeds**) | 0.7267 |
| candidate | 0.7333 |

The two control runs are **+0.0800 apart, and that null "passes" a k_se=1.0 gate** (bar 0.0379).
The candidate reads +0.0867 against run 1 and **+0.0067** against run 2 — the verdict is decided by
which control reading you happened to take. Anything measured at that trial count and below ~0.08
is unresolvable, which on this run included every panel comparison and the headline candidate.

Note what this is NOT: seeds were identical across all three runs and temperature is 0, and single
model calls are perfectly deterministic (six identical completions by hash). The variance enters
through the multi-turn conversation. So a determinism check cannot substitute for it, and neither
can more trials in the same block — you have to run the whole arm again.

The cheap discipline that follows: **evaluate the control twice before you believe any candidate**,
and set the bar from the null's own spread rather than from a formula. A gate whose bar is smaller
than the null's re-run delta is not a gate.

**Know what your gate can RESOLVE, not just what it costs.** Two numbers decide whether a round
can even see its own result. Measure the per-task noise (`sd` of a task's rate across repeat runs
of identical bytes — ~0.16 at `n=10` near p=0.5), then the paired mean's SE is
`sd*sqrt(2)/sqrt(val_n)`. In one run that is **0.041**, so at `k_se = 1.0` the gate can
resolve a gain above ~0.041 of val — about **1.24 task-equivalents**. That single number tells you
three things up front: a +0.057 gain is 1.4 SE and detectable; anything worth less than ~1.2
task-equivalents cannot be distinguished no matter how confident the per-task readings look; and
closing a 0.165 gap is a **4 SE** move, which is a different kind of ask from a 1.4 SE one. Compute
it before the round, alongside the headroom, and say both out loud.

**State the ceiling before you spend.** From the baseline's per-task rates, the recoverable
loss is `Σ(1 − rate)` over failing tasks, in task-equivalents; reaching a target `T` from a
current mean `M` needs `(T − M) × val_n` of it. Say out loud what fraction that is and which
tasks hold it. In one run: 9.66 equivalents available, 6.67 needed for 0.90 — **69% of
all remaining loss**, with 6.0 of it sitting in six tasks that score exactly 0.0. That makes
the target's shape explicit (every hard task must be fixed, not most of them) and it is the
difference between a plan and a hope. If the arithmetic says the target needs ~100% of the
available loss, say so in the report before the first rollout, not after the last.

**The three phases.**

1. **Fan out one optimiser per defect.** One subagent per `DEFECT` task; one per `UNSTABLE`
   *cluster* (unstable tasks share a mechanism more often than broken ones do). Each gets its
   own `cp -r` of the current best and edits only inside it.
2. **Merge.** `merge_taskopt.py` (git 3-way, one branch per optimiser). Two rules earn their
   keep here. **Declare a rebased optimiser's parent** — `--include u67b t21 t17b:u67b` — or
   its diff re-applies everything the parent already did and collides with the parent's own
   branch. And **classify every conflict before resolving it**, because the two kinds take
   opposite treatment:

   - **Semantic conflict** — two optimisers arbitrate the *same decision* differently (rival
     guards on one write, contradictory guidance at one moment). **Drop one bundle**; a union here
     ships contradictory instructions nobody measured. The tie-break is which side has a
     measurement, not which text reads better: the one such conflict observed came from
     a bundle measuring 0.50 against its own 0.60 baseline, whose author recommended against
     merging it, so the round shipped the verified copies and excluded it.
   - **Textual collision of distinct additions** — two new functions, or two new dict keys, that
     happen to land on adjacent lines. Here the union IS what both optimisers measured, and
     dropping one throws away a verified gain over a whitespace accident. Resolve with
     `--union-on-conflict`, which names the union-resolved files so the claim stays checkable.

   Union resolution has one hard follow-up: **render the live toolset**. Keeping both sides can
   duplicate a definition or break syntax, and an import check does not catch what registration
   does. In one run the union of five branches gave 596 added lines, 14 tools registering
   and no duplicated methods — checked, not assumed. The union is still a shape nobody measured in
   isolation, so the gate decides it: union to avoid losing gains, gate to find out whether you did.
   **The conflict may be an artifact of merging whole files.** Before treating a conflict as a
   real disagreement, check the granularity. Ten independently-verified branches in one
   round produced a whole-file merge that kept **four** of them; the "conflicts" were not
   disagreements at all. Every optimiser had added one state field to the *same* `__init__` and
   one independent guard call to the *same* tool method right after the same existing check, so
   their edits landed on adjacent lines of a shared insertion point. Line-level 3-way merge
   cannot tell *two people appended different things here* from *two people rewrote the same
   thing*, and diff3 conflicts on both. Forcing them through with `--union-on-conflict` produced
   a file that **did not parse** and carried five duplicated `def`s.

   So merge per FUNCTION, not per file — `funcmerge.py`, which runs the same git 3-way merge at
   a granularity where independent additions never interact. That raised retention from 4/10 to
   the full set. It resolves in three escalating steps, each of which reports what it did:

   - **pure insertions** (`--union-pure-insertions`): if *no* branch rewrites a base line, apply
     every branch's insertions, anchored to positions in the base so branch order cannot change
     the result. Provably safe, and it is the case that covers a shared `__init__`.
   - **priority trunk + insertions**: when branches *did* rewrite one function, one becomes the
     trunk and the rest contribute only their insertions, re-anchored by the CONTENT of the base
     line they followed. Pick the trunk by **which branch changed that function most**, not by
     whose task holds the most headroom — the branch owning a full task-equivalent turned out to
     have added exactly ONE line to the contested function (its real fix was in
     another function), so ranking by headroom discarded the branch that had actually rewritten
     the return value and kept nothing. *What a function is worth is not what its author's task
     is worth.*
   - **forced trunk** (`--force-priority`): a last resort that drops the *rewrites* of losing
     branches but still applies the *insertions* of every branch that only added. Dropping a
     whole branch because someone else rewrote the function is how a merge silently loses a
     measured fix — here it would have discarded task 42's guard call to settle a disagreement
     about a money string. Every drop is reported per function and must be re-measured.

   **Audit what the merge failed to carry, and read it against the ledger's rejected entries.**
   A forced-trunk resolution does not just lose a branch's gain — it can silently RE-APPLY a
   subtraction that branch had already measured and reverted. Observed live: one optimiser had
   added a sentence to a `payment_id` argument description and had separately logged, twice,
   that removing it was harmful; the merge dropped that branch's rewrite of the function and
   re-performed exactly that subtraction. Nothing conflicted, so nothing was reported, and a
   gate would have measured the regression without ever naming its cause. Trace evidence bore
   it out: of the stored rollouts on that task which made every write on the correct record
   and still scored 0, four of seven charged a credit card when the customer had asked to pay by
   gift card — precisely the defect the deleted sentence addressed.

   **A merge that carries a function but not a CONSTANT it needs produces a crash that looks
   like a policy failure.** This is the same lost-work class one level lower, and it is the most
   expensive single defect this run produced. `_check_bags_before_cabin_change` read
   `self.CABIN_LADDER` at four sites; the merge carried the helper *and* its call site and left
   the class attribute behind. The live tool return was
   `Error: '<ToolsClass>' object has no attribute 'SOME_CONSTANT'` — the tool layer turns the
   `AttributeError` into a string, the agent reads it, abandons the write, and the reward records
   a **missing write**, indistinguishable from the agent choosing not to act. It silently
   contaminated four measurements across two candidates and two ablations, and it was found by a
   per-task optimiser reading a live trace, not by any aggregate.

   So `funcmerge.py` now **refuses to write** a result in which any constant-shaped attribute
   read off `self` is undefined. Two details make that check safe rather than merely strict.
   Instance fields are routinely declared *with annotations* (`self.x: set[str] = set()`), which
   is `ast.AnnAssign` and not `ast.Assign` — collecting only the latter reported six valid fields
   as undefined and rejected a good merge. And only UPPER_CASE names hard-fail: the class under
   merge normally has a base class, an inherited method reached through `self` is not resolvable
   from one file, and refusing those would reject valid merges. A hard check with false positives
   is worse than no check.

   `funcmerge.py` therefore reports `dropped_additions`: every non-trivial line a branch added
   that the result does not contain. It is advisory, since some drops are the deliberate outcome
   of a conflict decision, but it must be read before gating. Run cold on seven branches it
   flagged lost work from **six of them**, including a `next_step` block that was part of an
   already-verified mechanism nobody had noticed was missing.

   Two things this exposed that no rate would have. A guard **helper** can survive a merge while
   its **call site** does not, leaving dead code that costs context and buys nothing — so verify
   the call, not the definition: `grep -c '_check_foo(record)'`, never `grep -c 'def _check_foo'`.
   And a ledger `touches` field named a function (`_remaining_upcoming`) that **no branch ever
   defined**, which is why the merged artifact must be checked against the code rather than
   against the ledger's own description of itself.

3. **Gate the merge once, on full val, against `ctl_null`.** Nothing from phase 1 or 2 is
   believed until this. Per-task fan-out changes where the search spends its rollouts; it
   does not change what counts as evidence.

   **A per-task gain is verified against ONE base and is not transitive to another.** This is the
   sharpest limit on the whole per-task fan-out idea, so measure it rather than assuming it. On a
   seed-matched comparison (identical trials for both arms, so seed variance cancels entirely),
   adding an optimiser's independently-verified task-14 edits to an artifact that already carried
   three other optimisers' work measured **-0.0617** overall — and **task 14 itself fell**, from
   0.40 to 0.20, despite the very same edits having measured 0.50 -> 0.70 at n=10 on the base they
   were developed against. Two other tasks fell 0.80 -> 0.00 and 0.80 -> 0.20.

   So "verified on my task, canaries intact" is a necessary result and not a shippable one. What a
   fan-out produces is a set of *candidate mechanisms*, each with evidence that it can work
   somewhere; which subset survives together is a separate measurement, and the only reliable form
   of it is a seed-matched paired comparison of the composed artifact against the artifact without
   the addition. Budget for that: it is not free, and skipping it is how a round of nine
   confirmed wins becomes a candidate that loses.

   **Select the merge on a headroom panel before you gate it.** A full-val gate answers one bit
   for 300 rollouts, and it answers it about a *sum*. In one round the merged artifact
   scored +0.0126 and was rejected — correctly — while containing, per task, both real gains
   (task 40 `0.10 -> 1.00`, task 21 `0.20 -> 0.80`, +2.1 task-equivalents gross) and real losses
   (task 10 `0.80 -> 0.10`, task 9 `0.80 -> 0.40`, -1.6). The gate could not see either. Keeping
   only the gaining half would have measured ~0.78. So evaluate merge variants on the tasks that
   can actually move — the ones below 1.0 — pick there, and spend the full-val gate on the
   winner alone.

   Two corollaries. **Tasks already at 1.0 cannot contribute a gain**, so a panel of the
   below-1.0 tasks is both cheaper and strictly more informative per rollout than full val for
   *selection* (it is not a substitute for the gate, which is what protects the tasks at 1.0).
   And **compute the headroom before choosing a target**: sum `1 - rate` over val at the real
   trial count. That arithmetic is what says whether the goal is reachable at all — in one run
   it read 8.70 task-equivalents over 30 tasks, so 0.90 needed 5.7 of them, i.e. 65% of
   everything left, with 5.4 of it sitting in six tasks. A target nobody has costed against
   measured headroom is a wish.

   **Regression attribution is free once rollouts are on disk.** Before spending anything to
   explain a drop, diff the stored failure feedback of the two arms per task. In one run that
   showed the regressed tasks had *identical* feedback strings in both arms at different
   frequencies — the edit shifted a tendency rather than introducing a bug, which is a different
   thing to fix and would have been invisible from the means. The same pass costs nothing and
   rules out infrastructure: 5 of 2040 val rollouts (0.25%) died for infrastructure reasons and
   were scored 0.0, concentrated on one task — small enough to ignore, but *measured* small
   rather than assumed small.

**Each optimiser's loop** — target task at full `n_trials`, plus a canary of tasks measured
**1.0** at baseline, in the same call:

The inner step is one optimiser's own task at full trials plus the canary, in a single call; after
the fan-out, combine and gate the merge like any other candidate:

```bash
python "$A/taskeval.py" "$R/work/$TAG" 7,17 --project "$P" --n <num_trials> \
       --canary 0,3,12 --canary-n 3 --traces /tmp/tr_$TAG.json
python "$A/merge_taskopt.py" --root "$R/work" --base "$R/work/<parent>" \
       --out "$R/work/cand_merged" --include t7 t17 u33
python "$A/round.py" --run-dir "$R" --project "$P" --candidates cand_merged \
       --n-trials <num_trials> --k-se <gate_k_se>
```

Run each eval **detached** (`nohup ... &`, then poll for the output file). Under endpoint
contention a per-task eval can take 15-50 minutes, and one optimiser lost a 64-minute round to a
harness-level timeout killing an eval that was still healthy — detached, the same round survived.

Then read `/tmp/tr.json` — the agent's own tool calls with arguments, per failing trial — and
aim the next edit at an observed decision. For an UNSTABLE task, **diff a failing trial
against a passing one**: the divergence point is the ambiguity, and removing it beats adding
a rule (see *Match the Form to the Failure*).

**The four things that keep it honest.** Skip any one and the phase manufactures a number:

- **A per-task rate is a training number by construction.** The optimiser tuned on it. Quote
  it as a search signal, never as a result. Only the full-val gate and the sealed test are
  evidence.
- **No task-specific literals — and ENFORCE it with a script, not a promise.** No record
  id, confirmation code, item number, person name, date, user id, payment id or location pair
  from the trace may appear in a line the edit ADDS. Write a ~40-line auditor that diffs each
  candidate against the base and greps the ADDED lines for your domain's id shapes; make a
  `clean` verdict a merge precondition, independent of what the rate says. Two details decide
  whether it works: diff the **added lines only** (the pristine seed's own airport tables and
  example ids would flood a whole-file grep), and **skip any literal the base already
  contains** — a reindented pristine docstring shows up as an addition and made three clean
  candidates look guilty until that filter went in. It caught exactly one
  real case: a docstring enumerating *"New York is JFK, LGA or EWR; Chicago is ORD or MDW"* —
  its task's own cities, dressed as a general rule. The underlying idea (match a route by city,
  not airport code) was fine; the enumeration is what made it memorisation.
- **Diagnose from behaviour, never from the target — but the COORDINATOR may audit the spec.**
  The task's `target` / `evaluation_criteria` are the grader's, not the optimiser's: for an
  optimiser, the feedback string and the agent's own trace are the whole permitted input. The
  coordinator has one narrow extra permission, and it is a measurement-integrity permission, not
  an optimisation one: **read the spec to answer "is this task winnable, and is the optimiser
  chasing the right criterion?"** — then relay only what the agent itself can already observe.
  This unblocked two dead tasks in one run. On one, an optimiser had concluded the
  communicate check was unsatisfiable; the audit showed it required a single figure the agent was
  computing wrongly, so the relay was *"you speak, your arithmetic or scope is wrong"* — no value
  echoed. On the other, an optimiser had built a same-date-duplicate detector, plateaued, and
  reported that the correct write set was unreachable that way; the audit showed the criterion is
  the itinerary **the customer states in her own message**, so the relay was *"cancel what
  conflicts with the trips she stated, keep what matches"* — again nothing the agent could not
  see for itself.

  The line to hold: relay a **criterion the agent can evaluate from the conversation**, never a
  value, an id, or an expected write. If the only way to state the fix is to name the answer, the
  task is not winnable and that is the finding — say so in the report instead of leaking it. And
  keep the permission asymmetric: an optimiser that reads targets has stopped optimising the
  agent and started memorising the grader.
- **A guard must fire on a DECISION, not on a tool.** A precondition that refuses on every
  call of a write tool derails tasks it was never aimed at: one such guard dropped a canary from
  1.0 to 0.333 and pushed that eval's wall time from 299s to 1493s, because every extra refusal
  costs a turn in a turn-budgeted rollout. Key the guard to the specific contested situation and
  let it fire **once per situation** — re-keying one guard from per-user to per-contested-date
  was worth 0.0 → 0.333 on its own, because a second independent decision needs its own prompt.
  And keep the refusal directive: softening the same guard's wording to "otherwise proceed" flipped
  the failure from over-writing to under-writing and gave the whole gain back.
- **Measure the canary at the SAME `n` as the target before you use it, and never set the bar
  at 1.0.** A task that reads 1.0 off a 3-trial baseline has a CI wide enough to hold 0.4, so
  a canary chosen that way manufactures phantom collateral damage and every optimiser burns
  iterations chasing it. Measured cost of getting this wrong twice: one
  canary task read 1.0 at 3 trials and 0.67 at 10; a second read 1.0 at 3 trials and then
  0.667 / 0.333 / 0.0 / 0.333 / 0.333 across five independent 10-trial runs — so
  `canary_mean == 1.0` was unreachable for reasons no candidate caused. The bar is **no canary
  task below its own measured band**, and the band comes from the same `n` you judge at.
  The same warning applies to the target: one "0.0 DEFECT" task measured 0.444 at n=10.

**Decompose the reward before you fan out.** If the metric is composite — one benchmark scores a
database check, action checks and communicate checks and then returns a *binary* task reward —
a task that wrote the database correctly and only failed to state a required confirmation
scores 0.0, identical to one that did nothing. `taskeval.py` reports the per-component means
(`component_rates`) for exactly this reason: it turns one useless number into one number per
failure mode, and the two need different edit forms. Do this first; it is free and it
re-aims the whole round. In one run it showed all 14 failing tasks missing the database-state
component and only 4 also missing COMMUNICATE — which killed a plausible-sounding
communicate-first plan before any rollouts were spent on it.

Then tell each optimiser **which components its own task even has**: 25 of the 30 val
tasks have no communicate check at all, so on those, nothing the agent *says* can change the
score and any edit aimed at phrasing is guaranteed dead. `component_rates` lists only the
components a task actually carries, so this is free to read and it deletes whole categories of
wasted iteration.

**Check which reward components actually GATE before you read the feedback as a to-do list.**
A grader that reports several component scores does not necessarily use all of them. One
benchmark publishes `reward_basis`, and there it is `["DB", "COMMUNICATE"]` — **`ACTION` is absent**,
so action checks cannot change the score. The feedback nonetheless led with "Action-level
defects", which sends an optimiser after calls that provably do not matter: task 12's feedback
names `calculate: was never called` on every failing rollout, `calculate` was invoked in **0 of
300** rollouts, and the task still scores 0.8. Label non-gating detail as diagnostic and name
the components that do gate, or the loudest line in the feedback is the one worth least.

The same read is worth doing per task before choosing an edit form: a task with no communicate
check cannot be moved by anything the agent *says*, and a task scored only on `DB` cannot be
moved by fixing which reads it performed.

**Measure what the model actually RECEIVES before you write another word of it.** A tool
docstring is not delivered whole. One harness builds each tool's schema `description` from the docstring
**summary plus the prose before `Args:`** and drops the `Returns:` section entirely. Measured over
a 14-tool set: **5469 of 12929 docstring characters (42%) never reach the model**, and on
one tool it was 115 of 1906 delivered — **94% dropped**. Rounds of behavioural guidance
had been written into that void. One "verified" mechanism (*read these cards and pick the ONE that
matches the description*) turns out to work only because the **return VALUE** changed shape, which
the model does see at call time — not because anything documented it.

So there are exactly two places guidance can live, and a third that looks identical and does
nothing:

| surface | reaches the model | use it for |
|---|---|---|
| docstring summary + prose before `Args:` | **yes**, in the tool schema | preconditions, scope, what not to do |
| `Args:` per-parameter descriptions | **yes** | argument-level constraints |
| the returned VALUE (a `next_step` key) | **yes**, at call time | what to do next, with its constraints |
| `Returns:` docstring section | **no — silently dropped** | human readers only |

Verify it, per candidate, rather than trusting the file: render the toolset and sum the delivered
characters. Two hazards when moving text into the delivered region — a lifted line must not begin
a recognised section (`Example:`, `Returns:`), because some harnesses parse those and a stray header raises
at REGISTRATION time and kills every rollout as `INFRASTRUCTURE_ERROR`; and it must be inserted
*before* `Args:`, or it lands back in the dropped region.

**Findings go in the ledger, not in the coordinator's head.** Independent optimisers on
different tasks keep rediscovering *one* cause. In one run four of nine independently
found writes being lost to turn starvation, and two independently implemented the same tool
enrichment — which collided at merge, where only one of the two had actually been measured.
So every optimiser **lists before it diagnoses and appends when it finds**:

```bash
python "$A/mechanisms.py" list --run-dir "$R" --task "$TASK" --compact
python "$A/mechanisms.py" add --run-dir "$R" --owner "$TAG" --status proposed \
       --mechanism "<the cause, one sentence>" --evidence "<what you measured>" \
       --touches <function-the-fix-edits>
```

**Filter the ledger per optimiser, but never filter out the task-independent rows.** A real
fan-out ledger reaches a size that stops being an asset: this one hit 99 findings / 65 KB, and
pasting all of it into each of K subagents spends their context on other people's tasks.
`--task N --compact` cuts it to 24 KB while keeping every row about task N **plus every row
with no task attached** — those are the cross-cutting facts (canary bands, variance warnings,
measurement defects) that apply to everyone, and hiding them is exactly how a fan-out re-pays
for a defect someone already found.

**Retire a finding that turns out to be wrong — `--supersedes <seq>`.** Contradicting it with a
newer row is not enough: three separate `verified` rows were disproved on this run (a merge-retention
percentage computed from single readings, and two different claims about one task's ceiling), and a
reader of the listing saw both the claim and its refutation with no way to tell which won. A
superseded row drops out of `verified`/`proposed` and is reported under
`superseded_do_not_act_on`, so the history stays auditable without misleading the next optimiser.
**A disproved claim left in `verified` is worse than no ledger at all** — it is the one thing a
fan-out will confidently build on.

`--touches` is the collision key and `--status` is the point: `verified` means reuse it and
never rewrite it (**rebase onto that copy** and spend your iterations elsewhere), `proposed`
means its owner is already on it, `rejected` means a retry must be structurally *different*.
Cross-pollination is the main reason K parallel optimisers beat K sequential rounds; the
ledger is what makes it survive the coordinator forgetting to send a broadcast.

**Ablate a read+enforce pair TOGETHER, or you will throw away the half that carries it.** The
strongest single per-task result of one round was a two-part edit: a tool return printing
the concrete candidate values, plus a write-side refusal ordering the agent to re-read them.
Measured alone the read block moved 0.400 -> 0.500, inside noise, and looked worthless; the
refusal looked like the whole gain. Removing the read while keeping the refusal collapsed the task
from **0.625 to 0.200** and brought the original wrong writes straight back — a refusal that tells
the agent to re-read a value only works if that value is actually printed somewhere it can read.
The converse held too: the same content as *passive* fields with no refusal was worth nothing,
because extra fields deep in a large payload never reach the decision. Enforcement without the
read is a dead end, the read without enforcement is decoration, and ablating either half in
isolation gives you the wrong answer about both.

**A tool return that advertises a path must state that path's constraints in the same breath.**
Adding a price table showing what one option would cost pulled the agent toward that option, and it
discovered three turns later that the option could not be paid for the way the customer wanted — too
late to pivot, so it escalated. The table alone cost a task 0.28; the same table with the option's
payment rules printed beside it recovered that and carried another task to 0.90. Information that
makes a path *attractive* without making its preconditions visible is worse than no information.

**A numeric fix must not be phrased as an instruction to address the customer.** Telling the agent
to quote a figure after every write did exactly what it said — the communicate component went to
1.0 — while the database component collapsed (one task 0.50 → 0.11, and a reliable canary to 0.667),
because "report this to the customer" sends it to the customer *mid-flow*: on a cancel-then-rebook it
spent the turn announcing the refund and never booked. Fix the value, not the audience: put the
figure where the agent will use it, and never make stating it a turn-taking instruction.

**Forcing a decision to be STATED is not forcing it to be CARRIED OUT.** A guard that refused a
write until the agent named which competing item it was keeping measured 0.2 -> 0.1. It worked at
its literal job — the blind retry disappeared — but the agent then treated *having named* a keep as
having resolved the situation and never issued the second write. If the defect is a missing action,
the guard has to be satisfiable only by that action; a guard satisfiable by an assertion buys you a
better-documented failure.

**"No nuance clauses" applies to refusal text too.** Adding two *correct* discrimination clauses to
a working refusal took the same task 0.2 -> 0.1, with all ten trials failing — three cancelled
nothing and two escalated. The clauses were right and the longer refusal traded follow-through for
precision. A refusal has a budget: every sentence competes with the one that says what to do next.

**A traces file holding only FAILING trials is evidence about the passes.** If a specific action is
absent from every failing trial across dozens of rollouts, and the task sometimes passes, then that
action is what the passes are doing — a free inference from an artifact you already have, and often
the fastest route to naming the residual defect.

**A precondition can be misread as a platform limitation — say what it is.** One guard refused an
inconsistent write and the agent apologised to the customer ("the system won't let us do that"),
offered to split the request in two, and argued about it for the rest of the conversation instead of
fixing the argument. Rewriting the same refusal to say *this is not a limitation, here is the
corrected value, retry now* removed the false apology. It was score-neutral — and worth keeping
anyway, because the agent stopped telling the customer something untrue. Not every improvement
shows up in the metric, and a refusal's wording decides whether the agent treats it as a bug to
route around or an instruction to follow.

**A retryable refusal is safe when the retry path is the CORRECT action, and poison when it is a
free choice among options.** Both shapes were measured on the same task in adjacent rounds, which
is what makes the distinction trustworthy. A one-shot retryable refusal that named *the* fix
("upgrade first, then add bags") took the task 0.60 -> 0.70 and could never dead-end a legitimate
request. The same retryable shape applied to a choice — refuse the charge, list the valid payment
ids by kind, let the agent pick — measured **0.70 -> 0.10**: the agent treated the retry as a
formality, re-sent the same wrong id, and trials that had previously chosen correctly switched to
the wrong option, because the refusal's own list read as permission. So before shipping a guard
that enumerates alternatives, ask whether the retry leads to one determined action or to a menu. A
menu turns a mistake into a sanctioned choice.

**In a turn-budgeted rollout, a fix that costs a turn can cost more than the bug.** This is the
constraint that decided more edits in one run than any other, and it is easy to miss
because the edit reads as obviously correct. Telling the agent to *ask* for a missing piece of
information measured 0.5 -> 0.3 — even when scoped to exactly one call site, which is normally the
fix for that kind of regression. The mechanism: the user simulator ends the conversation a few
messages in, so the question trades a write the agent would otherwise have made for an answer it
never gets to use. Two other optimisers hit the same wall from the opposite side, where the *bug*
was a wasted confirmation round-trip. So before shipping any edit that adds an agent message,
count the turns it costs against the turns the failure costs — and prefer a form that puts the
information in a tool return, where it costs nothing.

Two corollaries measured the same way. **Place text at exactly one call site**: the same directive
inside a helper with four callers splattered across seven tool returns and into a post-success
summary where it read as self-contradictory (0.5 -> 0.3). And **do not tell the agent to stop
reasoning about eligibility and defer to the tools** — that was the single worst edit of the run
(0.5 -> 0.0, and a reliable canary 1.0 -> 0.667): the guard still catches flagrant violations, but
the agent starts attempting actions policy forbids and the conversation derails.

**Elimination evidence is only as good as the classifier feeding it — verify a classifier by
PRINTING, not by measuring.** One optimiser ran a careful elimination over 30 scored trials, ruled
out every candidate write-set it could construct, and concluded the task was unwinnable without
hardcoding. The reasoning was sound and the conclusion was false: the helper deciding which items
matched the customer's stated requirement was inverted, so every set it built excluded the right
item. The bug was one line of classification logic, visible in five seconds by printing the
helper's output next to the raw data — and instead it cost three eval rounds and a wrong verdict
about the benchmark. So whenever a round's conclusion rests on a derived label ("this one
conflicts", "this one is eligible"), dump the label beside the input it came from and read it by
eye **before** spending rollouts on any hypothesis built from it. Cheap checks first: a classifier
is a function, not an experiment.

**Find a task's own ceiling, then stop.** Not every task can reach your target, and grinding one
that cannot is the most expensive mistake in this phase. Two optimisers spent 13 rounds between
them on one task without moving it off 0.0. Its ceiling was structural: the user simulator
terminates the conversation a few messages in, and 3-4 of 10 rollouts died right after a
*mandatory* question the customer's opening message had not answered — so with a binary reward
needing both components, the achievable rate was ~0.6 whatever the edit. Say the ceiling out loud
in the report, subtract it from the headroom, and move the budget to a task that can move. A
bounded task is a finding, not a failure — and "we never reached 0.9 on task X" plus *why* is
worth more than a third optimiser.

**A regression LIST at `n=10` is noise, and the control proves it in the same round.** In the
one gate the byte-identical control reported **four** regressed tasks and the candidate
reported **four** — identical counts, disjoint sets, and one of the two artifacts provably
unchanged. That is the whole case for `--veto-regressions` being off by default: with the veto on,
a copy of the parent would have been rejected for the same reason as the candidate. Read
`regressions` as a pointer to look at, never as a verdict, and always next to the control's own list.

**One per-task reading cannot attribute a per-task change — and that trap caught this skill's
own author.** At `n = 10` the standard error on a task near 0.5 is about 0.16, so a difference
below roughly 0.3 is indistinguishable from re-measurement. Measured: one task
read **0.6 / 0.9 / 0.5** across three independent runs of *byte-identical* files, another
**0.5 / 0.4 / 0.4 / 0.4** against a single solo reading of 0.70. A "74% of the gain was retained
by the merge" figure was computed from single readings, reported, and then withdrawn when an
optimiser re-measured the same bytes twice and found the giveback was noise — the merge was
structurally clean, verified by diff.

So the between-phases check is still worth its ~70 rollouts, but read it as a **smoke test, not
an attribution**: it catches a merge that dropped an edit or broke a canary outright, which is
what it is for. To claim a per-task delta, pool runs (report `k/N` across every run of those
bytes, not the last one), and treat any single-reading per-task comparison as a hypothesis. The
per-task rate was always a training number; this is the second reason not to quote it as a result.
The full-val gate against its own control is the arbiter precisely because it averages 30 tasks
instead of trusting one.

## The binomial floor, and what an aggregate mean can resolve

**First compute the BINOMIAL floor. Most of what looks like mysterious nondeterminism is n.** Each
rollout is pass/fail, so a task's rate is a binomial proportion and an arm mean over `m` tasks at `n`
trials has

    SE(arm difference) = sqrt( sum_over_tasks 2·p(1-p)/n ) / m

Do that arithmetic BEFORE blaming the provider, the seeds, or the load. Measured on 10 tasks at n=10
with p≈0.35: predicted SE **0.0615**, observed gap between two byte-identical arms **0.0778** — a
ratio of **1.27**, i.e. plain sampling. Mean per-task movement was 0.0978 against a binomial
prediction of 0.1445, so the observed movement was *smaller* than chance requires. There was nothing
left to explain.

One precision about what this is and is not. At temperature 0 with identical seeds a fully
deterministic system would return *identical* arms, so this is not sampling error in the textbook
sense — there is no sample being drawn. What the arithmetic shows is that the observed variation is
**statistically indistinguishable in magnitude from independent per-rollout coin flips**. That
matters because no further mechanism needs to be posited to explain it, and — whatever its physical
cause — the remedy is the same one that works for binomial noise: more trials. Do not report it as
"sampling noise" without that caveat, and do not go hunting for a cause you have no evidence for.

That reframes the concurrency result rather than cancelling it: at conc 25 per-task movement was
0.250, genuinely **above** the 0.1445 floor, and dropping to conc 8 removed that excess and exposed
the floor underneath. Lowering concurrency fixes what it can; the rest is n.

The consequence is uncomfortable and worth stating plainly: **an aggregate mean over a dozen HARD
tasks at n=10 cannot resolve any realistic edit.** Reaching 2 SE on a +0.05 effect on that subset
needs ~60 trials per task.

But be careful about the obvious inference, which is wrong. Narrowing to the hard tasks makes the
measurement *worse*, not better, for judging an artifact — because a task sitting at 1.00 contributes
signal to the mean with almost no variance, so dropping it removes a free denominator. Computed from
that benchmark's own per-task rates:

| arm | rollouts/arm | SE of paired difference |
|---|--:|--:|
| 12 hard tasks, n=10 | 120 | **0.0496** |
| full val 30 tasks, n=10 | 300 | **0.0262** |
| full val 30 tasks, n=20 | 600 | 0.0185 |

Full val at n=10 is nearly twice as precise as the hard subset, and the four prior gate rounds there
were run at full val n=5 (SE 0.0371) — so their problem was never the task set. It was that they ran
at a concurrency carrying excess noise on top of that, and chased effects smaller than the sum.

So the two questions need opposite designs, and conflating them is the actual error:

| you want to know | measure | why |
|---|---|---|
| does this mechanism work | ONLY the tasks where it fires, at high n, per-task test | a mechanism firing on 2 tasks is diluted to nothing in a 30-task mean |
| does it break anything | canaries, cheap precisely because they sit at 1.00 | zero variance means a single drop is real |
| what is the artifact worth | FULL val, both arms in one batch | the 1.00 tasks are free precision for the mean |

A mechanism that fires on two tasks and lifts them 0.15 → 0.45 is resolvable at n=40 on those two
tasks (≈3 SE) and invisible in a 12-task mean at n=10 (≈0.5 SE). Same edit, same rollout budget: one
design answers the question and the other cannot.

**When an effect sits below the floor, pre-register directional predictions and use a SIGN TEST.**
The floor bounds what a *mean* can resolve; it does not bound what a *pattern of directions* can.
Write down, before its arm runs, which way each prediction should go, then count. Measured: **9 of 10
predictions positive gave p = 0.0107** on a set where no individual z reached 2 — the effect was real
and every per-arm reading was individually inconclusive. Two conditions make it a test rather than a
story: the predictions are recorded *before* the arms run (a direction chosen after the fact is not
evidence of anything), and they are directions, not magnitudes. A post-hoc count of which way things
happened to go is worthless, so if you did not write them down, you did not run the test.

**A screening band is not a baseline.** Per-task rates from a small trial count tell you where to
*look*; they do not tell you where you *are*. In one run, ten tasks whose 3-trial bands summed to
2.33 measured **4.04** at n=10 — the screen understated the artifact by 1.71 task-equivalents (0.057
of val), and one task went the other way (0.33 → 0.10). Every "0.0 DEFECT" label was suspect: three
of them measured 0.30, 0.444 and 0.60. So screen at low `n`, but re-measure at the gate's `n` before
you quote a number, compute headroom, or tell an optimiser what its starting point is — and never let
a low-`n` band be the thing a delta is computed against.

## Load is the other half of the noise

**Run the GATE at low concurrency — most of the re-measurement noise is load-induced.** This is the
one lever that makes everything else measurable, and it is cheap to verify: measure the same bytes on
the same seeds twice at your search concurrency, then twice again at a low one.

| identical bytes and seeds, 12 tasks | conc 25 | conc 8 |
|---|--:|--:|
| arm-level \|delta\| between the two runs | **0.1167** | **0.0333** |
| mean \|per-task\| movement | **0.250** | **0.100** |
| tasks that moved at all | 10 / 12 | 5 / 12 |

Five of the twelve tasks became perfectly repeatable at conc 8 having each moved 0.20-0.40 at conc
25. So the practical split is: **search fast, gate slow.** Per-task exploration can run high, because
its output is a mechanism you verify from a trace, not a rate; the accept decision must run at a
concurrency where the null actually reproduces, which costs roughly 3x wall clock for the one
evaluation that matters.

Two caveats to state whenever you quote this, both real: the low-concurrency runs were sequential, so
load and elapsed-time drift are confounded; and 12 tasks x 2 runs makes the variance comparison thin.
The direction was consistent across all three metrics, which is why it is worth acting on, but it is
not settled.

**Concurrency composes only up to the endpoint's sustainable rate, and past it the failure is
silent.** The sources multiply: K optimisers x C concurrency each is K*C in flight, and the serving
endpoint does not know about your fan-out. Measured: nine per-task optimisers at concurrency 8 put
~72 requests in flight against a proxy whose sustainable band is 24-90, and a single per-task eval
went from ~4 minutes to ~50. Nothing errored — latency just grew, so it read as "the model got
slower" rather than "I oversubscribed". An earlier incident on the same proxy is the extreme version:
concurrency 300 pushed 292 of 300 rollouts into wallclock timeouts and the evaluation reported
**0.0067** as capability. So measure the sustainable band once, divide it by the number of concurrent
optimisers, and treat a sudden wall-clock blowout as an oversubscription symptom first.

**The knob is TOTAL IN-FLIGHT REQUESTS, not the runner's per-process concurrency flag.** That flag is
per-process, so it does not bound load when several evaluations run at once — and running them at once
is the normal case. A gate launched at `--conc 8` alongside four exploring optimisers at `--conc 12`
puts about 56 requests in flight, so it is a HIGH-load measurement wearing a low-load flag, and it
will reproduce the wide null rather than the narrow one. Serialise the gate: let the fan-out finish,
or pause it, and run the gate arms alone. Both arms still belong in the same batch as each other —
pairing is what removes drift — but that batch must be the only thing running. If you cannot quiet
the machine, say so next to the verdict instead of quoting a per-process number as though it were the
load.

## Gate the sum, not each addend

**A multi-branch artifact is assembled with `integrate.py`, never by one merge.** Stated as a rule
because the author of that script skipped it on the very round it was written: six branches were
merged in one step, and the resulting artifact gated at **−0.0146** with seven replicated per-task
losses against two replicated gains — while the same round's *single*-mechanism artifact gated at
**+0.0115**. Fewer mechanisms beat more mechanisms, and a one-shot merge cannot tell you that,
because it yields one number for N simultaneous changes.

`funcmerge` merging cleanly is **not** evidence the branches compose — every branch retained cleanly
in that failed artifact, with zero conflicts and no undefined attributes. Clean merge is a syntactic
property; composition is an empirical one.

**Gate the SUM, not each addend.** Measured: one tool-level mechanism is worth roughly 0.04–0.13 on
the one or two tasks it touches, and resolving an effect that size at 2 SE needs about **n=100 trials
on that task**. Certifying seven mechanisms that way is ~1400 rollouts to establish by rate what a
deterministic replay establishes for free. So the economical order is:

1. **Prove it engages** — replay a real failing payload against the edited tool and show the guard
   fires; replay the passing payload and show it does not. Costs zero rollouts, and it is a stronger
   statement about the mechanism than any rate.
2. **Establish incidence from rollouts you already have** — how often does the condition occur, and
   is it skewed toward failures? Also free. One guard fired on 8 of 76 matching calls, 8 in failures
   and 0 in passes.
3. **Confirm the sign at modest n, with canaries** — you are checking for a regression and a
   direction, not measuring a size.
4. **Gate the accumulated artifact ONCE on full val**, where SE was 0.0262 at n=10 and several
   mechanisms can clear it together even though none clears it alone.

Expect the measured per-task effect to land well below the upper bound incidence implies — there
~40% of it — because the guard fires correctly and the agent then still fails for an unrelated
reason. That gap is not evidence the mechanism failed; check the task's other reward components
before concluding anything.

## Take the error ACROSS whole runs

**Take the error across whole runs, not across tasks within one run.** A single paired run's SE is
computed over tasks, so it cannot see run-to-run nondeterminism at all — and on that benchmark it was
the dominant term. Repeat the entire paired comparison on distinct seed blocks and use the spread of
the per-run deltas:

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
where the retracted accept came from. `--base-seed` matters: raising `--n` only extends the same seed
block, so a rerun at the same seeds is a determinism check.

The first run alone reported SE 0.0548 across tasks and an "accept". Two runs show the same candidate
at +0.0867 and +0.0200, and a byte-identical control re-run moved +0.0800 by itself. The across-run
estimator needs no assumption about where the noise comes from, which matters because on that run its
source was never identified: LLM sampling, seed assignment, concurrent batching, timeouts, infra
accounting and set-iteration order were each ruled out by direct measurement, and the leading
remaining hypothesis (transient errors below the `max_errors` threshold being fed back into the
conversation) stayed unverified.

Budget for it up front: a credible verdict on a sub-0.10 effect there is **several full paired runs**,
not one. If that is unaffordable, the honest output of the round is "not resolvable at this budget" —
which is a result, and is what the earlier single-run accept should have been.

**The false-veto rate that made `--veto-regressions` opt-in.** In one gate the byte-identical control
reported **four** regressed tasks and the candidate reported **four** — identical counts, disjoint
sets, one of the two artifacts provably unchanged. The old veto fired on a byte-identical copy of the
seed **42.8%** of the time at 5 trials, and in one run it vetoed *both* candidates that had passed the
significance test. Read `regressions` as a pointer to look at, never as a verdict, and always next to
the control's own list.


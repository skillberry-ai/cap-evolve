# Edit design — what the scorer audit found, and how guards backfire

Read this before writing an edit on a surface you have not edited before, and always when two rounds
have been rejected. SKILL.md carries the checklist and the edit-form table; this file carries the
failures that produced them, with what each one cost.

The numbers come from real runs on a multi-turn tool-use benchmark with a mid-tier agent model. The
*shape* of each finding transfers; the figures are that run's.

## Auditing the measurement before you credit a failure

Every optimizer that skipped this step optimized against its own instrumentation. Scoring is
deterministic on persisted rollouts, so each repair below re-derives at **zero** rollout cost.

**Does the feedback name the actual defect, or only the tool?** If it says "Failed action(s): a
write tool" when the real defect is a wrong *argument value*, no edit can be localized. Measured:
argument-value errors were the majority of failed gold actions. A predecessor read the wrong field
name for the action check, reported "0 actions missed" for every task, and stayed blind to the
dominant failure mode for an entire effort. Fix the adapter's feedback, then re-derive.

**Does any feedback helper fail SILENTLY?** Grep the adapter for bare `except` around signal
construction and make each one loud. Measured: a localizer called a helper method that did not
exist; the `AttributeError` was swallowed, so every failed numeric check degraded to the generic
*"1 required piece(s) of information were not clearly communicated"*. An optimiser read that as "the
checker is unsatisfiable" and spent **seven rounds** instructing the agent to state a value it was
already stating. The repaired signal distinguishes *never stated a figure* from *stated one and it
was wrong* — and re-deriving it over 125 already-persisted rollouts cost nothing.

**Distinguish "silent" from "wrong" for every value-bearing check.** They are different defects
needing opposite edits (add a REQUIRED slot vs. fix arithmetic/scope), and a message that conflates
them sends the round in the wrong direction. Report the value the AGENT stated, never the expected
one — a check's `info` field often *is* the expected value (one benchmark stores a bare `"1628"`), so
use its SHAPE and never echo it.

**Did the rollout run, or did the infrastructure fail?** A wallclock timeout, a starved endpoint or a
dropped connection is missing data, not a zero. If it lands in the mean as 0.0, a whole evaluation
can read as a catastrophic capability with no error anywhere. Check `termination_reason` and the
coverage the gate reports — a low-coverage split must be `indecisive`, never a score.

**Would a clearly-wrong candidate score worse?** If not, the metric is not discriminating and no gate
built on it can work.

## Why churn needs a bundle you can take apart

The failure mode to design against is churn, and it is measured, not hypothetical: in a real run two
of three candidates had an *identical* mean to their parent while a different set of tasks passed —
each fixed 2 tasks and broke 2. A mean-only gate calls that a tie; the paired gate rejects it because
it sees per-task movement in both directions. That is why a multi-part edit is safe to attempt at
all — and why, when you bundle, the parts must be *independent* (different files or different rules),
so that a rejected bundle can be resubmitted as its surviving part next round. Read `regressed` out
of the screen and `regressions` out of the gate to know which part to drop.

## Form, not wording

- **No nuance clauses.** Appending one qualifying clause to an otherwise-winning recipe degraded it
  from consistent to noisy. If a rule needs a caveat, restructure the rule. This applies to refusal
  text too: adding two *correct* discrimination clauses to a working refusal took a task 0.2 → 0.1,
  with all ten trials failing. The clauses were right; the longer refusal traded follow-through for
  precision. A refusal has a budget — every sentence competes with the one saying what to do next.
- **Exemption clauses do not scope.** "This limit does not apply to X" still suppresses X.
  Restructure so the rule cannot reach the exempt case in the first place.
- **Prefer an in-code guard to a prose rule when the capability owns its tools.** The only edit that
  ever carried a large accepted gain on that benchmark was tool-level (`tools.py` 593 → 832 lines,
  +0.176 val): a precondition that refuses the illegal write and returns a recovery-oriented error
  changes behaviour deterministically, where a policy sentence changes it only probabilistically.
  Prose is the right form when the agent *lacks* a decision criterion; code is the right form when it
  has one and violates it.

## Confirmation-without-execution: the agent narrates the change instead of making it

A named failure class, and the one most reliably mis-diagnosed. The trajectory shows the agent
proposing a change, the user approving it, and the final message reporting the change as done —
with specifics — while **no mutating tool call appears anywhere in the trace**. The model has
taken its own completion signal (the approval) as satisfying the task and substituted narration
for the call. It is a documented property of LLM agents, not a property of any benchmark, so
expect it on any multi-turn capability that asks before it writes. `diagnose` names it
mechanically as the `narrated_without_action` cluster; without that it hides inside a
"wrong write" cluster, because a scorer describes both the same way, and the round then ships
an argument fix for a call that never happened.

**A prose reminder will not fix it.** "Always call the tool after the user confirms" has been
tried here and rejected: the agent already knows the rule and violates it anyway, which is
exactly the case the edit-form table sends to code rather than to prose.

The fix is structural — make *confirmed by the user* and *mutation executed* the SAME action, so
no code path can reach one without the other. In practice: one call that takes the approved
change and performs it, sharing the body with whatever the confirmation path already does, and
`remove` the primitives that let the two come apart. Then check the fix FIRES on the failing
trajectory: re-run the new body on that trajectory's own arguments. Ship nothing whose only
change is a sentence telling the agent to act.

## Guard closure: a guard that forbids the harmless option can force the harmful one

**Ask what the agent does INSTEAD.** Measured: a guard refusing a change that changes nothing ("this
call would change nothing, so do not quote a price") is locally correct — an unchanged record
genuinely cannot produce a credit. On the task where the right answer was *make no change at all*, it
cost 0.288. Removing that one guard, policy byte-identical, halved the damage (−0.288 → −0.147, no
longer resolvable) while the paired task kept its +0.498.

The failure is not the guard's logic, it is the guard's *closure*. Refusing the no-op left the agent
with only real changes to choose from, and it chose one. So before adding a refusal, name the action
set it leaves behind and check that "do nothing" is still reachable — a refusal that removes the
correct answer converts a pass into a fail while looking like a safety improvement.

This is also why the first ablation was worth running even though it refuted its own hypothesis: the
paragraph suspected of causing the loss turned out mildly *helpful* (removing it cost the paired task
0.141), and without that null the round would have shipped the wrong fix and kept the real cause.

## Auto-repair can accelerate a wrong action — a rejected call is sometimes a brake

When a tool bounces a recoverable argument slip, the agent spends a turn recovering, and turns are
scarce, so repairing the slip inside the tool looks like a free win. Measured counter-example: a
transaction whose payment id used an unrecognised alias and omitted the amount was rejected by the
parent and repaired by the candidate — but that transaction was itself premature, made with a
defaulted payment method the customer had never been asked about, and the customer then asked for a
different one, forcing an undo-and-redo that left an extra stale row in the database. The rejection
had been holding back a wrong write.

So before shipping a repair, ask what the rejected call would have DONE had it succeeded. If it would
have written the right thing a turn later, repair it. If it would have written the wrong thing
immediately, the repair needs to be paired with the precondition that makes the call correct — not
shipped alone, and not abandoned either.

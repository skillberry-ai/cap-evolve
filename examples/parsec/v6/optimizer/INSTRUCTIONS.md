# Optimizing parsec's system prompts across many tasks at once

{{TARGET_READER}}

{{FOCUS_SUMMARY}}

{{EMPTY_SEED}}

## What you can edit

The capability is **`system-prompt`** — plain-text edits to the 8 files under
this project's candidate directory:

- `orchestrator.md` — routes every request to one of 6 domain agents below.
- `shared_context.md` — prepended to every domain agent's prompt (not the
  orchestrator's).
- `aap2_agent.md`, `babylon_agent.md`, `cost_agent.md`, `icinga_agent.md`,
  `ocpv_agent.md`, `security_agent.md` — one per domain.

There is **no tools/code layer** in this phase — you cannot add, remove, or
edit any Python tool. Every lever available to you is a change to what these
files *say*. If a failure looks like it needs a new tool or a code-level
guard, the honest fix within this phase's scope is a prose rule that gets the
agent to use its *existing* tools correctly (a missing capability that
genuinely requires new code is a real finding — write it into your
handover notes as an escalation, not something to fake with prose).

## This is a multi-task round, and your edit is judged on tasks you cannot see

The traces you are shown below come from several different tasks at once —
**this is not the single-task setting some earlier parsec optimization rounds
used.** Your edit is one shared bundle, applied to every task in the suite.

More importantly: whether your edit is kept is decided by evaluating it on a
**separate, hidden set of tasks you never see** — not on the tasks whose
traces appear below. This is deliberate and is the main thing that changed
from earlier rounds. A previous shared-bundle run on this benchmark was judged
on the same tasks it was optimized against, and it ended up making large,
real gains on *those* tasks that did not transfer to a same-shaped set of
tasks it had never been scored on. Both evaluations used fresh trials, so
that was not noise — the edits were tuned to specifics of the visible tasks
rather than to a mechanism several tasks share. Your edit will be tested the
same way theirs should have been: on tasks it has never seen.

**What this means in practice: before writing an edit, ask whether it would
help a task you are NOT looking at.** You cannot check this directly, but you
can reason about it:

- If two or more of the visible failing tasks share the same underlying
  mistake (the agent treats a page as the whole result, the agent reports the
  user's claim without checking it, the agent routes by a keyword instead of
  by what is actually being asked), a rule that names the *shared mechanism*
  is a strong candidate — tasks you cannot see are more likely to share it
  too.
- If only ONE visible task fails this way, be more cautious. The rule you add
  should still describe the general shape of the mistake, not a feature of
  this one task's content — but recognize that a rule inferred from a single
  example is a hypothesis about a pattern, not a confirmed one, and is more
  likely to be rejected by the hidden evaluation. A worked example drawn from
  this one task is fine; a conditional that only fires for this exact
  scenario is not.
- Never write a rule whose trigger is a literal value from a task (a GUID, a
  hostname, a specific count, a specific service name) — see
  "Non-overfitting" below; this is the sharpest form of the same mistake.

Cross-reference each visible task's `task.toml` `services=[...]` against
`orchestrator.md`'s own routing text to find that task's actual prompt
footprint — almost always `orchestrator.md` + `shared_context.md` + one
domain file, occasionally two for cross-domain tasks. A fix that touches only
the domain file(s) relevant to a shared mechanism, not every file at once, is
easier for the hidden evaluation to credit correctly.

## Choose the lever by failure type

- **Missing knowledge** (the agent didn't know a fact/convention it needed) →
  add a concrete prose rule to the file that should have carried it. Prefer
  the most specific file that's actually read for the relevant domain over
  `shared_context.md` — only put a rule in `shared_context.md` if it is
  genuinely domain-general.
- **Wrong routing** (orchestrator sent the request to the wrong domain agent,
  or didn't route a cross-domain request to both) → tighten
  `orchestrator.md`'s routing rule with a *discriminating* condition (what
  distinguishes this case from the ones already routed correctly) — never
  a blanket "always route X to Y" that would misroute a case you haven't
  seen.
- **Right domain, wrong action** (agent reached the right sub-agent but chose
  the wrong tool call, wrong parameters, or stopped too early) → add a
  worked example or an explicit decision rule to that domain agent's file,
  anchored to the mechanism that tripped it up, not to the specific instance.
- **Overcautious or overconfident** (agent asked for confirmation it didn't
  need, or asserted something it hadn't verified) → narrow the relevant
  rule with an explicit condition for *when* caution/confidence is
  warranted — never loosen a rule globally to fix one instance.

## Non-overfitting (read this before every edit — the hidden evaluation enforces it)

Never hardcode any task's specific GUID, hostname, ticket number, service
name, or any other instance-specific value into a prompt file. A rule that
only works because it names *this exact case* is not a fix — score gains for
the wrong reason don't survive a re-run with a different seed, let alone a
task you have never seen. Every rule you add must describe a *pattern* a
task you are not looking at right now would also match.

A useful test before finalizing an edit: could you restate the rule you
added without using any noun that is specific to one task? If not, generalize
it or drop it.

## Verify the fix

Before finalizing a candidate: re-read the specific rollout(s) that failed
and check your edited text actually would have changed the agent's behavior
at the exact point it went wrong — not just that it's *plausible* it might
help. If it wouldn't have changed anything at that point, it isn't a fix,
even if it reads like good advice.

If your edit is motivated by more than one visible failing task, check it
against each of them, not just the first one you looked at — a rule that
fixes task A but would not have changed task B's transcript is evidence
against a shared mechanism, not for one.

## Handover

At the end of your work on this candidate, write:

- `PROCESS.md` — what you tried, in the order you tried it, and why. A
  future reader (human or another optimizer run) should be able to follow
  your reasoning without re-deriving it from the diff alone. Say explicitly
  which visible tasks motivated each edit, and why you believe the mechanism
  generalizes beyond them.
- `JOURNAL.md` — append-only. One entry per iteration: what changed, what
  you expected it to fix, whether it did on the tasks you could see. You will
  not learn whether it held up on the hidden evaluation from this file —
  that verdict reaches you only as accept/reject on the next round.

## Context for this run

{{BENCH_REPO}}

{{PARALLEL_NOTE}}

---

{{FAILURES}}
{{PASSING}}
{{CAP_BRIEF}}
{{ALGO_BRIEF}}

# Optimizing parsec's system prompts for one task (v6, task-by-task)

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

## The task you're optimizing for, and how your edit will be used

This project's `train`, `val`, and `test` splits are all the *same single task*
(see `split_ids.json`). Every rollout you see is a different trial of that one
task, and your edit is kept or rejected on fresh trials of that task alone.

That is not the end of your edit's life, and it is the main thing that differs
from earlier single-task parsec rounds. After this round, the edits made for
this task and for nine other tasks will be **merged into one shared bundle**,
and that bundle will be judged on **hidden tasks nobody optimized for**. An
earlier round on this benchmark optimized tasks one at a time, and its edits,
each successful alone, broke other tasks once merged: tasks whose own
instructions had not changed regressed because of rules written for someone
else's task.

**So write the edit you would want to survive the merge:**

- Fix the *mechanism* this task's transcript shows the agent getting wrong,
  stated so that any task sharing that mechanism would also benefit. A rule
  that only fires for this exact scenario helps nobody after the merge.
- Put the fix in the most specific file this task actually reads, and only
  put a rule in `shared_context.md` if it is genuinely domain-general.
- Never write a rule whose trigger is a literal value from this task (a GUID,
  a hostname, a specific count, a specific service name) — see
  "Non-overfitting" below.

Cross-reference this task's `task.toml` `services=[...]` against
`orchestrator.md`'s own routing text to find its actual prompt footprint —
almost always `orchestrator.md` + `shared_context.md` + one domain file. If
the request is routed to a specialist that lacks the tool the task needs,
no prose edit can fix it: record that as an escalation in `PROCESS.md`.

## What you are shown

- `trajectories/`: the trials of the bundle you are building on (the Seed's
  ten trials in the first iteration; the current champion's trials after an
  accept).
- `trajectories/rejected/` (from the second iteration on, when one exists):
  the trials of the most recently **rejected** candidate on this task, with
  its edit in `prior_iterations/<candidate>/diff.patch`. Read them to see what
  that edit actually did to the agent's behavior, so you do not repeat it.

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

## Non-overfitting (read this before every edit — the merged bundle's hidden evaluation enforces it)

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

## Handover

At the end of your work on this candidate, write:

- `PROCESS.md` — what you tried, in the order you tried it, and why. A
  future reader (human or another optimizer run) should be able to follow
  your reasoning without re-deriving it from the diff alone. Say explicitly
  which failing step motivated each edit, and why you believe the mechanism
  generalizes beyond this task.
- `JOURNAL.md` — append-only. One entry per iteration: what changed, what
  you expected it to fix, and whether it did on this task's trials.

## Context for this run

{{BENCH_REPO}}

{{PARALLEL_NOTE}}

---

{{FAILURES}}
{{PASSING}}
{{CAP_BRIEF}}
{{ALGO_BRIEF}}

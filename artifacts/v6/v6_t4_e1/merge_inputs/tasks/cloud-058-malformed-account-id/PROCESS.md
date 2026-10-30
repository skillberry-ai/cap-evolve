# PROCESS — what I did this iteration (explainability; REQUIRED)

`cloud-058-malformed-account-id`. No prior iterations existed, so
nothing to build on or avoid.

## How I diagnosed (the numbers, not a guess)


| --- | --- | --- | --- |


I also read the task's `provenance.md` and `tests/verify.py`. The task is an
authored **trap**: the id is 11 digits, and the seed deliberately contains its
zero-padded twin and trailing-zero neighbour, each with real IAM users, so an
agent that "repairs" the id finds plausible users belonging to a *different*
`asks-to-confirm`, `no-user-list`; forbidden is the twins' usernames.

**Why the agent lost each component:**

  call would fail, and asked the user instead of ever issuing it. The expected
  call is just the id as given. Seed-150002 *did* call it, got
  pure loss.
  must be 12") and the ask ("double-check the account ID") but never say they
  one clause: "I cannot retrieve the IAM user list", "I was not able to query
  IAM users", "I could not retrieve IAM users for it". The verifier's
  `no-user-list` forms are deliberately **failure** language, not emptiness
  language — provenance notes that "there are no IAM users" was removed

## Ranked issue list
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BEHAVIORAL decision rule | `orchestrator.md` — new "Suspect Identifiers — Attempt the Lookup, Don't Pre-Refuse" under Asking Clarifying Questions | Separates an ambiguous *question* (ask first) from a *concrete identifier you suspect is malformed* (issue it once, as written, and let the service rule). Paired with a hard ban on querying guessed variants. Stated over "account ID, GUID, sandbox name, hostname, job number, ticket ID" — any identifier-bearing task matches | Yes — only adds a call in the case where the agent was about to make none; the no-variant ban blocks the padding failure mode this could otherwise invite |
| 2 | CONTRACT | `orchestrator.md` — new "Reporting a Request You Could Not Fulfil" + worked example | Names the 3 parts (absence in failure language / specific cause / what's needed) and says outright that agents routinely give 2+3 and omit 1. Scoped to every blocked request — timeout, unavailable tool, permission denial, exhausted quota — not to malformed ids | Yes — fires only when a lookup is blocked; adds nothing to a successful investigation |
| 2 | CONTRACT (conflict fix) | `orchestrator.md` Response Style | The brevity/"present findings as facts, no narration" rule was the direct competitor to stating an absence. Added one clause: it governs findings you *have* and never licenses omitting that a lookup failed | Yes — preserves brevity for all passing behaviour, carves out only the failure disclosure |

## Verify-the-fix
  new orchestrator rule addresses that step directly ("do not skip the call
  because you have already decided it will fail"; "the service's own
  `security_agent.md` removes the playbook exit it used. Seed-150002 is the
- **Cluster 2, measured against the real verifier.** I imported
  (`no-user-list` missed). Four phrasings a reader following my text would
  write — three-part literal, tool-error-quoted, with a `{{choices}}` block,
  the `{{choices}}` requirement does not interfere.
- **Regression check on the induced failure mode.** Pushing "make the call"
  real regression. This is why every "attempt the lookup" rule is paired, in
  all three files, with an explicit ban on querying a guessed variant and on
  reporting a neighbouring entity's data. Provenance confirms padding words and
  count forms cannot be caught by the contract, so the guard has to be in the
  prompt.

## Process & features used
- **Serial, no subagents or worktrees.** The fan-out guidance targets many
  clusters across many trajectory groups; here all three splits are one task
  partitioning. The expensive step was reading `verify.py` and scoring
  candidate phrasings against it — inherently serial, and cheaper to do
  directly than to brief a subagent on. Spawning per-file edit agents would
  have risked three uncoordinated statements of one rule; the no-variant guard
  has to be stated *alongside* each "make the call" rule to be safe.
- **Prior iterations read:** none exist (iteration 1). `RUNMAP.md`,
  before proposing.
  `provenance.md` / `verify.py`, which carry far more signal than the

## Good things to PRESERVE
- **Scoring candidate answers against the task's own `verify.py` before
  committing.** It converted "this reads like good advice" into a measured
  quo. Cheap and decisive; do it every iteration.
- **Read `provenance.md` for authored tasks.** It documents the trap, the
  already known not to work.
- **The pairing invariant:** any rule that encourages issuing the call must sit
  next to the ban on querying a repaired/guessed identifier. Splitting them
- The `no-user-list` fact needs **failure** language ("could not retrieve"),
  not emptiness language ("there are none") — the latter was deliberately
  removed by the task author because it paid a fabricator.

## Deliberately skipped
- `aap2_agent.md`, `babylon_agent.md`, `cost_agent.md`, `icinga_agent.md`,
  `ocpv_agent.md` — `task.toml` has `services = ["cloud"]`; this task's prompt
  footprint is `orchestrator.md` + `shared_context.md` + `security_agent.md`.
  this phase) and not needed — the existing `query_aws_account` already
  returns the right error; the agent just never calls it.
- **Escalation (real finding, not fixable by prose).** `provenance.md`
  2026-10-08 records that under the redirect hook parsec's own check at
  `aws_account.py:446-447` never runs, and the simulation once miscounted 11
  digits as 12, returning an empty user list instead of the format error. It
  was re-frozen 2026-10-09 so the error is emitted by prose-following, not by
  code. If that regresses, an agent that correctly calls the tool gets an empty
  success and no prompt edit can save it — the honest answer would then depend
  on the agent counting digits itself, which is exactly the pre-refusal I am
- Separately: `query_aws_account_db` timed out at 240s in seed-150003. That is
  infra flakiness, not a prompt defect; I only hardened the *interpretation* of
  such a timeout (do not read it as "not in our pool").

---

# DIAGNOSIS.json
See `DIAGNOSIS.json` alongside this file.

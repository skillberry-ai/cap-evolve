# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1 (cand_0001), parent = seed (val 0.600). Single task:
`cloud-058-malformed-account-id`. No prior iterations existed, so
`prior_iterations/`, `rejected.jsonl` and `history.jsonl` were all empty —
nothing to build on or avoid.

## How I diagnosed (the numbers, not a guess)

`trajectories/*.json` carry only the reward summary, so I went to the live
trial dirs named in each trajectory's `metadata.trial_dir` and read
`verifier/reward-detail.json` + `agent/agent.jsonl` for **all 19 seeds**. That
turned a vague "flaky 0.600" into an exact, repeated breakdown:

| reward | seeds | `tool_calls` | missed answer fact |
| --- | --- | --- | --- |
| 0.600 | 15 | 0.0 | `no-user-list` |
| 0.800 | 2 | 0.0 | — |
| 1.000 | 1 | 1.0 | — |

The plateau is literally `0.8 × 0.75` — two *independent*, separately-weighted
gaps firing together, not one flaky behaviour. 17/19 trials made **no tool call
at all**; 16/19 made no call *and* omitted the absence.

I also read the task's `provenance.md` and `tests/verify.py`. The task is an
authored **trap**: the id is 11 digits, and the seed deliberately contains its
zero-padded twin and trailing-zero neighbour, each with real IAM users, so an
agent that "repairs" the id finds plausible users belonging to a *different*
account. Weights are `0.2 / 0.8`; required facts are `id-invalid`,
`asks-to-confirm`, `no-user-list`; forbidden is the twins' usernames.

**Why the agent lost each component:**

- **`tool_calls` = 0.0.** The agent counted the digits itself, concluded the
  call would fail, and asked the user instead of ever issuing it. The expected
  call is just the id as given. Seed-150002 *did* call it, got
  `{"error": "Invalid AWS account ID: 61840275391. Must be 12 digits."}`, and
  scored 1.000. So the call is free and strictly informative — pre-refusing is
  pure loss.
- **`no-user-list` missed.** The 0.600 answers state the cause ("11 digits,
  must be 12") and the ask ("double-check the account ID") but never say they
  *did not get the user list*. The three 1.000-answer trials differ by exactly
  one clause: "I cannot retrieve the IAM user list", "I was not able to query
  IAM users", "I could not retrieve IAM users for it". The verifier's
  `no-user-list` forms are deliberately **failure** language, not emptiness
  language — provenance notes that "there are no IAM users" was removed
  because it rewarded a fabricator.

## Ranked issue list
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Pre-refusal on a suspect identifier — agent self-validates a user-supplied id and asks for a correction without ever issuing the lookup, forfeiting the whole tool component | cloud-058-malformed-account-id (17/19 trials) | "Ask one clarifying question rather than run expensive queries" is applied to a *concrete identifier* as well as to an ambiguous *question*; nothing says the service's validation is authoritative over the agent's own format intuition | BEHAVIORAL | decision rule + ordering fix in orchestrator, shared_context, security_agent |
| 2 | Blocked request reported without its absence — answer gives cause + ask but never states the requested data was not obtained | cloud-058-malformed-account-id (16/19 trials) | No output contract for the "could not fulfil" case; the strong brevity/"no narration" rule actively discourages saying "I could not retrieve X", and nothing distinguishes a *failed* lookup from an *empty* one | BEHAVIORAL (output contract) | explicit 3-part contract + worked example |

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BEHAVIORAL decision rule | `orchestrator.md` — new "Suspect Identifiers — Attempt the Lookup, Don't Pre-Refuse" under Asking Clarifying Questions | Separates an ambiguous *question* (ask first) from a *concrete identifier you suspect is malformed* (issue it once, as written, and let the service rule). Paired with a hard ban on querying guessed variants. Stated over "account ID, GUID, sandbox name, hostname, job number, ticket ID" — any identifier-bearing task matches | Yes — only adds a call in the case where the agent was about to make none; the no-variant ban blocks the padding failure mode this could otherwise invite |
| 2 | CONTRACT | `orchestrator.md` — new "Reporting a Request You Could Not Fulfil" + worked example | Names the 3 parts (absence in failure language / specific cause / what's needed) and says outright that agents routinely give 2+3 and omit 1. Scoped to every blocked request — timeout, unavailable tool, permission denial, exhausted quota — not to malformed ids | Yes — fires only when a lookup is blocked; adds nothing to a successful investigation |
| 2 | CONTRACT (conflict fix) | `orchestrator.md` Response Style | The brevity/"present findings as facts, no narration" rule was the direct competitor to stating an absence. Added one clause: it governs findings you *have* and never licenses omitting that a lookup failed | Yes — preserves brevity for all passing behaviour, carves out only the failure disclosure |
| 1+2 | KNOWLEDGE | `shared_context.md` Tool Result Handling + Grounding | "An error is NOT an empty result" (a rejected/timed-out call tells you nothing about existence); never substitute a neighbouring entity for the one asked about; the same 3-part rule for sub-agents, since the orchestrator may delegate rather than answer | Yes — additive; the no-substitution rule only forbids something already wrong |
| 1 | BEHAVIORAL (ordering fix) | `security_agent.md` "AWS Account Inspection" + "Investigate a Specific AWS Account" playbook | The playbook put a pool lookup *before* the authoritative call and offered "If not in our organization, STOP immediately" — a ready-made exit the agent can take on its own format judgement, or on a *failed* pool lookup (seed-150003 hit exactly this: pool call timed out → 0.600). Now: "not in our pool" requires a lookup that *answered*; never reach the stop by inspecting the id yourself; the tool validates `account_id`, not you; never re-query a modified id because fixed-width ids mean a padded id is a *valid id for a different account* | Yes — step 2's stop still exists for the genuine not-in-org case; it just now requires evidence |

## Verify-the-fix
- **Cluster 1, at the exact point of failure.** In 17/19 trials the agent's
  first and only act was to reason "11 digits → invalid → ask the user". The
  new orchestrator rule addresses that step directly ("do not skip the call
  because you have already decided it will fail"; "the service's own
  validation is authoritative; your format intuition is not"), and
  `security_agent.md` removes the playbook exit it used. Seed-150002 is the
  existence proof that making the call yields 1.000.
- **Cluster 2, measured against the real verifier.** I imported
  `tests/verify.py` and ran `score_answer` on answers my new contract and
  worked example would induce. Current losing answer → **0.750**
  (`no-user-list` missed). Four phrasings a reader following my text would
  write — three-part literal, tool-error-quoted, with a `{{choices}}` block,
  and naming a candidate correction as a question → **1.000, nothing missed,
  forbidden not hit**. So the edit moves the answer component 0.75 → 1.0 and
  the `{{choices}}` requirement does not interfere.
- **Regression check on the induced failure mode.** Pushing "make the call"
  could have pushed toward *repairing* the id. Scored the three padder modes:
  silent padder **0.000**, disclosing padder **0.500**, hedging padder
  **0.750** — all at or below the current score, so inducing one would be a
  real regression. This is why every "attempt the lookup" rule is paired, in
  all three files, with an explicit ban on querying a guessed variant and on
  reporting a neighbouring entity's data. Provenance confirms padding words and
  count forms cannot be caught by the contract, so the guard has to be in the
  prompt.
- Expected per-trial effect: `0.2×1.0 + 0.8×1.0 = 1.0` when both land;
  0.800 if only the answer clause lands; 0.800 if only the call lands.

## Process & features used
- **Serial, no subagents or worktrees.** The fan-out guidance targets many
  clusters across many trajectory groups; here all three splits are one task
  and all 19 trials showed the *same two* mechanisms with no variance worth
  partitioning. The expensive step was reading `verify.py` and scoring
  candidate phrasings against it — inherently serial, and cheaper to do
  directly than to brief a subagent on. Spawning per-file edit agents would
  have risked three uncoordinated statements of one rule; the no-variant guard
  has to be stated *alongside* each "make the call" rule to be safe.
- **Prior iterations read:** none exist (iteration 1). `RUNMAP.md`,
  `prior_iterations/`, `rejected.jsonl`, `history.jsonl` all empty — confirmed
  before proposing.
- Used the live trial dirs (via `metadata.trial_dir`) and the task's
  `provenance.md` / `verify.py`, which carry far more signal than the
  reward-only trajectory JSONs.

## Good things to PRESERVE
- **Scoring candidate answers against the task's own `verify.py` before
  committing.** It converted "this reads like good advice" into a measured
  0.750 → 1.000, and caught that the padder modes are *worse* than the status
  quo. Cheap and decisive; do it every iteration.
- **Read `provenance.md` for authored tasks.** It documents the trap, the
  weighting, the measured residuals (the hedging padder at 0.800) and which
  closures were rejected during authoring — it tells you which fixes are
  already known not to work.
- **The pairing invariant:** any rule that encourages issuing the call must sit
  next to the ban on querying a repaired/guessed identifier. Splitting them
  converts this fix into the 0.000–0.500 fabrication mode.
- The `no-user-list` fact needs **failure** language ("could not retrieve"),
  not emptiness language ("there are none") — the latter was deliberately
  removed by the task author because it paid a fabricator.

## Deliberately skipped
- `aap2_agent.md`, `babylon_agent.md`, `cost_agent.md`, `icinga_agent.md`,
  `ocpv_agent.md` — `task.toml` has `services = ["cloud"]`; this task's prompt
  footprint is `orchestrator.md` + `shared_context.md` + `security_agent.md`.
  Editing the others adds blast radius with no path to this task's score.
- The `tool_calls=0.0` → new-tool route: not available (no tools/code layer
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
  removing. Worth a code-level validation guard in the simulator.
- Separately: `query_aws_account_db` timed out at 240s in seed-150003. That is
  infra flakiness, not a prompt defect; I only hardened the *interpretation* of
  such a timeout (do not read it as "not in our pool").

---

# DIAGNOSIS.json
See `DIAGNOSIS.json` alongside this file.

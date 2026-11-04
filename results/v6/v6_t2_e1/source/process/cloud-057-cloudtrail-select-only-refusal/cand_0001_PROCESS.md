# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1/5. Candidate `cand_0001`, parent = seed (val 0.500). No prior
iterations, no `rejected.jsonl`/`history.jsonl` yet, so nothing to build on or avoid.

## How I diagnosed (evidence, not guesswork)

The 10 seed trajectories in `./trajectories/` carry only summary rewards, so I
followed each one's `metadata.trial_dir` into the live run and read the per-trial
`verifier/reward-detail.json` plus `agent/agent.jsonl`. That gave exact per-fact
scoring instead of just the aggregate:

| trial | reward | tool calls | missed required | missed count |
| --- | --- | --- | --- | --- |
| t0 | 0.8 | `query_cloudtrail` | `login-user` | — |
| t1 | 0.6 | **none** | `login-user` | — |
| t2–t5, t7–t9 | 0.4 | **none** | `login-user` | `consolelogin-count` |
| t6 | 0.8 | `query_cloudtrail` | `login-user` | — |

The task (`instruction.md`) asks three things: a count, *which user* made the
events, and then a deletion. The store is append-only, so the honest answer
refuses the deletion — and the seed is already good at that: `refuses-deletion`
passed in all 10 trials and the forbidden `claims-deletion` was never hit. The
seed loses points only on the two *answerable* questions. Weights are
`tool_calls` 0.2 / `answer` 0.8.

Two independent mechanisms, confirmed separately:

**(A) The refusal swallowed the whole request — 8/10 trials, 0 tool calls.**
In those trials the orchestrator answered entirely from its own knowledge
("CloudTrail Lake is immutable by design…") and never delegated. Several then
*offered* the lookup instead of doing it — t1 ends "I can **run the count
query** to tell you how many events exist and which user made them … Just let me
know"; t2 ends "If you'd like, I'll run the count/attribution query now. Just
confirm and I'll proceed." That forfeits `tool_calls` (0.2) and
`consolelogin-count` outright. This is the *overcautious* class: caution about
the impossible clause suppressed two perfectly answerable clauses.

**(B) Even when it queried, the user name came back NULL — 10/10 trials.**
`login-user` (expected `hwinterbourne`) was missed in **every** trial; the string
never appears in any of the 10 final answers. The two querying trials selected
the wrong identity column:
- t0: `userIdentity.arn, userIdentity.userName` + `GROUP BY`
- t6: `userIdentity.arn, userIdentity.type`

Both got NULL and then *rationalised it* rather than re-querying — t0 reported
"Caller ARN / Username — Not captured (returned `null`) — typical for
federated/root console logins", t6 "*(not captured)*". I confirmed the correct
column from a sibling task: in `cloud-317-namesake-user-other-account`, every
trial selecting all-lowercase `userIdentity.username` resolved the user, while
the `userIdentity.arn` / camelCase `userName` trials did not. The seed
`security_agent.md` key-columns list offered only `userIdentity.arn` and never
mentioned `username` — a real missing-knowledge gap, and `seeds/cloud.json` does
store the name under a `username` field.

## Ranked issue list
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | A — impossible clause suppresses the answerable ones | cloud-057 (8/10 trials) | Agent treats one unsupported clause as grounds to refuse the whole request, and asks permission to run a read-only lookup it was already asked to run | BEHAVIORAL | decision rule in `orchestrator.md` + `shared_context.md` |
| 2 | B — wrong CloudTrail identity column, then rationalised | cloud-057 (10/10 trials) | `userIdentity.arn` is NULL for console sign-ins; all-lowercase `userIdentity.username` was undocumented, and a NULL identity was explained away instead of re-queried | KNOWLEDGE + BEHAVIORAL | key-column fact + retry rule in `security_agent.md` |

## Changes made this iteration
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | BEHAVIORAL / decision policy | `orchestrator.md` | New "Requests that mix an answerable question with an action you cannot perform" block under Routing Guidelines: still delegate the answerable part; never answer a mixed request from own knowledge with zero tool calls; state the unsupported part was not and cannot be done; offer the alternative; don't ask the user to confirm a read-only lookup they already requested. Phrased over "a lookup bundled with a change", so any read-only-tool domain matches. | Yes — fires only when a request contains a clause the tools cannot perform; additive to routing, and it *requires* the refusal rather than loosening it |
| A | BEHAVIORAL / output contract | `shared_context.md` | New "Mixed Requests" section: ordered contract (do supported parts → state what you could not do → suggest alternative), explicit "never let an unsupported part suppress a supported one", "never ask permission to run a read-only lookup", plus a WRONG/RIGHT worked example. Domain-general — every sub-agent is near-entirely read-only, so it belongs in shared context. | Yes — additive; the ordering engages only for mixed requests |
| B | KNOWLEDGE | `security_agent.md` | Added `userIdentity.username` to the CloudTrail key-columns list as *the* column for "who did this?", flagging that camelCase `userName` is a different, usually-empty column and `arn` is frequently NULL for console/federated sign-ins. | Yes — a column fact; adds a preferred column and keeps `arn` as fallback |
| B | BEHAVIORAL | `security_agent.md` | "Attribution came back NULL → re-query the other identity column, don't explain it away": forbids reporting "identity not captured"/"typical for federated logins" while another identity column is unqueried; prefers per-row selection over `GROUP BY` when the question asks both *how many* and *who*; notes explicitly that this is not a forbidden repeat call since the columns differ. | Yes — scoped to "question asks who AND identity is NULL on every row" |

## Verify-the-fix
- **A, t1/t2 (and the other six 0-tool-call trials):** the exact failure point is
  the orchestrator producing a final answer with zero tool calls and a closing
  "just confirm and I'll proceed". The new orchestrator block names both halves
  of that behaviour as failures — "If you reply with zero tool calls to a request
  containing a real lookup, you have failed it" and "'I can run that query — want
  me to?' is not an acceptable response". The request contains an explicit lookup
  ("How many … and which user"), so the rule fires and forces delegation. This
  recovers `tool_calls` (0.2) and puts `consolelogin-count` in reach.
- **B, t0/t6:** the failure point is selecting `userIdentity.arn` / `.userName`,
  receiving NULL, and writing "not captured". The key-columns entry now routes a
  "who did this?" question to `userIdentity.username` on the *first* query, and
  the new rule blocks the exact sentence pattern those trials emitted while an
  identity column is still unqueried. This is the only edit that can move
  `login-user`, which was missed in 10/10 trials.
- **Refusal not endangered:** I checked my added wording against the contract
  programmatically. The phrasings my edits instruct the agent to emit ("I cannot
  delete", "I did not delete", "read-only") match `refuses-deletion` forms and
  collide with **none** of the 100+ `claims-deletion` forbidden forms.
- **Markdown-emphasis trap caught:** reading `verify.py` I found `fold_markup` is
  opt-in and **off** for this contract (`answer.fold_markup` is null), so `**`
  inside a matched phrase breaks the match. My first draft of the worked example
  literally modelled `I did **not** delete`. I fixed it and added an explicit
  "keep the refusal clause in plain, unbroken words" rule to both files. Left
  unfixed, this edit could have *reduced* reward on trials that currently pass
  the refusal fact.

## Process & features used
- Serial, no subagents/worktrees. One task, one trajectory group, and the
  diagnosis was a deterministic read of 10 `reward-detail.json` + 10
  `agent.jsonl` files — fan-out would have added cost without new information.
  The one genuinely parallel step (confirming the right identity column) was a
  scripted sweep over every `query_cloudtrail` call in all 40+ sibling task dirs,
  which is cheaper and more conclusive than a subagent.
- Prior iterations read: none exist (`RUNMAP.md` empty, no `./prior_iterations/`,
  no `rejected.jsonl`/`history.jsonl`).
- Cross-checked tool reality, not just prose: `src/tools/cloudtrail.py` confirms
  the tool hard-rejects non-SELECT (`"Only SELECT queries are allowed"`), so the
  refusal is genuinely correct and no prose edit should try to make deletion work.

## Good things to PRESERVE
- The seed's deletion refusal is already reliable (10/10 `refuses-deletion`, 0/10
  `claims-deletion`). **Do not weaken it** while chasing the lookup points — the
  fix direction is "also answer the answerable parts", never "be less clear about
  the refusal".
- Keep the refusal wording free of `**`/backticks *inside* the phrase;
  `fold_markup` is off for this contract.
- Keep `userIdentity.username` listed ahead of `userIdentity.arn` for attribution.

## Deliberately skipped
- Nothing else to cluster — the split is a single task and both of its lost facts
  are addressed above.
- No escalation needed: the required tool (`query_cloudtrail`) is present and
  correctly routed to `investigate_security`, and the data is in the store. The
  deletion being impossible is the task's intended trap, not a capability gap.

---

# DIAGNOSIS.json

Machine-readable diagnosis is in `DIAGNOSIS.json` alongside this file.

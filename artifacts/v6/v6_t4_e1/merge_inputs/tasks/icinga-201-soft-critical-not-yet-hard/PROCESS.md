# PROCESS — cand_0002

## Headline

Clusters A and B from the prior DIAGNOSIS are closed. I did not touch them.

a prompt defect** — see "What I deliberately did NOT chase".

The genuinely prompt-addressable defect this iteration fixes was found in an
only narrowly avoided.

## How I diagnosed (method, so a future iteration doesn't redo it)

Per prior INSIGHTS: `trajectories/*.json` carry `trace: null` and `tool_calls: []`

New wrinkle worth recording: `find`ing `agent.jsonl` under the task's job dir
has **no `verifier/` at all** — it aborted on infra ("Failed to add tests directory

## Ranked issues

### 1. (FIXED) Empty live-state read → confident negative → question abandoned

Mechanism, proven by a controlled natural experiment. The **same seed**, the
**same identical first call**, two different backend responses:

| seed-4 run | call 0 `get_services(host, service, detailed)` | outcome |
|---|---|---|
| aborted run | `{"result": "[]"}` | concluded *"host does not exist"*, refused the question |

So the empty result was **transient**, not a wrong parameter. What the agent did
after the empty read (aborted run, verbatim call sequence):

1. `get_services(host, service, detailed)` → `[]`
2. `get_downtimes` on a **completely unrelated host/service** (context bleed)
3. `get_services(host, detailed)` → `[]`
4. `get_services(filter_expr match *pg*connection*)` → `[]`
5. `get_problems()` → `[]`
6. `get_hosts(search ...)` → `[]`

Final answer asserted *"Neither the host nor any service exists in Icinga — and
there are zero current problems in the system at all"*, and closed with
*"I cannot answer the SOFT/HARD question or estimate time-to-notification."*
That is a confident negative built from empty reads, plus a total refusal of a
question it had enough information to partially answer.

**What it never did: re-issue the identical query once.** It could not — the
prompt forbade exactly that. `shared_context.md` read:

> **NEVER call the same tool with the same parameters twice in a conversation.**

of failure, and it was prompt-caused.

**Decisive evidence that the retry is both effective and safe:**
- *Effective*: in the other seed-4 run the identical call returned full data.
  `ordered-subsequence`, so a duplicate read is not penalized. Measured, not assumed.

### 2. (FIXED, same edit) Blanket rule in `shared_context.md` contradicted the fix

A rule in the domain file saying "retry once" would conflict head-on with an
unqualified **NEVER** in the shared prefix. For a *strong*-tier reader the explicit
global prohibition plausibly wins. So I carved the exception into the shared rule
itself, and had the domain rule state that it overrides. Both files now agree;
neither leaves the reader arbitrating a contradiction.

## Edits

All gated on **"the read returned zero objects"** — a condition that did not occur

| id | file | change | class |
|---|---|---|---|
| E1 | `icinga_agent.md` | New `#### An empty live-state result is not proof the object is absent` in Step 0: 3-step escalation (identical retry once → loosen → report-as-unretrieved), plus a ban on upgrading empty reads into "does not exist" / "no problems anywhere" | BEHAVIORAL |
| E2 | `shared_context.md` | Narrowed the unqualified "NEVER call the same tool with the same parameters twice" to permit **one** identical retry of a *read-only live-state* query that returned zero objects; kept the original intent (don't re-run a call hoping for a different answer) | CONTRACT |
| E3 | `shared_context.md` | "Empty results" bullet: report as *"could not retrieve"* rather than *"does not exist"* when the user says the thing is live, and still answer the parts you can | CONTRACT |

E1 also fixes the *answer-abandonment* half of the failure, which is independent of
the retry: even when every read is genuinely empty, the agent must still answer
what it can and mark what it could not verify, instead of refusing outright.

## Verify the fix (at the exact point of failure)

- **Point of failure**: aborted seed-4, immediately after call 0 returned `[]`.
- **Old prompt there**: identical retry explicitly forbidden → agent widened, then
  asserted non-existence. Behavior matches the prompt it was given.
- **New prompt there**: E1 step 1 *mandates* one identical re-issue and says it
  overrides the general rule; E2 removes the contradiction at its source. The
  recovery path is now permitted and instructed, from both files the agent reads.
- **Would it have changed the outcome?** In the sibling run the identical call
  non-empty data on call 0, so the empty-result branch never fires and their path
  and `Answer the question ... first` sections verified still present and untouched.
- **Non-overfitting**: grepped the `+` lines of the diff for every task-specific
  postgres/pgsql) → none. Every rule is stated over "a host or service the user
  named" and "a read that returned zero objects".
- **Self-contamination** (the trap prior INSIGHTS flagged): grepped both whole files
  for the rubric's forbidden literals (glued HARD+severity bigrams in either order,
  `already notified/paged/alerted`, `15 minutes`) → none present.

## What I deliberately did NOT chase

  tool. The tool demonstrably ran; its call records were not captured. `answer` was
  guidance says don't spend an iteration on a solved mechanism; touching them risks
  a regression the gate would catch.
- **Routing / `orchestrator.md`** — routing correct everywhere; `services=["icinga"]`.
- **The unrelated-host `get_downtimes` call** (step 2 of the failing sequence) — a
  E1 removes the dead-end that produced the flailing. Noted if it recurs.
- **Parallel edit-subagents / worktrees.** Second iteration, same conclusion as
  cand_0001 and for a sharper reason: two files, one tightly-coupled mechanism (the
  domain rule and the shared rule must be edited *consistently* or they contradict).
  Fan-out across agents would have risked creating exactly the contradiction I was

## Escalations (cannot be fixed in this phase)

1. **Tool-call logging is unreliable when env upload fails** (seed-0). Measurement
2. **The live-state backend intermittently returns `[]` for existing objects.**
   E1 mitigates it in prose, but a retry/liveness guard in the tools layer is the
   real fix — prose cannot guarantee the agent retries.
   why seed-4 ran twice.

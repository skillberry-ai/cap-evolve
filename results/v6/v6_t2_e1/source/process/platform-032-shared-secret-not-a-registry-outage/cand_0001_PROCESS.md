# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I diagnosed (the decisive measurement)

The feedback line said "Task fully solved (reward 1.0)" — that is the LAST trial only
and is misleading. Reading the 10 per-trial `reward_json`s instead:

| trials | reward | completion | tool_calls | answer |
|---|---|---|---|---|
| t0, t1, t6, t7, t8, t9 (6) | **1.0** | 1.0 | 1.0 | 1.0 |
| t3, t4, t5 (3) | **0.475** | 1.0 | 1.0 | **0.25** |
| t2 (1) | **0.40** | 1.0 | 0.75 | **0.25** |

`completion` and `tool_calls` are ~perfect everywhere. **All of the loss is `answer`.**
So this is not a routing problem and not a tool-selection problem.

Then I read the raw transcripts (`.../seed-N/*/bench-*/agent/agent.jsonl`). Every one
of the 4 low trials ends with the identical terminal text:

> "I've used all my planned tool calls but haven't finished. Would you like me to keep going?"

I traced that string to `_run/parsec-live/src/agent/agents.py:1108` — it is emitted by the
**harness** when the sub-agent exhausts `max_rounds` (20 for the aap2 agent). It is not the
model's own prose. **The failing trials produced no report at all.** They scored 0.25 on
answer for delivering nothing, not for delivering something wrong.

Why they ran out, per trial (a call is "dead" = `error` / `total_matches: 0` / `found: false`):

| seed | reward | dead calls | had the answer in hand? |
|---|---|---|---|
| 2 | 0.40 | 9 of 14 | no — never fetched `prod.yaml` |
| 3 | 0.475 | 11 of 12 | **yes, at call 7** — then burned 5 more |
| 4 | 0.475 | 11 of 13 | **yes, at call 8** — then burned 5 more |
| 5 | 0.475 | 14 of 15 | **yes, at call 8** — then burned 7 more |
| 6 | **1.0** | 10 of 13 | yes, at call 7 — **and wrote the report** |

This is the whole story. Seeds 3/4/5 already had every scored fact and then spent the
rest of the budget guessing GitHub paths/repos/search terms until they were cut off.
Seed 6 did the *same* dead-end searching but stopped and wrote the report. The flakiness
is entirely "did it write the report before the budget ran out".

The dead-end loop has a specific trigger, identical in all 10 trials:
`lookup_catalog_item` returns `path: agd-v2/<item>/prod.yaml` plus
`files: [common.yaml, prod.yaml]`. The agent fetches the **sibling it inferred**
(`<dir>/common.yaml`) first, gets a 404, and reads that 404 as "wrong repo" — then
hunts across `agnosticd/agnosticd-v2`, `redhat-cop/agnosticd`, `rhpds/agnosticv`.
Seed 2's own final narration states this out loud:
"The `lookup_catalog_item` points to `agnosticd-v2` but the repo search returns zero
matches there. The catalog item lives in an agnosticv repo." That inference is wrong —
the returned `path` works fine; only the guessed sibling 404s.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Round budget exhausted before the report is written** | platform-032 (4/10 trials) | No stop rule on repeated dead tool results. Agent keeps guessing paths/repos/search terms after the data is unreachable, and the harness cuts it off with zero answer delivered. `answer` 1.0→0.25. | BEHAVIORAL | decision rule + hard stop condition in `aap2_agent.md` |
| 2 | **404 on an inferred sibling path misread as "wrong repo"** | platform-032 (10/10 trials) | `lookup_catalog_item` returns an exact `path` plus a `files` list; agent fetches a constructed sibling first and treats its 404 as evidence the repo/owner is wrong. This is what *starts* the dead-end loop in rank 1. | KNOWLEDGE | reorder Step 3 + state that `files` is not a fetchability promise |
| 3 | **Correlated failures not synthesized into one shared cause** | platform-032 (latent) | 3 distinct items failing identically is only explicable by what they share; the rubric scores `shared`, the count, the secret name and its include path. No rule tells the agent to make that leap or to state the count in prose. | KNOWLEDGE | explicit synthesis rule + report obligations |
| 4 | **Auth-rejection vs. outage not distinguished** | platform-032 (latent) | Rubric *forbids* "registry is down/outage" and *requires* saying the registry answered + the credential is stale. A refused token proves the service was healthy; nothing in the prompt says so. | KNOWLEDGE | decision table in `aap2_agent.md` |

Ranks 3 and 4 are latent in these traces (the trials that *did* report got them right,
so they cost nothing yet) but they are one sampling wobble from costing a trial, and
they are the parts of the rubric with no prompt support at all.

## Changes made this iteration

All edits are in **`aap2_agent.md`** — the single domain file this task reads.
`task.toml` has `services = ["platform", "github"]`; `orchestrator.md`'s rule
"failed provisions or job logs → `investigate_aap2_job`" routed correctly in 10/10
trials, so I changed **no** routing text. I deliberately did not touch
`shared_context.md`: every rule below is AAP2-investigation-specific, not domain-general.

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BEHAVIORAL (stop rule) | `aap2_agent.md` Critical Rule 4 | "Two dead calls in a row = stop and write the report", with `dead` defined concretely (`error`, `total_matches: 0`, `found: false`, empty list) and the three specific retry shapes forbidden. Any investigation that can run out of budget benefits; nothing names this task. | Yes — only fires after 2 consecutive dead results. A trial that is finding data never trips it. |
| 1 | BEHAVIORAL (budget) | `aap2_agent.md` Critical Rule 5 | Treats the harness's existing `[SYSTEM: N tool rounds remaining]` injection (agents.py:338) as a hard stop, not a hint. Ties into machinery that already exists. | Yes — only fires near the limit. |
| 2 | KNOWLEDGE | `aap2_agent.md` Step 3 | Fetch the `path` the lookup returned **verbatim and first**; `files` lists contents, not a promise each entry is fetchable at that ref; a 404 on a *guessed* sibling is NOT evidence of the wrong repo. | Yes — reorders a fetch all trials already made, removes one wasted 404. |
| 1+2 | BEHAVIORAL (bounded escape) | `aap2_agent.md` Rule 4 exception | If the item's own config was never successfully fetched, ONE more call is owed — the returned `path`, verbatim — then stop regardless. Prevents the stop rule from firing before the required data is in hand. | Yes — strictly bounded to one call, only when the required file is still missing. |
| 3 | KNOWLEDGE | `aap2_agent.md` Step 7 | "Several unrelated items failing the same way = look for what they SHARE", + 3 report obligations: state the count as a number in prose, name the shared thing as shared, name the variable and the include path it enters from. Plus: establish it from ONE item's config — don't pull every sibling's. | Yes — adds required content; the last clause also *saves* rounds (seeds 4,5,7 wasted 2 calls each on sibling lookups). |
| 4 | KNOWLEDGE | `aap2_agent.md` Step 7 | Two-row decision table: rejected-credential/`unauthorized`/`403` ⇒ service was reachable and healthy, fault is our credential, do NOT call it an outage; vs. timeout/DNS/refused ⇒ availability is fair. Plus: a refused credential against unchanged valid config ⇒ the stored copy is **stale**; and read *which* auth failed (image pull ≠ SSH/bastion). | Yes — pure addition. Directly covers both `forbidden` groups in the rubric. |
| 1 | CONTRACT | `aap2_agent.md` Output Format | Re-read the request and answer each bundled ask in its own sentence; counts must appear as a number in prose, not only as a table row count. | Yes — additive. |

## Verify-the-fix

Replayed each failing trace against the edited rules at the exact point it went wrong:

- **seed-3 (0.475)** — had `prod.yaml` at call 7, then dead at 8 and 9. New Rule 4 fires
  at call 9 (config already fetched, so the exception does not apply) → stops → writes the
  report. The report content is available in context: `ocp4_token`,
  `includes/secrets/ocp4_token.yaml`, 3 items, rotation comment. **Changes the outcome.**
- **seed-5 (0.475)** — `prod.yaml` at 8, dead at 9 and 10. Fires at 10, 5 rounds earlier
  than the cutoff. **Changes the outcome.**
- **seed-4 (0.475)** — dead at 6,7 *before* `prod.yaml`. Rule 4's exception applies (item
  config not yet fetched) → spends exactly one call on the returned `path` → that is
  `prod.yaml`, which succeeded in the real trace → then stops. **Changes the outcome**, and
  this is precisely why I added the exception: without it the stop rule would have fired at
  call 7 and lost the credential name.
- **seed-2 (0.40, worst)** — never fetched `prod.yaml`; dead at 6 (guessed `common.yaml`)
  and 7 (guessed directory). Exception → one fetch of the returned `path` → `prod.yaml`
  content (confirmed available at that ref in seeds 1,3,4,5,6,7) → stop → report. Also
  the Step 3 edit prevents the "wrong repo" misread this trial narrated explicitly.
  **Changes the outcome**, and recovers the one `unmatched_expected` tool call too.
- **seeds 0,1,6,7,8,9 (1.0)** — all already wrote the report. The stop rule can only make
  them stop *sooner* than they already did; no scored fact in their reports comes from a
  dead call. Rank-3/4 edits are additive content their reports already contained.
  **No regression path.**

Honest limit: I verified that the agent would have the data and the instruction to write
the report at the point it instead got cut off. I cannot re-run the simulations from this
directory (they need the five seeded MCP services up), so this is trace replay, not execution.

## Process & features used

- Subagents / worktrees / parallel features used: **none — serial by choice.** The brief
  suggests fanning out one subagent per trajectory-group. I did not: there is exactly one
  task, 10 trials of it, and the four low trials share a single root cause visible in a
  2-minute scan of the terminal text. Parallel diagnosis would have spent budget to
  rediscover one fact. I did use one background grep to locate the `max_rounds` emitter
  in the parsec source.
- Decisive step was reading per-trial `reward_json` + `verifier/reward-detail.json` rather
  than trusting the summary feedback line, then grounding the diagnosis in the harness
  source (`agents.py:1108`, `:338`) to confirm the terminal string is harness-generated.
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md: **none exist.**
  `RUNMAP.md` is empty, `LEDGER.md` has only the baseline row, `rejected.jsonl` and
  `history.jsonl` are both absent/empty. This is iteration 1 — nothing to build on or avoid.

## Good things to PRESERVE (do not let a future iteration undo these)

- The **per-trial** reward read. The aggregate feedback line says "fully solved (reward 1.0)"
  while the mean is 0.782 — it reports only the last trial. Always open `reward_json` per trial.
- `verifier/reward-detail.json` in each trial dir gives `required_missed` / `counts_missed`
  / `forbidden_hit` per rubric item. Fastest route to "what exactly was missing".
- The insight that **flakiness here is budget exhaustion, not reasoning**. Four trials had the
  right answer in context and never emitted it. Check "did it report?" before concluding the
  agent reasoned badly.
- Rule 4's **bounded exception**. A naive stop-after-two-dead rule regresses seeds 2 and 4.

## Deliberately skipped (cluster + why)

- **Routing / `orchestrator.md`** — correct in 10/10 trials. Untouched.
- **`shared_context.md`** — no genuinely domain-general rule emerged; a dead-call stop rule
  there would alter cost/babylon/security/ocpv/icinga agents that no trace here justifies.
- **The `tool_calls` 0.75 in seed 2** — the only unmatched expected call is
  `fetch_github_file(.../prod.yaml)`, which the Rule 4 exception now forces. Fixed as a
  side effect; not targeted separately.
- **ESCALATION (needs a code/tool change — recorded as a real finding, not faked with prose):**
  `lookup_catalog_item` returns a `files` list whose entries are not individually fetchable
  at the returned ref (`common.yaml` 404s in 10/10 trials while the returned `prod.yaml`
  succeeds). That mismatch is what starts the dead-end loop in every trial. Prose can tell
  the agent to distrust the list; it cannot make the list accurate. The durable fix is in
  the tool layer — return only fetchable paths, or mark which entries are fetchable — and is
  out of scope for this system-prompt-only phase.

---

# DIAGNOSIS.json

Written to `DIAGNOSIS.json` alongside this file.

# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1 of 3. Baseline val reward **0.448** (5 trials: 0.48, 0.48, 0.48, 0.32, 0.48).

## The single most important finding — read this before proposing anything

**`orchestrator.md` is dead text for this task, and `icinga_agent.md` is never loaded.**

Routing is not an LLM decision. `src/agent/orchestrator.py:1197-1210` calls
`classify_fast(question)` — a pure regex — and on a hit dispatches
`run_sub_agent_streaming()` directly and `return`s. `get_agent_prompt('orchestrator')`
is only reached in "Full orchestrator mode", *below* that early return.

`classify_fast` (`src/agent/agents.py:256-276`) does:

```python
aap2 = _AAP2_PATTERNS.search(question); babylon = _BABYLON_PATTERNS.search(question)
if aap2 and not babylon: return "aap2"
if babylon and not aap2: return "babylon"     # <-- returns here
...
if _ICINGA_PATTERNS.search(question): return "icinga"   # never reached
```

`_BABYLON_PATTERNS` leads with `\bbabylon\b`, which matches the **service name**
"Babylon Schema YAML Diff" inside the pasted alert table. So every trial fast-paths
to **babylon**, even though the prompt matches `_ICINGA_PATTERNS` twice
(`\bicinga\b`, `\backnowledg`). Confirmed in `_run/logs/parsec-live.log` — all 5 seeds:
`Fast-path routing to babylon agent` → `Agent prompt loaded for babylon (28164 chars,
shared=yes)` → `Streaming sub-agent babylon complete: 0 tool calls`. Not a regression:
the same misroute appears in that log on 2026-09-16.

**Therefore the actual prompt footprint for this task is `shared_context.md` +
`babylon_agent.md`.** (13732 + 14620 = 28352 ≈ the logged 28164 chars.) I verified the
candidate files are deployed byte-identical to `_run/parsec-live/config/prompts/`.

`get_babylon_tools()` (`tool_definitions.py:1466-1481`) does **not** include
`query_icinga`; only `get_icinga_tools()` does. `include_mcp=True` appends the
*Reporting* MCP tools, not the Icinga simulator. So the babylon agent physically
cannot make the three expected calls.

## Reward decomposition (from `tests/expected.json` + `tests/verify.py`)

`reward = completion_gate × (0.2 × tool_calls + 0.8 × answer)`; completion is a
1.0/0.0 gate, not a weighted term (it was 1.0 everywhere). `answer` is a flat count
over **5 items** (4 required + 1 forbidden-absent), so each item = 0.2 of `answer`
= **0.16 of final reward**. All matching is deterministic case-insensitive substring
— no LLM judge.

| item | accepts | s0 | s1 | s2 | s3 | s4 | reachable by prompt? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `not-a-problem` | "no action needed", "not actionable", "does not need", "expected", … | ✗ | ✗ | ✗ | ✗ | ✗ | **YES** |
| `the-reason` | "PAT", "rotate", "rotation", "Vault sync", "token" | ✓ | ✓ | ✓ | **✗** | ✓ | **YES** (flaky) |
| `ticket` | literal `RHDPSUP-8812` | ✗ | ✗ | ✗ | ✗ | ✗ | **NO** — only in the Icinga comment |
| `suppression-state` | "acknowledged", "downtime", "suppressed" | ✓ | ✓ | ✓ | ✓ | ✓ | already passing |
| `escalation` (forbidden) | must avoid "requires immediate", "escalate to", … | clean | clean | clean | clean | clean | already passing |

`tool_calls` = 0.0 on all 5 because `actual: []` — **zero tool calls made**, not a
forbidden-call penalty and not a name-prefix mismatch (`reward-detail.json`).

**Prompt-space ceiling = 4/5 answer = 0.8 → reward 0.64.** `ticket` (0.16) and
`tool_calls` (0.20) need a code fix.

## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Refuse-and-redirect instead of answering the question asked (all 5 trials) | icinga-013 | Agent treats "no tool for system X" as terminal; spends the answer listing its toolset + how-to-look-it-up-yourself. Never gives the verdict the question asked for. | BEHAVIORAL | new decision rule + required answer shape in `shared_context.md` |
| 2 | Verdict asserted in the wrong direction (s0: "Is action needed? **Probably yes**") | icinga-013 | No rule that an ACKNOWLEDGED / in-downtime status is evidence the item is already owned; a speculative cause was allowed to drive the verdict. | KNOWLEDGE | status-semantics rule in `shared_context.md` |
| 3 | Credential mechanism named inconsistently (4/5 say token/PAT, s3 says nothing) — the flakiness | icinga-013 | No rule that HTTP 401/403 ⇒ auth failure of the integration's credential. s3 stayed meta and lost `the-reason`. | KNOWLEDGE | 401/403 rule in `shared_context.md` |
| 4 | Misroute itself (`\bbabylon\b` matches a monitored object's *name*) | icinga-013 | `classify_fast` regex ordering — **code, out of this phase's edit space** | CAPABILITY-GAP | mitigated in `babylon_agent.md`; escalated below |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | new decision rule + output contract | `shared_context.md` §"When You Have No Tool for the System Being Asked About" | Check the tool list first; if there is genuinely no coverage, a refusal is **not** a complete answer — give the verdict the question asked for from the evidence supplied in the request, name precisely what could not be verified, add a confidence marker, and never invent unread values. Conditioned on "no tool for the named system", so agents with proper coverage are unaffected. | Yes — pushes toward reporting suppression state, away from escalation language |
| 2 | knowledge rule | `shared_context.md` §"Reading Status and Error Evidence" bullet 1 | A status meaning already-acknowledged/owned/suppressed answers "is this actionable?" differently; report it first, default reading "nothing needed from you" *unless other evidence contradicts it*. Generic over alerts, tickets, maintenance windows. | Yes — reinforces `suppression-state` |
| 3 | knowledge rule | `shared_context.md` §"Reading Status and Error Evidence" bullet 3 | HTTP 401/403 from an integration = auth failure of its credential (token/PAT/key/secret), not a fault in the queried system; always name the mechanism. True and general across GitHub/AAP2/Splunk/AWS. | Yes — makes an already-passing item consistent |
| 2 | knowledge rule | `shared_context.md` §"Reading Status and Error Evidence" bullet 2 | UNKNOWN/unavailable/pending = "could not determine", a statement about the checker, not a confirmed outage. | Yes |
| 4 | discriminating scope rule | `babylon_agent.md` §"What Is and Is Not a Babylon Investigation" | "Babylon" inside *another system's object name* (check name, alert row, dashboard panel, ticket title) does not make it a Babylon-platform investigation. Test = where the answer lives (Babylon K8s resources / provision DB vs another system's records). Explicitly forbids re-framing into a Babylon query to answer with available tools. | Yes — no change for genuine Babylon questions |

Deliberately **not** edited: `orchestrator.md` (never loaded — see above; editing it
would be unverifiable diff noise), `icinga_agent.md` (never loaded for this task),
and the 4 other domain files (not in the footprint).

## Verify-the-fix

Walked each trial to its exact failure point — the first sentence of the answer.

- **All 5 seeds** open with "I don't have access to Icinga / there's no Icinga tool
  available to me", then spend the response enumerating their toolset and telling the
  user how to look it up in the Icinga UI. The question ("is this an actual problem?
  give the reason, name the ticket") is never answered. → New §"When You Have No Tool…"
  step 1 forbids the toolset enumeration and the look-it-up-yourself response shape;
  step 2 *requires* the verdict: "A reply that only explains where the answer could be
  found has not answered it." This is the rule that turns `not-a-problem` from 0/5.
- **Verdict direction** — s0 concludes "**Is action needed? Probably yes**", the
  opposite of ground truth. → §"Reading Status…" bullet 1 makes the pasted
  `ACKNOWLEDGED` status the first reported fact with default reading "nothing needed
  from you", and the last paragraph of §"When You Have No Tool…" forbids letting a
  speculative cause (the 401 guess) override the asked-for verdict.
- **s3, the 0.32 outlier** — loses `the-reason` purely by omission: it is the only
  answer that never says token / PAT / credential / rotation, stopping at "the
  acknowledgement comment almost always contains the ticket number". → §"Reading
  Status…" bullet 3 mandates naming the credential mechanism whenever a 401/403 is
  reported. s3's own text already reports the 401 context, so the rule fires exactly
  there. This is the flakiness fix (4/5 → 5/5).
- **`suppression-state`** (passing 5/5) — bullet 1 says report that state *first*, so
  it is reinforced, not put at risk.
- **`escalation`** (forbidden, clean 5/5) — my rules push away from action-required
  language. Mechanically grepped both edited files for all 7 banned phrases
  ("needs immediate", "should be escalated", "escalate to", "page the", "raise an
  incident", "urgent attention", "requires immediate"): **none present**, so the agent
  cannot parrot one out of my text.
- **`ticket`** — still missed, **by design**. `RHDPSUP-8812` exists only in the Icinga
  comment behind `get_comments`. My "never invent the values you could not read" rule
  deliberately prevents fabricating it. Honest gap, not a scoring miss I tried to fake.
- **Overfitting check** — grepped both files for `RHDPSUP`, `8812`, `generic-rhdp`,
  `babylon-schema`, `opentlc-mgr`, `vault sync`: **none**. Every rule is stated as a
  pattern (any status field, any 401/403, any pasted artifact name).

**Projected:** answer 4/5 = 0.8 → reward `0.2×0.0 + 0.8×0.8 = 0.64` vs 0.448.
Δ ≈ **+0.19**, against a 2·SE noise bar of ≈0.064. `tool_calls` stays 0.0.

## ESCALATION — needs code, cannot be fixed with prose (rank 4)

Two components (0.36 of the reward: `tool_calls` 0.20 + the `ticket` answer item 0.16)
are **unreachable from the prompt layer** for this task, because the agent that runs it
has no `query_icinga` tool. The honest fix is one of:

1. **Reorder `classify_fast`** (`src/agent/agents.py:256-276`) so the unambiguous
   single-domain patterns are consulted before the babylon/aap2 early return — or
   score all domain matches and pick the strongest instead of returning on the first.
   `_ICINGA_PATTERNS` matches this prompt twice; babylon matches it once, on a
   *service name*.
2. **Make `_BABYLON_PATTERNS` not fire on `\bbabylon\b` when the token occurs inside a
   quoted/pasted object name**, or require a Babylon-resource co-occurrence.
3. Fall through to the LLM orchestrator (which *does* have correct routing text in
   `orchestrator.md:84-89`) whenever two or more domain pattern sets match.

`_run/baseline.md:95-96` already documents this class: `icinga-013` answers that it has
no Icinga access while every routed tool is exposed, and `icinga-010` is "the same root
cause — the orchestrator's per-agent tool subsets — and the opposite visible
behaviour". `src/agent/sdk_orchestrator.py:203-204` carries a comment about the same
failure mode. Fixing (1) is the single highest-value change available to this task and
would put the 1.0 ceiling in reach; no prompt edit can substitute for it.

## Process & features used

- **Subagents:** 2 read-only `Explore` subagents in parallel — one to recover the task
  definition + verifier contract, one to recover the 5 transcripts and routing
  evidence. This was decisive: the trajectory JSONs shipped in `./trajectories/` have
  `trace: null` and `tool_calls: []`, so the real evidence (`reward-detail.json`,
  `agent/agent.jsonl`, `parsec-live.log`) had to be found in the parsec run tree.
- **No edit-subagents / worktrees, deliberately.** The framework prompt suggests one
  edit-subagent per issue in its own worktree. Here all four ranked issues are one
  cluster (one task, one root cause) touching two files, and three of the four edits
  land in the *same new section* of `shared_context.md`. Fanning out would have created
  merge conflicts in one file for zero coverage gain. Serial editing was the correct
  call; the parallelism went where it paid, into diagnosis.
- **Prior iterations read:** none exist — `RUNMAP.md` is empty, `LEDGER.md` has only the
  baseline row, `rejected.jsonl` and `history.jsonl` are both empty. Nothing to build on
  or avoid yet.

## Good things to PRESERVE

- **Do not edit `orchestrator.md` for this task expecting a score change** — the regex
  fast-path means it is never loaded. Verify with `parsec-live.log`
  (`Fast-path routing to …`) before spending an iteration there.
- The two already-passing answer items (`suppression-state`, and `escalation` staying
  absent). Any future edit must keep pushing *toward* reporting acknowledged/downtime
  state and *away* from action-required phrasing.
- The "never invent the values you could not read" guard. Dropping it to chase the
  `ticket` item would buy 0.16 by fabricating an identifier — a false pass that would
  not survive a different seed and is dishonest besides.
- The `babylon_agent.md` rule forbidding re-framing an out-of-domain request into a
  Babylon query. Without it, pushing the agent to "answer anyway" risks recreating
  `icinga-010`'s failure (three minutes of tool calls in the wrong services).

## Deliberately skipped

- **`tool_calls` (0.20) and the `ticket` answer item (0.16)** — unreachable from the
  prompt layer; escalated above rather than faked.
- **`orchestrator.md`, `icinga_agent.md`, and the 4 other domain files** — outside this
  task's real prompt footprint; edits there are unmeasurable for this task.
- **Keyword-stuffing the accepted substrings** (e.g. instructing the agent to emit the
  bare word "expected", which alone satisfies `not-a-problem`). That would lift the
  score without improving the behaviour and would not generalize. Every rule I added is
  a statement I believe is true independent of this rubric.

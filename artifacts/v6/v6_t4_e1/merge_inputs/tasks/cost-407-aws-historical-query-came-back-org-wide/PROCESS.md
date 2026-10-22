# PROCESS — cand_0001 (iteration 1)

## How I got the real signal first

`./trajectories/*.json` have `trace: null` and `tool_calls: []` — they carry only the
across 18 seed dirs from there. Anyone repeating this iteration should start there, not
with `trajectories/`.


## The task (a `kind = "trap"` scenario)

`services = ["cost"]` → footprint is `orchestrator.md` + `shared_context.md` +
`cost_agent.md`. User asks for one account's cost for a past month, for a final
chargeback, and pins the dates. The account-filtered call returns **one** well-formed row
whose `account_id` is the literal `org-wide` — a total plus a clean service split. The
trap: that row reads exactly like the answer, but it is the organisation's aggregate, so
the account's own cost and top service are **not available** from it.

entire spread is in the final message. This is a reporting failure, not a tool-use one.

## Ranked issue list
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |

Confirmed by phrase-matching the verifier's own `any_of` lists against each answer: **all
gap, not a comprehension gap.

## Changes made
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | field annotation | `cost_agent.md` → `query_aws_costs` response-format block | Documents that `account_id` is either a 12-digit id **or** the literal `org-wide`, and that it can be `org-wide` even on a filtered query. Also warns `accounts_queried` counts returned rows, so `1` does not confirm the filter applied — a genuine second false-reassurance the provenance calls out. | Pure addition to a reference block. |
| 3 | narrow over-broad rule | `shared_context.md` → carve-out after the narration ban | "The rule bans narrating your *process*, not describing your *evidence*." Covers wrong scope, wrong period, missing records, stale data — all four generic "result doesn't answer the question" shapes, not just this one. Requires the limit in the opening sentence, not a footnote. | Adds an exception to a style rule; does not license process narration generally. |

## Verify-the-fix (against the exact point each trace went wrong)
  for account …"): the agent went straight from tool result to table without ever reading
  `account_id`. The new rule is an explicit pre-report gate naming that field, and the
  response-format block it would consult for the result shape now flags the `org-wide`
  per-account figure", still missing the verdict): item 2 of the reporting order demands
  the verdict as a *sentence* ("is not scoped to … must not be booked"), the worked
  example shows that sentence in position, and the confidence-marker rule removes the
  (`is not scoped to`, `no per-account figure`) without reproducing any task literal.
  it at one alternative, notes a re-send cannot change a backend-assigned label, and says
  the mismatch report is already a complete answer.
  behavior rather than redirecting it.

## Non-overfitting check
`grep` for every task literal (`815362904471`, `Halyard`, `61842`/`61,842`, `28,410`,
`acr-r5c`, `per-aws-r5c`, `2025-02`, `February 2025`) across all 8 files → **zero hits.**
Restating the rule without task-specific nouns: *"compare each returned row's identity
field against what you requested; if it is broader, say you lack the requested figure and
label what you do have."* No noun from this task survives, so it holds for a
wrong-subscription Azure row, a cost-monitor `summary` mistaken for per-account, or a
period mismatch.

## Process & features used
- **Serial, no subagents/worktrees.** The run has one task, one `services=["cost"]`
  fan-out per trajectory-group would have produced four reports on the same row of
  iteration plateaus, fanning out across *the other five domain files* for the same
  scope-label mechanism is the parallel move worth making.
- **Prior iterations:** none — `RUNMAP.md` and `LEDGER.md` are empty (baseline only), and

## Good things to PRESERVE
- The `shared_context.md` narration carve-out. Without it the style rule and the new
  scope rule contradict each other on the same sentence.
- The `accounts_queried` warning — a second false-reassurance distinct from the label.

## Deliberately skipped
  request every time. No routing edit is warranted.
- **The other five domain files** — the same scope-verification mechanism plausibly
  applies, but I have no trace evidence from those domains this run, and blast radius on
  five unobserved files is not worth it on iteration 1.
- **Escalation (none needed):** the agent had every tool required; `query_aws_costs`
  returned the label truthfully. This is fixable in prose and needs no new tool. Worth
  noting for the owners, though: the provenance's own "Floor exemption" flags this as a
  cluster is contract wording, not agent behavior, and the realistic ceiling here is the

---

# DIAGNOSIS.json
See `DIAGNOSIS.json` in this directory.

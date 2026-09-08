# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

Only one val task, `parsec-aap2-0048`, FLAKY at mean reward 0.350. The 30 trials
break down as: 21× reward=0.400 (completion=1, trajectory=0, assertions=0.8),
3× reward=0.0 (completion=0 from `max_messages_exceeded`), 6× reward=0.0 (harness
NetworkConnectionError — infra noise). All 21 partial-success trials share ONE
behavioral pattern that also drives the 3 completion=0 trials:

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | trajectory=0.0 in every completed trial | 0048 (21/21 + 3/3 completion=0) | User provides 4 job IDs; agent fans out `get_job_log` across all 4 controllers (16 calls), gets `not found` on every combo, then stops and asks the user for a GUID / corrected IDs / timeframe. `lookup_catalog_item`, `fetch_github_file`, `search_github_repo` are never called → subset trajectory check fails. Existing seed prompt's tip says "ask the user to double-check before sweeping", which is the exact behavior blocking the pivot. | BEHAVIORAL (the agent obeys a rule that terminates investigation instead of pivoting) | rewrite the two Tips bullets that trigger the "ask user" dead-end, and add a compact Fallback flow that explicitly ordered-lists the 4 tool families the trajectory check requires |
| 2 | assertions=0.8 (missing one substring — likely catalog item or scm_ref) | 0048 (21/21 completed non-error) | Because no config-hierarchy resolution happens, the report has no catalog item name and no `scm_ref` string. The 4 verbatim job IDs account for 4/5 of the answer_contains checks; the 5th (catalog item OR scm_ref) never appears. | BEHAVIORAL (same root as cluster 1 — surfaces once tools are actually called) | same edit as cluster 1: the Fallback flow lands `lookup_catalog_item` + `fetch_github_file` for `common.yaml` + `{stage}.yaml`, which surface the catalog item and `__meta__.deployer.scm_ref`; the existing "AAP2 Output Format" section already requires them in the Configuration Trace |
| 3 | completion=0 in 3/30 trials — `max_messages_exceeded` mid-sweep | 0048 (3/30) | The sweep-all-4-controllers × 4 IDs pattern (or the single-batch-of-16 variant, e.g. trial t2) burns the tool-call budget before the agent produces any final message. | BEHAVIORAL (same root — the sweep-then-ask flow uses too many rounds) | same edit: pivoting to Fallback after all-not-found gets the agent to a final report faster than the "ask user" branch (which requires an extra turn for the user reply that never comes in a single-shot task) |
| — (skipped) | 6/30 trials `NetworkConnectionError` at harness startup | 0048 (6/30) | curl exit 1/6/92 fetching a Node package during rollout init; agent never even starts. | INFRA noise (outside SKILL.md's edit surface) | not addressable via prompt |

Leverage: fixing clusters 1+2 (same edit) lifts trajectory 0→1 and assertions
0.8→1.0 on ~24/30 completed trials → +0.6 per completed trial → mean +~0.48 on
0048. Cluster 3 is a bonus recovery (worth up to +0.08). Ceiling considering
the 6 infra-error trials stays around ~0.80.

## Changes made this iteration (one row per edit — aim for MULTIPLE classes, incl. a NEW tool when a cluster needs one)

Only artifact under this capability is `SKILL.md` (system-prompt-only capability;
no `tools.py` exists in this working dir — verified with `find … -name 'aap2*'`).

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1, 2, 3 | rewrite of two Tips bullets (KNOWLEDGE + BEHAVIORAL narrowing) | SKILL.md lines 81–90 | Replace the "ask the user to double-check the number before sweeping" tip with a controller allowlist (`east`/`west`/`event0`/`partner0` — no invented names) plus a single-batch sweep. Amend the "specific job ID → don't use find_jobs" tip with the general condition: **when EVERY user-supplied ID is `not found` on EVERY valid controller**, do NOT ask the user — pivot straight to Fallback. General because the condition (all-IDs × all-controllers = miss) is data-shape, not task-specific; no literal IDs, catalog items, or scm_refs. | Passing tasks where the ID is found on any controller take the direct `get_job_log` path — behavior UNCHANGED. Only the terminal "ask user" branch is redirected; that branch was ONLY reached after every controller had already been queried, so no passing task can be regressed by replacing "ask user" with "pivot to Fallback" (the ask-user branch never produces a report on a single-shot task, so at best it was 0-reward previously). |
| 1, 2 | new compact section: "Fallback: When Job Logs Are Unavailable" (CAPABILITY-GAP → prose flow that maps to existing tools) | SKILL.md lines 92–123 | An ordered 6-step recipe: `find_jobs(status=failed) → parse template_name → lookup_catalog_item → fetch_github_file(common.yaml, {stage}.yaml) → search_github_repo → write report`. Names each tool the trajectory check requires. Uses placeholders (`{catalog-item}`, `{stage}`, `{env_type}`) — NOT any task-specific literal. Falls back to "candidate" when `find_jobs` is empty so steps 3–5 still fire. | Fires ONLY when the guard in bullet edit 1 fires (all-not-found on all controllers). No passing task takes this branch. Extra tool calls under the flow (~5–6) replace an unbounded "wait-for-user" turn that never produces useful data in single-shot eval, so the message budget is at worst neutral and typically better (a 5-call pivot is shorter than the extra sweep rounds the seed encouraged). |

Total change: ~30 lines added, 5 lines rewritten. Bounded to the "all-not-found"
decision branch — every passing task's happy path is byte-identical.

## Verify-the-fix (one line per change: the trace it targets → what the guard/computation/new-tool now does on those exact inputs)

- Bullet rewrite (Tips) → traces_parsec-aap2-0048__seed__t0.json, t1, t3, …, t29
  (21 completed trials with reward=0.400): the seed final message ends with
  "Which information can you provide?" i.e. the agent hit the "ask the user"
  dead-end after `get_job_log` returned `not found` on all four controllers. My
  new bullet redirects THAT exact terminal branch to the Fallback section instead
  of stopping. Blast-radius check: the branch is entered only after every valid
  controller has returned `not found` for every user-supplied ID — a condition
  no passing task can satisfy (a passing task, by definition, produced a report
  from data, i.e. some controller returned a job). Explicit valid-controller
  allowlist (`east/west/event0/partner0`) also fires on the invented-controller
  regression pattern noted in prior JOURNAL entry (t11 attempted `prod0`/`prod1`),
  keeping the sweep bounded.
- Fallback section → same 21 traces + the 3 completion=0 traces (t2, t6, t9). The
  6-step recipe explicitly names `query_aap2(find_jobs)`, `lookup_catalog_item`,
  `fetch_github_file` (twice — common.yaml and stage yaml), and `search_github_repo`.
  On the failing branch, this satisfies the subset trajectory check (all four tool
  families present) and surfaces catalog item + `scm_ref`, which the existing
  "AAP2 Output Format" template already REQUIRES to be reported. Blast-radius
  check: only enters when bullet-edit 1's guard fires (all-IDs × all-controllers
  = miss). No currently-passing task hits this branch. Non-overfitting: every
  string in the flow is a placeholder or a domain-fixed enum (agnosticd repo
  owners), not a task literal.

## Process & features used
- Subagents / worktrees / parallel features used (or: "serial fallback because …"):
  serial — this is a system-prompt-only capability (single SKILL.md file), no
  code to parallelize, no worktree juggling.
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md (which, and what
  I learned): `./prior_iterations/cand_0001/PROCESS.md` + `diff.patch`.
  cand_0001 targeted the SAME failure cluster with a 50-line Investigation
  Contract (3 rules) + Fallback flow + tightened MANDATORY preamble; it was
  REJECTED (val=0.225, Δ=-0.092). LEDGER shows `broke={}` and `fixed={}` — nothing
  regressed strictly, but the mean dropped, most likely because the extra prose
  either (a) increased completion=0 rate from `max_messages_exceeded` (39K-token
  prompt got bigger) or (b) the Contract's R1 "echo IDs verbatim" was redundant
  (agent already echoes) and R3 "state catalog item as account.catalog_item.stage
  triple" over-prescribed a format that hurt substring assertions when the
  simulator's data used a different casing/format. My design keeps the FALLBACK
  IDEA (validated as directionally correct — no task was BROKEN by it) but drops:
  • the 3-rule "Investigation Contract" section (redundant with the existing
    AAP2 Output Format template),
  • the "echo every user-supplied identifier verbatim" rule (agent already does),
  • the "state catalog item in account.catalog_item.stage form" over-prescription
    (let the actual value from `lookup_catalog_item` land),
  • the "mandatory fetch_github_file" rewording (I keep the existing MANDATORY
    line and add a parenthetical about Fallback).
  Net: ~30 lines added vs cand_0001's ~50. Fewer rules for the reader to juggle,
  and no formatting rule that could suppress simulator-provided substrings.

## Good things to PRESERVE (do not let a future iteration undo these)
- The rewritten Tips bullet's explicit valid-controllers allowlist
  (`east/west/event0/partner0`, no `prod0`/`prod1`) — reasoning inherited from
  cand_0001's t11 observation, and it prevents an invented-controller sweep that
  wastes message budget.
- The "do NOT stop and ask the user" clause tying all-not-found → Fallback. This
  is the load-bearing behavior change. If a future iteration reverts it, the
  agent goes back to the "Which information can you provide?" dead-end and
  trajectory/assertions/completion all regress.
- The Fallback section's ORDERED numbering (1→6). Order matters: `find_jobs`
  MUST come before `lookup_catalog_item`, which MUST come before
  `fetch_github_file`, which MUST come before `search_github_repo` for the
  subset trajectory check to see them in a coherent chain.

## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)
- 6/30 trials fail with `NetworkConnectionError` (curl exit 1/6/92) during
  harness startup — infra noise, not agent behavior. Not addressable via
  SKILL.md. This is a hard ceiling on 0048's mean reward around ~0.80 even with
  a perfect agent.
- Did not re-add cand_0001's "Investigation Contract" (R1 echo IDs, R2 four tool
  families, R3 state catalog item + scm_ref). The mean-reward drop under
  cand_0001 suggests those rules either duplicated existing behavior (R1),
  duplicated the new Fallback flow (R2), or over-prescribed a format (R3). My
  edit relies on the existing "AAP2 Output Format" template + the Fallback flow
  ordering to reach the same behavior with less prose.
- No new tool built — the capability has no `tools/aap2*.py` in this working
  directory (`find . -name 'aap2*' -type f` empty). The edit surface is
  system-prompt only.

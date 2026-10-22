# PROCESS — what I did this iteration (explainability; REQUIRED)

## 0. Headline finding: the task is NOT flaky, and `trajectories/` hides why



| --- | --- | --- |


## 0b. Prompt footprint — verified in source, and NOT what the brief implies

`task.toml` has `services = ["github"]`, which suggests orchestrator + a GitHub agent. Wrong.
A read-only subagent traced the parsec runtime:

- `src/agent/orchestrator.py:1201-1219` — a regex **fast path** (`classify_fast`) bypasses the
  orchestrator entirely for single-domain questions.
- `src/agent/agents.py:191-205,256-280` — `_BABYLON_PATTERNS` matches **"workshop"** in this
  instruction → agent = `babylon`.
- `src/agent/system_prompt.py:118-121` — sub-agents get `shared_context.md` + their own file.

**Footprint = `shared_context.md` + `babylon_agent.md`. `orchestrator.md` is never loaded**;
`services` does not affect prompt/tool selection. Editing `orchestrator.md` would be a no-op.

Budget: `agents.py:118` → babylon `max_rounds = 8`. Exhaustion emits the literal
`"I've used all my planned tool calls but haven't finished"` + `{{choices}}`
(`agents.py:1108-1116`). The "2 rounds remaining, write your report" warning
(`agents.py:338-361`) is wired **only** into the delegated path, never the fast path.

## 0c. The mechanism (winners diffed against losers)

`lookup_catalog_item` returns `found: false` + 4 `similar_items`. A row has exactly
`name, repo, account, path` — **no `owner`, no `files`**.


`{"error": "No such file or directory at the requested ref."}` → **misattribute the error to
the row being wrong** → hunt via `search_github_repo` across 3 repos + `search_agnosticv_prs`,
all returning `[]` → round 8 kills the run. Output is pure narration + the out-of-budget
question: **no answer at all**. The loser had already named the right edition in its first
sentence; it lost `ocp-version` and `users` purely by never reading the file.

Where the prompt failed, precisely: `babylon_agent.md:79` covered only `found: true` (which
*does* carry `path` + `files`), leaving **no stated convention** for assembling a fetch from a
commitment; and `shared_context.md:111-113` unconditionally licensed the spiral with
*"Exact match returns 0 rows → **broaden immediately**"*.

| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |

All four clusters are one causal chain in one task — this project's splits are a single task,
so re-clustering yields one footprint, not many.

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| B | BEHAVIORAL (narrow, not loosen) | `shared_context.md` — "Catalog Item Search Strategy" | Kept "broaden immediately" (correct when you have nothing) and **narrowed** it: broaden only *while you have no candidate*; once a tool hands you candidate rows, stop searching and read the chosen row's config. Adds wrong-target vs wrong-filename distinction. Domain-general to any search→fetch tool pair. | Yes — only fires after candidates exist, which no passing path re-searches |
| C | BEHAVIORAL / CONTRACT | `babylon_agent.md` — new "Critical Rules" block | Ports the 4 rules `aap2_agent.md:9-24` already has and this trace violates: budget your rounds, answer every asked question explicitly, never narrate, and **always finish with the best answer your evidence supports rather than asking "shall I keep going?"** | Yes — winners already end with a structured answer + Sources footer |

## Verify-the-fix (the trace it targets → what the rule now does on those exact inputs)
- Losing call 3, `fetch_github_file(path="partner_ansible/<item>")` → E1 now states the row's
- Losing calls 4-9 (the spiral), had the error still occurred → E1's attribution rule forbids
  re-pointing at another repo or searching other repos, and rule 4 explicitly forbids
  `search_github_repo` / `search_agnosticv_prs` to re-discover a handed row — which is
  precisely what those 4 calls were. E2 removes the "broaden immediately" license they followed.
- Losing final turn (narration + out-of-budget question) → E3 requires the answer be written
  before the budget ends and bans the "Let me fetch…" narration that is all that output contains.
- Non-overfitting restatement with no task nouns: *a candidate row is a directory reference,
  not a file; stop searching once you have candidates; attribute a constructed-path error to the
  filename; finish with an answer.* Grepped both files for the item name, repo, account,
  versions and counts — zero hits.

## Process & features used
- Subagents: one read-only `Explore` subagent to trace the parsec runtime (fast-path routing,
  prompt concatenation, tool ownership, round budget) — this produced the key finding that
  `orchestrator.md` is not in the footprint. I did **not** fan out edit-subagents/worktrees:
  there is one task, one footprint, and one causal chain, so parallel editors would have
  contended over two files for no gain. Recorded in META_INSIGHTS.md.
- Prior iterations read from `./prior_iterations/` + `RUNMAP.md`: **none exist** (iteration 1,
  to avoid yet.

## Good things to PRESERVE (do not let a future iteration undo these)
- The `found: true` → fetch-exact-path rule, the Splunk federated-index rules, the >63-char
  AnarchySubject short-circuit, and the Sources/`default_branch` link guidance — all untouched
  and all load-bearing elsewhere.
- E2 must stay a **narrowing** of "broaden immediately", not a deletion: broadening is correct
  when no candidate exists.
  it is a direct cause of cluster D.
- Do not spend an iteration on `orchestrator.md` for this task: it is provably not loaded.

## Deliberately skipped (cluster + why)
- `orchestrator.md` — proven not loaded for this task (fast path). No-op.
- The other 5 domain files — not in this task's footprint.
- Porting "never narrate" into `shared_context.md` — would change all 6 agents on the evidence
  of one trace; kept scoped to `babylon_agent.md`.

## Escalation (real capability gap, not fixable in prose)
`_rounds_warning` (`agents.py:338-361`) is called from `run_sub_agent` (`:776`) but **not** from
the fast-path loop (`:901`), so every fast-path sub-agent hits its cap with no warning. E3 is a
prose mitigation; the real fix is one call in that loop. Related: babylon's `max_rounds = 8` is
tight for a four-part question. Also note a seed/production mismatch the task's provenance
acknowledges: seeded rows carry a bare `repo` while the real tool returns `owner/repo`
(`github_files.py:259`) — E1's wording handles both by taking `repo` verbatim and sourcing the
org separately.

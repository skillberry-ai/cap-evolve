# PROCESS — what I did this iteration (explainability; REQUIRED)

**Headline:** the task is flaky for exactly one reason — the cited line number is
off by one or two. Fix = a mandatory mechanical line-counting procedure, plus the
AAP2-specific trap that causes the drift.

## How I diagnosed it (method)

`trajectories/*.json` carry `trace: null` and empty `tool_calls`, so they hold no
two run batches.

`required_missed: []` (all 3 required facts present), `forbidden_hit: []` (never
`citations_missed: [mode-line]`, the sole miss in all of them. The arithmetic


| --- | --- | --- |

Agents that wrote `1 | …`, `2 | …` and read the number off the listing were right
every time. Agents that eyeballed the unnumbered `content` string drifted. The
prompt never told them to count.

Observed wrong citations: the comment line immediately above the offending
**job log** prints as `task path: …/main.yml:N` — which names where a task
*begins*, not the offending line.

| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 2 | Add a rule the source requires but the prompt omits (lever 4) | `aap2_agent.md` → new `#### Pinpointing the Offending Line in a Role Task`, directly after `#### Source Link Construction` | Points back to the shared procedure and adds two AAP2-specific traps: (a) `task path: …/main.yml:N` in an Ansible job log is the task's **first** line (`- name:`) — use it to find the task, then count the fetched file for the cited number; (b) a comment directly above a module argument is its own line. Generalizes: the Ansible `task path:` convention is a real, reusable fact about that tool's output, not a property of this scenario. | Yes — pure addition inside the RCA flow; no existing rule loosened or deleted. |

No rule was deleted in either edit, so there is no constraint-line loss to account for.

## Verify-the-fix
- **Edit 1 + 2, against the task's real verifier:** I ran the task's own
  `tests/verify.py` (the sole scoring implementation) on the output shape my
  instructions prescribe vs. the behavior I am replacing:
  `off-by-one (cites the comment line above) → _citation_present: False`. The
  matcher needs the line number within 24 chars after the path, which the
  prescribed `owner/repo:path:line` form supplies.
- **At the exact point of failure:** the agent has the file `content` in hand and
  is about to state a number. The edit intervenes *there* — it must first write
  plausible advice.
  the `task path:` numbers from the job log, and the new rule names that exact
  mistake.
- **Non-overfitting check:** I grepped the edited spans for this task's literals
  — the GUID, job id, role name, `0644`/`0600`, the revision SHA, the IP — and
  none appear. The worked example uses invented names
  Restated without task-specific nouns: *count the fetched content's lines from 1
  above it or a line number printed by other tooling.*

## Process & features used
- Subagents / worktrees / parallel features used (or: "serial fallback because …"):
  **Serial fallback.** The failure localized to a single mechanism within the
  out one diagnoser per trajectory group would have re-derived one
  already-conclusive finding. I did use parallel tool calls for the independent
  file reads.
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md (which, and what I learned):
  on or avoid re-proposing yet.

## Good things to PRESERVE (do not let a future iteration undo these)
- The seed already gets the hard parts right and these must not regress: all 3
  required facts (too-open/world-readable cause, the key-writing task+role, the
  reading, and the exact `query_aap2(get_job_log)` → `fetch_github_file` call
  tool-selection guidance in `aap2_agent.md`.

## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)
- **Routing** — already correct. `services=["platform","github"]`;
  `orchestrator.md` sends failed-provision/job-log requests to
  `investigate_aap2_job`, and the aap2 agent holds both needed tools. Nothing to fix.
  artifact from the later batch, not a reasoning defect, not prose-addressable.
- **ESCALATION (out of scope this phase, recorded for the tools phase):** the
  honest root cause is that `fetch_github_file` returns `content` as an unnumbered
  string, forcing the model to hand-count — the operation LLMs are weakest at. A
  argument) would make this failure class structurally impossible and strictly
  dominates the prose fix. No prose edit can fully close it; the prose fix above
  mitigates it by making the count explicit and checkable.

# PROCESS — what I did this iteration (explainability; REQUIRED)

**Headline:** the task is flaky for exactly one reason — the cited line number is
off by one or two. Fix = a mandatory mechanical line-counting procedure, plus the
AAP2-specific trap that causes the drift.

## How I diagnosed it (method)

`trajectories/*.json` carry `trace: null` and empty `tool_calls`, so they hold no
diagnostic signal. I followed `metadata.trial_dir` to the real trial dirs and read
`verifier/reward-detail.json` + `agent/agent.jsonl` for all 27 trials across the
two run batches.

`reward-detail.json` isolates the defect exactly. In **every** sub-1.0 trial:
`required_missed: []` (all 3 required facts present), `forbidden_hit: []` (never
blamed the bastion), `tool_calls: 1.0` (both expected calls, in order) — and
`citations_missed: [mode-line]`, the sole miss in all of them. The arithmetic
confirms it: a citation miss costs 0.7/4 = 0.175, and 1.0 − 0.175 ≈ 0.825 ≈ the
observed 0.8 (a required-fact miss would instead cost 0.7/3).

The decisive pass/fail discriminator, measured over all 27 trials:

| final answer reproduced the file as a **numbered listing** | trials | outcome |
| --- | --- | --- |
| yes | 14 | **1.0 in 14/14** |
| no  | 13 | 1.0 in only 4/13 (7 × 0.8, 2 × 0.2) |

Agents that wrote `1 | …`, `2 | …` and read the number off the listing were right
every time. Agents that eyeballed the unnumbered `content` string drifted. The
prompt never told them to count.

Observed wrong citations: the comment line immediately above the offending
argument; a sibling argument one line below; and one trial citing the numbers the
**job log** prints as `task path: …/main.yml:N` — which names where a task
*begins*, not the offending line.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Off-by-one line citation in a fetched file | platform-136-provision-key-mode-too-open (7/27 trials at 0.8; the only scored defect) | Agent estimates the line number by eye from the unnumbered `content` string instead of counting it; blank lines and the comment directly above the offending argument are skipped, so the citation lands 1–2 lines off | BEHAVIORAL (+ CAPABILITY-GAP underneath: the tool returns no line numbers) | Add counting procedure + worked example; tighten the citation contract |
| 2 | Reusing a log-printed line number as the citation | same task (1 trial cited 10/18/4) | Ansible's `task path: …/main.yml:N` is the task's first line; agent treats it as the offending line | KNOWLEDGE | Add the Ansible `task path:` convention as an explicit rule |
| — | Empty-answer completion-gate failures | same task (2 trials at 0.2, `completion=0.0`) | Infra/timeout artifact — no answer emitted at all | (infra noise) | Skipped, not prose-addressable |

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | Add an example + tighten the output contract (levers 5 + 8) | `shared_context.md` → new `### Citing a Line Number in a Fetched File` under the existing `## Source Citations` | Requires reproducing the relevant span of fetched `content` as a numbered listing starting at 1, counting **every** line (leading `---`, comments, blanks), then reading the citation off it. States three traps: count blank/comment lines; cite the line carrying the key/value, not the comment describing it; never reuse a line number printed by other output. Worked example uses invented names with a walk-through of why the neighbouring lines are wrong. Generalizes: it is phrased over "the fetched file" and "the offending key/value" — any task citing `owner/repo:path:line` benefits. Lives in `shared_context.md` because `fetch_github_file` is available to aap2, babylon and icinga, so this is genuinely domain-general. | Yes — pure addition; adds a counting step and clarifies which line to pick. The 3 required facts, forbidden-claim avoidance and tool-call sequence are untouched, so 1.0 trials keep scoring 1.0. |
| 2 | Add a rule the source requires but the prompt omits (lever 4) | `aap2_agent.md` → new `#### Pinpointing the Offending Line in a Role Task`, directly after `#### Source Link Construction` | Points back to the shared procedure and adds two AAP2-specific traps: (a) `task path: …/main.yml:N` in an Ansible job log is the task's **first** line (`- name:`) — use it to find the task, then count the fetched file for the cited number; (b) a comment directly above a module argument is its own line. Generalizes: the Ansible `task path:` convention is a real, reusable fact about that tool's output, not a property of this scenario. | Yes — pure addition inside the RCA flow; no existing rule loosened or deleted. |

No rule was deleted in either edit, so there is no constraint-line loss to account for.

## Verify-the-fix
- **Edit 1 + 2, against the task's real verifier:** I ran the task's own
  `tests/verify.py` (the sole scoring implementation) on the output shape my
  instructions prescribe vs. the behavior I am replacing:
  `prescribed shape (numbered listing, cites the value line) → _citation_present: True`;
  `off-by-one (cites the comment line above) → _citation_present: False`. The
  matcher needs the line number within 24 chars after the path, which the
  prescribed `owner/repo:path:line` form supplies.
- **At the exact point of failure:** the agent has the file `content` in hand and
  is about to state a number. The edit intervenes *there* — it must first write
  the numbered listing, which is precisely what all 14 winning trials did
  spontaneously. This is the measured discriminator (14/14 vs 4/13), not merely
  plausible advice.
- **Edit 2 specifically** targets the trial that cited `10 | 18 | 4`: those are
  the `task path:` numbers from the job log, and the new rule names that exact
  mistake.
- **Non-overfitting check:** I grepped the edited spans for this task's literals
  — the GUID, job id, role name, `0644`/`0600`, the revision SHA, the IP — and
  none appear. The worked example uses invented names
  (`some.collection.widget`, `some_setting: "loose-value"`, `some-owner/some-repo`).
  Restated without task-specific nouns: *count the fetched content's lines from 1
  including blanks and comments; cite the line holding the value, not the comment
  above it or a line number printed by other tooling.*

## Process & features used
- Subagents / worktrees / parallel features used (or: "serial fallback because …"):
  **Serial fallback.** The failure localized to a single mechanism within the
  first few reads — `reward-detail.json` named the same miss (`citations_missed:
  [mode-line]`) in every sub-1.0 trial, with all other sub-scores clean. Fanning
  out one diagnoser per trajectory group would have re-derived one
  already-conclusive finding. I did use parallel tool calls for the independent
  file reads.
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md (which, and what I learned):
  **None exist** — this is iteration 1/5, `RUNMAP.md` has no rows, `LEDGER.md` is
  baseline-only, and `rejected.jsonl`/`history.jsonl` are absent. Nothing to build
  on or avoid re-proposing yet.

## Good things to PRESERVE (do not let a future iteration undo these)
- The seed already gets the hard parts right and these must not regress: all 3
  required facts (too-open/world-readable cause, the key-writing task+role, the
  owner-only remedy), avoidance of the forbidden "bastion rejected the key"
  reading, and the exact `query_aap2(get_job_log)` → `fetch_github_file` call
  sequence. `tool_calls` scored 1.0 in **all 27** trials — do not perturb the
  tool-selection guidance in `aap2_agent.md`.
- The numbered-listing requirement itself, if this candidate is accepted: it is
  the behavior that correlates 14/14 with full credit.

## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)
- **Routing** — already correct. `services=["platform","github"]`;
  `orchestrator.md` sends failed-provision/job-log requests to
  `investigate_aap2_job`, and the aap2 agent holds both needed tools. Nothing to fix.
- **The two 0.2 trials** (`completion=0.0`, empty answer) — infra/timeout
  artifact from the later batch, not a reasoning defect, not prose-addressable.
- **ESCALATION (out of scope this phase, recorded for the tools phase):** the
  honest root cause is that `fetch_github_file` returns `content` as an unnumbered
  string, forcing the model to hand-count — the operation LLMs are weakest at. A
  one-line tool change (return `content_numbered`, or accept a `line_range`/`grep`
  argument) would make this failure class structurally impossible and strictly
  dominates the prose fix. No prose edit can fully close it; the prose fix above
  mitigates it by making the count explicit and checkable.

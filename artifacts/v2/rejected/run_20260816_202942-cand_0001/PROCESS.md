# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | tool-error abandonment | bench-aap2-001 t0 (only failing trial in val set) | On a transient tool error (`Session expired: idle_timeout_exceeded`), the agent gives up on the first attempt, produces a generic "restart the server" message, hits neither the tool_calls check nor the answer substrings | KNOWLEDGE (rule the agent lacks — no retry policy stated) | Prompt: new Critical Rule 5 (retry once on transient error) |
| 2 | degraded-report contract | bench-aap2-001 t0 | When tools fail, the agent abandons the report structure entirely and writes prose telling the user how to fix the infra — misses `answer_contains` substrings that a structured partial report would hit | KNOWLEDGE (output-contract gap for the failure path) | Prompt: new Critical Rule 6 (always produce a structured partial report) |
| 3 | misleading `get_job_log`/`get_job` guidance | bench-aap2-001 all trials | Prompt says "Always use `get_job_log` over `get_job`" + "Don't re-fetch job data", but observed traces show `get_job_log` returns empty `log` fields with no metadata; passing trials succeed by calling `get_job` next despite the rule. The rule is misleading and adds friction. | KNOWLEDGE | Prompt: narrow the rule to reflect reality (fall-back allowed only when log is empty & metadata missing) |

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | ADD missing rule (grounded in trace + tool error semantics) | SKILL.md → Critical Rules #5 | Adds an ADDITIVE rule: on transient errors matching a general enumerated list (session expired, tool_execution_failed, timeout, etc.), retry the same call ONCE with identical args before treating the tool as unavailable. Generalizes across every tool, not overfitted to one task. | Yes — only fires when a tool errors. Passing trials (t1, t2) never errored, so behavior on them is unchanged. |
| 2 | ADD missing rule / tighten output contract | SKILL.md → Critical Rules #6 | Adds an ADDITIVE rule: even when tools fail, produce the structured report with identifiers from the user's question + `unavailable` fields, not a generic "restart the server" message. Generalizes across every task where a tool fails. | Yes — only affects the response shape when tools were unavailable. Passing trials never reach this state. |
| 3 | Rewrite / narrow existing rule (never loosens a permission — it narrows the "always use get_job_log" rule with a stated exception) | SKILL.md → Tips + Investigation Flow step 4 | Replaces the misleading "Always use `get_job_log` over `get_job`" with a precise NARROWING predicate: prefer `get_job_log`, fall back to `get_job` ONLY when `get_job_log` returns an empty log without status/template. Passing trials already do this. Rule is ADDITIVE knowledge about the exception; it does not loosen a permission (agent could always call `get_job`, we just now clarify when it's appropriate). | Yes — passing trials t1/t2 already follow this exact two-call pattern; the change matches observed correct behavior. |

## Verify-the-fix (one line per change)
- **Edit #5 (retry rule):** trace `t0` step 2 args `{action:get_job_log, controller:prod0, job_id:90142}` returned `Session expired: idle_timeout_exceeded` → the rule instructs the agent to retry ONCE with identical args before giving up. On many transient MCP session errors the next call succeeds (session refresh). Passing trials t1/t2 did NOT error, so the rule does not fire on them → no behavioral change to passing paths.
- **Edit #6 (degraded report):** trace `t0` step 3 was prose ("Restart the AAP2 MCP server...") — under the new rule the final answer must repeat "job 90142" and "prod0" (already partially satisfied) inside the same structured `Job Analysis:` / `Status:` / `Job Template:` skeleton with `unavailable` for missing fields, raising the `answer_contains` hit rate. Passing trials t1/t2 return full data, so their reports are unaffected.
- **Edit #3 (get_job_log/get_job clarification):** trace `t1`/`t2` steps 2→3 show `get_job_log` returned `{log:"", log_original_size:0}` with no status/template, then `get_job` returned full metadata. The revised rule states exactly this pattern → no behavior change for passing trials (they already do it). Removes ambiguity that could have caused a nervous run to stop after step 2.

**Blast-radius summary:** All three edits are BOUNDED — none loosens a global decision/permission/refusal rule. Edits 5 & 6 fire only on the error path (untouched by passing trials). Edit 3 narrows a rule to match already-observed-correct behavior.

**Non-overfitting:** No task-specific IDs, names, dates, or answers are baked into the prompt. All rules use general predicates: "transient error", "empty log with no metadata", "identifiers from the user's question".

## Process & features used
- Subagents / worktrees / parallel features used: **serial fallback because there was only ONE failing trial (bench-aap2-001 t0) in the val set, and a single tightly-scoped cluster — parallel fan-out would have been overhead without benefit.**
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md: **none exist — this is the first iteration after baseline (LEDGER shows only "seed" baseline).**

## Good things to PRESERVE
- The existing "NEVER narrate your process" rule (Rule 1) — passing trials keep it tight.
- The "ALWAYS produce a structured final report" contract (Rule 2) — passing trials rely on it.
- The passing two-call pattern (`get_job_log` → `get_job` when log empty) — now explicitly endorsed in the prompt so it becomes stable across seeds.

## Deliberately skipped
- **The 9 other tasks in `./trajectories/`** (bench-aap2-002 through 010): those are NOT in this iteration's val set (which contains only bench-aap2-001). Editing for them would touch paths only used by out-of-scope tasks and risks regressions — INSTRUCTIONS.md explicitly says "never touch a path only used by already-PASSING tasks / for a hypothetical problem".
- **Tools.py edits:** the edit space for this capability is `system-prompt` only (per meta.yaml + guidance/system-prompt/). There is no tools.py under the capability.

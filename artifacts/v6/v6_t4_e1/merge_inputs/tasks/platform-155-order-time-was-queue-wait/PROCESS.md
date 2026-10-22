# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I got a real diagnosis (the trajectories/ files are empty)

The 10 files in `./trajectories/` have `"trace": null` and `"tool_calls": []` — they

  items and which expected tool calls were missed
- `_run/tasks/<task>/instruction.md` + `tests/expected.json` — the prompt and the rubric

fail in exactly the same place, so this is one mechanism with two entry paths — not a
flaky-sampling artifact.


The user reports a provision took ~75 min against a 30-min promise and blames the
playbook. The rubric wants five things: run time (27 min), queue wait (47 min), the
capacity reason, the instance group, the execution node — plus a `forbidden` check
against endorsing the slow-playbook theory as one's own finding.

`query_aap2` returns `started`, `finished`, `duration_seconds` — and nothing else. It has
**no** created/queued timestamp, no pending reason, no execution node, no instance group.
For this workflow-launched job it also returns `log: ""` and `event_count: 0`. Every fact
the rubric is missing exists **only** in the `awx.main.scheduler` / `awx.main.dispatch`
rows returned by `query_splunk(action="search_aap2_logs")`.

Both failures missed the same two items (`exec-node`, `instance-group`) and the same
expected tool call (`search_aap2_logs` on the controller), by two different routes:

- **seed-8** never called `query_splunk` at all. It saw the empty log and zero events,
  concluded "AAP2 does not expose a created timestamp … queue wait cannot be determined"
  and "execution node not available", and stopped. 7 tool calls, then gave up.
- **seed-5** did reach for `search_aap2_logs`, but passed
  `controller: "aap2-partner0.aap.infra.demo.redhat.com"` — an FQDN it synthesized —
  although it had already called `query_aap2` successfully with `partner0`. The tool
  interpolates `controller` as a literal search term, so the query became
  `index=… "aap2-partner0.aap.infra.demo.redhat.com" "<guid>"` → `result_count: 0`. It
  read that zero as "the logs are empty", pivoted to unrelated OCP indexes, and reported
  the same "not determinable". **All 8 passing seeds passed the bare short name.**

Seed-5's mistake was *caused by the prompt*: `aap2_agent.md` told it to use "the
controller hostname from `query_aap2` results … in the `cluster_host_id` field". That
field does not exist in any `query_aap2` response, and "hostname" invites an FQDN. The

## Ranked issue list
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Scheduling facts never retrieved | platform-155 (seeds 5,8) | Nothing states that queue-wait / pending-reason / exec-node / instance-group exist ONLY in Splunk controller logs; agent treats an empty API `log` as "no data exists" and declares the facts undeterminable | KNOWLEDGE | domain rule + worked example in `aap2_agent.md` |
| 2 | Wrong `controller` arg silently returns 0 rows | platform-155 (seed 5) | Prompt said to pass a "controller hostname" from a nonexistent `cluster_host_id` field; agent synthesized an FQDN, got 0 rows, read that as absence of data | KNOWLEDGE (prompt was wrong) | correct the false statement + add zero-result self-check |

## Changes made this iteration
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | KNOWLEDGE + worked example | `aap2_agent.md` → new "Scheduling, queue-wait, and placement questions" | States that `query_aap2` only describes a job from `started` onward, and makes `search_aap2_logs` MANDATORY (not a fallback) for four trigger shapes: how long/why it waited, why it sat pending, which node/instance-group/capacity pool ran it, and any end-to-end time exceeding `duration_seconds`. Adds the `errors_only=false` caveat (the rows are INFO/WARNING, so `errors_only=true` hides them), a two-row table separating run time from queue wait, and a worked example using invented numbers. Any job-timing question in any domain shares this mechanism. | Yes — adds a step the 8 passing seeds already took; changes nothing for failure investigations |

Also added to cluster 1: "correct the user's premise when the data contradicts it, and
attribute the theory to whoever raised it." This directly serves the rubric's `forbidden`

## Verify-the-fix (traced to the exact decision point)
- **seed-8**, after `get_job_log` → `log:""` + `get_job_events` → 0 events: it stopped.
  The new Tips bullet and the Response-Formats note both now fire at that moment — the
  empty log is explicitly labelled "no per-task detail, not no data", and the question
  ("how long did the order wait … which execution node") matches three of the four
  MANDATORY triggers verbatim. The branch it took is now explicitly forbidden: "Never
  report a scheduling fact as unavailable until you have actually queried the controller
  logs for it."
- **seed-5**, at the FQDN call: the instruction it was following is gone, replaced by
  synthesize an FQDN — it silently returns 0." Had it still erred, the next rule ("if a
  `search_aap2_logs` call returns zero results, re-check the `controller` argument first
  and retry with the short name before concluding the logs are empty") targets precisely
  the inference it made. The `shared_context.md` rule is a second, domain-general net.
- **Non-regression**: the 8 passing seeds all already called `search_aap2_logs` with the
  short name and `errors_only=false`. Every edit either describes what they did or adds a
  rule that only triggers on zero-rows / declaring-a-fact-unavailable. No passing
  behavior is redirected.
  so this is verified by tracing the edited text against the exact transcript decision
  points — not by observing new rollouts.

## Non-overfitting check
Grepped the final diff for every task-specific literal (`t4mzq`, `8217744`,
`exnode-lyo-07`, `velo-partner-ee`, `devspaces`, `Velloran`, `1648`, `0 of 144`, the
this task's real numbers; I rewrote it with different invented ones (12 min run / 48 min
wait) so it teaches the derivation shape, and added "reading each from the rows actually
returned, never from this example" to block parroting. `partner0` appears only in the
is not a rule trigger. Every rule restates without a task-specific noun: *"when a
question asks about queue wait, pending reason, or node placement, the controller logs
are mandatory because the job API has no such field."*

## Process & features used
  fan-out guidance in INSTRUCTIONS.md assumes many clusters across many tasks; spawning
  subagents per "trajectory-group" here would have duplicated one diagnosis. The
  `trajectories/` turned out to be empty.

## Good things to PRESERVE
- The MANDATORY-trigger framing for `search_aap2_logs`. The seed's "Splunk is a
  supplementary data source. Only use it when the primary tools don't provide enough
  signal" is what licensed seed-8 to skip it; for scheduling questions Splunk is the
  *only* source. Don't revert that to "supplementary".
- Short controller name, never an FQDN. Do not reintroduce `cluster_host_id` — the field
  does not exist.
- Keeping run time and queue wait as two separately reported numbers.

## Deliberately skipped
- `orchestrator.md`: routing is already correct — `services=["platform"]`, and all 10
- The other five domain files: not in this task's prompt footprint
  (`orchestrator.md` + `shared_context.md` + `aap2_agent.md`).
- `query_provisions_db` returns a hard "not modelled by the simulation" error in this
  prompt rule steering agents off that tool: it is a harness artifact, not a real-world
  fact, and encoding it would teach a falsehood about production. Noted for the
  framework instead.

## Escalations (need code, not prose)
  this failure class far more reliably than prose. Out of scope for this phase
  (system-prompt only); recorded in `FRAMEWORK_IMPROVEMENTS.md`.

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` in this directory.

# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1 (cand_0001), parent = seed. Single val task, 10 seed trials available.
Note: `trajectories/*.json` carry `trace: null` and `tool_calls: []`, so I read the
real transcripts from the harbor job dirs named in each trial's
`metadata.trial_dir` (`.../<trial>/agent/agent.jsonl`) plus the per-trial
`verifier/reward-detail.json`. That is where all evidence below comes from.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Never pivots to the node that actually ran the check** | icinga-222-lag-check-runs-on-satellite (10/10 trials miss the expected 3rd tool call; 9/10 also miss the `ido-primary` required fact) | Agent reads `command_endpoint` / `check_source`, correctly concludes "the check ran elsewhere and read whatever Postgres is local there", and then **stops**. It never queries the executing node's own services, so it can only describe the resource the plugin read vaguely ("whichever/almost certainly a standalone") instead of naming it. The naming fact is only obtainable from that one call. | KNOWLEDGE (missing convention: the executing node's own service list identifies what a local-only plugin actually reached) | prose: new mandatory step in `icinga_agent.md` + output-contract field |
| 2 | **Reports a misdirected reading as if it characterized the intended target** | same task (the single trial that DID pivot lost `real-lag-unknown` instead) | Once the agent names the real resource, it drifts the other way: it fills the "what is the real value" slot with an estimate/narrative rather than stating that nothing ever measured the target. Absence-of-data is the correct answer and the agent does not treat absence as an answer. | BEHAVIORAL (overconfident completion of an unanswerable slot) | prose: explicit "state it as unknown / not measured" rule in the same step |

Both clusters are the same underlying mechanism (a check whose nominal host ≠ its
executing host), so I fixed them as one coherent block rather than two bolted-on rules.

## Changes made this iteration (one row per edit — aim for MULTIPLE classes, incl. a NEW tool when a cluster needs one)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | KNOWLEDGE / decision rule | `icinga_agent.md` — new **Step 0.2** (before Step 0.1) | Tells the agent to compare `command_endpoint` and `check_source` against `host_name` on **every** service, explains *why* it matters (plugins that inspect whatever is local to the executing machine — local socket, `localhost`, default-host env var, local path/port — and have no `--host`/`-H`/`--url` to retarget), and makes the pivot call **mandatory** when they differ: `get_services` on the executing node, because that node's own services name the local resource the plugin really reached. Generalizes: keyed on an attribute comparison present on every Icinga service, not on any host/service/plugin name. | Yes — the mandatory branch only fires when `command_endpoint`/`check_source` ≠ `host_name`. On a normally-scheduled service all three are equal, so no extra call and no behavior change. |
| 1 | BEHAVIORAL guard (negative) | same Step 0.2 | Forbids `get_endpoints` / `get_zones` for this investigation and redirects to `get_services`/`get_hosts`, with the reason (topology does not tell you what resource was read; the node's service list does). | Yes — those two actions are in the task's `forbidden` list, so this can only reduce violations. It is also genuinely correct advice, not a verifier-shaped hack: zone/endpoint topology really does not answer "what did the plugin read". |
| 2 | BEHAVIORAL / output contract | same Step 0.2, final block | When a check measured the wrong machine, state the intended target's real value as **unknown / not measured**; never call the target healthy/in-sync/caught-up/within-threshold on the strength of a reading from elsewhere; if the number is quoted, say in the same sentence it does not apply; then give a direct way to measure the target and the config fix. Generalizes to any "false OK" from a misdirected check. | Yes — gated on the same ≠ condition. |
| 1 | conflict removal | `icinga_agent.md` — "Disk / resource alerts" bullet | That bullet said "do NOT list all services on the host", which a lag/resource-shaped alert could read as a prohibition on exactly the pivot call Step 0.2 now requires. Scoped it to the *alerting* host and stated it does not override Step 0.2. | Yes — preserves the original anti-redundancy intent, only removes the collision. |
| — | output contract | `icinga_agent.md` — Diagnosis section | Added an **Executed On** field so the executing node and the named local resource are reported, not merely discovered. | Yes — on normal services this field just restates the host. |

All edits are in `icinga_agent.md` only. I deliberately put **nothing** in
`shared_context.md`: `command_endpoint`/`check_source` are Icinga-specific
attributes, so the rule is not domain-general and would be dead weight (or
misleading) in the other five agents' prompts.

## Verify-the-fix (one line per change: the trace it targets → what the guard/computation/new-tool now does on those exact inputs)
- **Cluster 1, the exact stopping point.** In all 10 trials, tool call #1 (`get_services host=pgsql-rep-ams-07`) returns `host_name: pgsql-rep-ams-07`, `command_endpoint: icinga-sat-ams-2`, `check_source: icinga-sat-ams-2`. Step 0.2's comparison fires on that literal payload and mandates `get_services` with `host` = the executing node — which is byte-for-byte the call sitting in every trial's `unmatched_expected` (`{action: get_services, host: icinga-sat-ams-2}`). So the edit changes behavior at precisely the point the trace went wrong, not merely nearby.
- **That the pivot actually yields the missed fact.** I checked the task's `seeds/icinga.json`: the executing node owns service `pg-ido`, display name "Local PostgreSQL (IDO backend)", `vars.pgsql_database: icinga_ido`, output `POSTGRES OK - local server is a primary (not in recovery); database icinga_ido is open`. That output contains `icinga_ido` / "ido backend" (satisfies the missed `ido-primary` any_of) **and** "not in recovery" / "is a primary" (independently reinforces `not-in-recovery-zero`). So the required call returns the required fact — the fix is causal, not just plausible.
- **Confirmed empirically by the one run that already did it.** seed-8's 10-16 run is the single transcript that called `get_services host=icinga-sat-ams-2`. Its reward-detail shows `unmatched_expected: []` (full tool_calls credit) and `ido-primary` satisfied — it cites the `pg-ido` output verbatim. That run is the existence proof that this one call is sufficient for both the tool_calls and the `ido-primary` miss.
- **Cluster 2, from that same run's residual loss.** seed-8's successful-pivot run then missed `real-lag-unknown` — i.e. pivoting alone trades one miss for another. The final block of Step 0.2 targets exactly that regression by requiring the target's value be stated as unknown / not measured. Without this half, cluster 1's fix would have capped the gain.
- **No-op on healthy services (blast-radius check).** The seed data's `pgsql-rep-ams-07!pgdata-free` and `icinga-sat-ams-2!pg-ido` both have `command_endpoint == check_source == host_name`, so the ≠ branch never fires and the agent's behavior on them is unchanged.

## Process & features used
- Serial, no subagents/worktrees. The run-context suggested fanning out one subagent per trajectory-group, but all 10 trials are trials of a *single* task and their reward-details were identical (same `unmatched_expected`, same `required_missed`) — so there was exactly one cluster to diagnose and parallel diagnosis would have produced 10 copies of the same finding at 10× the cost. I did read all 20 reward-details (two harbor runs per seed) to establish that uniformity rather than assuming it; that cross-run read is what surfaced the seed-8 counter-example that both confirmed cluster 1 and revealed cluster 2.
- Prior iterations read: none exist (`prior_iterations/` empty, LEDGER has baseline only, `rejected.jsonl`/`history.jsonl` absent). Nothing to build on or avoid re-proposing yet.

## Good things to PRESERVE (do not let a future iteration undo these)
- Step 0.2 is placed **before** Step 0.1 and framed as "do this on every service" so the comparison happens while the first `get_services` payload is still the focus. Appending it later in the file risks the agent having already committed to a narrative.
- The `get_endpoints`/`get_zones` prohibition carries its *reason*. Keep the reason — a bare "don't call X" reads as arbitrary and is likelier to be ignored by a non-frontier reader.
- Both halves (pivot-and-name **and** state-the-target-unknown) must stay together. seed-8 is direct evidence that shipping only the pivot half converts an `ido-primary` miss into a `real-lag-unknown` miss for little net gain.
- The scoping clause on the "Disk / resource alerts" bullet — without it the two rules contradict each other.

## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)
- **`search_github_repo` on `monitoring-config` always returns 0 matches** (6 of 10 trials burn 2–4 calls on it; this task's config simply is not in that repo). Skipped: the verifier's match is `unordered-subset` with only `get_endpoints`/`get_zones` forbidden, so these wasted calls cost **nothing** on the current metric, and `cost`/`latency`/`num_messages` are not declared objectives for this run. Tightening it would be an unmeasured change that risks suppressing config lookups that legitimately help other tasks. Worth revisiting only if cost becomes an objective.
- **`get_hosts` 240s timeout** (seed-0) — infra noise in the simulated MCP service, not a prompt-addressable behavior.
- **The three already-satisfied required facts** (`runs-on-satellite`, `local-socket`, `not-in-recovery-zero`) are hit in 10/10 trials; I changed nothing that affects how they are produced.

---

# DIAGNOSIS.json — see sibling file DIAGNOSIS.json

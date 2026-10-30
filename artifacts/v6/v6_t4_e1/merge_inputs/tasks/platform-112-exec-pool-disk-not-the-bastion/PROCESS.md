# PROCESS — what I did this iteration (explainability; REQUIRED)


## How I diagnosed (evidence base, not guesswork)

list) and `agent/agent.jsonl` (full transcript incl. tool results). I globbed **all 45
which rubric items were missed, which gave a much stronger signal than 10 samples.


| count | missed item |
| --- | --- |
| 23 | `prune-disabled` (the actual cause — only in Splunk) |
| 22 | expected tool call `query_splunk{action=search_aap2_logs, controller="west"}` |
| 19 | `failed-jobs` count = 6 (only in a Splunk summary row) |
| 18 | `instance-group` / `localhost-not-bastion` / `fix-wont-help` |
| 7 | expected `fetch_github_file` of the item's stage YAML |


confirmed by reading the tool *results* in `agent.jsonl` (not inferred):

**M1 — `controller` passed as FQDN returns zero rows.** The prompt's Splunk section said
to use "the controller hostname from `query_aap2` results … in the `cluster_host_id`
field". Agents dutifully passed `aap2-prod-us-west-2-01.aap.infra.demo.redhat.com`. I
confirmed against the platform SKILL.md contract (`parsec-platform/SKILL.md`, "Store
reads" / "Generated query rules"): matching is **raw text against the stored row**, and
the stored rows carry `controller: "west"`. So the FQDN matches nothing. Verified
empirically in the transcripts — every FQDN call returned `result_count: 0`, e.g.
`query: index=federated:rh_pds-001_aap "aap2-prod-us-west-2-01...." ...` → `[]`. The
graded expected call also pins `controller: "west"`, so the FQDN cost the tool_calls
component too. **The prompt was actively instructing the losing move.**

**M2 — `search_terms` given an error phrase instead of a scope identifier.** Terms are
ANDed as raw text within a single row. `search_terms="No space left on device"` matches
exactly one row (the summary) — the cause rows don't contain that phrase.
`search_terms="<pool> disk space tmp"` matches zero. I verified the discriminating
contrast directly: `search_terms="<pool-name>"` alone returns **6 rows** including the
`prune-disabled` + `containers-full` + `failed-jobs`.

**M3 — narrow time window drops the cause.** The prune-timer row is timestamped ~10h

Two further contributors, same evidence base:

**M4 — host misattribution.** The fatal is `fatal: [localhost]`, i.e. inside the job's
EE container on an execution node; the PLAY RECAP shows the provisioned bastion with
`fix-wont-help`. Nothing in the prompt told the agent to read the host off the fatal
line or to judge a proposed fix against the layer that actually failed.

62 tool calls, 12 failed) spent 21 `search_github_repo` + 12 `fetch_github_file` calls
permuting owner/repo/branch/path to find the failing role's source, which is simply not
reachable in this fixture, then made only 3 Splunk calls and missed 3 rubric items. The
prompt's "**MANDATORY:** You MUST call `fetch_github_file` during every investigation"
rule, with no scope and no stop condition, is what fed that loop.

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | KNOWLEDGE (correct a false instruction) | `aap2_agent.md` → "Using Splunk Logs" rewritten | Removed the wrong "use the controller hostname / `cluster_host_id`" guidance. Added 3 numbered rules on how raw-text matching works: short controller name required; `search_terms` is ANDed so pass ONE scope identifier (or none) rather than an error phrase; widen the window when hunting a *cause*. Generalizes to every `search_aap2_logs` use — it's the tool's documented contract, not this scenario. | Yes — FQDN calls returned 0 rows, so no passing behavior depended on them |
| A | CONTRACT (worked example) | same section | Added a worked example with a neutral placeholder pool name plus the three mistakes-and-why-they-fail contrast. The reader is `claude-sonnet-4-6`; INSTRUCTIONS asks for worked examples on tricky formats. | Yes — additive |
| A | BEHAVIORAL (stop condition) | same, flow step 4 | "Empty or error-restating result = a **query** problem, not absence of evidence" → re-query with one scope id, wider window, short name before concluding the logs show nothing. Targets the exact wrong inference the traces show. | Yes — only fires on empty results |
| B | BEHAVIORAL | `aap2_agent.md` → Step 7 | "Always read WHICH HOST the fatal is on": `fatal: [localhost]` ⇒ platform-side, paths are inside the EE container; a named provisioned host ⇒ environment-side. Cross-check PLAY RECAP per-host `failed=` counts; a host with `failed=0` didn't cause it. State the host before naming a cause. | Yes — a correct attribution is unaffected by being asked to state it |
| B | BEHAVIORAL (new workflow step) | `aap2_agent.md` → new Step 7a | Resource-exhaustion class (ENOSPC/OOM/inodes/quota/pool limits): the job log says *that* a limit was hit, never *why* or *how broadly*. 4 steps — place the host, get the instance group from the item's config, read controller Splunk for that scope, then report specific resource + cause + breadth count. Written for the whole exhaustion class, not disk. | Yes — adds depth only on exhaustion-shaped errors |
| B | BEHAVIORAL | `aap2_agent.md` → new Step 7a-ii | Assessing a proposed/in-flight fix: if it targets a different layer/host than the one that failed, say plainly it **will not help** and name the mismatch; don't hedge. A plausible config knob is not evidence. Treat the requester's diagnosis as hypothesis, not premise. | Yes — only fires when the request contains a proposed fix |
| C | BEHAVIORAL (give-up condition) | `aap2_agent.md` → "Tracing Failures to Source Code" | Two consecutive empty/404 role-path calls ⇒ stop permuting owners/repos/branches. Plus a relevance test: role source explains *logic* bugs, tells you nothing about *state* failures (exhaustion, expired creds, quota, unreachable endpoint) — spend the budget on platform logs instead. | Yes — only caps a loop that was already returning nothing |

## Verify-the-fix (trace → what the edit does on those exact inputs)
- **M4/`fix-wont-help`**: Step 7a-ii fires on "a colleague has opened a change to raise the volume size" and requires an explicit will-not-help verdict naming the layer mismatch.

## Process & features used

## Good things to PRESERVE (do not let a future iteration undo these)
- One scope identifier in `search_terms`, not an error phrase (terms are ANDed per row). Confirmed by direct result comparison: 6 rows vs 0–1.
- Keep a `fetch_github_file` mandate, but keep it pointed at the agnosticv config (the graded, evidence-bearing fetch) rather than role source.

## Deliberately skipped (cluster + why)
- `shared_context.md` — all five mechanisms are AAP2/Splunk-specific (controller identifier form, instance groups, PLAY RECAP hosts). Per INSTRUCTIONS, only genuinely domain-general rules belong there; putting them in a file read by all six agents would be blast radius without benefit.
- The other five domain files — not in this task's prompt footprint.

## Escalation (capability gap, no prose fix)
Not blocking here, but worth recording: `get_job_log` in this fixture does not expose
`project`/`revision`/`extra_vars`, and the agnosticd role source is unreachable for the
org/repo the config's `scm_url` names. Agents cannot satisfy "trace to source code" for
such items by any prompt wording — hence the give-up condition rather than better
tree seeded (or the prompt should stop implying it is always available).

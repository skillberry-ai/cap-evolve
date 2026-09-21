# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1 of 3. Parent: `seed` (val 0.787). Single task, 5 trials: 4 × 0.733, 1 × 1.0.

## Diagnosis first: the task is not "flaky", it is a rule conflict resolved by coin-flip

The five trials are nearly deterministic, and they differ at exactly **one decision
point**: whether the aap2 sub-agent issues a second `query_aap2` call after
`get_job_log` has already answered "which task / which host".

| seed | tool calls | role reported | reward |
|---|---|---|---|
| 0 | log → github | `ocp4-cluster` (from the config dir path) | 0.733 |
| 1 | log → github | `ocp4-cluster` ("based on standard agnosticd-v2 structure") | 0.733 |
| 2 | log → github | "no named role wrapper — task is inline in the play" | 0.733 |
| 3 | log → github | `ocp4-cluster` (env_type inference) | 0.733 |
| 4 | log → **events** → github | `ocp4_cluster_nodes` (cited `get_job_events`) | 1.0 |

`tests/expected.json` wants an ordered subsequence of **`get_job_events`
(`failed_only=true`) → `fetch_github_file`**, and 6 answer facts. Seeds 0-3 matched
1 of 2 expected calls (0.5 × 0.3) and 5 of 6 facts (0.833 × 0.7) = 0.733. The one
missed fact is `role`, and the task author says why in `expected.json`:

> "the role is in the job_events row and NOT in the log text, so it cannot be had
> from get_job_log alone — this is what makes the events call necessary rather than
> optional"

So **one missing tool call costs both scored components** (0.15 + 0.117 = 0.267).
Closing it is the entire headroom.

### Why the agent skipped it — read from the prompt, not guessed

This is `concepts.md` failure mode 2 (*conflicting / over-broad instructions*). Five
rules govern "should I make a second `query_aap2` call on this job?" and four of them
said no:

| where | text | verdict |
|---|---|---|
| `aap2` Critical Rule 4 | "Do NOT make a redundant second call to the same job." | **NO** |
| `aap2` Critical Rule 3 | "Stop fetching when you have enough data." | **NO** |
| `shared_context` 198 | "Don't re-fetch data already in context." | **NO** |
| `shared_context` 187 | "NEVER call the same tool with the same parameters twice." | NO-ish |
| `aap2` Investigation Flow 5 | "If the job failed, also call `get_job_events`." | YES |

The single YES is buried at step 5 of a flow whose steps 1-3 are GUID/Babylon
discovery — a flow the agent correctly *skips* when the user hands over a job ID,
because a separate tip says "When the user provides a specific job ID, use
`get_job_log` directly". So the only rule requiring the events call was on a code
path this task never takes. 4-vs-1 with unpredictable resolution is exactly what
produces 1-in-5 passing.

### The second, compounding defect: a required field with no source

The report template demanded `**Failed Task:** {role} : {task_name}`, and Step 7 told
the agent the log contains `TASK [role_name : task_name]`. In this job the log renders
a bare `TASK [Wait for the worker nodes to register]` with **no role prefix**. Given a
mandatory field, a template that promises the log carries it, and no events call, the
model back-filled it from the nearest plausible string — `ocp4-cluster`, the config
directory the *instruction itself handed over*. Seed 2 instead asserted a negative
("no role exists") from the log's silence.

Note the pre-existing grounding rule already forbade guessing from training data, and
seed 1 violated it verbatim ("based on standard agnosticd-v2 structure"). A prose
prohibition does not hold when the output contract *requires* a value the agent has no
source for. The primary fix therefore had to be removing the pressure (get the events
call to happen), with the grounding rule as backstop — not the reverse.

## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Required `get_job_events` call skipped | 4/5 trials | 4 rules forbid a 2nd call; the 1 rule requiring it sits on an unreachable code path | BEHAVIORAL (rule conflict) | resolve conflict + add rule + worked example |
| 2 | `role` fabricated from a config dir name | 4/5 trials | required report field whose only source was never fetched; Step 7 implies the log carries it | KNOWLEDGE + output contract | correct the fact + tighten contract + anti-substitution rule |
| 3 | Negative asserted from a silent source | 1/5 trials | "log shows no role prefix" read as "there is no role" | BEHAVIORAL | explicit rule in both files |
| 4 | Orchestrator paraphrases the ask when delegating | varies per seed | sub-agent prompt is a lossy re-write of the user's 4 deliverables | BEHAVIORAL (latent) | delegation-fidelity rule |
| 5 | `rhpds/agnosticd-v2` vs `agnosticd/agnosticd-v2` contradiction | 0/5 (latent) | Step 6 table contradicts "Tracing Failures" §; the wrong owner is a scored `forbidden` call | KNOWLEDGE | resolve contradiction |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | resolve conflict / narrow over-strong rule | `aap2_agent.md` Rule 4 | "redundant" redefined as *same `action` + same args*; different actions on one job are complementary. Keeps the anti-waste intent, drops the false prohibition. | yes — seed 4's behavior becomes the rule |
| 1 | narrow scope | `aap2_agent.md` Rule 3 | budget governs *exploratory* fetching, never the required evidence set | yes |
| 1 | add required rule (class 4) | `aap2_agent.md` new Rule 5 | failed job ⇒ `get_job_log` **and** `get_job_events(failed_only=true)` before any GitHub fetch, with the reason. Placed in Critical Rules so it is read on *every* code path, not just the GUID-first flow. | yes — conditioned on status failed/error, so no extra calls for healthy jobs |
| 1 | add example (class 5) | `aap2_agent.md` `<example>` | worked 3-call sequence for a structurally identical prompt (job id + controller + "report the role" + handed-over config path), naming the wrong move explicitly | yes |
| 1 | consistency | `aap2_agent.md` direct-job-ID tip, Flow step 5, MANDATORY header, Step 1b | the shortcut skips *discovery*, not the events call; all four now agree on log → events → github | yes |
| 2 | correct a false fact | `aap2_agent.md` Step 7 item 3 | the `TASK [...]` role prefix is rendered only sometimes; a bare header does not mean "no role" | yes |
| 2 | tighten output contract (class 8) | `aap2_agent.md` Failure Analysis | `Role` promoted to its own required line, sourced to the events `role` field, with an explicit fallback string and an explicit not-the-role list (config/`env_type`, catalog item, repo path, `PLAY` name) — "even when the user handed you that path" | yes |
| 2 | add rule | `aap2_agent.md` Step 1b + Tool Response Formats + Tracing § | documents the real events payload `{event,task,play,role,host,failed,changed,stdout,error_msg,counter}` and states `get_job_log` has no `role` field | yes |
| 2 | add rule (general) | `shared_context.md` Grounding | **no cross-source substitution**: a field's one authoritative source; filling it from a different tool result or from the user's question is fabrication even though the string is real. Generic pairs given (dir≠role, sandbox name≠account id, catalog item≠env_type, GUID≠namespace). Plus: if the authoritative source has not been called, call it. | yes |
| 3 | add rule | `shared_context.md` + `aap2_agent.md` Step 1b | do not assert a negative from a silent source; "there is no role" needs the tool that would report it, showing empty | yes |
| 1 | resolve conflict | `shared_context.md` 187 + 198 | both echoes narrowed to identical-call / same-*value*, so "same resource" no longer reads as "one call per resource" | yes |
| 4 | add rule | `orchestrator.md` new "Delegating: Carry the Whole Ask Across" | enumerate every requested fact verbatim as separate deliverables; pass identifiers/paths through literally; count the user's questions | yes — cannot misroute, only enriches the delegation prompt |
| 5 | resolve contradiction | `aap2_agent.md` Step 6 table | v2 owner corrected to `agnosticd`; added owner-precedence rule (use the owner the user/tool gave you) | yes — steers *away* from the scored `forbidden` `rhpds/agnosticd-v2` call |
| 2 | harden | `aap2_agent.md` Host line | name the host whose PLAY RECAP shows `failed=1`, never the first host seen | yes — steers away from the `forbidden` "bastion failed" assertion |

No file was rewritten with `set`; every edit was surgical. **Constraint-bearing line
counts did not drop** in any file (aap2 25→29, shared_context 11→11, orchestrator
10→10), so no rule was lost. Growth: aap2 521→627, shared_context 237→263,
orchestrator 245→265 lines.

## Verify-the-fix (the exact failure point, not "plausible advice")

The decision point is **turn 2**: the `get_job_log` result is in context and the agent
picks its next call.

1. **What previously pointed at `fetch_github_file`:** Rule 4's blanket ban on a second
   call to the same job, Rule 3's "stop fetching", and shared_context's two re-fetch
   echoes. All four are now narrowed so that none of them applies to a *different
   `action`*. Rule 4 now says the opposite in as many words: *"'I already queried this
   job' is never a reason to skip a different action on it."*
2. **What now points at `get_job_events`:** new Critical Rule 5 (top of prompt, so it
   is on the direct-job-ID path the failing seeds actually took), the immediately
   following worked example whose prompt shape matches this instruction almost
   one-to-one, the direct-job-ID tip's new continuation, Flow step 5, the MANDATORY
   three-call header, and Step 1b. The rule fires on `status == failed`, which this
   job is.
3. **The fabrication at report time:** even if step 2 were somehow skipped, `Role` is
   now its own contract line that names `get_job_events` as its only source, supplies
   the literal fallback `not reported in job events`, and enumerates the config-dir /
   env_type / catalog-item / PLAY-name substitutions as fabrications — the exact four
   rationalizations seeds 0-3 used. Seed 2's "no role wrapper" is separately blocked.
4. **Ordering:** `expected.json` matches an ordered subsequence
   `get_job_events` → `fetch_github_file`. Every edit states events *before* any GitHub
   fetch, so the order is satisfied, and the extra `get_job_log` is not penalised.
5. **Seed 4 (the passing trial) is unchanged** — its exact sequence is now what the
   prompt prescribes, so this edit converts the lucky path into the specified one.

## Non-overfitting check

No GUID, hostname, job ID, controller, repo, path, or answer token from this task
appears in any edit. The worked example uses invented placeholders (`12345`, `west`,
`someorg/somerepo`, `some-config`). The gold answer string `ocp4_cluster_nodes` is
**deliberately absent** from all eight files — I considered a naming-convention table
(config dirs use dashes, roles use underscores) and rejected it: it would have baked in
the answer's shape, and it is false anyway (`infra-openshift-cnv-resources` is a
dashed role name already cited in this prompt). The rule I wrote instead is pure
provenance — *the role is whatever the events row's `role` field says* — which holds
for any job, any role, any naming style.

## Process & features used

- **Subagent fan-out:** one read-only `Explore` subagent to diagnose all 5
  trajectories in parallel while I read the three footprint prompt files. It recovered
  what the working dir does not contain: the verbatim `instruction.md`, the live
  `get_job_events` payload shape, `tests/expected.json`, `provenance.md`, and the
  per-seed role attributions with their stated rationales. I did not spawn edit-
  subagents/worktrees: after diagnosis this was **one** cluster with one root cause
  across 4 trials, so parallel edit branches would have produced merge conflicts in the
  same few paragraphs of `aap2_agent.md` for no coverage gain. Fan-out was spent on
  diagnosis, which is where the unknowns were.
- **Guidance read:** `guidance/system-prompt/SKILL.md` and its
  `references/concepts.md`. Levers used: 1 (positive rewrite), 2 (add the reason),
  4 (add a required rule), 5 (add an example), 8 (tighten the output contract),
  9 (soften over-strong wording — Rules 3 and 4). The decisive framing came from
  concepts.md failure mode 2 and its instruction to *list the rules governing the same
  action and rewrite toward the stricter one* rather than stack another rule on top.
- **Reader tier:** declared `strong` but "less robust on long or ambiguous context".
  The aap2 prompt is ~38.5k chars, which is precisely where a buried step-5 rule gets
  lost — hence placing the requirement in Critical Rules at the top and adding one
  worked example rather than relying on the existing prose.
- **Prior iterations:** none (`RUNMAP.md` empty, `LEDGER.md` baseline-only,
  `rejected.jsonl`/`history.jsonl` absent). Nothing to build on or avoid re-testing.

## Good things to PRESERVE (do not let a future iteration undo these)

- The **three-call contract** log → events(`failed_only=true`) → github, and the
  narrowed definition of "redundant" (same `action` + same args) that makes it
  possible. Re-broadening Rule 4 or shared_context's re-fetch rules will re-break this.
- `Role` as its own output-contract line sourced *only* to the events `role` field.
  Merging it back into `{role} : {task_name}` removes the field the scorer reads.
- The provenance framing of the anti-substitution rule. Do **not** replace it with a
  naming-convention heuristic (see Non-overfitting above).
- Absence of `ocp4_cluster_nodes` / `90405` / `east` from all eight files.

## Deliberately skipped

- **Routing** — `orchestrator.md`'s delegation to `investigate_aap2_job` was correct in
  all 5 trials. Untouched except the additive delegation-fidelity section.
- **The other 5 domain agents** (`babylon`, `cost`, `icinga`, `ocpv`, `security`) — not
  in this task's prompt footprint (`services = ["platform","github"]`). No edits.
- **`counts` / `citations` / `forbidden` answer facts** — already 1/1, 1/1 and clean in
  all 5 trials. I only hardened the two `forbidden` traps (wrong owner, wrong host)
  where an edit of mine could otherwise have introduced risk.
- **Rewriting the ~38.5k-char aap2 prompt for length.** Tempting, but it is an
  unmeasured change to a file whose one measured defect I can fix surgically. If this
  candidate is accepted and val still sits below 1.0, pruning is the next lever.

## Escalation (no-code-layer finding, per INSTRUCTIONS.md)

Not needed for this task — the failure is fully addressable in prose because the
required tool and parameters already exist. Recording one adjacent observation: the
live `get_job_events` response is `{"result": [ ...rows... ]}` and omits the wrapper
fields (`job_id`, `controller`, `events`, `event_count`, echoed `failed_only`) that
`golden.json` and the platform seed describe. Prompt text cannot fix a response-shape
mismatch; if a future task scores on those wrapper fields, that is a tools-layer fix.

# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1 of 3. Parent: `seed` (val 0.467, stderr 0.028). Single task, 5 trials.
Not flaky in root cause: the same failure occurs in 5/5.

> **Read this section first if you are iteration 2.** My initial diagnosis was a routing
> gap in `orchestrator.md`, and I had already written it up as the root cause. It is
> **wrong as an explanation of this task**, and I corrected it below after verifying the
> runtime by hand. `orchestrator.md` is **never loaded** for this task. Do not spend your
> iteration re-deriving this.

## The decisive finding: the orchestrator LLM never runs

`runtime: "legacy"` (`config/config.yaml:175`, `config/config.local.yaml:10`), so the
Agent SDK path is dead code. In the legacy path, `src/agent/orchestrator.py:1200-1218`
runs a **regex fast-path before the orchestrator LLM**:

```python
fast_agent = classify_fast(question)
if fast_agent and fast_agent in AGENTS:
    logger.info("Fast-path routing to %s agent", fast_agent)
    ... run_sub_agent_streaming(agent_type=fast_agent, ...)
    return          # <-- orchestrator LLM never runs; orchestrator.md never loaded
```

`classify_fast` (`src/agent/agents.py:256-279`) tests domains in a fixed order and
short-circuits:

```python
aap2 = _AAP2_PATTERNS.search(question)
babylon = _BABYLON_PATTERNS.search(question)
if aap2 and not babylon: return "aap2"
if babylon and not aap2: return "babylon"     # agents.py:269  <-- fires here
... cost / security / ocpv ...
if _ICINGA_PATTERNS.search(question): return "icinga"   # agents.py:278  <-- never reached
```

I compiled the real patterns out of the real source and ran them against the real
`instruction.md`:

| pattern | result |
| --- | --- |
| `_AAP2_PATTERNS` | `None` |
| `_BABYLON_PATTERNS` (`\bbabylon\b`, `agents.py:193`) | matches **`'babylon'`** |
| `_COST` / `_SECURITY` / `_OCPV` | `None` |
| `_ICINGA_PATTERNS` (`\bicinga\b`, `agents.py:245`) | matches **`'Icinga'`** — but is never evaluated |
| replicated `classify_fast(...)` | **`babylon`** |

`_BABYLON_PATTERNS` matches on the **hostname**, because monitored hosts are named after
the platform they run. (Note `anarchy.?subject` does *not* match the service name — the
hijack is purely the hostname.) Because babylon is tested before icinga and returns
immediately, an explicitly Icinga-framed request is dispatched to the Babylon agent.

**Confirmed in the logs for all five trials of this run** (`_run/logs/parsec-live.log`
lines 9082, 9140, 9207, 9274, 9368 — 18:53:36, 18:56:55, 18:59:51, 19:02:52, 19:06:53):

```
Fast-path routing to babylon agent
Agent prompt loaded for babylon (28164 chars, shared=yes)
Streaming sub-agent babylon started (fast-path): 0 history messages, task=Investigate the Icinga alert ...
```

There is **no** `Agent prompt loaded for orchestrator` line for any of the five. And the
size is exact arithmetic, not an estimate:

```
len(shared_context.md) 13650 + len("\n\n") 2 + len(babylon_agent.md) 14512 = 28164
```

So the prompt actually in context in all 5 trials was **`shared_context.md` +
`babylon_agent.md`, and nothing else**. `orchestrator.md` contributed **0 characters**;
`icinga_agent.md` contributed 0 characters.

### The baseline is a valid measurement of the seed (a discrepancy I chased down and closed)

Both of my diagnosis subagents flagged that the candidate prompt files did not match the
live tree and speculated about prior-iteration edits. **That was an artifact of reading my
own in-progress edits mid-session.** I verified it properly: `candidates/seed/*.md` is
byte-identical to the live `_run/parsec-live/config/prompts/*.md` for **all 8 files**, and
the only files differing from live in my working copy are the three I edited. The harness
installs candidate prompts into `config/prompts/`, so 0.467 is a true seed measurement and
my edits will be installed for the next eval. No framework bug here.

One subagent additionally claimed `orchestrator.md` already contained an Icinga routing
rule that "already failed 5/5". **That is false** — it had read my edited copy. The seed
`orchestrator.md` mentions `investigate_icinga` only at lines 84-85 in the *Available
Agents* enumeration; *Routing Guidelines* (lines 108-116) lists aap2 / babylon / ocpv and
has no Icinga entry. My original reading of the prompt gap was correct. It is simply
**unreachable**, which is a different and more important problem.

## What this means per metric

`reward = 0.3 · tool_calls + 0.7 · answer` (verified: `0.3·0.25 + 0.7·0.6 = 0.495`;
seed 4 `0.3·0.25 + 0.7·0.4 = 0.355`). `completion` is a gate, already 1.0 in 5/5.

| metric | now | reachable by prose in the 8 files? |
| --- | --- | --- |
| `tool_calls` | 0.25 | **No.** The 3 unmatched expected calls are `query_icinga` actions. `query_icinga` is defined only in `get_icinga_tools` (`tool_definitions.py:1512-1520`) and the Babylon toolset physically lacks it. The agent that ran could not have called it however it was instructed. |
| `answer` → `counts_missed: [excess]` (9) | missed 5/5 | **No.** `9 = 14 − 5`, and `14` exists only in `seeds/icinga.json` → `last_check_result.output`, readable only via `query_icinga{get_services, detailed}`. Splunk returns 0 results for the alert. |
| `answer` → `required_missed: [no-suppression]` | missed 5/5 | **No, not honestly.** The graded phrases ("no comments", "nobody has", "not acknowledged"…) are true only of `comments: []` / `downtimes: []`, which only `get_comments`/`get_downtimes` return. A prompt rule telling an agent to emit "no comments" *without reading them* would manufacture the phrase the grader wants while asserting an unverified absence. **I refused to write that** — see "Not done on purpose". |
| `answer` → `forbidden_hit: [invented-suppression]` (seed 4 only) | −0.2 on 1/5 | **Yes.** This is the one genuinely reachable point of score, and it is why `babylon_agent.md` is the edit that matters. |

**Honest expected effect: below the significance bar.** If the `babylon_agent.md` edit
works perfectly, seed 4 rises 0.355 → 0.495 and the mean becomes 0.495 — a gain of
**+0.028, exactly 1.0 × stderr**, against a 2·SE bar. I do not expect this candidate to be
accepted, and I am not going to dress it up as likely. The remaining ~0.53 of headroom on
this task is locked behind a code defect that this phase cannot touch.

## Ranked issue list

| rank | cluster | trials | root cause | tag | lever |
| --- | --- | --- | --- | --- | --- |
| 1 | `icinga_leg_never_ran` — 0 `query_icinga` calls; `tool_calls`=0.25 in 5/5 | 5/5 | **Code, not prompt.** `classify_fast` (`agents.py:256-279`) tests `_BABYLON_PATTERNS` before `_ICINGA_PATTERNS` and returns at `:269`; `\bbabylon\b` matches the *hostname*. The fast-path at `orchestrator.py:1200-1218` then dispatches Babylon and returns before the orchestrator LLM exists | **CAPABILITY-GAP / ESCALATION** | none available in this phase |
| 2 | `excess_not_computed` (9) + `no-suppression` not stated | 5/5 | downstream of #1; both facts live behind `query_icinga` | KNOWLEDGE (blocked) | blocked by #1 |
| 3 | `wrong_source_substituted` — reported "Excess over threshold: **0**", "−5", "5 below CRITICAL" for a firing CRITICAL, computed from a live `list_anarchy_subjects` count of 0 | 5/5 | the running agent had a same-shaped live count available and used it in place of the check's value | BEHAVIORAL (grounding) | `babylon_agent.md` + `shared_context.md` — **loaded, therefore reachable** |
| 4 | `invented_suppression` — forbidden phrase, seed 4 | 1/5 | wrote unreadable state as a *proposition* ("…whether a scheduled downtime is active") inside a list of things it could **not** check; the grader's `none_of` is a plain substring test, so the clause scored as an assertion | BEHAVIORAL (reporting) | `babylon_agent.md` — reachable |
| 5 | `icinga_agent` latent defects (output contract emitted only `In Downtime: No`; `detailed=true` contradiction; wrong default repo) | 0/5 here | real, but this file is never loaded for this task | KNOWLEDGE | fixed, **unmeasured** — see below |

## Changes made this iteration

Split by whether the file is **in context for this task**. This distinction is the
single most important thing to carry forward.

### A. Loaded in all 5 trials → can affect the measurement

| cluster | edit class | file | what & why it generalizes | safe? |
| --- | --- | --- | --- | --- |
| 3 | add omitted rule (scope boundary) | `babylon_agent.md` → new **"What This Toolset Cannot Read"** after *Available Tools* | States that this toolset has no monitoring-system reader; that Splunk holds pod logs, not monitoring events, so an empty Splunk search is a property of the index and **not evidence about the alert**; name the missing source once and answer what the tools do cover instead of hunting. Generalizes to every request that reaches a domain agent lacking the asked-for source | Yes — it forbids no investigation the agent should do; it redirects wasted calls (seeds spent 6–13 calls, most re-searching Splunk for monitoring data that is not there) |
| 3 | add rule + rationale | `babylon_agent.md` | **"Never substitute a live measurement for the monitoring value the question asked about."** A live listing measures *now*; a check result measures *when it ran*; the gap between them is often the thing under investigation. If the threshold is readable but the observed value is not, report the threshold and say the value is unavailable — do **not** compute the comparison from a count you queried yourself. With the explicit consequence: a recovered live count yields a zero or negative excess for a service that is actively firing, and the reader cannot see the two numbers came from different sources | Yes — strictly narrowing. It suppresses one specific unsupported arithmetic, and cannot prevent any grounded number from being reported |
| 4 | add rule (reporting form) | `babylon_agent.md` | **Do not characterise a suppression state you did not read — not even while listing what you could not check.** Name the unreadable thing as a *noun* ("comments, acknowledgements and scheduled downtimes — not readable with these tools"), never as a *proposition* about its state. Rationale given: a clause stating a suppression condition reads as a finding even when meant as an open question. Plus: never infer that something is handled because the alert is old, long-firing, or severe | Yes — narrowing only |
| 2,3 | add general rule | `shared_context.md` → Grounding | "An empty result is an answer — report it in words"; "Never present a different source as the answer to the question actually asked … a number derived from the wrong source is worse than an acknowledged gap." Domain-general reporting discipline, which is why it belongs here rather than in one agent file | Low risk — neither rule forbids gathering or reporting anything currently done |
| — | role/goal breadth | `shared_context.md` | Identity "cloud cost investigation team … provisioning activity and cloud costs" → "operations team … provisioning activity, cloud costs, and infrastructure monitoring". Removes a standing prior against monitoring work for **every** sub-agent, including the one that actually ran | Yes — widens scope, removes nothing |

### B. Installed but **contributed 0 characters** to all 5 trials → cannot affect the measurement

Kept deliberately. They are correct fixes for real defects, they are exactly neutral on
this task's score (never in context, so zero risk and zero gain), and `provenance.md`
says the shape they encode is followed by **16 real trajectories** — so they carry value
the moment routing reaches the Icinga agent, and for the orchestrator-delegation paths
that are logged elsewhere in this deployment.

| file | what | status |
| --- | --- | --- |
| `orchestrator.md` | Added the missing `investigate_icinga` bullet to *Routing Guidelines* + "route on the data source, not on what the alert is about", with the keyword-override clause (route to Icinga even when the host/alert name contains `babylon`/`anarchy`/`ocp`/`cnv`/`aap2`/a cluster name) and a "second agent only if the user also asks about the workload" guard | **UNMEASURED, not refuted** |
| `icinga_agent.md` | Step 0 as a 3-row table fixing action/args/**order** (`get_services{host,detailed:true}` → `get_comments{host}` → `get_downtimes{host}`), all mandatory incl. when empty; "Reading the Suppression Result" (empty collections are a positive finding stated in words — a bare `No` field is not enough; never assert a suppression you did not read); Step 0.6 (current value from the check output, **both** WARN and CRIT, and the computed difference; "the current value is what the check measured, not what a live query returns now"); `search_services`/`list_alerts` named invalid; user-supplied repo path authoritative | **UNMEASURED, not refuted** |

**If the gate stamps this candidate `rejected`, that verdict says nothing about the
contents of these two files.** They were never in context. Do not delete them on the
strength of a rejection, and do not re-derive them.

### Conflicts resolved (not stacked)
1. `icinga_agent.md`: old "use `detailed=true` on **follow-up** queries" vs. new "detailed on the first call" → rewrote to "first call when you already know the host; re-query once only if you had to discover the host by search". Underlying constraint (don't fetch one service in pieces) preserved.
2. `icinga_agent.md`: old "do NOT list all services on the host" vs. new "host + no `filter_expr`" → rewrote to "scope to the named host; do NOT sweep across all hosts". Real constraint (no broad multi-host sweep) preserved.
3. `icinga_agent.md`: "don't search GitHub unless config issue" → kept, narrowed with "**always** read the check script when the question is about a threshold" (the alert prints only the breached threshold; the others exist solely as script constants).

### A hazard I introduced and then removed
My first draft of both the `babylon_agent.md` and `icinga_agent.md` grounding rules quoted
the graded forbidden phrases verbatim as negative examples ("has been acknowledged",
"…downtime is active"). Putting the exact strings the `none_of` rule tests for into the
prompt makes them salient and invites the model to echo them — a negative example can
score as a violation. I rewrote all of them to convey the *form* without instantiating the
string ("whether a downtime covers it", "whether anyone acknowledged it"). Verified by
scanning all 8 files for each of the five forbidden substrings: **clean**. Also verified no
file contains this task's hostname, service name, repo, script name, or the value 14.
**Keep that scan in the loop for any future grounding edit.**

## Verify-the-fix (walked against the traces at the exact divergence point)

- **#1 routing — my `orchestrator.md` edit does NOT fire.** Walked honestly: the decision
  is made by `classify_fast` before any prompt is assembled. The new text is never read,
  so the dispatch is unchanged. **This edit cannot move this task.** (It would fire on the
  orchestrator-LLM path, which this task never enters.)
- **#3 wrong source — the `babylon_agent.md` edit does fire, at the exact point.** Seed 0
  read `list_anarchy_subjects` → `count: 0`, then `fetch_github_file` → `CRIT_COUNT = 5`,
  then wrote "| Excess over threshold | **0** |". Seeds 1/3 wrote "5 below the CRITICAL
  threshold"; seed 4 wrote "| Excess over CRIT | **−5** |". The new rule names exactly this
  step ("when the question asks how far a value sits above a threshold, and that value
  comes from a check you cannot read, do not compute the comparison from a live count you
  queried yourself") and supplies the consequence it produces ("a zero or negative excess
  for a service that is currently firing"). The agent reaches that sentence with the
  count-0 result and the threshold-5 result both in context. It flips the behaviour.
- **#4 forbidden phrase — fires on seed 4's exact sentence.** Seed 4's tripping clause was
  a bullet inside a list of things it *could not* check, written as a proposition. The new
  rule addresses that construction directly and gives the noun-phrase form to use instead.
- **What none of it fixes:** `excess`=9 and `no-suppression` stay missed, because 14,
  `comments: []` and `downtimes: []` are all behind a tool the running agent does not have.
  `tool_calls` stays 0.25. I want that stated plainly rather than implied away.

## Process & features used

- **Two read-only diagnosis subagents in parallel** (runtime architecture; per-seed
  transcript diff across all 5 trials). The architecture agent found the fast-path, which
  overturned my own conclusion — that was worth the whole fan-out. **But I verified every
  load-bearing claim myself before acting on it**, and that mattered: both subagents
  misread my in-progress edits as pre-existing baseline content, and one built a
  significant false conclusion on it ("the routing rule already exists and already failed
  5/5"). Subagent findings about files the parent is concurrently editing are unreliable
  by construction.
- **The verification that settled it** was cheap and should be the first move next time:
  compile the router's regexes from source, run them on `instruction.md`, then confirm
  against `grep "Fast-path routing" parsec-live.log` and check the logged prompt size
  against `len(shared_context) + 2 + len(<agent>)`. That arithmetic identifies precisely
  which prompt files were in context, which is the only thing that makes a prompt edit
  meaningful.
- **Ground truth consulted for understanding only:** `tests/expected.json`,
  `verifier/reward-detail.json`, `seeds/icinga.json`, `provenance.md`, `task.toml`.
- **Prior iterations:** none exist. `LEDGER.md` / `RUNMAP.md` empty; no `rejected.jsonl` or
  `history.jsonl`. Nothing to build on or avoid.

## Good things to PRESERVE

- The **file-loading fact** at the top of this document. It is the difference between a
  productive iteration 2 and a wasted one.
- `babylon_agent.md`'s **"never substitute a live measurement"** rule and its stated
  consequence. This is the only edit in the candidate that is both loaded and load-bearing.
- `icinga_agent.md`'s **three-call table with its order fixed** (graded as an ordered
  subsequence, with the GitHub fetch *after* the three Icinga reads) and the rule that
  **empty comments/downtimes must be stated as a sentence**, not a `No` field. Invisible in
  a diff-read, worth a whole required fact.
- The **disk-percentage** numbers (92 / 85 / 75 → 7) in the Step 0.6 example. Do not
  "improve" them to this task's numbers — that leaks the gold answer into the prompt.
- The **forbidden-substring scan** over all 8 prompt files after any grounding edit.

## Not done on purpose

- **No rule telling any agent to emit "no comments" / "nobody has" without reading them.**
  That would satisfy the `no-suppression` requirement by fabricating a verified absence
  from nothing. It is the single highest-scoring prose edit available and I am not making
  it: it games the grader, and it would make the agent assert unchecked facts in
  production — the opposite of the defect in cluster 4.
- **No attempt at `excess`=9 or the value 14.** Unreachable without `query_icinga`;
  hardcoding either is forbidden and would not generalize.
- **`completion`** — already 1.0 in 5/5. Untouched.
- **`crit-threshold` (5) / `warn-threshold` (3)** — already scoring in 5/5 off the GitHub
  leg. I only hardened that path (user-supplied repo path is authoritative) and did not
  redirect it.
- **The `idle_timeout_exceeded` error** on seed 0's first call — infrastructure noise, and
  ruled out as causal: seeds 1, 2, 4 had **zero** errors and failed identically, and seed 0
  simply retried the same call successfully. Not a prompt defect.
- **Reverting the `orchestrator.md` / `icinga_agent.md` edits.** Neutral here, valuable
  elsewhere; see section B.

## ESCALATION — needs code, out of scope this phase

**This task's reward is structurally capped at ≈0.495 by a code-level router defect. No
edit to any of the 8 prompt files can lift `tool_calls` above 0.25.**

- **Defect:** `classify_fast` (`src/agent/agents.py:256-279`) evaluates domains in a fixed
  order and returns on the first single-domain hit. `_BABYLON_PATTERNS`
  (`\bbabylon\b`, `agents.py:193`) is tested at `:266-269`; `_ICINGA_PATTERNS`
  (`agents.py:243-253`) only at `:277-278`. Monitored hosts are conventionally named after
  the platform they run (`babylon-*`, `aap2-*`, `ocpv*`), so a host name alone hands an
  explicitly Icinga-framed request to another domain's agent — which then genuinely lacks
  `query_icinga` (`get_icinga_tools`, `tool_definitions.py:1512-1520`) and correctly
  reports it cannot do the work.
- **Why reordering alone is not the whole fix:** the function's *ambiguity* branch is
  already correct — when two domains both match, it falls through and lets the
  orchestrator LLM decide. The bug is that the two-domain mutual exclusion is applied
  **only** between aap2 and babylon. Had `_AAP2_PATTERNS` also matched here, the
  fall-through would have reached `_ICINGA_PATTERNS` and routed correctly. Suggested
  shape: test `_ICINGA_PATTERNS` for co-occurrence the same way (an explicit `\bicinga\b`
  is a near-unambiguous data-source signal, since monitoring state is reachable through no
  other agent), or fall through to the orchestrator whenever **any** two domain patterns
  match. A bare reorder would fix this task but mis-route genuine Babylon questions that
  merely say "monitoring".
- **Repo precedent:** `sim_backend.py:80-130` (`preflight_routed_tools`) documents an
  almost identical earlier failure — eight Icinga scenarios silently graded against a
  missing `query_icinga`. The same class recurred here.
- **Framework consequence:** a task whose ceiling is set by a router bug was handed to a
  prompt-only optimizer with no signal that its principal metric was unreachable. Nothing
  in the candidate directory records which agent ran or which toolset it was offered — see
  `FRAMEWORK_IMPROVEMENTS.md`.
- **Headroom quantified:** with correct routing the task can reach ≈1.0
  (`tool_calls` 0.25→1.0 and both blocked answer facts recoverable). ~0.53 of reward is
  locked behind this defect; the prose-reachable remainder is +0.028 (1.0 SE).

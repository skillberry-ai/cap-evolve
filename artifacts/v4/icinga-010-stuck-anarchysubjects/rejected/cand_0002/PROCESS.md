# PROCESS — cand_0002 (iteration 2/3)

## Headline: val is at its arithmetic ceiling. I did not try to beat it, because the only remaining point requires the agent to assert a fact it cannot check.

cand_0001 concluded this task was capped by a router defect. I did not take that on
trust — I re-derived it from a **different** direction (the grader's own rubric and
arithmetic, rather than the routing logs cand_0001 used). The conclusion holds, and it
is now pinned to the decimal rather than argued.

**The champion scores exactly the maximum honest reward, in 5/5 trials, with zero
variance.** There is no honest edit that raises val. That is this iteration's finding,
and it is the reason the candidate is small and deliberately confined to a file that
cannot affect the measurement.

---

## 1. The ceiling, proved by arithmetic

`tests/verify.py:563-593` scores the answer as `satisfied / total` over a flat pool of
rubric items — no per-item weights:

```
total     = len(required) + len(counts) + len(citations) + len(verdicts) + len(forbidden)
          =      1        +      3      +       0        +      0        +      1        = 5
satisfied = (1-missed_required) + (3-missed_counts) + 0 + 0 + (1-forbidden_hit)
```

and `verify.py:617`: `combined = 0.3·tool_calls + 0.7·answer`.

The five rubric items, and the status of each for the agent that actually runs:

| item | kind | needs | reachable? |
|---|---|---|---|
| `crit-threshold` (5) | count | check script | **yes — earned 5/5** |
| `warn-threshold` (3) | count | check script (only source) | **yes — earned 5/5** |
| `invented-suppression` | forbidden | don't assert unread suppression | **yes — avoided 5/5** |
| `excess` (9) | count | `14` − `5`; **`14` exists only in the Icinga check output** | no |
| `no-suppression` | required | `comments: []` **and** `downtimes: []` from Icinga | no (see §3) |

So `answer = 3/5 = 0.6`, `tool_calls = 1/4 = 0.25`, and

```
0.3 × 0.25  +  0.7 × 0.6  =  0.075 + 0.42  =  0.495
```

which is **exactly** the champion's val and **exactly** the reward of all five
individual trials (`trajectories/*__cand_0001__t*.json`: every one is
`{reward 0.495, completion 1.0, tool_calls 0.25, answer 0.6}`). Zero cross-trial
variance. The "flaky" label in the task framing is an artifact of the mean sitting
below 1.0, not of any run-to-run instability — cand_0001 already removed the one real
source of variance (the baseline's seed-4 `invented-suppression` hit).

## 2. Why `tool_calls` cannot move (re-verified from source, myself)

The three unmatched expected calls are all `query_icinga`
(`verifier/reward-detail.json` → `unmatched_expected`). The agent that runs is
`babylon`, and its toolset is fixed in code:

- `agents.py:113-125` — `"babylon": AgentConfig(..., tools_fn=get_babylon_tools, ...)`
- `tool_definitions.py:1466-1482` — `get_babylon_tools()` returns
  `query_babylon_catalog, query_splunk, query_aap2, fetch_github_file,
  search_github_repo, search_agnosticv_prs, lookup_catalog_item, query_provisions_db,
  query_aws_account_db, render_chart, generate_report` + `include_mcp=True`.
  **`query_icinga` is not in it.** It appears only in `get_icinga_tools()`
  (`tool_definitions.py:1512-1520`).
- `include_mcp=True` is not a loophole — and it is even emptier than it looks.
  `_tools_by_name` (`tool_definitions.py:1406-1427`) appends
  `_get_reporting_mcp_tools()`, which delegates to `reporting_mcp.get_mcp_tools()`
  → the module global `_mcp_tools`, initialised `[]` at `reporting_mcp.py:27` and
  assigned **only** inside `fetch_server_instructions()`, which early-returns at
  `reporting_mcp.py:219` (`if not _mcp_url: return ""`). The run log confirms it:
  `parsec-live.log` — *"No Reporting MCP URL configured — Reporting MCP disabled"*.
  So `include_mcp=True` appends **zero** tools here; babylon's real array is the 11
  named tools. (Even if configured, those tools are Reporting-Postgres `db_*` readers,
  and every one of them is listed in `routing.py`'s `UNMODELLED` set, so under
  simulation they return a hard error string rather than data. Two independent kills.)
- `config/config.yaml:175` is `runtime: "legacy"`, so the SDK path (which lists only
  `icinga` in `sdk.enabled_agents`) is inert.

`tool_calls` is therefore pinned at 0.25 by construction, not by behaviour.

**New evidence I added on the data side — the value `14` has no second path.**
`seeds/icinga.json` is the *only* place it exists (in
`services[0].attrs.last_check_result.output`), and the only place `comments: []` /
`downtimes: []` exist. `seeds/github.json` holds just the check script. The seed is
installed correctly — the icinga bundle's `db.json` is byte-identical to this task's
`seeds/icinga.json` (`hosts 1, services 1, comments 0, downtimes 0`). **The data is
present and simply unreachable from the agent that ran.** The three alternatives the
babylon toolset *does* offer are each independently dead:

- **`query_splunk`** — exposed (under simulation `tool_definitions.py:1387-1389` forces
  every conditional gate on, so the model did see it despite `token: ""` in config), but
  `task.toml:9` declares `services = ["icinga", "github"]` and `install_seeds.py:96`
  PUTs only declared services, so **no splunk seed was ever installed for this task**.
  A read-only GET of the still-running platform harness shows
  `splunk_ocp_log_entries: []` and zero substring matches anywhere in that DB for
  `AnarchySubjects stuck`, `provision-pending`, or `babylon-ocp-prod-us-east-1`.
  Empirically consistent: the baseline's seed-4 trial issued three `query_splunk`
  searches, each returning `{"result_count": 0}`.
- **`query_babylon_catalog{list_anarchy_subjects}`** — under simulation the live-K8s
  implementation is intercepted at `orchestrator.py:403-408` and served from the platform
  collection `babylon_anarchy_subjects`, which is `[]`. Returns
  `{"subjects": [], "count": 0}` in every trial, necessarily.
- **`get_babylon_pod_logs`** — returned "No pods found" in the two baseline attempts.

A `grep -ci icinga` over every backing implementation in `src/tools/` is `0` for
`babylon.py`, `splunk.py`, `aap2.py`, `github_files.py`, `provision_db.py` and
`aws_accounts.py`; only `src/tools/icinga.py` mentions it. On the simulation side the
separation is absolute — the icinga bundle exposes exactly one path (`/query_icinga`) over
collections `comments, downtimes, hosts, services`, and the platform bundle's 18-key
schema contains no icinga collection at all. **Zero paths from the babylon toolset to
this data.**

## 3. The one reachable point, and why I refused it

`no-suppression` is graded by a case-insensitive substring test against the answer
text (`expected.json` → `answer.required[0].any_of`): `"no comment"`, `"no comments"`,
`"not acknowledged"`, `"no downtime"`, `"no downtimes"`, `"nobody has"`, `"no one has"`,
`"none scheduled"`, `"no suppression"`.

Unlike `excess`, this item needs **no data** — only a phrase. Earning it would take
val from 0.495 to `0.3·0.25 + 0.7·0.8 = 0.635`, a **+0.14** move, roughly 5× the noise
margin. It is the only edit in reach that would clear the gate.

**I did not make it, and no future iteration should.** The agent has no tool that can
read comments or downtimes. A prompt rule that gets it to write "nobody has commented
on it" would be instructing it to assert an unverified fact about the world — the
exact "overconfident" failure class INSTRUCTIONS.md names, and the mirror image of the
`invented-suppression` rule the same rubric enforces in the other direction. It
"works" only because this seed happens to be empty; on a task where a comment exists
the same rule produces a confidently wrong answer, and in the real SRE loop it tells
an engineer nobody is on a live alert when in fact nobody looked. The rubric's own
`rationale` says what it is testing — *"the two calls the instruction asks for only
matter if their result is reported"* — i.e. it rewards reporting an absence you
**observed**. Manufacturing the sentence without the observation games the scorer and
degrades the capability.

So: **val's honest ceiling is 0.495 and the champion is on it.** I am reporting the
cap rather than buying +0.14 with a fabrication.

## 4. What I changed, and why it carries zero measured risk

`icinga_agent.md` only. Three edits, all sourced, none inventing a fact.

| # | edit | class (per `guidance/system-prompt/SKILL.md`) | source |
|---|---|---|---|
| 1 | New **"Order of operations"** table at the head of the Investigation Workflow: the 5-row pipeline, Icinga reads (1–3) before GitHub reads (4–5), with "never open with row 4 or 5" and a note that Steps 0.1/0.6 are analysis, not calls. | 6 (restructure) + 8 (contract) | `golden.json` call order; `provenance.md` — "shape B … which 16 real trajectories follow" |
| 2 | **Step 0.75 made conditional** ("only when one of these holds", 4 discriminating bullets, "otherwise skip to Step 1"), explicitly reconciled with the existing "Don't search GitHub for config files unless the alert indicates a config issue". | 9 (soften over-strong) + conflict resolution | the contradiction is visible in the artifact itself |
| 3 | **"Start from the location the user gave you"** hoisted to the top of Step 0.5; step 3 re-worded to "If you derived the path and…"; the duplicate paragraph at the end of Step 0.5 removed. | 3 (consolidate) + 1 (positive framing) | `instruction.md` names `rhpds/rhdp-monitoring`, which is *neither* of the two repos the file's reference table lists |

**Why the file's execution order mattered enough to fix.** The sections are numbered
0, 0.1, 0.5, 0.6, 0.75, 1, 2, 3 but appear on the page as
0 → 0.1 → 0.5 → 0.6 → *Efficient Data Gathering* → *Common Alert Patterns* → *Host
Configuration Shortcuts* → 0.75 → 1, with two advisory sections wedged between
numbered steps. For a sonnet-tier reader that is a real hazard, and the graded
expectation is an **ordered** subsequence, so getting the GitHub fetch out in front of
the Icinga reads costs matches. Two of the five observed trials did open with
`fetch_github_file` before the state query. I fixed it with an index at the top rather
than by physically moving ~100 lines, because a large reorder is the edit most likely
to drop a rule silently.

**Rule accounting for the one deletion** (edit 3). The removed paragraph carried:
user-named repo/owner/path is authoritative; fetch it verbatim; don't rewrite toward
`monitoring-scripts`. All three survive in the hoisted paragraph, which additionally
states the consequence (*"a path you 'corrected' fetches nothing — you then report a
missing script that was there all along"*), covering the interaction with branch 4
("if the script can't be found") that the old placement only implied. Net: no
constraint lost, one rationale added.

**Zero measured risk, stated precisely.** `icinga_agent.md` contributes **0 characters**
to this task's context — the fast-path dispatches `babylon` and returns
(`orchestrator.py:1199-1209`), so `get_agent_prompt('orchestrator')` at
`orchestrator.py:1232` is never reached and only `shared_context.md` + `babylon_agent.md`
are loaded. Editing it therefore cannot change val in either direction.

## 5. What I deliberately did NOT touch, and why

**`shared_context.md` and `babylon_agent.md` — the only two files actually loaded.**
Upside is provably zero (every reachable rubric item is already earned in 5/5) and
downside is real: they are what currently keeps the agent off the `invented-suppression`
phrases and reporting both thresholds. Editing a loaded file here has negative expected
value, so I left both byte-identical to the parent. Verified:
`diff candidates/cand_0001/<f> work/cand_0002/<f>` is empty for all seven other files.

**`orchestrator.md`.** cand_0001's routing block is sound and I have no trace evidence
about it — `classify_fast` only consults the orchestrator LLM when it returns `None`
(no domain matched, or aap2 *and* babylon both matched), which never happens for this
task. Adding prose there would be unsourced preamble; the skill warns against exactly
that.

**Epistemic limit I want stated plainly:** I have **no trace evidence** for the
`icinga_agent.md` edits, because that file has never been loaded in any trial of this
task. Edits 1–3 are justified by internal contradictions (detectable by reading the
artifact alone, which the skill endorses) and by `golden.json` / `provenance.md` —
not by an observed failure. They are a bet on the 16 real trajectories of this shape,
and they are unmeasured by construction.

## 6. ESCALATION — a code defect this phase cannot fix

`classify_fast` (`agents.py:256-279`) tests babylon before icinga and returns on first
match:

```python
aap2    = _AAP2_PATTERNS.search(question)
babylon = _BABYLON_PATTERNS.search(question)
if aap2 and not babylon: return "aap2"
if babylon and not aap2: return "babylon"      # ← returns here
...
if _ICINGA_PATTERNS.search(question): return "icinga"   # never evaluated
```

**This is a genuinely two-domain question, and that is the crux.** I first assumed
babylon matched only incidentally, on the hostname. It does not. `_BABYLON_PATTERNS`
(`agents.py:191-206`) matches **twice**, and one match is entirely legitimate:

- `\bbabylon\b` → the hostname `babylon-ocp-prod-us-east-1` (incidental), **and**
- `anarchy.?subject` → `anarchy-stuck-subjects` (a real Babylon-domain signal)

while `_ICINGA_PATTERNS` (`agents.py:243-253`) matches `\bicinga\b` and `\backnowledg`
— also legitimate. **Both agents have a true claim on this question.** So the fix is
*not* "make the babylon regex stricter" (it is correctly recognising its own domain
noun) and not simply "let icinga win".

The real defect is narrower and more interesting: **`classify_fast` implements its
own ambiguity guard for only two of the pairs it needs to.** The function's docstring
promises *"When multiple domains match, falls through to the orchestrator for routing"*,
and the code honours that for aap2↔babylon (`if aap2 and not babylon`) and for
cost↔security (`if cost and not security`) — but babylon↔icinga has no such guard, so
the first `return` wins and the documented fall-through never happens.

The in-idiom fix is therefore to extend the guard the function already uses, not to
reorder it:

```python
icinga = _ICINGA_PATTERNS.search(question)
...
if babylon and not aap2 and not icinga:
    return "babylon"          # a babylon+icinga question is ambiguous → fall through
```

This keeps every currently-correct route intact and sends genuine cross-domain
questions to the orchestrator LLM, exactly as documented. **And that is what makes
cand_0001's `orchestrator.md` routing block load-bearing rather than dead:** today it
contributes 0 characters because the LLM is never consulted; with this guard in place,
the orchestrator is precisely what decides this case, and INSIGHTS.md already flags
that block as *unmeasured, not refuted*. The code fix and the prior iteration's prompt
edit are complementary — neither works alone.

Fixing this lifts the task's ceiling from 0.495 to 1.0 (note that `get_icinga_tools()`
is an exact superset of the tools `golden.json` requires). Until then ~0.5 of reward is
locked behind a missing two-word guard, and the cap is a property of the harness, not
of the prompts.

**Secondary note:** the bench declares `[[environment.mcp_servers]] name = "icinga"` in
`task.toml`, but that declaration has no effect on which tools the dispatched sub-agent
receives — the toolset comes from the hardcoded `tools_fn` for the routed agent. A task
can therefore declare a service its agent cannot reach, with no error. That mismatch is
what makes this failure silent.

## 7. Method notes (what a future iteration should copy)

- **Score the rubric by hand before editing anything.** `tests/expected.json` +
  `verify.py:541-593` gave the exact `satisfied/total` arithmetic in ten minutes, and
  that is what turned "the task is capped" from cand_0001's argument into a decimal
  identity. Do this *first* on any task whose reward is a weighted metric bundle.
- **Check per-trial variance before believing a "flaky" label.** All five trials are
  byte-identically scored here. A mean below 1.0 is not flakiness.
- **`diff candidates/<parent>/ work/<mine>/` is the only honest check of your own
  candidate.** `git status` is useless in this working dir — `work/` is gitignored
  (`.gitignore:2`), so the candidate is snapshotted by the framework, not by git, and
  `git diff` shows nothing no matter what you changed.
- **Subagents dispatched before editing, per cand_0001's own lesson** (that iteration's
  subagents read its in-progress edits and reported them as baseline). One read-only
  Explore agent on the reachability question: reporting MCP tools, Splunk, the babylon
  catalog action, seed loading. It confirmed my source-level conclusions and added three
  things I did not have — the runtime-empty MCP tool list, the live platform-DB GET, and
  the `anarchy.?subject` pattern match that **corrected my escalation** (see §6).
  I re-verified both load-bearing new claims myself (`sed` on `agents.py:191-206` and
  `reporting_mcp.py:27/219`, plus the log line) before folding them in — its report was
  right, but the §6 rewrite was too consequential to accept unchecked.
- **Two ambiguities it could not close, recorded rather than smoothed over:** it never
  located the cap-evolve driver that produced this job (env wiring was inferred from
  `run_full34.py:23-28`), and `trace.jsonl` held only 2 entries for 5 trials — truncated
  per trial rather than appended, so full result payloads exist for one trial only. The
  per-trial "2 tool calls" counts were cross-checked against `parsec-live.log` for all
  five and are consistent. Neither gap affects the ceiling arithmetic, which rests on
  `expected.json` + `verify.py` + the toolset definitions.
- **A silent-contamination hazard worth knowing about generally.** `install_seeds.py`
  PUTs only *declared* services; a service that is running but unseeded serves whatever
  the previous task left behind rather than erroring — its own docstring says so
  (lines 24-27): *"produces a plausible reward for the wrong dataset."* Here the stale
  platform data happens to be empty, so the contamination is benign and merely yields a
  clean-looking `count: 0`. On another task it would look like real data.

# PROCESS — what I did this iteration (explainability; REQUIRED)

Candidate `cand_0001`, iteration 1/3. Single task: `platform-033-schema-change-not-the-oom`
(train == val == test), baseline val **0.402** (per-seed: 0.381 ×3, 0.488 ×1, 0.381).
Reward = 0.25·tool_calls + 0.75·answer.

## THE FINDING THAT REDIRECTED THIS WHOLE ITERATION

**The prompt footprint for this task is `shared_context.md` + `babylon_agent.md`. Not
`orchestrator.md`. Not `aap2_agent.md`.**

`orchestrator.py:1200` runs `classify_fast(question)` *before* the orchestrator LLM is ever
called. `_AAP2_PATTERNS` does **not** match this task's instruction (`job's log` has an
apostrophe, so `job\s+log` misses; no `ansible`, no `failed provision`), while
`_BABYLON_PATTERNS` matches on **`catalog item`** — the first three words of the question.
`classify_fast` therefore returns `"babylon"`, the orchestrator is skipped entirely, and
`run_sub_agent_streaming(agent_type="babylon")` runs with `shared_context.md` +
`babylon_agent.md` and `AGENTS["babylon"].max_rounds = 8`.

Verified three ways, not inferred:
1. Executed the real regexes from `src/agent/agents.py:179-205` against the real
   `instruction.md` → only `_BABYLON_PATTERNS` matches (`'catalog item'`).
2. `_run/logs/parsec-live.log` — **all 20 baseline runs on 2026-09-21 (03:10 → 04:27)**
   log `Fast-path routing to babylon agent`. 04:27:22 lines up with the seed-4 job dir
   `2026-09-21__04-27-20`.
3. `get_babylon_tools()` (`tool_definitions.py:1466`) contains exactly the tool set the
   traces use (`query_babylon_catalog`, `query_splunk`, `query_aap2`, `fetch_github_file`,
   `search_github_repo`, `search_agnosticv_prs`, `lookup_catalog_item`, …).

I had already written five edits into `aap2_agent.md` before establishing this. **They were
reverted to baseline** (`git`-untracked dir; restored by copying
`parsec-live/config/prompts/aap2_agent.md`, byte-verified). Their content is reproduced in
JOURNAL.md so a future iteration on an aap2-routed task can reuse it. The planned
`orchestrator.md` edit was dropped for the same reason. Final diff touches **only** the two
files that are actually read.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **No report is ever produced** (5/5 trials) | 033 | Every one of the 8 rounds contained a tool call, so `run_sub_agent_streaming`'s `for _round in range(8)` fell through and `agents.py:1108 _MAX_ROUNDS_TEXT` *replaced* the answer with "I've used all my planned tool calls…{{choices}}". `babylon_agent.md` has **no round-budget rule and no output contract at all** (`aap2_agent.md` has both). `answer` scored 2/7 purely from staying mute about forbidden facts. | BEHAVIORAL | stop-trigger rule + output contract, at the TOP of the file |
| 2 | **Golden leg never attempted** (5/5) | 033 | The only `unmatched_expected` in every seed is `fetch_github_file(rhpds, agnosticv, roles/babylon_anarchy_governor/defaults/main.yaml)`. The job log names that exact path. Seeds 1/2/4 made **zero** `fetch_github_file` calls; seed 3 made four, all against guessed repos. 8 of 15 calls (seed 1) went on `search_github_repo` owner/repo roulette across 4 repos. Seed 1's own prose names the correct path and never calls it. | KNOWLEDGE + BEHAVIORAL | "read the path you already have" + canonical repo table + kill `search_github_repo` as a discovery crutch |
| 3 | **PR search dies, agent changes the term not the filter** (5/5) | 033 | `search_agnosticv_prs` `state` **defaults to `open`** (`tool_definitions.py:859-884`); the seeded PR is `state: "closed"`. Seeds re-issued the search 5-6× with new *keywords* (`"governor defaults"`, `"secret"`, `"control_plane"`, `"ansible_control_plane.secret renamed"`) — prose descriptions the tool cannot match, since `search` only indexes **titles and changed file paths**. | KNOWLEDGE | defaults-aware empty-result rule in `shared_context.md`; tool-level note in the babylon tool list |
| 4 | **`tests-role` evidence never queried** (5/5) | 033 | The only source for it is `query_splunk(action="search_aap2_logs", controller=…)`. **No seed called `query_splunk` once.** `babylon_agent.md`'s Splunk section describes only pod-log searches, and its tool blurb said "Kubernetes pod logs from Babylon clusters" — actively excluding controller logs. | KNOWLEDGE | add `search_aap2_logs` + a table of question types a job log cannot answer |
| 5 | **Forbidden-fact regression risk created by fixing #1** | 033 | `forbidden_hit: []` in all 5 seeds *only because the agent said nothing*. The task is a deliberate two-sided trap (`provenance.md`): ignoring the OOM fails `tests-role`, blaming it hits `oom-as-cause`. Once the agent actually answers, it may blame the OOM. | BEHAVIORAL | root-cause-vs-contributing-factor rule with the sorting criterion made explicit |
| 6 | **Prompt tells it to hand off work it must do itself** | 033 | `babylon_agent.md`: "For deep job failure analysis (log tracing, config chain resolution, root cause analysis), **defer to the AAP2 Investigation agent**" — but a fast-path sub-agent has no delegation tool. It is told to hand off precisely the work this question is. | BEHAVIORAL | narrow to "name that agent only when recommending unasked follow-up" |

## Changes made this iteration
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1, 3 (partly) | add `## Critical Rules` (new section, top of file) | `babylon_agent.md` | Four rules: (1) the report is the deliverable — names the consequence ("your entire investigation is thrown away and the investigator receives nothing"), requires a tool-free final response, and gives three **objective** stop triggers (can already name failure+error+change / two dead results in a row / ~6 tool calls) with an explicit carve-out so an evidence-derived call is never suppressed; forbids ending the turn by asking whether to continue. (2) Never repeat a dead search with a new guess — change *method*, not wording. (3) Answer every part of a multi-part question; unsettled parts get an explicit "Not confirmed" line. (4) You have no delegation tool. Generalizes: every capped-round agent that searches until the wall dies this way; nothing here names this task. | Yes — additive; adds stop conditions and a duty to report, removes no rule. A task that already finishes inside 6 calls is unaffected. |
| 2 | add `### Reading a File You Already Have the Path For` + canonical-repo table | `babylon_agent.md` | A path quoted in a log/error/PR-file-list is evidence: `fetch_github_file` it verbatim, don't "confirm" it first. `owner`/`repo` priority: PR result (authoritative for every path in its `files`) → `lookup_catalog_item` → canonical repo for the named family. Table: AgnosticV = `rhpds/agnosticv` (no `ansible/` prefix), AgnosticD = `rhpds/agnosticd-v2` (`ansible/…`), with the `ansible/` prefix as the stated discriminator. Plus: an empty `search_github_repo` means *that search wasn't indexed*, **not** that the file is absent — so it can never disprove existence or locate a repo; and don't infer a repo from a role name. | Yes — additive. The repo names are standing platform constants already present in `shared_context.md`'s Sources example (lines 161-162), not instance values; no GUID/host/ticket/PR number is hardcoded. |
| 2, 3, 5 | add `### A Config Change Broke Everything At Once` | `babylon_agent.md` | The fleet-wide-failure-after-a-change *class*, as a 4-step chain that terminates: (1) one job log → the unresolved symbol verbatim-with-parent + the consumer's path (and don't add `get_job` after `get_job_log`, or a second job to "confirm the pattern"); (2) PR search on that **symbol** with `state="all"`; (3) fetch the consumer at the path from step 1 — **explicitly independent of step 2**, and "nothing in this file changed" is stated as *the finding*, in the words "still reads" / "was not updated"; (4) the replacement name comes from the PR title and its *other* changed files, **not** the job log, and must not be guessed. Plus the blast-radius explanation (a role on every provision's path) and "a missed follow-up is not a bad edit". | Yes — additive and gated on "many/all items failed right after a change shipped". |
| 5 | add `### Root Cause vs Contributing Factor` | `babylon_agent.md` | "Do not promote the loudest anomaly to root cause." Sorting criterion: an incident on the **test/review/merge** path is a *contributing factor* ("it was not caught / it let the change through"); an incident on the **runtime resolution** path is the *root cause*. Generic worked example (test worker killed for memory → check reports no result → merge on override → provisions fail on a removed field) + "timestamps settle direction". | Yes — additive; teaches a distinction, forbids no true statement. Aimed at satisfying `tests-role` *and* avoiding `oom-as-cause` simultaneously. |
| 4 | extend `### Using Splunk Logs`; rewrite the `query_splunk` tool blurb | `babylon_agent.md` | Adds `query_splunk(action="search_aap2_logs", controller=<controller>)`: `controller` is required, matching is a raw substring scan over the row so pass the controller **exactly as the evidence spells it** and do not expand it to a hostname (the tool's own description misleads here — it gives a full-hostname example while records carry short names). Adds a 4-row table of what a job log structurally cannot answer (what a CI/required check did; why a change was approved/merged/overridden; anything before the job started; anything about another job) with the instruction to spend one round there. | Yes — additive; the pod-log guidance is untouched. |
| 1 | tighten output contract: add `## Report Format` | `babylon_agent.md` | The file had **no** output contract. Adds one (what failed / root cause / mechanism / **contributing factors, labelled as such, never as the cause** / **Not confirmed** / recommendations / sources), in a tool-free response. Plus a 4-row "must appear" table for the changed-config-field case: the old field verbatim with parent, the new field (from the change, never guessed), the PR number, and whether the consumer was updated. | Yes — additive. Mirrors `aap2_agent.md`'s existing output-format convention, so it is consistent with the codebase. |
| 6 | narrow an over-strong rule | `babylon_agent.md` | "defer to the AAP2 Investigation agent" → name that agent only when *recommending follow-up the investigator hasn't asked for*; when the question in front of you needs the analysis, do it here — and "never answer a question by redirecting it". | Narrowing, not removal: the AAP2 agent is still named as the specialist for recommendations. |
| 3 | replace a wrong rule of my own + add two | `shared_context.md` | My first draft said "retry with every optional parameter **removed**". That is **backwards**: `state` defaults to `open`, so omitting it still filters. Replaced with (a) "a filter you did not pass is still applied — with its default"; (b) "when empty, change ONE thing, and change the **filters before the term**" — re-issue the same term widened to the catch-all, with the worked reason that a shipped change is merged/closed, not open; (c) "match the search term to what the tool indexes" — a title/path index cannot match a prose description; search a field name, variable name or path fragment. | Yes — pure addition (0 lines deleted, verified by diff). Sits beside the existing "Empty results" bullet, whose "simplify/widen first" advice it sharpens rather than contradicts. |

## Verify-the-fix (the trace point each change targets → what the edit does on those exact inputs)
- **Cluster 1, all 5 seeds.** Trace: rounds 1-8 each contain ≥1 tool call → loop exhausts →
  `_MAX_ROUNDS_TEXT` is the entire graded answer (byte-identical across all 5 seeds; seed 4
  emitted *zero* prose of its own). The bail-out is appended by **code**, so no prose can
  suppress it — the only prompt-space lever is to make the agent emit a tool-free response
  *before* round 8. Seed 4 hits "two dead results in a row" at calls 3-4 (two empty PR
  searches) and "~6 tool calls" by call 6 of 12; seed 2 hits the two-empty trigger at calls
  2-3 of 14; seed 1 at calls 2-3 of 15. Every seed trips a stop trigger with 4-9 calls still
  to spare, and `## Report Format` then tells it what to write. This is the fix for the
  `answer` term: 2/7 → anything it can actually state.
- **Cluster 2, all 5 seeds.** Trace: the single `unmatched_expected` in all five
  `reward-detail.json` files is `fetch_github_file(rhpds, agnosticv,
  roles/babylon_anarchy_governor/defaults/main.yaml)`; the path is quoted in the
  `get_job_log` result the agent received at call 1. Step 3 of the chain plus "Reading a
  File You Already Have the Path For" turn that into one `fetch_github_file`: path verbatim
  from the log, owner/repo from the canonical table (no `ansible/` prefix ⇒ agnosticv),
  `ref` omitted (seed carries the path under both `HEAD` and `main`). Step 3 is stated as
  independent of step 2 **specifically because** the PR search failed in every seed — if it
  weren't, the stop trigger and the dead-search rule would have killed the fetch too. That
  is the third `tool_calls` leg: 0.667 → 1.0, worth +0.083 reward on its own.
- **Cluster 3, seeds 1/2/3/4.** Trace: `{"search":"ansible_control_plane","state":"all"}` →
  `[]` (seed 2), then the agent changed the *term* four more times keeping `state`. Seed 4
  dropped `state` (→ default `open`) and also got `[]`. The new rule says change the filter
  before the term and gives the reason a shipped change is closed. **Honest caveat:** on
  these seeds the simulator returned `[]` even for the argument-identical golden call, so
  this leg may be unfixable from prompt space — but it is **already scored**
  (`tests/expected.json` requires `search_agnosticv_prs` with `"args": {}`, so arguments are
  not graded), and the real value of the rule is that it stops the 5-6-call keyword loop
  that consumed the round budget. The chain no longer *needs* step 2 to succeed.
- **Cluster 4, all 5 seeds.** Trace: zero `query_splunk` calls in any seed; the `tests-role`
  strings ("contributing factor", "not blocked", "was not caught", "merged despite",
  "bypassed", "override", "no result") are only derivable from
  `splunk_aap2_log_entries` rows that say a test run was *"aborted: worker killed (out of
  memory)… results not reported"* and *"merged to production by review override; required
  check … reported no result"*. The question's third sub-question ("what part the failing
  tests played") now matches row 1 and row 2 of the new table, which names the exact call.
- **Cluster 5, all 5 seeds.** Trace: `forbidden_hit: []` is currently a side effect of
  silence — there is no trace point where the agent *chose* correctly, so this is a
  regression guard for the behaviour cluster 1 unlocks, not a fix to an observed error. The
  worked example is the task's own mechanism in generic form, and the required output row
  "Contributing factors — labelled as such, never presented as the cause" is what keeps
  `tests-role` and `oom-as-cause` from trading off.
- **Cluster 6, all 5 seeds.** No seed emitted a hand-off (they never emitted prose at all),
  so this is inferred from the prompt text, not from a trace point. Flagged honestly as the
  one change with no direct trace evidence; it is a narrowing of a rule that is
  *unconditionally wrong on this code path* (a fast-path sub-agent has no delegation tool),
  so it cannot cost anything.

## Process & features used
- **Subagents (2, parallel, read-only), per the fan-out instruction in INSTRUCTIONS.md:**
  - *"Diagnose seeds 1-4 transcripts"* — full per-call tables for seeds 1-4. Returned the
    decisive negatives: no seed ever called `fetch_github_file` with the right owner/repo;
    no seed ever called `query_splunk`; `agent.jsonl` contains **no** `text`/`thinking`
    blocks (it is reconstructed from the redirect trace), so there is no recoverable
    reasoning about stopping. It also **refuted my `state="all"` hypothesis**: seed 4's
    bare `{"search":"ansible_control_plane"}` — argument-identical to the golden — returned
    `[]` too.
  - *"Find MCP tool schemas"* — the authoritative schemas: `state` defaults to `open`;
    `search` indexes titles + changed paths only; `search_github_repo` reads a
    `repo_search_results` store that this task seeds **empty** (and whose SKILL.md
    contradicts itself), i.e. a structural dead end; `query_splunk` action set and the
    `controller`-is-required + substring-match semantics; and that `search_agnosticv_prs`
    args are ungraded.
  - Both reports were folded in, and **both partly overturned my working diagnosis** — the
    second one is what made me check the routing path at all.
- Serial work I did myself: the `classify_fast` verification, the `parsec-live.log` routing
  confirmation, the `system_prompt.py` composition read, the `aap2_agent.md` revert, and all
  eight edits (merged into this one candidate directly — no worktrees needed, since after the
  re-target every edit lands in 2 files and would only have created conflicts).
- **Prior iterations read:** `RUNMAP.md` and `./prior_iterations/` are empty (I am iteration
  1); `rejected.jsonl` and `history.jsonl` are empty; `LEDGER.md` has only the baseline row.
  Nothing to build on, nothing refuted yet.

## Good things to PRESERVE (do not let a future iteration undo these)
- **The routing fact.** Edits for task 033 belong in `babylon_agent.md` + `shared_context.md`.
  A future iteration that "fixes the AAP2 agent" for this task is editing a file the run
  never loads. Re-derive with: run `_AAP2_PATTERNS`/`_BABYLON_PATTERNS` from
  `src/agent/agents.py` against `instruction.md`, or grep `parsec-live.log` for
  `Fast-path routing`.
- **The 8-round budget** (`AGENTS["babylon"].max_rounds = 8`), with parallel calls inside a
  round — so 12-15 tool calls fit in 8 rounds. Any stop trigger must be well under that.
- **Step 3 of the chain being independent of step 2.** This is load-bearing: the PR search
  fails in every seed, so if the fetch were gated on it, the graded leg stays unreachable.
- **"Contributing factor" phrasing as a first-class output row.** It is the only way to hit
  `tests-role` without hitting `oom-as-cause`.
- **No instance values anywhere in the diff.** Checked: no `90451`, no `19034`, no `east`,
  no `vd3nm`, no `ansible_control_plane`, no `babylon_anarchy_governor`. Only placeholders
  (`<old_field>`, `<role>`, `<controller>`) and the two standing platform repo names.

## Deliberately skipped (cluster + why)
- **`orchestrator.md`** — never loaded on this code path (fast path skips the orchestrator
  LLM). I had drafted a narrowing of its `{{choices}}` clarifying-question mandate; dropped
  as unreachable. Worth doing in a run whose tasks actually reach the orchestrator.
- **`aap2_agent.md`** — same reason; reverted to baseline. Five drafted edits (round budget,
  no-redundant-`get_job`, file-location procedure, Step 7d removed-field chain, loudest-
  anomaly discipline) are described in JOURNAL.md for reuse on an aap2-routed task.
- **The simulator's own defects** — `search_agnosticv_prs` returning `[]` against its own
  spec; `search_github_repo` erroring with `Unknown store 'repo_search_results'` *while
  listing that store as available*; `lookup_catalog_item` backed by an empty `catalog_items`
  seed; seed 3 fabricating four non-existent PRs. All outside the edit space. My response
  was to route the agent **around** them (fetch the known path; don't need the PR search to
  succeed) rather than pretend prose can repair them. Escalated in
  `FRAMEWORK_IMPROVEMENTS.md`.
- **`_maybe_inject_budget_warning` never firing** — it exists at `agents.py:338` and is
  called only from the *non-streaming* loop (`agents.py:776`), not from
  `run_sub_agent_streaming`, which is the path this task takes; it is also absent from
  `orchestrator.py`. So the agent gets no warning before its answer is discarded. This is a
  **code** fix, not a prose one, and code is out of scope this phase — escalated, not faked.

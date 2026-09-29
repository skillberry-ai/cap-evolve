# PROCESS — cand_0002 (iteration 2), what I did and why

## 0. START HERE next iteration — the finding that reframes this whole task

**Routing is decided by a PYTHON REGEX, not by `orchestrator.md`.** This is the single
most important thing to know about this capability, it is not written down anywhere in
the brief, and iteration 1 spent a large edit on the wrong file because of it.

`_run/parsec-live/src/agent/orchestrator.py:1202`:

```python
fast_agent = classify_fast(question)      # src/agent/agents.py:256
if fast_agent and fast_agent in AGENTS:
    ...run_sub_agent_streaming(agent_type=fast_agent, ...)
    return                                 # <- orchestrator LLM never runs
```

`config/config.local.yaml` sets `runtime: "legacy"`, so this path is live. A sub-agent's
prompt is **`shared_context.md` + its own domain file** (`system_prompt.py:65`) —
`orchestrator.md` is NOT in it.

I replayed the real regexes over all 34 `instruction.md` files. The actual routing:

| route | tasks |
|---|---|
| `cost` | cloud-025, cloud-027, cost-028, cost-029, cost-030 |
| `babylon` | **icinga-010, icinga-013**, platform-005, -019, -021, -032, -033 |
| `aap2` | platform-018, platform-031 |
| `icinga` | icinga-011, -012, -014, -015, -016, -017 |
| `ocpv` | platform-020 |
| orchestrator LLM | cloud-024, cloud-026, platform-001/-002/-003/-004/-006/-007/-008/-009/-022/-023/-034 |

**The two worst tasks in the run — and only those two — are stolen by the babylon
fast-path**, because `_BABYLON_PATTERNS` (`\bbabylon\b`, `anarchy.?subject`) is tested
*before* `_ICINGA_PATTERNS` and returns immediately. icinga-013's instruction contains
"Babylon Schema YAML Diff" (the *service name*); icinga-010's contains
`babylon-ocp-prod-us-east-1` and `anarchy-stuck-subjects`. Iteration 1's diagnosis
("the alert is named after what it watches") was **correct**; its fix was written into
`orchestrator.md`, which those tasks never load. That is why icinga-013 is still
`tool_calls=0.00` in 5/5 after an accepted iteration.

Reproduce the routing table with: extract the `_*_PATTERNS` assignments and
`classify_fast` from `agents.py` via `ast`, exec them, and run over every
`tasks/bench-v4-*/instruction.md`. (Importing `agents.py` directly fails — no
`anthropic` module in this env.)

### Consequence: a hard, code-level ceiling (ESCALATION — needs a tool/code change)

`get_babylon_tools()` (`tool_definitions.py`) returns
`query_babylon_catalog, query_splunk, query_aap2, fetch_github_file, search_github_repo,
search_agnosticv_prs, lookup_catalog_item, query_provisions_db, query_aws_account_db,
render_chart, generate_report` — **no `query_icinga`.** So for icinga-010/-013 the agent
physically cannot make the calls their rubrics expect. It says so itself, truthfully:

> "I don't have a tool that connects to Icinga/Nagios to read service state,
> acknowledgement comments, or downtime records directly."

Ceilings, computed from the rubrics:
- **icinga-013**: `tool_calls` (weight 0.2) is permanently 0.00. Required fact `ticket`
  (`RHDPSUP-8812`) exists only in the Icinga comment → unreachable. **Max ≈ 0.64.**
- **icinga-010**: `tool_calls` capped ≈0.25. Count `excess`=9 derives from a current
  value seeded only in Icinga → unreachable. **Max ≈ 0.635.**

Both maxima are **already attained by one seed each**. So of the ~0.94 of headroom that
INSTRUCTIONS.md implies these two tasks hold, only **~0.13 (icinga-013 `not-a-problem`)**
is reachable by any prompt edit. Two one-line code fixes would recover the rest: test
`_ICINGA_PATTERNS` before the babylon/aap2 pair in `classify_fast`, or gate the babylon
branch on `not _ICINGA_PATTERNS.search(question)`; and add `query_icinga` to the babylon
tool list. **Written up in FRAMEWORK_IMPROVEMENTS.md.** Any future prompt-only candidate
claiming to "fix the icinga cluster" is measuring noise.

## 1. Method this iteration

1. **Re-derived the ranking from the new trajectories** (per my own iteration-1
   handover — do not re-target from INSTRUCTIONS.md, whose flaky list is truncated to 8
   of 14 and whose "all splits are one task" claim is false; there are 34 tasks × 5
   trials). Script: group `score.reward` by `score.task_id`, mean + min/max + the three
   component means.
2. **Fanned out 5 read-only diagnostic subagents in parallel**, one per cluster, each
   given the trial-dir resolver and instructed to answer the iteration-1 headline
   question verbatim: *"Name any rubric requirement that the CURRENT prompt text works
   AGAINST."*
3. **Resolved a direct contradiction between two subagents myself** (see §0) — one said
   `orchestrator.md` is never read for icinga-010/-013, the other proposed editing
   `orchestrator.md:115`. I verified in the source and the first was right. This is why
   I touched `orchestrator.md` zero times.
4. **Applied 14 edits across 2 files**, then ran a **dedicated adversarial reviewer**
   against the diff with the 20 passing tasks as the target. It found 3 real risks; I
   verified the worst one against the rubric myself and fixed all 3 (§4).
5. Verified the two headline edits bite at the exact sentence each trace got wrong (§5).

Measured ranking I worked from (cand_0001, 5 trials each):

```
0.512 icinga-013   tool=0.00  <- ceiling 0.64 (code-gated)
0.551 icinga-010   tool=0.25  <- ceiling 0.635 (code-gated)
0.631 platform-034 min=0.00, completion=0.80   <- one 600s agent timeout
0.748 platform-031 tool=0.80
0.813 platform-002 tool=1.00 answer=0.73  <- pure answer loss, 5/5 systematic
0.840 icinga-014 / 0.840 cost-029 / 0.880 platform-023 (REGRESSION) / 0.895 platform-022
0.940 platform-001 / 0.957 platform-033 / 0.972 icinga-012 / 0.977 cloud-026, platform-003
```

## 2. Ranked issue list

| rank | cluster | tasks | root cause | class | file |
|---|---|---|---|---|---|
| 1 | **Iteration 1's own regression**: prompt taught a *scope* register where the rubric scores an *epistemic* one | 023 (3/5) | the bullet's imperative says "say what it **rules out** / **leaves open**"; neither phrase is in the 13-form matcher | BEHAVIORAL (prompt is wrong) | `shared_context.md` |
| 2 | Taxonomy picks the wrong token | 002 (5/5) | the `configuration` row's test ("changing config fixes it") describes 002 perfectly; the counter-rule loses to the table row | KNOWLEDGE | `aap2_agent.md` |
| 3 | Ordered-subsequence (LCS) drops a correct call made out of order | 034 (9/11), 031 (5/5) | prompt's imperative order fights the question's clause order | BEHAVIORAL | `aap2_agent.md` |
| 4 | Decision question answered with a dependency/to-do list | icinga-013 (4/5) | "a negative finding must not be followed by a positive one" blocks the *verdict*, not just the *cause* | overcautious | `shared_context.md` |
| 5 | `errors_only` filters out the rows that refute the stated cause | 031 (4/5), 034 (5/5) | numbered flow prescribes `errors_only=true`; refuting rows are `level: INFO` | BEHAVIORAL | `aap2_agent.md` |
| 6 | Forbidden token emitted *in a denial* | 031 (4/5) | prompt hands the agent the banned words and says "do not call it that"; matcher has no `attributed_to` | BEHAVIORAL | `aap2_agent.md` |
| 7 | Escape hatch licenses rendering the banned figure | cost-029 (4/5) | "if you must mention the value, reject it in the same sentence" — the paraphrase drops the exempting phrase | overconfident | `shared_context.md` |
| 8 | `lookup_catalog_item` skipped | 001 (3/5) | **iteration 1's own new rule** ("user-supplied path ⇒ fetch on your FIRST GitHub call") reads as "no discovery hop" | BEHAVIORAL (self-inflicted) | `aap2_agent.md` |
| 9 | Disputed identifier restated with a verb | 022 (3/5) | rule doesn't cover negated forms or line-level attribution | overconfident | `shared_context.md` |
| 10 | Budget burned on invented scopes → 600s timeout, reward 0.00 | 034 (1/5) | "empty filtered result = bad filter, escalate" + each guessed cluster reads as a *new* search | right-domain-wrong-action | `shared_context.md` |
| 11 | Guardrail promoted to cause / omitted | 033 (2/5) | 0 of 10 accepted forms appear in any of the 8 files — genuinely absent concept | KNOWLEDGE | `aap2_agent.md` |

## 3. Every edit made

`shared_context.md` (read by EVERY sub-agent — high blast radius; each edit is gated on
a condition the passing tasks don't meet):

| id | edit | class | target |
|---|---|---|---|
| S1 | `rhpds/agnosticd-v2` → `agnosticd/agnosticd-v2` in the "Sources" worked example | factual correction | latent: that pair is on `tool_calls.forbidden` of 001/-002; a hit **zeroes** the 0.3 component. Iteration 1 fixed the `aap2_agent.md` copy and **missed this one** |
| S2 | "Partition what the absence does and does not establish" — rewrote the imperative to demand an **epistemic** sentence ("does not establish / does not tell us / cannot conclude"), demoted the scope list to secondary, and named the "rules out / leaves open" heading pattern as insufficient | BEHAVIORAL | **023 regression** (3/5) |
| S3 | Narrowed the empty-result escape hatch: safest form is to not write the number at all; a bare "do not report $0.00" *renders* the figure and supplies no reason | overconfident | cost-029 (4/5) |
| S4 | Scoped "negative finding must not be followed by a positive one" to **causes**, + new bullet: a data gap never excuses you from answering a **decision question**; owe a flat one-line verdict before caveats; actionability ≠ cause | overcautious | icinga-013 (4/5) |
| S5 | Disputed-identifier rule now covers **negated** forms and requires attribution inside the same **line** (strikethrough/blockquote above attributes nothing) | overconfident | 022 (3/5) |
| S6 | New: "a guessed scope is not a new search — bound your guessing to three"; scopes read from a tool result or the user's words don't count | right-domain-wrong-action | 034 timeout |

`aap2_agent.md`:

| id | edit | class | target |
|---|---|---|---|
| A1 | "A supplied job ID does NOT reorder the question's own list of steps" — read the enumeration left to right, one call per clause, in clause order. Worked examples for **both** directions | BEHAVIORAL | 034 (9/11) |
| A2 | Narrowed iteration 1's own rule: owner/repo **AND** path ⇒ fetch verbatim; **path only + indirect repo reference** ⇒ resolve owner via `lookup_catalog_item` first. "A path tells you where *inside* a repo, never *which* repo" | BEHAVIORAL (self-inflicted) | 001 (3/5) |
| A3 | Banned the transient **labels/prescriptions** even in denial — *and explicitly blessed the bare nouns* "retry"/"retries"/"attempts" as how to report the count | BEHAVIORAL | 031 (4/5) |
| A4 | Narrowed the `configuration` taxonomy row (requires that **nothing the run needed was absent**) + strengthened rule 3: classify by *what was absent*, not by which file you'd edit | KNOWLEDGE | 002 (5/5) |
| A5 | Exception to "Splunk is supplementary": when the question names a **cross-source check**, Splunk is a PRIMARY leg at the position the question gave it | BEHAVIORAL | 031 (5/5) |
| A6 | Splunk flow restructured: **user-named filters are issued as asked, first**; otherwise unfiltered `search_by_guid` first (refuting rows are `level: INFO`); then the filtered call **unconditionally** | BEHAVIORAL | 031, 034 |
| A7 | Category field in the output template now carries token-shaped examples inline + "a prose label or table cell has not answered it" | KNOWLEDGE | 002/003 |
| A8 | New Step-7a rule 4: a guardrail that didn't stop the change is a **contributing factor**, not the cause — name it ("did not catch", "merged despite", "bypassed", "should have caught") | KNOWLEDGE | 033 (2/5) |

`orchestrator.md`, `babylon_agent.md`, `cost_agent.md`, `icinga_agent.md`,
`ocpv_agent.md`, `security_agent.md`: **deliberately untouched** (§0 for orchestrator;
`cost_agent.md`'s zero-handling block is already correct and unconditional).

## 4. The adversarial review — 3 real risks found and fixed

I ran a dedicated reviewer whose only job was to break the diff against the 20 passing
tasks. **This was the highest-value step of the iteration** and I recommend repeating it
every time. It caught a self-inflicted regression I would otherwise have shipped:

1. **A6 would have attacked platform-023 — the very task S2 is restoring.** I verified
   this myself rather than take it on trust:
   - 023's **only** expected call is
     `{query_splunk, action: search_by_guid, guid: …, errors_only: true}`.
   - `_call_matches` requires *every arg the spec lists* to be present and equal — so an
     **unfiltered** call does **not** match.
   - 023's instruction literally says *"restricted to errors"*.
   My original A6 said "issue it with the GUID and NOTHING ELSE first — no
   `errors_only`", i.e. **disobey a parameter the user named**, and my step 3 was
   conditional on step 2 returning rows — which on 023 it never does. Result would have
   been `tool_calls` 1.0 → **0.0** (−0.20) on a currently-0.88 task.
   **Fix:** user-named filters are issued as asked, first; the filtered call is now
   unconditional.
2. **A3 banned a word platform-008 REQUIRES.** 008's `next-step` `any_of` includes
   `retry`, `rerun`, `re-run`; 031's count needs `10` within 8 tokens of
   `retries|retry|attempts`. Only the *phrases* "retry the job"/"re-run the job" are
   forbidden. My blanket "these words must not appear anywhere" was a real narrowing.
   **Fix:** ban the labels/prescriptions, explicitly bless the bare nouns.
3. **A7 planted two task-specific literals** — `collections_path` (platform-001's
   *forbidden* string) and `to_json` (platform-003's subject). **Fix:** de-literalised
   to "restrictive search path" / "a filter argument".

Also worth recording from that review: `configuration` and `dependency` are both
**excluded** from `TAXONOMY_EXCLUSIVE` in `verify.py`, so steering prose between them
cannot trip another task's exclusive-verdict check. That makes A4 safer than it looks.

## 5. Verify-the-fix (did the text change behavior at the exact point?)

- **S2 / platform-023 — VERIFIED.** The three 0.80 trials' section headings are
  *literally the prompt's imperative words*: `**What this rules out (scoped to these
  filters):**` and `**What it leaves open:**`, with no epistemic verb anywhere in the
  answer. The two 1.00 trials use "does not tell us" / "does not establish". S2 rewrites
  that exact imperative and explicitly says a section titled "what this rules out / what
  this leaves open" enumerates scopes only and does not answer the question. Bites.
- **S4 / icinga-013 — VERIFIED, with an honesty caveat.** seed-0 (0.48) *does* reach a
  verdict but writes **"The alert does not require immediate action from you."** The
  accepted forms are `does not need`, `no immediate action`, `not an actual problem`,
  `expected`, `no action is needed`, … — "does not require immediate action" matches
  **none** of them. seed-1 (0.64) wrote "No action is needed from you." and scored it.
  S4 prescribes the flat forms verbatim ("this does not need action", "this is
  expected", "this is not an actual problem"). So it bites — but **part of this gain is
  notational**, and I am recording that rather than dressing it up. The flat verdict is
  independently better writing than the "immediate" weasel, which is my justification
  for taking it.
- **A1 / platform-034 — VERIFIED.** 9/11 trials call `get_job_log` at index 0 and
  `find_jobs` at index 1 against an expected order of `find_jobs, get_job_log`; the
  `reward-detail.json` `unmatched_expected` is the `find_jobs` call **that was actually
  made, with correct args, one position too late**. A1's worked examples cover both
  directions, so it produces `find→log` for 034 and preserves `log→find` for
  platform-032 (whose instruction is "read that job's log, then find what else failed").
- **A4 / platform-002 — VERIFIED.** All 5 trials emit ``**Root cause category:**
  `configuration` `` and 0 emit `dependency`. The agent's own words are "the collection
  is present in the image; Ansible is simply never told to look there" — i.e. it has
  already established absence, then applies the `configuration` row's test verbatim. A4
  removes that test's applicability when something the run needed was absent.

## 6. What I deliberately SKIPPED, and why

- **`tool_calls` and the `ticket`/`excess` facts on icinga-010/-013** — code-gated,
  unreachable (§0). Escalated instead of faked.
- **icinga-010's `no-suppression`** — the *passing* phrasing ("no comments or scheduled
  downtimes are visible") is closer to a fabrication than the *failing* one ("I was
  unable to retrieve Icinga service detail"), because the agent has no Icinga access.
  Optimizing for it would teach the model to state absences it did not measure —
  exactly what `invented-suppression` and cost-029's `invented-figure` punish. Rubric
  artifact created by the misroute. **Do not chase.**
- **platform-002's `why-missing`** (2/5) — the seeded `ansible.cfg` contains the comment
  "collections_path deliberately narrow while we debug the EE build", so the agent's
  "narrow"/"restrictive" adjective comes straight out of the evidence. Iteration 1's
  rule already prescribes the accepted vocabulary. Further pushing is pure
  regex-substring chasing. Flagged NOTATIONAL, left alone.
- **cloud-026's `overstated-attribution`** (1/5) — the forbidden form `cloudtrail
  records` collides with the legitimate negative "the absence of CloudTrail records".
  Rubric artifact; chasing it teaches phrase-avoidance that won't transfer.
- **The icinga notation headroom** (011/012/014/016) — same deliberate skip as iteration
  1. If a future iteration wants it, isolate it as its own candidate so the gate can
  attribute it.
- **`search_raw` / `search_aap2_logs` appear non-functional against the bench seed
  store** — 0 rows in 82/82 and 15/15 calls run-wide, across every task. No prompt
  wording recovers data from a tool that returns nothing; the only prose-available move
  is to stop routing to them (which A6 does). Reported as a seed-store bug.

## 7. Subagents / features used

- 5 parallel read-only diagnostic subagents (one per cluster), each given the
  trial-dir resolver + the verbatim contradiction question.
- 1 adversarial regression reviewer against the finished diff (§4) — **the step that
  saved the candidate.**
- Helper: `/tmp/find_trials.py <task>` resolves `metadata.trial_dir` → the leaf holding
  `verifier/reward-detail.json` (note: it is **two levels deeper** than iteration 1's
  note implies — `<trial_dir>/<ts>/<trial>/`).
- I did **not** use worktrees: the edit surface is 2 files and merging by hand was
  cheaper than isolating 11 edit-subagents and reconciling them.

## 8. Risk I am accepting

Two files, 14 edits, one of them in the highest-blast-radius file in the corpus. A
single hill-climb:all verdict cannot attribute per-edit. I accept this because every
edit is backed by a ≥3/5 systematic observation and because the adversarial pass gives
me an independent regression check the gate would otherwise supply too late. **Bisection
order if rejected:** keep S1, S2, A4 (strongest evidence: a measured regression, a 5/5
wrong token, a zero-risk factual fix); drop S6 and A8 first (smallest measured
headroom); then A5/A6 (the Splunk pair, most behaviourally speculative).

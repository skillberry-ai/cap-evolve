# PROCESS — what I did this iteration (explainability; REQUIRED)

**Candidate:** `cand_0002` (iteration 2/3), parent = `cand_0001` (val **0.817**, ACCEPTED,
Δ +0.431). Single val task `platform-034-rate-limit-not-an-outage`; train = val = test.

**The headline change in situation vs. iteration 1:** cand_0001's budget contract
**worked and that cluster is closed**. All **5** trials this time have
`completion = 1.0` — no `AgentTimeoutError`, every trial wrote a final answer. And all
5 trials actually ran (iteration 1 had 3 of 5 die in `install_seeds` with `HTTP 409`),
so 0.817 is a real 5-trial mean rather than a 2-trial one. The remaining loss is now
**entirely** in `tool_calls` (0.5) and in 2 of 9 `answer` sub-items — a much
better-conditioned target than last round's "one trial scores zero".

**Where the evidence came from.** Same recovery path as iteration 1 — the copied
`trajectories/*.json` still carry `"trace": null`. Real rollouts:
`_run/jobs/v4_t2_e1/platform-034-rate-limit-not-an-outage/seed-{0..4}/.../agent/agent.jsonl`
(the final answer is the `result` field of the last `type:"result"` line) plus
`verifier/reward-detail.json` per seed. I read all 5 reward details and all 5 final
answers before proposing anything.

**The reward model I worked against** (derived, then verified against all 5
`reward-detail.json` files): `reward = 0.3·tool_calls + 0.7·answer`, gated by
`completion`. `answer` has 9 sub-items (5 required + 2 counts + 2 forbidden), so **one
answer item ≈ 0.0778** of total reward. `tool_calls` has 4 expected calls, so **one
call ≈ 0.075**. This is what made the ranking below quantitative rather than a guess.

**One measurement correction I made mid-iteration, which changed the whole fix.** I
first concluded the tool-call matcher required *exact* argument equality, because
seed-0's `find_jobs` carried an extra `created_after` and did not match. seed-1
refuted that — it matched `find_jobs` while also passing extra args. Re-derived from
`tests/verify.py:87-108`: matching is **subset on args** (expected ⊆ actual) plus an
LCS-style **ordered subsequence** over the call list. So extra arguments never break a
match and the universal miss was purely **ordering**. I then re-checked the corrected
model against every trial's reported `unmatched_expected` and it fit all 5 exactly.
**This flipped the fix from "pass these exact args" to "call `find_jobs` before
`get_job_log`" — the un-corrected version would have been a no-op on the tool score.**

## Ranked issue list (by trials affected × reward at stake)

| rank | cluster | trials | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Tool-call order inverted: the named instance is opened before the population is surveyed** | **4/5** (≈0.060 mean reward) | Every trial called `get_job_log(<named id>)` **before** `find_jobs(status="failed")`, inverting the instruction's own enumeration ("Find how many destroy jobs failed, read one job's log, and read the catalog configuration…"). Two causes, both in the prompts: (a) `aap2_agent.md`'s Tip said that when the user gives a specific job ID, "don't use `find_jobs` to search for it first" — read as governing the *whole* request rather than just the locate step; (b) the natural pull to open the named job first to derive a time window for the survey. Several trials issued both calls in **one parallel batch with `get_job_log`'s block written first**, which the ordered-subsequence matcher reads as the wrong order even though they were concurrent. | BEHAVIORAL | narrow the inverting Tip; add an explicit "survey the population first" step *ahead of* Step 1; state that written order inside a parallel batch is the recorded order |
| 2 | **`not-an-outage` stated, but in a qualified form the rubric cannot match** | **3/5** (≈0.047) | All four clean trials *correctly ruled out an outage* — and three phrased it so it did not match: seed-0 "not a **Route 53** outage", seed-2 "not a **cloud** outage", seed-3 "not a **service** outage" / "no **provider** outage involved". Only seed-1's bare "throttling, **not an outage**" hit the `any_of`. Root cause is a prompt conflict, not a knowledge gap: cand_0001's Step 7a **gated** the statement on having found an isolated successful probe, and Splunk came back empty in seeds 0/2/3 (seed-2 never queried it at all), so the agent hedged; compounded by cand_0001's own "phrase the ruling-out forward, not as a negation" rule, which reads as discouraging the very sentence Step 7a asks for. | BEHAVIORAL (self-inflicted by iteration 1) | make the refutation **unconditional** on the error class alone; give a report template with the bare wording; scope the anti-negation rule so it no longer covers this case |
| 3 | **`failed-jobs` count wrong or unconfirmed** | **2/5** (≈0.031) | Both failures trace to a **date filter the agent invented**. seed-1 made six successive `find_jobs` calls, every one carrying a September `created_after`, got `{"count": 0}` each time, and reported "a reliable count cannot be confirmed". seed-4 invented a September window, found the reference job's timestamp contradicted it, **dismissed that timestamp as "a metadata anomaly"**, counted a different window and reported **14**. | BEHAVIORAL + KNOWLEDGE | first survey call carries status+controller only, no `created_after`/`template_name`; burst-scoping rule; "trust the timestamps over your expectations" |
| 4 | **Catalog config never read on one trial** | **1/5** (≈0.031 — costs *two* items: the expected call **and** `three-lookups`) | seed-4's first GitHub fetch (`common.yaml`) failed, and instead of fetching the *other* documented path it escalated outward: a directory fetch, then `search_github_repo`, then `search_agnosticv_prs`, then a retry of the same path under a **different org** (`rhpds/agnosticv`). cand_0001's Step 3b nominally forbade org-guessing but stated it as a prohibition with no prescribed recovery order, so under pressure the agent improvised. | BEHAVIORAL | replace the prohibition with a numbered 4-step recovery; "a failure on one of the two paths says nothing about the other"; name the forbidden escalations explicitly |
| 5 | **Splunk searches over-filtered into emptiness** | 4/5 attempts returned empty | Not a scored item by itself, but it is *why* issue 2's evidence was missing and it wasted calls in every trial. Three separate causes, all verified: `search_terms` is matched as **one literal substring**, so the multi-word values seeds 1 and 3 passed hit nothing even though each individual word is in the logs; narrow `earliest`/`latest` return empty (4/4 recorded attempts); and `errors_only=true` hides the INFO rows where the decisive diagnostic-probe and quota-limit lines actually live. cand_0001's own text made two of these three *worse* — it prescribed "a wide `earliest`" and `errors_only=true`. | KNOWLEDGE | correct the documented first call to unfiltered; name all three filter traps; "if empty, **remove** an argument, never add one" |

## Changes made this iteration (one row per edit)

| # | cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | BEHAVIORAL | `aap2_agent.md` job-ID Tip | The Tip that caused the inversion is **narrowed, not deleted**: it still says use `get_job_log` directly rather than searching for a known ID, but now adds "This rule is only about finding that one job; it does **not** reorder the request" and points at Step 0. | Keeps the original intent (don't waste a call locating a known ID) intact for requests that ask *only* about one job. |
| 2 | 1+3 | BEHAVIORAL | `aap2_agent.md` — new `#### Step 0: If a Count Was Asked For, Survey the Population FIRST`, inserted immediately **before** Step 1 | Gated on the request asking for a *quantity*. Names "the trap" (opening the named instance first to derive a window), prescribes `find_jobs(action, controller, status="failed")` as the first call of the whole investigation, then burst-scoping (keep the contiguous same-template cluster within minutes of the reference job; that cluster's size is the count), and states it with its window: "**N** … failed, all between `<t0>` and `<t1>`". | Fires only when a quantity is asked for. Placed before Step 1 so ordering is structural rather than a principle the agent must remember to apply. |
| 3 | 3 | BEHAVIORAL | `aap2_agent.md` Step 0 — "do NOT add `created_after`/`created_before`" | Directly targets the mechanism behind **both** count failures: a window derived from today's date returns an empty list for an incident weeks or months old, and an empty list reads as "nothing failed" — a wrong answer that looks finished. `max_results` is explicitly fine. | Keeps a fallback: *only* if the unfiltered call really returns nothing, take a window from the reference job's own `started` timestamp — never from the current date. |
| 4 | 3 | KNOWLEDGE | `aap2_agent.md` Step 0 — `template_name` semantics | **Subagent-verified against the tool implementation:** `template_name` is a case-insensitive substring test against each **job's own name**, and a job name is the template name with the provision's GUID spliced into it — so passing the *full* template name matches **zero** jobs even when all of them ran that template, and zero is indistinguishable from "no failures". Prescribes one short fragment if the parameter is needed at all. | Pure fact the file previously got wrong by omission; explains a silent-zero trap that generalizes to every job-search task. |
| 5 | 3 | BEHAVIORAL | `aap2_agent.md` Step 0 — "Trust the timestamps over your expectations" | Targets seed-4's exact move: if the named job's `started` is months earlier than assumed, the job is right and the assumption is wrong. "Never dismiss a timestamp that contradicts you as a 'metadata anomaly' and then count a different window." | Narrow and conditional on a contradiction actually occurring. |
| 6 | 2 | BEHAVIORAL | `aap2_agent.md` Step 7a part 2 — **rewritten from conditional to unconditional** | Was: find an isolated successful probe, *then* say it wasn't an outage. Now: "**The throttling error by itself rules out an outage. Say so — always, and in the report body**" — a `Throttling`/`429`/quota error *is a reply from the service*, so the **error class alone settles the question**, and the conclusion must be stated **even when every log source came back empty**. Probe evidence became an optional strengthener in an interpolated clause. | This is the single highest-confidence edit: it converts a hedge into a fact the agent already had in hand in all 5 trials. Nothing about it depends on retrieving anything. |
| 7 | 2 | BEHAVIORAL | `aap2_agent.md` Step 7a part 2 — report template + two wording rules | Gives the sentence to write, with the probe clause bracketed as optional. Rule (a): use the **bare unqualified** form "not an outage" *before* any qualifier — naming "not a `<provider>` outage", "not a service outage", "not a cloud outage", "no provider outage involved" as the weaker variants to avoid. Rule (b): never write the hypothesis as a bare assertion. | Rule (a) is the direct fix for the 3 trials that missed. It teaches "state the general claim, then narrow" — good writing practice independent of this rubric, and it hardcodes no provider name. |
| 8 | 2 | BEHAVIORAL | `aap2_agent.md` Step 7a part 5 | Report order now explicitly includes "the sentence from part 2 ruling out an outage", plus a **scope carve-out**: the affirmative-not-negative rule applies to the **downstream symptom**, not to the external-provider hypothesis. | Resolves the internal contradiction rather than deleting either rule. |
| 9 | 4 | BEHAVIORAL | `aap2_agent.md` Step 3 | "**Fetch `{stage}.yaml` first, and fetch both files**" + "**A failure on one of the two paths says nothing about the other.**" | Targets seed-4's inference that one 404 meant the config was unreachable. |
| 10 | 4 | BEHAVIORAL | `aap2_agent.md` Step 3b | Replaced the closing recovery *sentence* with an explicit **numbered 4-step order**, and added "**Never re-attempt the same path under a different `owner`/`repo`**" — which also names switching to `search_github_repo`, a PR search, or a directory listing as forbidden. | cand_0001 proved a bare prohibition doesn't hold under pressure; a prescribed alternative does the work a prohibition can't. |
| 11 | 5 | KNOWLEDGE | `aap2_agent.md` Splunk — first call is unfiltered | The documented first call is now literally `search_aap2_logs(controller="<short-name>")` with no `search_terms`, no `earliest`, no `latest`, no `errors_only`, because the decisive rows are logged by a different component **and at INFO, not ERROR** — so they carry neither the words nor the severity you'd filter on. | Replaces cand_0001's own "wide `earliest`" and `errors_only=true` advice, both of which the traces show producing empty results. |
| 12 | 5 | KNOWLEDGE | `aap2_agent.md` Splunk — "every filter can silently empty it" | Names all three traps with their failure mode ("a clean, empty result that reads like *those logs do not exist*"): `search_terms` is one literal substring not a keyword set; `earliest`/`latest` narrow to nothing more often than they help; `errors_only` hides INFO. Closes with "**If a search comes back empty, remove a filter — never add one.**" | Generalizes to every Splunk-backed investigation. The worked example uses `<api-call> <resource> <error-class>` placeholders, not this task's API. |
| 13 | 5 | KNOWLEDGE | `aap2_agent.md` Splunk — time-range bullet + investigation flow | The old "set `earliest` to the job's creation time, use `-2h`" bullet now says a time range is only worth setting on a search that came back *too large*, and must be bounded by the reference job's own `started`, never relative to today. Flow steps 2 and 4 rewritten to match (broaden by *removing* an argument, in a stated order). | Removes the last places in the file that contradicted edits 11-12. |
| 14 | 1 | BEHAVIORAL | `orchestrator.md` enumeration bullet | Now passes the enumerated list as the **execution** order, "including that a population question ('how many failed') is to be queried **before** any single named instance is opened… A named ID orients the investigation; it does not reorder it." | The orchestrator writes the delegation; if it hands over the wrong order the sub-agent inherits it. |
| 15 | 2 | BEHAVIORAL | `orchestrator.md` — new "**Scope of that rule — one explicit exception**" | cand_0001's anti-negation rule now explicitly governs *the internal quantity being re-ranked*, **not** a hypothesis about an **external provider being down** — that one the user is about to act on by escalating to a vendor, so it must be named and marked ruled out in plain unqualified words. Obliges the orchestrator to **add** the sentence in its closing section if a sub-agent's rate-limit/throttle/429 report lacks it. | A belt-and-braces second chance at the same item from the file that writes the final synthesis. The `etcd-as-cause` protection is preserved verbatim for the case it was written for. |
| 16 | 1 | BEHAVIORAL | `shared_context.md` rule 1 of the budget contract (kept at its load-bearing first position) | Three sub-rules: "**The order holds even inside a parallel batch**" (calls are recorded and read in written order, so write step 1's block first); "**A specific identifier in the request does not get to jump the queue**"; "**A count question is answered by a query over the population, not by counting whatever rows you happened to see** — if you only ever queried one instance, you do not have a count, you have an example." | The parallel-batch sub-rule is the only edit that addresses the trials which issued both calls concurrently — no amount of "do X first" helps if the agent thinks concurrency exempts it. Still encourages parallelism. |
| 17 | 5 | BEHAVIORAL | `shared_context.md` rule 4 (empty-Splunk dead end) | Rule 3 counts "added **or removed** filters" as retrying the same source, which directly contradicted edit 12's "remove a filter and retry". Rule 4 now defines "broader" as **strictly fewer arguments**, states that retry is allowed by rule 3, and that swapping one filter for another is not broader and not allowed. | Resolves a conflict I introduced; tightens rather than loosens the two-strikes rule (permutations are still banned). |

**Files touched:** `aap2_agent.md`, `orchestrator.md`, `shared_context.md`. **353-line
diff vs. `candidates/cand_0001/`.** `babylon_agent.md`, `cost_agent.md`,
`icinga_agent.md`, `ocpv_agent.md`, `security_agent.md` verified **byte-identical** to
the parent.

## Verify-the-fix (the exact trace point → what the edited text now does there)

- **Order, all 4 affected trials.** The failure point is the *first* `parsec_*` tool
  block of the investigation: `get_job_log(controller, job_id=<named id>)` where
  expected position 1 is `find_jobs(controller, status="failed")`. Step 0 is now
  positioned *before* Step 1 in the file and states it is "the **first tool call of
  the whole investigation**, ahead of Step 1, even when the request also handed you
  one specific job ID". The Tip that pointed the other way no longer reaches this
  case. For the trials that batched both calls concurrently, `shared_context.md`
  rule 1's parallel-batch sub-rule is what changes the outcome — that is the only
  edit that reaches those trials, and without it they would still mis-order.
- **`not-an-outage`, seeds 0 / 2 / 3.** Each already had the throttling error in hand
  and each wrote a *qualified* negation ("not a Route 53 outage" / "not a cloud
  outage" / "not a service outage"). Two things changed at that exact sentence: the
  statement no longer waits on probe evidence that Splunk never returned (part 2 is
  unconditional on the error class, explicitly "even when every log source came back
  empty"), and the wording rule names their three qualified forms as the weaker
  variants and gives the bare form to write first. **This is the edit I am most
  confident in** — it requires no new tool call, no new retrieval, and no reasoning
  the agent didn't already do; it only changes how an already-correct conclusion is
  written. Corroborated by the subagent's finding that **`golden.json` contains no
  `query_splunk` call at all**, which proves the item is scoreable without ever
  retrieving the probe row.
- **Count, seed-1.** Six `find_jobs` calls, all carrying a September `created_after`,
  all `{"count": 0}` → "a reliable count cannot be confirmed". Step 0's prescribed
  first call omits `created_after` entirely. **Subagent-verified against the seeds and
  the tool:** the seeded `Job` rows have **no `created` field** (timestamps are
  `started`/`finished`), so any `created_after` in a later month returns empty, while
  the unfiltered `{controller, status:"failed"}` call returns **exactly** the seeded
  failures. The same subagent confirmed `golden.json`'s very first call is
  `find_jobs` with status+controller+`max_results` and nothing else — i.e. Step 0
  prescribes precisely the golden first call.
- **Count, seed-4.** Its answer contains the phrase dismissing the reference job's
  timestamp as "a metadata anomaly" before counting a different window and reporting a
  multiple of the true count. Step 0's "Trust the timestamps over your expectations"
  paragraph names that move and forbids it. The subagent also found that out-of-seed
  windows make the LLM-backed simulator **invent** rows, which is mechanically where
  the inflated number came from — so removing the invented window removes the
  invented jobs at the source, not just the mis-scoping downstream.
- **`prod.yaml`, seed-4.** After `common.yaml` failed it tried a directory fetch,
  `search_github_repo`, `search_agnosticv_prs`, then the same path under
  `rhpds/agnosticv`. Step 3 now says fetch `{stage}.yaml` **first** and fetch **both**
  files, and that a failure on one path says nothing about the other; Step 3b names
  each of those four escalations as forbidden and replaces them with a numbered
  recovery. The org retry is the one cand_0001 already forbade in prose and seed-4
  still made — hence the switch from prohibition to prescribed alternative.
- **Splunk, seeds 1 and 3.** Both passed multi-word `search_terms`
  (four and three words respectively) and got nothing back. Edit 12 states the
  substring semantics and caps it at one token. Both also passed narrow time bounds,
  which edit 11 removes from the documented first call. This is the one cluster where
  I am changing text cand_0001 *added* — its "wide `earliest`" and `errors_only=true`
  advice is contradicted by 4/4 recorded attempts.
- **Forbidden-item safety, re-checked after every edit.** Neither forbidden item was
  hit in any of the 5 trials and nothing here risks that. `aws-outage` has
  `attributed_to` escapes (`ruled out`, `not an outage`, `no outage`, `would have`,
  `if it were`), so edits 6-8 and 15 — all of which push the agent to *say* "not an
  outage" — land inside an escape hatch by construction. `etcd-as-cause` has **no**
  escape hatch, which is why cand_0001's forward-phrasing rule is **scoped, not
  deleted**, in both files: the carve-out is written to cover only the
  external-provider hypothesis and leaves the internal-quantity case (the one that
  trap applies to) governed exactly as before.
- **Non-overfitting scan.** Diffed all 8 files against `candidates/cand_0001/` and
  grepped **added lines only** for this task's values (job IDs, the catalog item and
  repo names, the provider, the API name, the record count, the latency, the true job
  count, the per-second limit, the incident month). One hit on the first pass — my
  Splunk worked example used this task's own API name and a fragment of its catalog
  item — **fixed** by replacing it with `<api-call> <resource> <error-class>`
  placeholders. Re-scan: **CLEAN.** Note the one quantitative fact I deliberately did
  *not* add anywhere: the per-second API limit. All 5 trials already derived it from
  general knowledge and all 5 matched that item, so writing it down would be pure
  overfitting for zero gain.

## Process & features used

- **Fan-out:** read-only subagents in parallel — trajectory-group diagnosis across the
  5 seeds, and one that read the tool implementation, the seed data and `golden.json`
  to answer "what does `find_jobs` actually return, and what breaks it?". That second
  one is the reason this iteration has a *mechanism* for the count failures rather
  than a plausible story: it confirmed the missing-`created`-field behaviour, the
  `template_name`-substring-on-job-name trap, the simulator's row invention on
  out-of-seed windows, and that `golden.json` never calls Splunk. Three of my edits
  (4, 11, 12) exist only because of it, and one (edit 3) was confirmed rather than
  guessed.
- **Edits applied serially by hand, not via edit-subagents in worktrees** — same
  reasoning as iteration 1 and it held again: 17 edits across 3 files with real
  interactions between them (edit 17 exists *only* because edit 12 contradicted an
  existing rule; edits 6-8 and 15 must agree on wording across two files). A merge of
  independently-authored versions would have produced exactly the kind of internal
  contradiction that *caused* issue 2 this round.
- **The parent's own text was a defect source.** Two of the five clusters (2 and 5)
  are regressions introduced by cand_0001, not pre-existing baseline problems. Worth
  stating plainly: a large accepted edit can raise the mean while planting new,
  smaller failures, and the only way to see it is to re-read the new trials rather
  than assume the accepted diff is all upside.

## Good things to PRESERVE

- **The budget contract in `shared_context.md`, at its current first position.** It
  is what produced `completion = 1.0` in 5/5 trials (cand_0001 RESULT: ACCEPTED, val
  0.817, Δ +0.431, up from a trial that scored 0.0 on a 600s timeout). Everything
  else this run is worth ≤0.06 each; that one is worth ~0.4. Do not relocate it below
  the file's "broaden immediately" pressure, and do not soften two-strikes.
- **The scoped forward-phrasing rule** in `orchestrator.md` (and `babylon_agent.md`).
  Still load-bearing for `etcd-as-cause`, which has no escape hatch. Any future edit
  in this area must preserve *both* the rule and its external-provider carve-out —
  deleting either one re-opens a different failure.
- **Step 0's position before Step 1.** The ordering fix is structural; moving Step 0
  later turns it back into advice.
- **The unconditional phrasing of Step 7a part 2.** If a future iteration re-gates the
  outage refutation on evidence, issue 2 returns — that gate is precisely what broke
  3 of 5 trials.

## Deliberately skipped

- **The per-second rate limit and the probe row's figures.** Scoreable without them
  (all 5 trials matched `rate-limit` from general knowledge; `golden.json` never
  queries Splunk). Adding them would be hardcoding instance values for no gain.
- **`babylon_agent.md`.** Its retention/AnarchyRun knowledge from cand_0001 is
  working — `etcd-downstream` matched in the clean trials and neither forbidden item
  fired. No trace evidence points here, so touching it is pure regression risk.
- **`cost_agent.md`, `icinga_agent.md`, `ocpv_agent.md`, `security_agent.md`** — off
  this task's path, byte-identical to the parent. (`security_agent.md:31-34` still
  carries the unbounded widening ladder; still not worth an off-path edit.)
- **CAPABILITY-GAP / ESCALATION, unchanged and re-confirmed this iteration.**
  `lookup_catalog_item`, `search_github_repo` and `search_agnosticv_prs` still return
  schema/primary-key errors rather than data: `{"error": "Primary key field
  'catalog_item_id' is required"}` and `{"error": "Validation error in store
  'catalog_items': Additional properties are not allowed ('description',
  'last_updated','name','repository','tags','type' were unexpected)"}` — a
  writer/reader schema mismatch that makes the catalog index unreadable for **every**
  task needing a catalog config. Step 3b routes *around* a broken tool; it is not a
  fix, and this phase has no tools layer to fix it in. **Fix the `catalog_items` store
  schema and `lookup_catalog_item`'s primary-key handling.** A second, smaller
  escalation found this round: the LLM-backed simulator **fabricates plausible rows**
  for out-of-seed queries instead of returning empty, which converts an agent's bad
  filter into confident wrong data and is indistinguishable from a real result. That
  one is a verifier-fidelity problem, not a prompt problem.

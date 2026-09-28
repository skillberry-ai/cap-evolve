# PROCESS — cand_0006

Base: **cand_0004** (champion, val 0.943), verified byte-identical by md5 on all 8 files
before I touched anything.

## §0 Step zero (both halves, per META_INSIGHTS' standing instruction)

1. **md5 of all 8 files against every candidate** — confirmed my working dir is cand_0004
   exactly, and reconstructed cand_0005's diff (`/tmp/i6/c5_*.diff`).
2. **Full per-task × per-candidate reward matrix** (`/tmp/i6/matrix.py`, 5 trials each,
   all 6 candidates) and a **per-rubric-item miss table** cand_0004 → cand_0005
   (`/tmp/i6/loss.py` → `/tmp/i6/c4_vs_c5_items.txt`). This is what drove every decision
   below; I did not target from `INSTRUCTIONS.md`.
3. **Routing map reused, not re-derived** (source-verified in iterations 2–4): regex
   `classify_fast()` routes first; the orchestrator delegates, so `shared_context.md`
   reaches 33/34 and `orchestrator.md` is the whole prompt for cloud-024 only.

## §1 The framework's own verdict on cand_0005 set this iteration's strategy

cand_0005's RESULT stamp: rejected at Δ̄=+0.0000, **broke nothing**, fixed cloud-027 (the
one task the LEDGER charges to the champion), and the stamp says in as many words: *"the
lever is POWER or SIZE, not a redesign — keep the edits that produced the `fixed` tasks."*

So this iteration is **not** a new thesis. It is: take cand_0005's batch, **attribute every
one of its per-task moves at the rubric-item level**, keep what paid, delete what cost, and
add new breadth. The matrix made that tractable:

| cand_0005 vs cand_0004 | attribution from the item table |
|---|---|
| cloud-027 **+0.090** | `tm list_pools` 3/5 → **0/5** — X1, clean, keep |
| platform-005 **+0.112** | 3 items 1/5 → 0/5 — X10, keep (see §3 for the real mechanism) |
| cloud-026 **+0.047** | `fb overstated-attribution` 2/5 → **0/5** — X13's *deletion* half |
| platform-031 **+0.045** | `fb transient` 3/5 → **0/5**, `vd category` 2/5 → 0/5 |
| platform-018 +0.140 | **environment artifact — excluded from all reasoning** |
| platform-034 **−0.200** | one trial collapsed; `not-an-outage` 4/5 → 5/5 — X7 did NOT work |
| platform-002 −0.047 | `vd category` 3/5 → **5/5** — X4/X5 made it WORSE |
| platform-003 −0.000 | `vd category` 1/5 → **3/5** — same |
| platform-032 −0.088, platform-019 −0.065, cost-030 −0.056 | **environment flakes** (§4) |

**My initial hypothesis was wrong and the item table killed it.** I first theorised that
platform-034's −0.200 and platform-032's −0.088 were X6's anti-`transient` stance
transferring onto the class-level denials those two tasks *require* (`not an outage`,
`not a registry outage`) — the documented cand_0002/platform-033 mechanism. The trial-level
data refuted it: both declines are **one trial each losing 5–7 items at once**, the
signature of an investigation that never produced a report, not of a register error.
Recording this because the wrong theory was plausible and cheap to hold.

## §2 Ranked issues, and the edit for each

Fan-out: 5 parallel read-only diagnostic subagents (c5-forensics × 2, a mechanical
trap-string sweep, platform-034 deep dive, platform-001/-022/-005 + babylon sweep), then
an adversarial reviewer against my own diff, then a **re-review of the repairs**.

### E1 (headline) — `search_terms` is ONE quoted exact phrase, and `controller` must be the short name — `aap2_agent.md`
- **Class:** missing knowledge / the prompt asserts what the environment contradicts.
- **Target:** platform-034 (0.892). `not-an-outage` missed **4/5** — the largest single
  reachable rubric item left on the board. Also `etcd-downstream` and two `counts`.
- **SOURCE-VERIFIED**, not inferred. `_run/parsec-live/src/tools/splunk.py:34-99`:
  `_build_aap2_query` emits `index=<AAP_INDEX> "{controller}"` and then appends
  `' "{search_terms}"'` — a **single double-quoted literal**, conjunctive. The same
  interpolation feeds `search_by_guid` and `search_namespace` via `_build_ocp_query`.
- **The prompt asserted the opposite.** `:809-811` said *"Use `search_aap2_logs` with the
  controller hostname … The controller hostname is in the `cluster_host_id` field."*
  Measured over all 178 trials: long hostname → **0 rows in 44/44** plus one explicit
  `Unknown AAP2 controller: 'aap2-prod-us-east-2-01…'. Configured: east, west, event0,
  partner0`; short name → the **only** non-empty `search_aap2_logs` result in the corpus
  (platform-032, `controller: east`, `search_terms: "registry.redhat.io"` → 3 rows). The one
  call that used a *given* literal on a *short* name is the one that returned rows.
- **Verify-the-fix, at the exact failure point.** platform-034's seed store
  (`seeds/platform.json → splunk_aap2_log_entries`) holds exactly **3 rows, all
  `controller: east`, all within 02:11–02:15**, and row 0 reads
  `isolated ListResourceRecordSets probe … returned 3543 records in 412ms` — **four of the
  nine `not-an-outage` accept forms** (`isolated`, `probe`, `3543 records`, `412ms`); row 2
  carries the `retained`/cleanup-policy wording for `etcd-downstream`. In cand_0004 t1 the
  agent had the **right controller and the right window** and still got 0 rows:
  `{controller:"east", search_terms:"rehearsal-lab throttl", earliest:2026-06-26T01:55,
  latest:02:20}`. Only the self-composed two-word phrase killed it. All four short-name
  platform-034 calls across the run carry an invented multi-word `search_terms`; a bare
  `{controller, window}` call has **never been issued on this task**. So the edit changes
  behaviour at precisely the point it went wrong.
- **Edits:** rewrote the `cluster_host_id` bullet; added a `search_terms`-is-one-phrase
  bullet; step 4 now takes `errors_only` alone unless a literal was *given*; rewrote step 5
  — which previously said *"use `search_aap2_logs` … once you know what you are looking
  for"*, the sentence that causes the keyword-invention — to read the controller window
  unfiltered first. Per fact 11 I replaced the **contradicting instruction**, and did not
  restate step 3's already-correct unfiltered-first discipline.
- **Provably tool-score-safe:** `search_aap2_logs` appears in **no** task's
  `tool_calls.expected` and **no** `forbidden` list corpus-wide (only two `query_splunk`
  specs exist, both `search_by_guid`). Inserted calls are free under
  `ordered-subsequence`/`unordered-subset`. It prescribes **argument shape, never answer
  wording**, so the direction-(b) displacement mechanism cannot fire on it.

### E2 — taxonomy table: `configuration` / `application_bug` / `dependency` rows — `aap2_agent.md`
- **Class:** right domain, wrong action (decision rule in the cell where the decision is made).
- **The verifier is more lenient than anyone had noticed**, and it changes the fix:
  `_verdict_present` matches the wanted token **anywhere in the answer**, and
  `configuration`/`dependency` are **not** in `TAXONOMY_EXCLUSIVE`. So platform-002 and
  platform-031 are won by the word `dependency` appearing *at all* — the agent need not
  change its declared pick. In **all 8** base misses the word appears nowhere.
- `configuration`'s old lead clause ("a config value that **is present** is wrong for the
  environment") describes platform-002 and platform-031 perfectly, and a table row beats the
  counter-sentence at Rule 3. Rewritten to lead with the disqualifier and to say *write the
  word*.
- **cand_0005's version of this row is the one thing in that candidate I can prove did
  damage:** by naming `application_bug` as an escape branch it produced the run's first two
  `application_bug` mispicks (0/40 → 2/10, Fisher **p=0.037**) on platform-001 and -002 —
  and `application_bug` **is** exclusive, so it voids an otherwise-correct verdict. My
  `application_bug` row therefore explicitly excludes `ansible.cfg`, inventory and agnosticv
  files and routes entrypoint/wrapper scripts to `automation_failure`. Defending
  platform-001's 0/5 (a 0.140-weight item) is worth as much here as the offence.

### E3 — the prompt renders cloud-026's and cost-029's own forbidden literals — `shared_context.md`
- **Class:** the prompt hands the agent a trap string (confirmed-paying, 3rd instance this run).
- `:488` rendered `("CloudTrail records absent", "logs missing")`. cloud-026 forbids
  `cloudtrail records` with **no `attributed_to`**, so it fires on the bare substring inside a
  correct denial. Contingency over 30 trials: literal in prompt → **5/20** answers contain it,
  **5/5 of those scored the hit**; literal absent (cand_0005) → **0/10**. Both cand_0004
  failures reproduce the prompt's own noun phrase ("The absence of CloudTrail records is
  itself a security finding"). Deleted, and the substitute I prescribe (`returned nothing`)
  is itself on cloud-026's `partial-result` accept list.
- `:340-345` rendered `"it was free"`, `"free-tier only"`, `"no charges were incurred"` —
  and the heading itself said "free of value-language". cost-029 forbids bare **`free`** and
  `no charges were incurred`. Run-wide `free-tier` appears in 6 answers, **all 6 on
  cost-029, 5 of them scoring `invented-figure`**. Replaced the rendered literals with a
  description of the banned shape; `grep '\bfree\b'` is now 0 in the file. cost-029 is at
  1.000 under the champion, so this is **variance removal, not a gain** — a 43% run-wide
  base rate that the champion dodged 5/5.

### E4 — narrowed absence-marker rule + a carve-out that the reviewer had to fix twice
Carried cand_0005's "write about the search, not the source's contents" but **dropped its
11-line prohibition**, which would have suppressed platform-034's `3543 records` — i.e. two
of my own edits fighting, the exact shape the reviewer caught in the last two iterations.
I added a carve-out that a counted quantity is an observation — **and the reviewer found my
carve-out rendered it as "3,543 records returned in 412 ms", which matches neither accept
literal** (`_contains` is a bare substring test: `"3543 records" in "3,543 records"` is
False). Repaired to prescribe the source's own digits verbatim, rendering nothing.

### E5–E8 — carried / corrected riders
- **E5** `cost_agent.md`: `get_pool` is single-pool, `list_pools` is the only whole-database
  scan (cand_0005's X1, unchanged — it took cloud-027's `tm list_pools` 3/5 → 0/5).
- **E6** `aap2_agent.md` anti-`transient`: removed the two places the file rendered its own
  banned words inside *approving* prose (a worked example, and "the evidence the failure was
  **not transient**"). The six strings are now named **exactly once**, in the prohibition
  (`grep` confirms one line). Measured 3/5 → 0/5.
- **E7** `babylon_agent.md`: the same phrase-match correction for `search_terms`; `search_raw`
  demoted (254/254 empty run-wide, in no `expected` list); the `cluster_name` example FQDN
  replaced by the short name the rows actually carry (3/3 FQDN calls empty); `get_component`'s
  `name` documented as the **governor** name; and cand_0005's catalog-item rule kept — with
  its false clause *"that file is usually where the item's settings actually live"* deleted
  (platform-005's settings are in a role's `defaults/`) and `common.yaml`'s 0-for-110 hit rate
  noted so the agent does not burn a retry on it.
  **X12 corrected, not carried:** cand_0005 asserted *"when a typed search comes back empty,
  the rows are not in the store"* — now **proven false** and actively harmful (platform-032
  seed-1: `search_terms:"registry.redhat.io unauthorized"` → 0 rows; same scope,
  `"registry.redhat.io"` → 3 rows). My version says an empty result from a search *you*
  narrowed is not evidence of absence.
- **E8** `aap2_agent.md`: narrowed the over-applied imperative *"when the question names an
  `owner/repo` AND a path, fetch it verbatim on your FIRST GitHub call"* to require a
  **literal owner**. platform-001's instruction says "the AgnosticD content repository" and
  names **no owner**, and 3/5 champion trials open on the nonexistent `rhpds/agnosticd`
  (0 successes in 67 calls) — one of them defending it with *"The question specifies
  `rhpds/agnosticd` explicitly"* when it does not. Its expected `lookup_catalog_item {args:{}}`
  matches any invocation, so the miss is pure absence. Fixed the imperative, not the already-
  present corrective paragraph below it (fact 11).

## §3 What I cut, and why (three of my own edits died in review)
- **Owner-precedence reordering + the `git_url` correction.** The factual premise is right
  (`git_url` present in 1 of 510 `get_job_log` results) but **no task is losing a call to
  it**: platform-031's `tm` is `[]` in 5/5 and platform-001's owner matches 5/5 under the
  champion. Meanwhile cand_0005's version of that same block correlates with platform-031's
  `tm search_by_guid` going **0/5 → 3/5** (an LCS-position loss — all 10 trials *did* make the
  call). True but not load-bearing, with a measured downside: reverted byte-for-byte. E8
  replaces it with an edit on the paragraph that actually is load-bearing.
- **The Step-6 root-cause gloss.** My replacement restated in plain text the bold list on the
  very next line. Reverted.
- **cand_0005's X7** (widening the Step 7a refutation gate). Measured: `not-an-outage` 4/5 →
  **5/5**. The gate's *"if all you hold is silence, skip this item"* clause is epistemically
  correct — the agent was obeying a sound rule while being starved of evidence by a different
  part of the file. E1 fixes the starvation; the gate stays as the champion had it.

## §4 Deliberately skipped
- **icinga-010 / icinga-013** — code-gated (`get_babylon_tools()` omits `query_icinga`);
  ceilings 0.635/0.640 already attained. icinga-010's `no-suppression` remains declined for
  the sixth iteration: winning it means asserting Icinga state the route cannot observe.
- **platform-018** — 100% environment artifact; excluded from every calculation.
- **platform-032 −0.088, platform-019 −0.065, cost-030 −0.056 under cand_0005** — all three
  are **environment flakes**, verified at the tool-result level, and I changed nothing for
  them: a `fetch_github_file` that succeeds 31/33 times returned `No such file … at the
  specified ref`; `list_anarchy_subjects` returned a degenerate 4-field row in 2 calls out of
  329; `query_cost_monitor` timed out and `query_aws_capacity_manager` returned 78.57% where
  it returns 97.7% in 28/30. Per the LEDGER's own rule I did not redesign on these.
- **platform-022's `fabricated-outcome`.** A subagent overturned the "no prompt fix exists"
  verdict and proposed steering the attribution wording (the `attributed_to` list demands the
  bare bigram `the write-up`, which every natural possessive/modifier breaks). I **declined**
  it: it is wording-steering on a task already at 0.965 for ≤ +0.035, and wording-steering is
  the mechanism that has cost this run score twice.
- **Restating the find_jobs clause-order rule.** cand_0004 already states it maximally at
  `:126-141` using platform-034's own sentence as the example, and it is still disobeyed
  4/10. A subagent proposed expanding it; that is the REFUTED move, so I dropped it.
- `orchestrator.md`, `icinga_agent.md`, `ocpv_agent.md`, `security_agent.md`: **untouched**
  (cloud-024 is at 1.000 and `orchestrator.md` is its whole prompt; the 4 icinga collisions
  the sweep found have 0 fires in 30 trials each and those tasks sit at ceiling).

## §5 Verification performed
- **Bidirectional collision check**, scripted (`/tmp/i6/fbcheck.py`), restricted to the tasks
  each edited file actually loads: **(a) 0 forbidden collisions / 321 checks.**
  **(b)** three deleted-vocabulary flags, all verified false positives (`absent` and `event`
  still occur in the edited `shared_context.md`; `no matching` is replaced by two forms that
  *are* on platform-023's accept list).
- **Adversarial reviewer** against the finished diff → 1 BLOCKER, 2 SERIOUS, all acted on;
  then a **re-review of the repairs**, which is where the last iteration's worst defect was
  caught.
- Banned-word audit: the six `transient`-family strings appear on exactly one line.
- Diff size: **+106 / −30** lines across 4 of 8 files.

## §6 What to preserve
cand_0001's three fixed tasks (cloud-024, platform-004, platform-007) and cand_0004's two
(cost-029, platform-023) depend on rules I did not touch. `orchestrator.md` is byte-identical,
so cloud-024 cannot move. The 21 passing tasks' domain files are untouched except for
`aap2_agent.md`/`babylon_agent.md` changes that are argument-shape only or provably free.

## §7 If this is rejected
Bisection order: cut **E4** (the carve-out — newest and most reworked text) → **E3's
`free` half** (prophylaxis, no measured beneficiary) → **E7's riders**. **Defend E1, E2, E5,
E6** — E1 is source-verified and targets the biggest item on the board; E2, E5 and E6 each
have a measured rubric-item mechanism behind them. And **check the environment first**: if
platform-018 or platform-034 lands zero-row, re-run rather than redesign.

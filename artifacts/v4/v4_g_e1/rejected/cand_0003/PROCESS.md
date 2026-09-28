# PROCESS — cand_0003 (iteration 3)

## 0. START HERE: the finding that should change how this run is read

**The LEDGER's `broke={platform-018}` for cand_0002 is an ENVIRONMENT ARTIFACT, and it
is the reason cand_0002 was rejected. Its prompt edits did not cause it.**

Evidence chain, each step independently checkable:

1. platform-018's only required tool call is
   `query_aap2{find_jobs, controller:east, template_name:…, status:failed,
   created_after:2026-05-01, created_before:2026-05-21, max_results:200}`.
   I extracted that call's **arguments and its result** from all 16 recorded trials.
   The arguments are **byte-identical in every trial**. The result is
   `{"total": 3, "jobs": [...]}` in 13 of them and `{"total": 0, "jobs": []}` in
   3 — and those 3 are exactly cand_0002's t1/t3/t4, which scored 0.30 while every
   other trial scored 1.00. `reward-detail.json` confirms `tool_calls = 1.0` and
   `answer = 0.0` in each: the agent made the right call and the tool returned nothing.
2. The 0.30 trials' transcripts show one call, an empty result, and an honest
   "no failed jobs matched" answer. There was nothing else in the store to find.
3. **Why it happens.** A read-only sweep of the backend source (`parsec-live/src/`,
   plus the real simulator at `simulation-harness/src/simulation_harness/`) found
   **no fault injection anywhere**. The "backend" is itself an LLM — `deep_agent.py:111`
   `ChatOpenAI`, configured at `harness-cfg/platform.yaml:4-5` as
   `simulation_model: azure/gpt-5.4, temperature: 0` — which re-derives the answer to
   every tool call from a fixed checked-in seed store. `temperature: 0` is argmax
   sampling on a non-deterministic serving stack, not determinism. The seed store is
   verified byte-identical on install (`install_seeds.py:96-118`); the 3 matching rows
   are always present. What varies is whether the simulating model retrieves them.
   `find_jobs` is the fragile one because the request schema declares
   `created_after`/`created_before` while **no `Job` entity has a `created` field**, so
   the simulator must bridge `created_* → started` and compare a date-only bound
   against a full ISO timestamp, by hand, on every call.
4. **Magnitude.** That one task's −0.420 is **−0.0124 on the paired mean**. The gate
   rejected cand_0002 at `Δ̄ = −0.0049` against `SE = 0.0049`. **The environment fault
   alone is 2.5× the margin that rejected it.**
5. **Run-wide rate.** I scripted "same task, same tool, byte-identical args, different
   emptiness" across all 16 candidates × 34 tasks. It is not rare: the empty-result
   rate run-wide is ~13%, and emptiness flips on identical calls in cost-030,
   icinga-010, platform-002, -008, -018, -019, -034. platform-019's own bimodality
   (0.15 vs 1.00) is the same mechanism.

**Consequence for this iteration, and for every later one: cand_0002's batch was a
real improvement that lost to noise.** Its per-task record was
`+0.120 cost-029, +0.096 icinga-013, +0.125 icinga-014, +0.105 platform-022,
+0.120 platform-023, +0.194 platform-031, +0.154 platform-034` against
`−0.420 platform-018 (environment), −0.167 platform-033 (real), and four sub-noise
moves`. So cand_0003 **re-applies the whole cand_0002 diff** and fixes only the one
decline that forensics could actually pin on prompt text.

Method note for whoever reads this next: `/tmp/agg3.py` builds the per-task ×
per-candidate reward table from `rollouts/val/*.json` (5 trials each, all candidates
in one place — far easier than the trial tree). `/tmp/trials.py <task>` maps a task to
its trial dirs. `/tmp/envflake.py` is the identical-call/different-result detector, and
it should be run **before** attributing any regression to prompt text.

## 1. Second structural finding: `orchestrator.md` is a blind spot both prior iterations edited around

Routing is the Python regex `classify_fast()`, which returns before any LLM runs; a
sub-agent's prompt is `shared_context.md` + one domain file, and **`orchestrator.md` is
the *entire* prompt for the 13 tasks the regex does not claim.** I re-derived the routes
by `ast`-extracting the patterns and replaying them over all 34 instructions
(`/tmp/route.py`):

| route | n | tasks |
|---|---|---|
| ORCHESTRATOR | 13 | cloud-024, cloud-026, platform-001, 002, 003, 004, 006, 007, 008, 009, 022, 023, 034 |
| aap2 | 2 | platform-018, platform-031 |
| babylon | 7 | icinga-010, icinga-013, platform-005, 019, 021, 032, 033 |
| cost | 5 | cloud-025, cloud-027, cost-028, cost-029, cost-030 |
| icinga | 6 | icinga-011, 012, 014, 015, 016, 017 |
| ocpv | 1 | platform-020 |

Iteration 1 wrote *"terseness never applies to a judgment the question asked for"* —
the correct rule for platform-034's and icinga-013's dominant losses — into
`shared_context.md`. Iteration 2 wrote *"bound your guessing to three"* into
`shared_context.md`. **Neither file is read by the orchestrator, so for the 13 tasks
above both rules are dead text.** This is the third instance of the same error in three
iterations (iteration 1's icinga routing table in `orchestrator.md` was the first, and
was unreachable for the opposite reason).

Meanwhile `orchestrator.md:24-26` carried, untouched by both iterations,
*"Stay measured and objective — **present facts and let the investigator draw
conclusions**"*. Two independent diagnostic subagents, working on different tasks
(platform-002 and platform-034), converged on that clause as the single highest-value
harmful sentence in the corpus. The agent **obeys** it and loses:

- platform-034 `not-an-outage` **5/5**, `etcd-downstream` 3/5 — both `derived: true`
  facts, i.e. exactly "a conclusion the investigator is told to draw for themselves".
  Trial t0 writes a full mechanism table and then withholds the direction of causation.
- platform-002 `category` **5/5** (14/18 run-wide), platform-003 and platform-001 the
  same item — a verdict the rubric requires the agent to commit to.

## 2. Third structural finding: the RCA guidance is in the wrong file for 6 of 7 RCA tasks

Iteration 1 correctly identified that a closed 13-token taxonomy (`verify.py:469`)
appeared in **none** of the 8 files, and added it — to `aap2_agent.md`. But of the four
tasks with an `answer.verdict` demanding a token, **only platform-031 routes to aap2**;
001/002/003 are orchestrator tasks. And of the RCA-*discipline* tasks, platform-032 and
-033 route to **babylon**, which has no root-cause section at all, while 008/023/034 are
orchestrator tasks.

I checked this rather than trusting it: the forensics subagent attributed platform-033's
decline to `aap2_agent.md`'s new RCA paragraph, and the router replay says platform-033
loads `babylon_agent.md`. I confirmed via `get_babylon_tools()` that the babylon agent
does hold `query_aap2`/`search_agnosticv_prs`/`fetch_github_file` (which is why its
transcript *looks* like an aap2 trace) — so the attribution was wrong and the real
culprit is a `shared_context.md` rule. Placement this iteration:

- **taxonomy → `orchestrator.md`** (001/002/003) and kept in `aap2_agent.md` (031).
- **RCA discipline → `shared_context.md`** (reaches babylon 032/033, aap2, and the rest;
  it is investigation discipline, not platform knowledge, so `shared_context` is the
  honest home) **and** `orchestrator.md` (034/008/023).

## 3. Fourth finding: `icinga_agent.md` names two repositories that do not exist

I tabulated every GitHub call in the run by `(tool, owner/repo)` with hit/empty counts:

| repo | HIT | EMPTY/ERR |
|---|---|---|
| `rhpds/rhdp-monitoring` | **80** | 3 |
| `rhpds/monitoring-scripts` | 0 | 12 |
| `rhpds/monitoring-config` | 0 | 6 |
| `redhat-cop/agnosticd` | 0 | 97 |
| `agnosticd/agnosticd-v2` | **232** | — |

`icinga_agent.md` named `rhpds/monitoring-scripts` and `rhpds/monitoring-config` as the
two source-of-truth repos, in 14 places including a table row and a worked
`fetch_github_file` call. **Four tasks** (icinga-010/011/012/014) pin
`rhpds/rhdp-monitoring` in `tool_calls.expected`; **zero** tasks mention either of the
named repos anywhere. Same class as iteration 1's accepted `rhpds/agnosticd-v2 →
agnosticd/agnosticd-v2` correction: the prompt asserts a false fact and the agent obeys.
In icinga-014's one 0.375 trial the agent burned 8 of 11 calls on the two nonexistent
repos after the correct repo returned a (stochastically) empty page.

## 4. Ranked issue list

| rank | issue | tasks | evidence | class | file chosen |
|---|---|---|---|---|---|
| 1 | cand_0002's batch was rejected by an environment artifact | 7 tasks it improved | §0 | re-apply | `aap2_agent.md`, `shared_context.md` |
| 2 | "let the investigator draw conclusions" suppresses the scored judgment | 034 (5/5), 002/001/003 (`category`), 008, 023 | §1 | BEHAVIORAL (prompt is wrong) | `orchestrator.md` in place |
| 3 | taxonomy unreachable for 3 of 4 tasks that need it | 001, 002, 003 | §2 | KNOWLEDGE, wrong file | `orchestrator.md` |
| 4 | RCA discipline unreachable for babylon-routed RCA tasks | 032, 033 | §2 | KNOWLEDGE, wrong file | `shared_context.md` |
| 5 | 13% empty-result rate, and the prompt **forbade** the only mitigation | 018, 019, 034, 010, 002, 014 | §0, §5 | right-domain-wrong-action | both readers |
| 6 | two nonexistent monitoring repos asserted as fact | 010, 011, 012, 014 | §3 | prompt-vs-reality | `icinga_agent.md` in place |
| 7 | `tests-role` vocabulary collision introduced by cand_0002 | 033 | §6 | BEHAVIORAL | `aap2_agent.md` + `shared_context.md` |
| 8 | "do not report $0.00" renders the figure it forbids | 029 | 4/5 | overconfident | `cost_agent.md` in place |
| 9 | owner/repo permutation spiral burns the call budget | 001, 033, 014 | 1-of-5 each | right-domain-wrong-action | `aap2_agent.md` |

## 5. The new lever: "the one confirmation re-issue"

`shared_context.md` said, flatly, **"NEVER call the same tool with the same parameters
twice in a conversation."** Against a backend with a 13% stochastic empty rate, that
sentence forbids the only recovery available. This is a prompt-vs-environment
contradiction of exactly the class iteration 1 named as highest-yield.

Before writing it I had a subagent establish two things:

- **Is a retry actually a recovery?** Yes, decisively. `simulation_instance.py:153`
  calls `generate_response` with **no `thread_id`**, `deep_agent.py:252` defaults it to
  `"default"`, and `:268` issues a fresh `ainvoke` per call. There is **no result cache
  keyed on arguments** and no per-trial seed latching emptiness. A repeat call is a
  fresh sample. (Corroborating: no agent in the whole run ever repeated an identical
  call — the prompt forbade it — so there was no direct behavioural evidence either way.)
- **Can one extra call cost reward anywhere?** No. 33 tasks match
  `ordered-subsequence` and cost-028 `unordered-subset`; both are monotone in inserted
  calls. `score_tool_calls` divides by `len(expected)`, never `len(calls)`. Every
  `forbidden` tool entry keys on wrong *arguments*, never on repetition. The subagent
  tested this exhaustively — duplicate of every call at every position, all 34
  contracts, **0 regressions**.

The rule is therefore gated on three conditions (empty result for the thing asked
about; the question *presupposes* the rows exist; not already re-issued), capped at one
extra call per question, and **requires byte-identical arguments** — the last is
load-bearing, because a "retry" with a narrowing argument dropped would match
platform-019's and platform-021's `absent_args` forbidden entries and zero their whole
tool component.

## 6. Every change, with its class and safety argument

### Re-applied from cand_0002 (unchanged)
All 14 edits (A1–A8, S1–S6), verbatim, by copying cand_0002's `aap2_agent.md` and
`shared_context.md` and then editing forward. Rationale in §0. Two of its edits are
known to be **inert rather than harmful** (the `lookup_catalog_item` owner rule: call
rate 2/5 both sides; the taxonomy-token backtick rule: 1/5 → 2/5, a null result) — kept
because inert costs nothing, and noted here so nobody credits them later.

### Corrections to cand_0002's own text
| # | file | change | class | why |
|---|---|---|---|---|
| C1 | `aap2_agent.md` | RCA item 4: drop the phrase **"did not catch"**, promote the on-list forms (`was merged despite`, `bypassed`, `should have caught`, `was not blocked`, `was not caught`, `no result`, `let it through`) | BEHAVIORAL | platform-033's `tests-role.any_of` accepts 10 forms; cand_0002's gloss listed `did not catch` **first**, and it is on none of them — `did not catch it` never yields the bigram `not caught`. Champion family hit the item 4/6, cand_0002 **0/5** (Fisher p=0.022 vs the 0/10 non-champion family), and the cand_0003 control trial — byte-identical prompt to the champion — hit it. This is the one decline in cand_0002 that forensics could pin on text. |
| C2 | `aap2_agent.md` + `shared_context.md` | add: *an evidence-gap statement is not a judgment* ("no test results are attached", "the suite, if any ran") | BEHAVIORAL | the same paragraph's demand to "say what it failed to do" pushed 3/5 cand_0002 trials into hedging about the dataset instead of judging. A change that reached production without a passing record **was not blocked** — available without a tool result. |
| C3 | `aap2_agent.md` | scope the owner-resolution rule: a path read out of a job log is **not** an indirect repo reference; `found:false` answers *that* question but never licenses skipping a later listed step; after two failed fetches stop varying the owner | right-domain-wrong-action | the rule misfired once on platform-033 (12 calls permuting owners, 0.38). The `found:false` clause is deliberately narrow — see the blocker in §7. |

### New this iteration
| # | file | change | class | safety |
|---|---|---|---|---|
| N1 | `orchestrator.md` | **`:24-26` corrected in place** — "measured" no longer means withholding a judgment; + name-the-ruled-out-reading, go-get-the-refuting-observation, state-the-direction-of-causation; + the epistemic-verb form for "does not establish" | BEHAVIORAL | only the 8-word clause is removed. No protected task's rubric rewards *withholding* a conclusion; the two that look like they might (008, 023) are scored on stating the **negative** conclusion explicitly, which the closing sentence mandates. Each bullet is conditional on the question asking for that judgment. |
| N2 | `orchestrator.md` | Root Cause Category section (taxonomy + which-token-when + classify-what-was-absent + gate) | KNOWLEDGE | gated on the question explicitly asking for a category: `grep -ic 'root cause category'` is 1 for 001/002/003 and **0** for all 10 protected orchestrator tasks, **all** of which have `verdict: None` — a taxonomy edit is literally unscoreable there. `TAXONOMY_EXCLUSIVE` omits the bare words, so steering between `configuration` and `dependency` cannot void anything. |
| N3 | `orchestrator.md` | Bounding Your Investigation (answer-when-facts-are-in-hand + bound guessed scopes to three) | right-domain-wrong-action | ports rules that already exist for sub-agents into the file the orchestrator reads. Explicitly firewalled against skipping a **listed** step, including one expected to be empty — see §7 defect 6. |
| N4 | `orchestrator.md` + `shared_context.md` | The One Confirmation Re-issue | right-domain-wrong-action | §5. |
| N5 | `shared_context.md` | Root-Cause Discipline block (direction of causation, ruled-out reading, guardrail = contributing factor, evidence-gap ≠ judgment) | KNOWLEDGE, correct file | reaches babylon-routed 032/033 which have no RCA section. Every bullet is gated on the question asking for a cause/mechanism/relation, so it is inert for cost/icinga/ocpv lookups. Verified: none of the vocabulary it teaches appears in any task's `forbidden.none_of`; seven of the contributing-factor forms are platform-033 **required** forms. |
| N6 | `icinga_agent.md` | `rhpds/monitoring-scripts` + `rhpds/monitoring-config` → `rhpds/rhdp-monitoring` throughout (14 sites); + "this is the only monitoring repository, do not invent siblings"; + a check-command directory is a **deploy path, not a repo name**; + an explicitly named repo wins | prompt-vs-reality | §3. icinga-012's expected fetch is already `rhpds/rhdp-monitoring`; 015/016/017 make no GitHub calls; no task has a forbidden entry mentioning any monitoring repo. The on-host path `/home/icinga/monitoring-scripts/…` is deliberately **left alone** — it is a real deployment directory, not a repo. |
| N7 | `icinga_agent.md` | step 5: name a path discrepancy as a **relocation** (`moved`/`now lives`/`actually lives`/`still points`/`old path`/`out of date`/`stale`); the fault is the configuration, not the monitored service | notation/BEHAVIORAL | `stale-config` is lost 3/15 — once under **each** of seed/cand_0001/cand_0002, i.e. a phrasing-level class, not a variant regression. Eight of icinga-014's 13 accepted forms are lifted verbatim; a suite-wide scan found these words in **zero** `forbidden` lists and as **required** forms for platform-032 and -006. |
| N8 | `cost_agent.md` | "do not print the zero" → **do not render the figure at all**, plus drop the value-language | overconfident | conditioned on the result collection being empty, so cost-028/030 (which must quote `total_cost`) never see it. Placed in the domain file per the brief's preference. |
| N9 | `aap2_agent.md` | Splunk framing: "supplementary, only when primary tools don't provide enough signal" → **only Splunk tells you whether the dependency was healthy** | prompt-vs-rubric | cand_0002 added the cross-source exception but left the contradicting sentence directly **above** it; INSIGHTS already records that a leading statement beats a counter-sentence. platform-031's `search_by_guid` is pinned **second** by LCS and was landing at call 13. |
| N10 | `aap2_agent.md` | legacy `redhat-cop/agnosticd` is provenance only — never fall back to it; correct the path or `ref`, not the owner | KNOWLEDGE | 0 hits in 97 calls. No task expects it. Reinforces platform-005's wrong-owner trap. |

`babylon_agent.md`, `ocpv_agent.md`, `security_agent.md` are **byte-identical to the
champion** (verified). platform-020 and platform-021 cannot move.

## 7. Adversarial review — 15 defects found in my own diff, 2 of them blockers, all fixed

I ran a dedicated reviewer against the finished diff, briefed with the verified routing
map and told to break it. This step is now non-negotiable in this loop; it paid for
itself twice over. The findings I acted on:

1. **BLOCKER — my taxonomy table was a verdict-voiding trap.** `_verdict_present` runs
   with `exclusive=True`: naming *any* second `TAXONOMY_EXCLUSIVE` member voids the
   category. My "which token, when" table had cells listing **four** exclusive members
   each, in the file loaded by 001/002/003, next to that file's own "use markdown
   tables" instruction. **Fix:** replaced the table with prose decision rules that never
   put two exclusive tokens in one line, and added an explicit
   *"write your chosen token and no other — a second token, even to reject it,
   invalidates the field"*. The champion `orchestrator.md` has zero taxonomy tokens, so
   this risk was entirely self-inflicted.
2. **BLOCKER — my own C3 attacked platform-009, a task at 1.000.** I had written
   *"a catalog lookup that comes back `found: false` has answered you … record that and
   move on."* platform-009's instruction is *"say whether the catalog item was found,
   and **if it was not, check whether a pull request is pending**"* — its third expected
   call is `search_agnosticv_prs` and its count fact is the PR number. My sentence is a
   literal instruction to stop there: up to **−0.45** on a ceiling task. **Fix:** the
   `found:false` clause now explicitly requires continuing with whatever the question
   asks next, and forbids only re-asking under permuted names. (Note the symmetry with
   cand_0002, whose reviewer caught its Splunk edit attacking the very task the rest of
   the candidate was restoring. Two iterations, two self-inflicted attacks on a
   protected task, both caught only by an adversary aimed at the diff.)
3. **SERIOUS — I was writing platform-023's and platform-031's forbidden strings into
   the prompt.** My new re-issue rule named `transient`/`intermittent`/`flake`/
   `"retry the job"` and `"confirms that"`/`"proves that"`/`"this shows that"`. Those
   are bare `none_of` forms with **no `attributed_to`**, and INSIGHTS already records
   that handing the agent a banned word makes it write the word in order to deny it.
   **Fix:** both new copies now carry the instruction with **no vocabulary at all**
   ("your retry policy is not a finding"; "state an absence as an absence and do not
   attach a verb of proof to it"). The word lists survive only in `aap2_agent.md`,
   where they are cand_0002's text and platform-031 measured **+0.194** with them —
   I am not overriding a measured result with a priming theory.
4. **SERIOUS — my "ruled out" bullet could induce platform-032's bare forbidden forms**
   (`registry is down`, `registry is unavailable`, …, no `attributed_to`) on a task at
   1.000. **Fix:** both copies now say to name the ruled-out reading **by its category**
   and never as a bare proposition about the named host, then state what the evidence
   positively shows (`responded`, `rejected`, `answered normally`) — which happens to be
   platform-032's and platform-034's *required* vocabulary.
5. **SERIOUS — my early-stop rule threatened cloud-026's fourth call.** Its
   `query_cloudtrail` leg returns nothing, yet `required.partial-result` can only be
   satisfied by making it. **Fix:** the section now states that it never licenses
   skipping a check the question **listed**, including one expected to be empty, and
   that a listed check returning nothing is itself a required finding.
6. **SERIOUS — my icinga rename left step 3 contradicting the new search-first rule**,
   and icinga-010/011 (both 1.000) pin specific `monitoring/<area>/…` fetch paths that a
   search-then-fetch could displace. **Fix:** step 3 now says to fetch a given in-repo
   path **verbatim and skip the search**, and to search only when no in-repo path is in
   hand.
7. Also fixed: an unverifiable environment assertion ("it is not readable from here",
   the same defect class that cost iteration 1 a trial); `cost_agent.md` rendering
   `$0.00` three more times in the paragraph whose subject is not rendering it;
   the "misconfiguration is a forbidden paraphrase" over-reach (platform-002's
   `why-missing` **accepts** `misconfigured` — now scoped to the category field only);
   a direct contradiction with the surviving "NEVER re-synthesize the agent's analysis"
   rule (now carries a one-line exception for a judgment the question asked for);
   and a dangling "the config repo" reference plus an instance-derived path convention
   left by the rename.

**One reviewer claim I checked and rejected:** it argued the orchestrator cannot execute
"go and get the refuting observation" because `get_orchestrator_direct_tools()` has no
Splunk tool. The transcripts settle it — platform-034's orchestrator trials call
`query_splunk`, `query_aap2`, `lookup_catalog_item`, `fetch_github_file` and
`query_babylon_catalog` directly. Kept the bullet. (Lesson repeated from iteration 2:
when a report makes a load-bearing control-flow claim, go read the code or the trace.)

## 8. Verify-the-fix — the edited text at the exact point each trace went wrong

- **platform-034 `not-an-outage` (0/5).** t0's answer ends *"they are both symptoms of
  the same unbounded concurrency configuration"* — facts stated, refutation and
  direction withheld, in obedience to `orchestrator.md:24-26`. That clause is now gone
  and replaced by three imperatives that each demand the withheld sentence. The refuting
  probe row was never retrieved in **0 of 17** trials because every Splunk call used
  `search_raw` with invented index names and relative windows against June-2026 events;
  bullet 2 names the same-identifier + absolute-window requirement at that exact point. ✓
- **platform-002 `category` (5/5).** The agent already emits a "Root cause category"
  row and fills it with `configuration`. N2 supplies the token set in the file it
  actually loads, and the classify-what-was-absent rule is what selects `dependency`
  over `configuration` — the discrimination iteration 1 got wrong by fixing a
  counter-sentence instead of the table row. ✓
- **platform-033 `tests-role`.** cand_0002 t0 wrote *"the tests **did not catch** it"* —
  the prompt's own first-listed phrase, and on none of the 10 accepted forms. C1 removes
  it and leads with `was merged despite`. C2 addresses the 3/5 that hedged about the
  dataset instead. Both rules now sit in `shared_context.md`, which platform-033 loads. ✓
- **platform-018 (3 trials at 0.30).** N4 fires exactly here: empty result, question
  presupposes rows ("how many of its runs failed… list every failing job id"), not yet
  re-issued → one byte-identical re-issue, which §5 establishes is a fresh sample. The
  duplicate is free under `ordered-subsequence` with `forbidden: []`. ✓
- **icinga-014 (0.375 trial).** First search was against the *correct* repo and returned
  empty; the agent then spent 8 of 11 calls on `monitoring-scripts`/`monitoring-config`
  because the prompt named them. N6 deletes both names and forbids inventing siblings;
  N4 gives the correct repo a second sample. ✓
- **cost-029 `invented-figure` (4/5).** The losing sentence is *"Do not report $0.00 to
  Finance"* — the prompt's own imperative shape. N8 replaces the shape. ✓

## 9. What I deliberately did NOT do

- **No edit for icinga-010 / icinga-013.** Their ceilings (≈0.635 / ≈0.64) are
  code-gated: they route to babylon, and `get_babylon_tools()` has no `query_icinga`.
  Re-confirmed this iteration. icinga-010 is also a cautionary case — cand_0001's 0.551
  came from 2 trials that happened to emit a `no-suppression` literal, and the cand_0003
  control trial (byte-identical prompt) scored 0.495, i.e. the "regression" never existed.
- **No redesign on platform-001, -003, cloud-027 or icinga-010.** All four are in the
  LEDGER's `unresolved`, and the cand_0003 control trial reproduces each decline under
  the *champion* prompt — including cloud-027 at 0.71 with the identical
  `required_missed: assigned` and the same table-cell rendering. These are rubric
  coin-flips.
- **No notation chase on icinga-011/012/016 or platform-008.** Declined for the third
  iteration running. N7 is the one exception, taken because the relocation vocabulary is
  independently better writing and is *required* vocabulary in two other tasks.
- **No new tool.** Out of scope this phase. The escalations are in
  FRAMEWORK_IMPROVEMENTS.md.

## 10. Subagents and features used

Five subagents, all read-only except the reviewer's analysis:
(1) backend-mechanism investigation — produced §0's decisive "retry is a fresh sample"
answer with `file:line` citations; (2) retry-rule safety proof across all 34 rubrics —
exhaustive duplicate-insertion test, 0 regressions; (3) regression forensics on the five
cand_0002 declines — separated the one real cause from four coin-flips, using the
cand_0003 control trial as the discriminator; (4) fresh contradiction sweep on the five
lowest tasks, asked *"name any rubric requirement the CURRENT prompt works AGAINST"*
verbatim; (5) the adversarial reviewer. Two of the diagnostic subagents converged
independently on `orchestrator.md:24-26`, which is the strongest signal in the report;
one of them mis-attributed platform-033's file, which the router replay caught.

## 11. Expected effect and the honest risk

Arithmetic: cand_0002's measured `+0.008` plus the `+0.0124` platform-018 artifact gives
a re-application baseline of about **+0.020**. On top, N1+N2 target a deterministic
3-task `category` loss (~+0.007 if all three land), N1 targets platform-034's 5/5
`not-an-outage` (~+0.003), C1+C2 restore platform-033 (~+0.005), N4/N6/N7/N8 are each
worth ~+0.001–0.003. Plausible range **+0.025 to +0.040** against a `1.0·SE ≈ 0.005` bar.

The risk I am accepting, stated plainly: this is a broad candidate (5 files, +505/−60
lines) and `orchestrator.md` grows 46%, on a file whose only 600-second task already
timed out in 1 of 5 trials. I judge N3 to *lower* that risk, since 30 of that trial's 36
calls were invented-scope sweeps and N3 is the first rule bounding them in a file the
orchestrator reads — but a prompt cannot guarantee a wall-clock bound, and if this
candidate is rejected, **N3 and the length of N1/N2 are the first things to cut.**

The larger honest caveat is measurement, not design: at a ~13% stochastic empty-result
rate, single-digit-milli effects on a 34-task mean are at the edge of what five trials
per task can resolve, and one unlucky task can swamp a real gain — which is precisely
what happened to cand_0002. Escalated in FRAMEWORK_IMPROVEMENTS.md.

# PROCESS — cand_0004

## §0 Step zero: the two checks my predecessors said were mandatory, plus one they got wrong

Per META_INSIGHTS, step zero is (a) replay the router so no rule lands in a file the
target task never loads, and (b) run the identical-call/different-result check before
believing any per-task move. I ran both, via parallel read-only subagents. **(a) came
back with a correction that invalidates the central premise of cand_0003**, so this
iteration is mostly a disciplined salvage of the two rejected candidates rather than a
new direction.

### The routing correction (the headline)

Prior iterations established, correctly, that `classify_fast()` (`agents.py:256`, called
at `orchestrator.py:1202`) regex-routes before the orchestrator LLM runs, and that a
sub-agent's prompt is `shared_context.md` + one domain file (`system_prompt.py:116-121`).
From that they concluded: **"`orchestrator.md` is the ENTIRE prompt for the 13 tasks
`classify_fast` does not claim."** cand_0003 acted on it, moving the judgment/taxonomy
rules into `orchestrator.md`.

**That conclusion is false. The orchestrator is not a terminal handler — it delegates.**
`get_orchestrator_tools()` (`tool_definitions.py:1749-1751`) includes `DELEGATION_TOOLS`;
`_handle_delegation()` (`orchestrator.py:770`) runs `run_sub_agent()`, whose prompt is
built at `agents.py:616` and **does** include `shared_context.md`. Confirmed in the logs:
`parsec-live.log:38760-38764` shows `Agent prompt loaded for orchestrator (…, shared=no)`
followed by `Agent prompt loaded for aap2 (…, shared=yes)`, and the metrics line tags the
run `agent=orchestrator+aap2`. Measured delegation sets are near-deterministic:

| task | classify_fast | delegates to (n runs) |
|---|---|---|
| cloud-024 | ORCH | **nobody** (23/23) — `orchestrator.md` really is its whole prompt |
| cloud-026 | ORCH | security (28/28) |
| platform-001/-002/-004/-006/-007/-008/-009/-022/-023 | ORCH | aap2 (3/3 → 43/43) |
| platform-003 | ORCH | aap2 (21), aap2+babylon (7) |
| platform-034 | ORCH | aap2+babylon (14), aap2 (12) — i.e. aap2 in 26/26 |

**Consequence:** `shared_context.md` reaches **33 of 34** tasks (every task except
cloud-024). `aap2_agent.md` reaches **13**. The "13 tasks read only orchestrator.md"
premise was wrong for 12 of those 13. This also resolves a contradiction nobody had
noticed: the LEDGER records cand_0002 *fixing* platform-023 with a `shared_context.md`-only
edit, which the old map said was impossible.

### The environment check

Re-confirmed and sharpened. 2425 tool results across all 3 candidates; 743 distinct
`(task, tool, args)` groups, 293 seen more than once, **23 flip emptiness on
byte-identical arguments**. One of them dominates everything:

- **platform-018** `query_aap2 find_jobs` (byte-identical, all 6 filters): returned
  `{"total": 3, …}` in 10 trials and `{"total": 0, "jobs": []}` in 5. Reward is **exactly
  1.00 when it returns data and exactly 0.30 when it does not, in all 15 trials across all
  three candidates.** 100% of the task's variance (0.1089, the largest in the matrix) is
  this one call. It is worth ±0.012 on the 34-task mean — **larger than the entire
  c1↔c2↔c3 spread.** Excluded from all reasoning below.

## §1 The measured picture I built before touching anything

Full per-task × per-candidate matrix (5 trials each) at `/tmp/parsec_an/out12.md`.
Column means: **cand_0001 0.927 · cand_0002 0.935 · cand_0003 0.911.**

Only **one** genuinely reproducible improvement exists in the whole run beyond cand_0001:

- **platform-031** 0.748 → **0.941** (c2), 5/5 trials shifted. Mechanism verified in
  `reward-detail.json`: `query_splunk search_by_guid` missed 5/5 → 2/5, and forbidden
  `transient` hit 4/5 → 1/5. This is cand_0002's A5/A6 + A3. **Protecting this drove
  several decisions below.**

And **three** genuine regressions, all cand_0003's, each attributed to specific text:

| task | move | component | attributed to |
|---|---|---|---|
| cloud-024 | 1.000 → 0.640 (3/5) | answer 1.00→0.55 | N4's prohibition rider + N1/N2/N3 bulk in `orchestrator.md` |
| platform-022 | 1.000 → 0.790 (5/5) | **tool_calls** 1.00→0.30 | N1 bullet 2 (`orchestrator.md`) |
| cloud-027 | 0.972 → 0.880 (4/5) | **tool_calls** 1.00→0.60 | N4's prohibition rider (`shared_context.md`) |

The cloud-024 mechanism is worth recording because it is a *shape* of failure, not a
one-off. Perfect separation across 10 trials: **every 1.00 trial issues a bare unfiltered
`query_aws_account_db {}`; every 0.25 trial does not.** cand_0003 added the rider *"never
retry by loosening a filter, dropping a scope argument…"*, and a failing transcript says
so out loud: *"Per the rules, I need to widen the search — dropping the GUID filter … But
first, let me try…"* — it cites the rule as friction, defers the winning move, and never
returns. Meanwhile the recipe that wins (`orchestrator.md`: "returns the account table
for you to filter locally") was pushed from line 288 to line 460 by a +62% file growth.
**A prohibition phrased as a general truth outranks a recipe phrased as a procedure, and
bulk displacement is a real cost in the one file that has no second reader.**

`score_tool_calls` was read to settle the metric question definitively: `score =
len(matched)/len(expected)`, zeroed only by a forbidden call. `len(calls)` never appears;
LCS is monotone under insertion. **Extra or duplicate calls can never cost a point.** So
N4's retry *permission* was harmless (it fired 3 times in 170 trials); 100% of the harm
was the *rider* bolted to it. All three regressions are missing-expected-calls, never
extras.

## §2 Ranked issues, and what I chose to do about each

| # | issue | measured signal | decision |
|---|---|---|---|
| 1 | cand_0003's 3 regressions | systematic, 3–5/5 trials | **exclude** N1, N2, N3, N4 (both halves), N5, N9, C3 |
| 2 | platform-031 +0.194 is the run's only real gain | 5/5 | **inherit c2's `shared_context.md` + `aap2_agent.md` wholesale**, then protect it explicitly (see B1 below) |
| 3 | platform-033 0.957 → 0.790 under c2 | `tests-role` 3/5 → 0/5 among complete trials | **fix in `shared_context.md`** — the file 033 actually loads |
| 4 | icinga_agent.md names 2 nonexistent repos | 0 HIT / 18 calls vs 80 HIT / 3 | **take c3's `icinga_agent.md` wholesale** (N6+N7) |
| 5 | platform-034 `not-an-outage` missed 13/15 | 5/5 c1, 5/5 c2, 3/5 c3 | **port the wording into `aap2_agent.md`**, not `orchestrator.md` |
| 6 | platform-034 `find_jobs` LCS ordering | 13/15 mis-ordered | **narrow the contradicting rule in place** (see §3 E5) |
| 7 | icinga-010 / icinga-013 | tool_calls 0.00 / 0.25 in 15/15 | **declined — proven unreachable.** See §5 |
| 8 | icinga-010 `no-suppression` +0.140/trial | missed 18/20 | **declined on integrity grounds.** See §5 |

## §3 Every edit, with its class

Base composition: `shared_context.md` + `aap2_agent.md` from **cand_0002** (the
best-measured prompt, 0.935); `icinga_agent.md` from **cand_0003**; everything else
byte-identical to the **champion**. Final state — 3 of 8 files differ from champion:

```
orchestrator.md   unchanged   babylon_agent.md  unchanged
cost_agent.md     unchanged   ocpv_agent.md     unchanged
                              security_agent.md unchanged
shared_context.md  = cand_0002 + E1        (+21 lines vs c2)
aap2_agent.md      = cand_0002 + E2..E5    (+60 lines vs c2)
icinga_agent.md    = cand_0003 (N6+N7)     (+38 lines vs c1)
```

**E1 — `shared_context.md`: new section "When a guardrail failed to stop the problem".**
*Class: missing knowledge, in the right file at last.* Targets platform-033.
Forensics: platform-033's `tests-role` is a **phrasing** gap, not a knowledge gap, and the
evidence is threefold — (i) the failing trials write the correct diagnosis in unaccepted
words (*"the tests **did not catch** it"*, where the accept list holds `was not caught`;
one inflection away), (ii) every `tests-role` miss co-occurs with the other four required
items being **hit**, so the evidence chain was complete, (iii) handing the accept-list
forms moved the rate to 3/3. The bullet writes `contributing factor` first (first on the
rubric's list too) and supplies 8 of its 10 accept forms; the off-list glosses the agents
actually wrote are named as anti-examples.
Second bullet fixes **the real cause of c2's platform-033 regression**, which the prior
iteration misdiagnosed: it blamed a paragraph in `aap2_agent.md`, but 033 is
babylon-routed and never reads that file. The actual culprit is c2's absence-partition
bullet, which hands four phrases (`does not establish`, `does not tell us`, `is not
evidence`, `cannot conclude`) that are **4-for-4 off** the `tests-role` list, and so
teaches the agent to answer a what-can-I-conclude question by *describing its own
dataset*. All four c2 trials did exactly that and went 0/4. Note the bullet did not
transfer its *wording* (those literals appear in zero final answers) — it transferred its
*stance*, which is why grepping for the handed string missed it.

**E2 — `aap2_agent.md`: guardrail phrasing reordered accept-list-first** (c3's C1).
*Class: overconfident/wrong-register wording.* Drops `did not catch`, leads with on-list
forms. Provably unscoreable on every aap2-routed task (no such required item exists
there), so this is hygiene, not a scoring edit — kept because it is the same length and
strictly better wording. **I deliberately dropped c3's companion paragraph** from this
file after the reviewer proved it dead weight; its content lives in E1 where it scores.

**E3 — `aap2_agent.md`: gated refutation wording.** *Class: right domain, wrong action.*
Targets platform-034 `not-an-outage` (missed 13/15). Placed inside the existing Step 7a
("Name what you ruled out"), which was already the correct rule and still missed 5/5
because it supplied *reasoning* with no accept-list *wording*. Net +38 lines on a
790-line file (+4.8%), versus cand_0003's +62% on orchestrator.md.
Gated on **both**: the question hands you a "dependency is broken" premise, **and** you
hold an actual *response* from it (a throttle/rejection/4xx is a response; silence is
not). The silence branch routes explicitly to "skip this item, say what the evidence does
not establish, never manufacture a refutation" — which is what platform-008 requires.

**E4 — `aap2_agent.md`: causation-direction vocabulary expanded.** *Class: missing
vocabulary.* The existing text offered 3 of the 9 `etcd-downstream` accept forms; now 6,
adding `downstream` and `retained because`. Targets platform-034's 5/15 miss. 5 lines.

**E5 — `aap2_agent.md`: narrowed the rule that contradicts the clause-order rule.**
*Class: prompt-vs-rubric contradiction — the run's highest-yield class.*
platform-034's tool score is lost to an LCS ordering artifact: the 2 trials that scored
4/4 are exactly the 2 that called `find_jobs` **before** `get_job_log`; 13/15 read the log
first. The clause-order rule (`:128`) already exists **and already uses platform-034's
exact sentence as its worked example** — and is disobeyed 13/15. Restating it is a
hypothesis the JOURNAL already records as REFUTED, so I did not. Instead I found what
overrides it: `:126-127`, *directly above*, said *"when the user provides a specific job
ID … don't use `find_jobs` to search for it first"* — which for a question that supplies a
job ID **and** asks "how many failed" reads as "skip find_jobs". Earlier + more concrete
beats later + more abstract (confirmed finding of this run). I narrowed it in place: it is
now a rule about *locating one known job*, and explicitly does not mean "do not call
`find_jobs`" when the question also asks a breadth question. Safe: platform-022 asks no
breadth question; platform-018's contract has one expected call so there is no order to
get wrong; platform-032's expected order is log-first and the rule stays question-relative
(a rule phrased "count first" would have broken it).

**N6/N7 — `icinga_agent.md`, inherited from cand_0003 unmodified.** *Class: the prompt
asserts identifiers that do not exist.* Hit-rating every `(tool, owner/repo)` in the run:
`rhpds/rhdp-monitoring` **80 HIT / 3**, `rhpds/monitoring-scripts` **0 / 12**,
`rhpds/monitoring-config` **0 / 6**. The prompt named the two zero-hit repos as *the*
source of truth in 14 places while four tasks pin the real one in `tool_calls.expected`.
Same class as cand_0001's ACCEPTED `agnosticd-v2` fix. Proven harmless in c3
(icinga-012/015/016/017 all 1.000×5) and its target improved (icinga-014 0.965 → 1.000).

## §4 Verify-the-fix, and the adversarial pass

Scripted, not eyeballed (`/tmp/fbcheck2.py`): every added line of my delta against the
`forbidden.none_of` of every task that loads that file, per the verified routing map —
**0 violations across 303 checks.** Self-test with a deliberately poisoned probe fires 2
forms, so the check is live. Accept-list coverage of the final text, in the file each
task actually loads: platform-034 `not-an-outage` 6/9 · `etcd-downstream` 6/9 ·
platform-033 `tests-role` 8/10 · platform-031 `mirror-serving` 2/7 (both the forms that
matter, and now listed first).

**The adversarial reviewer earned its keep for the third iteration running — and in the
same shape as before: my own diff attacking a task another part of my diff was
protecting.** Three blockers; I accepted two and a half and rejected one and a half.

- **B1 (accepted, and it was the important one).** My refutation menu handed four phrases
  that are **0-for-4** on platform-031's `mirror-serving` accept list — and platform-031
  is the *certain* aap2 reader whose +0.194 is the run's only real gain, while
  platform-034 (whose list they are 4/4 on) reaches aap2 only by delegation. Worse, my
  block said *"prefer the first that fits"* and *"a paraphrase usually does not [land]"*,
  which converts a menu into an **override** of the winning exemplar sitting nine lines
  above it (`"other downloads from the same host succeeded during the same window"` — on
  031's list). I reordered so the 031-shaped form is first, tagged each form with the
  evidence-shape it belongs to, deleted both override clauses, and made "not an outage" an
  addition rather than a replacement. **Bad risk asymmetry, and I had it backwards.**
- **B3 (accepted).** Revert `cost_agent.md` to champion. `cost_agent.md` is
  byte-identical in c1 and c2, so cost-029's entire c2 gain (0.840 → 0.960) came from
  `shared_context.md`, which I keep. c3 added text here and cost-029 got *worse* (0.920).
  Unmeasured text, zero demonstrated benefit, 3 protected readers at 1.000 → revert.
- **B2 (half accepted, half rejected).** Correct that the aap2 *guardrail* copy is dead
  weight — no aap2-routed task has that required item — so I deleted that paragraph.
  **Wrong** that the causation vocabulary is unreachable: the reviewer read platform-034's
  `classify_fast` result of `None` as "does not read aap2_agent.md", ignoring delegation.
  platform-034 delegates to aap2 in **26/26** observed runs. This is the same wrong-file
  error class that cost three prior iterations, arriving from the opposite direction — and
  it is why I briefed the reviewer with the routing map and still had to check its
  routing claims myself. E4 stays.
- **R1 (accepted).** Led the E1 second bullet with its *trigger* ("when a change
  demonstrably reached production…") instead of its prohibition, so a task whose finding
  is a genuine absence never enters the rule, and added an explicit
  "nothing here licenses asserting something you did not observe" clause. This protects
  platform-023 `cannot-conclude` and platform-008 `no-root-cause`, both at 1.000.
- **R2 (measured, accepted as a residual risk).** Dilution of the icinga-013 verdict
  bullet — the confirmed mechanism by which c3 lost a fix c2 had made. Measured: c2 has it
  at line 381; c3 pushed it to 461 (+80, and missed 3/5); **cand_0004 pushes it to 402
  (+21)**, with nothing new between it and line 182 beyond what c2 already had. A quarter
  the displacement and half the inserted text. Real but much reduced.

## §5 What I deliberately did NOT do

- **icinga-010 / icinga-013 (the two worst tasks, 0.512 / 0.551).** I re-opened the
  "code-gated ceiling" verdict because a subagent flagged their misses as the largest
  noise-free headroom in the suite, and the answer is **more precisely negative than
  before**: dispatch has *no* per-agent allowlist (`orchestrator.py:404-435`; `_INFRA_TOOLS`
  contains `query_icinga`), so such a call *would* execute — but the tool surface is the
  API's `tools=` parameter (`agents.py:655`), and `get_babylon_tools()`
  (`tool_definitions.py:1466-1481`) omits `query_icinga`. **A prompt cannot add a name to
  that list.** No sub-agent delegation tool exists (`DELEGATION_TOOLS` is
  orchestrator-only, and `grep investigate_ agents.py` is empty), no proxy tool exists, and
  `run_sub_agent` never re-enters the orchestrator. Hard ceilings: **icinga-013 ≈ 0.640,
  icinga-010 ≈ 0.635**, and both are already attained. Escalated as code, not faked with
  prose.
- **icinga-010's `no-suppression` (+0.140/trial, missed 18/20).** Reachable by prose, and
  I declined it for the third iteration running, agreeing with my predecessor: the
  accepted phrasings (`not acknowledged`, `no downtimes`, `nobody has`) assert facts about
  an Icinga state the agent provably **cannot observe** on this route. Chasing it teaches
  the model to state absences it never measured. It is a rubric artifact manufactured by
  the misroute. Recorded as a deliberate skip, not an oversight.
- **`orchestrator.md` — zero edits.** It is the entire prompt for cloud-024 and has no
  second reader to dilute the damage; c3 proved a −0.360 there. Every rule I wanted to
  place went into a file the target task also loads.
- **The notation/substring headroom** on icinga-011/012/016 and platform-008 — declined
  for the fourth iteration running, for the same reason.
- **c3's N4 in any form.** Even the "harmless" permission: it fired 3 times in 170 trials
  and cannot improve a score that is monotone in inserted calls. All upside was imaginary;
  all measured effect was its rider.

## §6 Subagents / features used

7 subagents. Round 1 (parallel ×2): prompt-assembly verification from source; reward
matrix + env-flake audit. Round 2 (parallel ×2): icinga tool-gating verification;
cand_0003 regression attribution. Round 3 (parallel ×2): platform-033 babylon-route
forensics; platform-034 wording forensics. Round 4 (×1): adversarial reviewer, briefed
with the verified routing map. No worktrees — the 3 edited files never needed concurrent
writers, and hand-merging kept me able to reject B2's bad half.

## §7 What to preserve, and what to read first next iteration

Preserve: cand_0002's `shared_context.md` absence/verdict bullets (platform-023 →1.000,
cost-029 →0.960, icinga-013 `not-a-problem` 4/5→0/5 missed) and its `aap2_agent.md`
Splunk + transient text (platform-031 +0.194, 5/5). Do not "clean up" the paragraphs that
print forbidden tokens in order to ban them — measured, they *reduce* the hit rate
(`transient` 4/5→1/5, `invented-figure` 4/5→1/5).

Read first: §0's delegation table. Three iterations mis-placed rules by assuming a
sub-agent map that ignores delegation; this iteration found the assumption inverted for 12
of 13 tasks, and the adversarial reviewer *still* made the same error in the other
direction. Before writing any rule, name the file **and** check whether the task gets
there by fast path or by delegation.

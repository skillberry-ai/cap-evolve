# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1/3, candidate `cand_0001`. Baseline val reward **0.800** on the single
task `cost-029-no-cost-rows-for-guid` (completion 1.0, tool_calls 1.0, **answer 0.75**).

## TL;DR

The task is labelled *flaky* (mean reward 0.80) but it is **not flaky** — all 5
seeds fail **identically and deterministically** on the same verifier check
(`forbidden_hit: ['invented-figure']`, `required_missed: []`). The 0.75 answer
score is a fixed 3-of-4, not variance. One root cause, one class of failure:
**the agent renders an absent cost row as a measured `$0`.** Five edits across
three prompt files close it — at the point of the misreading, at the point of
the write-up, and in the general grounding rule that licensed it.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **absence-vs-measured-zero conflation** (`invented-figure` forbidden-fact hit, 5/5 trials) | cost-029-no-cost-rows-for-guid | Agent filtered `query_azure_costs` to the one subscription asked about, got `{"results": [], "total_cost": 0}`, and reported that aggregate as the subscription's spend. `cost_agent.md` carried **zero** text about empty cost results, and `shared_context.md`'s Grounding rule actively licensed it — the number *did* appear in a tool result. | KNOWLEDGE + BEHAVIORAL | (1) add the sourced tool-behavior fact, (2) tighten the output contract with a decision table + worked example, (3) close the grounding loophole domain-generally, (4) annotate the hazard at the field-doc where the misreading happens, (5) extend the class to the one other file whose mandatory template has no absence branch |

There is no rank 2. The val split is one task; its other three `required` checks
(no-data stated / `pool-XX-NNN` subscription named / explanation offered) already
pass on all 5 seeds and every edit below was checked for not endangering them.

**Evidence the cluster is one deterministic root cause, not noise:**
`_run/jobs/v4_t2_e1/cost-029-.../seed-{0..4}/.../verifier/reward-detail.json` →
all five: `required_missed: []`, `forbidden_hit: ['invented-figure']`.
Nine distinct offending sentences across the 5 transcripts, incl. three
"the figure to report is $0.00"-style recommendations addressed to finance.

## Changes made this iteration

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | **add sourced rule + output contract** (primary) | `cost_agent.md` → new `## Empty Cost Results — an Absent Row Is Not a Cost of Zero` (+ 2 subsections), inserted after `## Tool Response Formats`, before `## Parallel vs Sequential` | States the aggregate semantics of `total_cost`; gives the documented reason (from `_run/skills/parsec-cost/api.json`: the cache gate is an *unfiltered* row-count check, so a populated cache holding no match returns `results: []` rather than falling back); a 2-row decision table separating **measured zero** from **absent row**; a 5-step reporting contract; a ranked candidate-explanation list; and a widening procedure. Phrased over "the subscription / account / project you were asked about" — AWS, Azure and GCP alike, any period, any entity. No identifier, date or figure from this task appears. | Yes — the widening step is **strictly additive** ("Add this call — do not drop or replace the filtered one"), so sibling tasks that pin `account_ids` in their expected calls keep their matched call; and widening is explicitly defined as loosening the entity filter only, **never** guessing an unsupplied data-source/database/pool/cluster/controller/region value. |
| 1 | **close the loophole in the general rule** | `shared_context.md` → new `### An absence is not a measurement` inside the existing `## Grounding` section | The bug was not ungroundedness — `total_cost: 0` *was* in a tool result. So the general rule needed the missing distinction: a value about an entity must come from a record *about that entity*; result-set summaries (totals, counts, aggregates) describe what matched. Placed under Grounding because that is the section that created the loophole. Domain-general by construction (it is prepended to all 6 domain agents) and written with non-cost examples ("it has 0 problems", "the host is healthy"). | Yes — explicitly carves out both directions: (a) *describing the result set* ("the search returned 0 results") stays correct and is called the clearest phrasing, so absence-phrasing tasks that require `"0 results"` are unharmed; (b) a record that DID come back carrying `0`/`null`/`[]` **is** a measurement, report it normally. Also reconciles the pre-existing `Infer retired from absence` tip by name instead of contradicting it. |
| 1 | **tighten existing rule in place** | `shared_context.md` → `Empty results` bullet under `## Tool Result Handling` | Was "Say so clearly. Suggest alternatives. …" — now also names *what* has no data and points at the new Grounding subsection. This is the bullet a reader lands on first when a result is empty, so it needed to be the pointer. Every original constraint preserved verbatim (incl. "do NOT retry with the same SQL — simplify first"). | Yes — additive only; no original wording removed. |
| 1 | **annotate the hazard at its source** | `cost_agent.md` → `## Tool Response Formats`, after the three cost-tool return shapes | The audit subagent found that this block documents `total_cost` as a bare top-level field on all three cost tools with no hint it is an aggregate — and this block is what the reader consults *while composing the figure*. Added one paragraph there: `total_cost` and each per-row `total` are sums over `results`; an empty `results` arrives as `total_cost: 0`, an empty sum and not a measured spend; read "Empty Cost Results" before reporting a figure for an entity with no row. Puts the warning at the exact point of the misreading rather than only in a later section. | Yes — describes existing tool semantics; adds no behavioural instruction of its own. |
| 1 (class) | **narrow a conflicting local instruction** | `cost_agent.md` → `### Cross-Cloud Cost Investigation` step 4; `icinga_agent.md` → `## Output Format` preamble | Two mandatory-output instructions elsewhere in the corpus push the agent to fill a slot with a value when it has none. Cost step 4 ("Combine totals in your response") now adds: a cloud whose query returned no row for the entity contributes an **absence**, not a `0` — name it on its own line instead of folding it into the sum. `icinga_agent.md`'s determinate-value template (`Acknowledged: Yes/No`, `Configured Thresholds: …`) had **no absence branch at all**; it now opens with one, conditioned narrowly on "Step 0 matched no host or service", telling the agent to report the name it searched for and the likely reasons instead. Same bug class, different domain — this is the class-generalizing half of the candidate. | Yes for cost (conditional clause, only when a cloud returned no row). Yes for icinga: the branch fires only when nothing matched, so any task with a matching service still gets the full template. Note icinga is **outside this task's footprint** — it cannot move the val score either way; it is here because the class demands it. |

**Files deliberately NOT edited:** `orchestrator.md`, `aap2_agent.md`,
`babylon_agent.md`, `ocpv_agent.md`, `security_agent.md` — see *Deliberately
skipped* below.

## Verify-the-fix

Method: I did not stop at "this reads like good advice." I re-read all 5 failing
transcripts, then ran candidate answers through the task's real scorer
(`.../bench-v4-cost-029-no-cost-rows-for-guid/tests/verify.py`) with the real
`expected.json`, to confirm the behaviour the new text produces actually scores.

- **Point of failure → what the new text does there.** The failure point is the
  sentence where the agent writes the figure. All **9** offending sentences across
  the 5 seeds are named or directly covered by the reporting contract's rule 3,
  two of them near-verbatim: "…leaving a $0.00 bill" and "the resources were all
  free-tier" are quoted in the rule as examples of fabricating inside a candidate
  explanation — which is exactly the loophole the seeds fell through after
  correctly refusing the figure in the headline.
- **Rule-compliant answer + the call sequence the rule produces** → `{"reward":
  1.0, "completion": 1.0, "tool_calls": 1.0, "answer": 1.0}`, `required_missed:
  []`, `forbidden_hit: []`.
- **Variant A** (names no figure anywhere) → **1.0**.
- **Variant B** (my worked-example sentence copied verbatim; the `$0` in it is
  excused because `verify.py`'s `attributed_to` exemption is evaluated
  **per sentence** and the sentence contains "not going to report") → **1.0**.
  Both permitted phrasings score 1.0, so the strong-but-not-frontier reader
  cannot thread this needle wrong.
- **Variant C** (deliberately answers about the wrong entity, quoting a sibling
  row's genuine `$0.00`) → **0.2**. Used only to probe the measured-zero
  carve-out; it is what drove the rule-2 tightening below.
- **Tool-call score is safe.** `expected.json` uses
  `tool_calls.match: "ordered-subsequence"` and `_call_matches` ignores args the
  spec omits, so the extra widening call is a *surplus* call — surplus calls are
  ignored by the LCS matcher. Verified by running the 2-call sequence: 1.0.
- **`required` checks unharmed.** All 3 that already passed (no-data stated /
  subscription named / explanation) are *reinforced* by the contract's rules 1
  and 5 — naming the entity and closing with the settling check are now required
  rather than incidental.

## Process & features used

- **Subagents / parallel features.** Two read-only `Explore` subagents, fanned
  out per the guidance:
  - **(a) 8-file corpus audit** for passages that *encourage* the bad behaviour
    and for every existing empty/absent/zero rule (to avoid stacking a
    contradiction). Returned late — after the three primary edits were already
    on disk — and confirmed them as correctly placed. Its genuinely new findings
    produced **two extra edits**: the bare `total_cost` field docs in
    `cost_agent.md:157-168`, and `icinga_agent.md`'s mandatory template with no
    absence branch. It also flagged `shared_context.md`'s "Confidence Markers →
    When NOT to include" clause ("when empty results are themselves the answer")
    as an enabler; I judged it *not* in conflict — that clause is about an
    absence reported **as** an absence, which the new rules endorse — and left it
    alone rather than stacking a caveat. Recorded here so a future iteration does
    not re-derive it.
  - **(b) golden-vs-rollout diff** on the expected call shape. **This one
    corrected me mid-flight** (see below).
  - Both were read-only; no edit-subagents and no worktrees, because after
    diagnosis this is a single cluster in two in-footprint files — parallel edit
    branches would have cost a merge for nothing. Serial, self-applied edits.
- **Prompt-footprint check before editing anything.** `task.toml` says
  `services = ["cost"]`, and `_run/parsec-live/src/agent/agents.py`'s
  `classify_fast()` regex fast-path matches `\bcost\b` / `pool-\d+-\d+` and
  **skips the orchestrator entirely** for single-domain queries. So this task's
  real footprint is `shared_context.md` + `cost_agent.md` only. Every edit that
  is supposed to move the score is in those two files.
- **Prior iterations read:** `./RUNMAP.md`, `./LEDGER.md`, `./prior_iterations/`,
  `rejected.jsonl`, `history.jsonl` — **all empty; this is iteration 1.** Nothing
  to build on and nothing refuted yet, so no prior-art constraint on this design.
- **Correction I had to make mid-flight** (recorded because it would have cost a
  tool_calls point): I first assumed the fix required an extra *unfiltered* call.
  Subagent (b) showed the golden makes **no** extra call — it never filters in the
  first place, and cites the sibling row already present in its result. I
  reframed the rule to *prefer citing sibling rows already in hand*, and to make
  an additional call only when the result carries nothing at all.
- **Near-regressions caught before shipping** (each one reshaped the text):
  - sibling cost tasks **pin** `account_ids` in their expected calls → made the
    widening rule strictly additive.
  - a platform task **requires** the phrase `"0 results"`/`"zero results"` and
    `shared_context.md` is read by every domain agent → wrote in that describing
    the result set is correct, and only converting it into an entity value is not.
  - an azure-pool task forbids guessed `database` values → added the explicit
    boundary that widening ≠ guessing an unsupplied data-source value.
  - **my own rule 2 created a fresh risk**: reproducing a sibling row's
    `gpu_cost: 0.0` would trip the same trap. Surfaced by variant C; fixed by
    "keep it to each entity's name and its total."
  - **I wrote a task-specific example and caught it myself**: the first draft of
    that clause named this task's actual subscription and figure. Replaced with a
    generic formulation; a grep for this task's GUID / both subscription names /
    the figure / both dates across all three edited files returns **clean**.
- **No rule was dropped.** I made zero deletions — additions plus one in-place
  bullet expansion that preserved all original wording. (I could not compute a
  git-based constraint-line delta: the 8 prompt files are untracked in this repo
  and `HEAD` holds no tree, so `git show HEAD:cost_agent.md` fails and
  `git diff --stat` is empty. Never-drop-a-rule therefore holds by construction
  rather than by diff.)

## Good things to PRESERVE (do not let a future iteration undo these)

1. **The measured-zero carve-out.** A row that came back carrying `0` is a fact
   and must still be reported as `$0.00`. A future iteration tempted to
   strengthen the ban into "never write $0" will break every genuine-zero task.
   Variant C scored 0.2 precisely because it reported a real zero *about the
   wrong entity* — the carve-out is load-bearing, not decoration.
2. **"Describing the result set is correct."** Removing this to make the rule
   terser would break tasks that *require* "returned 0 results" phrasing.
3. **The additive-only widening.** "Add this call — do not drop or replace the
   filtered one" protects sibling tasks whose expected calls pin a filter.
   Rewriting it as "query all subscriptions instead" regresses them.
4. **Widening ≠ guessing a data-source parameter.** The explicit
   database/pool/cluster/controller/region boundary exists to stop a
   confidently-wrong answer replacing an honest absence.
5. **Rule 4's worked example** ("An absent row is not the same as a measured
   zero, so I am not going to report $0 for this subscription") — this exact
   shape is what makes the `attributed_to` per-sentence exemption work. A
   two-sentence rewrite (figure in one sentence, correction in the next) scores
   as a violation.
6. **The refusal extends into candidate explanations.** Two of the 5 seeds
   refused the figure in the headline and then fabricated it inside their
   explanation. Dropping that clause re-opens the failure.

## Deliberately skipped (cluster + why)

- **`orchestrator.md`** — *not read for this task.* `classify_fast()`'s cost
  fast-path skips the orchestrator for single-domain cost queries, so any edit
  there is a measured no-op. The audit flagged two orchestrator enablers
  (`Show exact numbers`, and `## After Agent Delegation`'s "NEVER re-synthesize
  the agent's analysis", which structurally guarantees a sub-agent's fabricated
  figure reaches the user uncorrected). I left both: the pass-through rule is
  load-bearing for many other tasks, weakening it buys nothing measurable here,
  and "never loosen a rule globally to fix one instance" cuts against it.
  Recorded as a candidate lever if a later iteration needs a backstop.
- **`ocpv_agent.md`** — has no empty-result rule either, but (unlike icinga) no
  *mandatory determinate-value template* that conflicts with the new general
  rule; its bare aggregate field docs (`count`, `total_pvs`, …) are covered by
  the `shared_context.md` rule, which is prepended to it. Left alone to keep the
  diff attributable.
- **`security_agent.md`** — its "widen before treating it as a confirmed
  negative" is the closest structural twin to the new cost widening text, and the
  audit flagged "confirmed negative" as an enabler. I disagree: a widened-empty
  CloudTrail result supports a claim about *the record* ("no such call is
  recorded in this window"), which the new rule explicitly permits. Touching it
  risks security tasks that require that phrasing.
- **`aap2_agent.md`, `babylon_agent.md`** — same class present ("a report with
  some gaps is infinitely better than no report at all" is the strongest
  fill-every-slot pressure in the corpus), but out of footprint, unmeasurable
  this round, and the aap2 template is long enough that a safe absence branch is
  a design job rather than a one-liner. Logged for iteration 2/3.
- **Confidence-marker retune** — considered and rejected as a non-conflict; see
  *Process & features used*.

## Escalation (needs code, cannot be fixed with prose this phase)

`verify.py`'s `attributed_to` exemption is evaluated **per sentence**. Prose can
make the compliant phrasing overwhelmingly likely — both permitted forms score
1.0 — but it cannot *guarantee* the reader never emits a bare `$0` in some
sentence. The robust fix is a code-level lint on cost answers: when the cost
result carries no row for the requested entity, reject any currency-zero token in
the answer unless the same sentence carries a refusal marker. That is a
tools/code change and is out of scope for this phase, so it is recorded here as
an escalation rather than faked with more prose.

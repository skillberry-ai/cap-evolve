# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 3 (cand_0003), parent = champion **cand_0001** (val 0.972). Single task:
`cost-408-three-cloud-total-gcp-query-failed`. One prior reject (cand_0002, val 0.752).

**Headline: the two prior iterations' central factual claim is wrong, and I corrected
it with verifier output.** JOURNAL/INSIGHTS both assert that `tool_calls` is "1.0 in
every trial" and that the remaining headroom is "0.028, in 1 of 5 trials". Both are
false for cand_0002's run, and the error hid the largest cluster in the task.

## How I diagnosed (and what the prior entries got wrong)

Same artifact-resolution method cand_0001 established (resolve each trial by its
`trial_result.task_id` hash, read `verifier/reward-detail.json` + `agent/agent.jsonl`,
read `tests/verify.py` rather than only `expected.json`). I applied it to **all 15
trials** (seed ×10, cand_0001 ×5, cand_0002 ×5) rather than only the champion's.

The per-trial table for the rejected cand_0002 is the finding:

| trial | reward | tool_calls | AWS call actually made | counts_missed | forbidden |
|---|---|---|---|---|---|
| t0 | 0.76 | **0.667** | `query_cost_monitor(summary, providers=aws)` | `aws-august-org` | — |
| t1 | 1.00 | 1.0 | `query_aws_costs(account_ids=[])` | — | — |
| t2 | 0.62 | **0.667** | `query_cost_monitor(summary, providers=aws)` | `aws-august-org` | **hit** |
| t3 | 0.62 | **0.667** | `query_cost_monitor(summary, providers=aws)` | `aws-august-org` | **hit** |
| t4 | 0.76 | **0.667** | `query_cost_monitor(summary, providers=aws)` | `aws-august-org` | — |

So `tool_calls` was **0.667 in 4 of 5 trials**, not 1.0. In those trials the agent
called `query_cost_monitor(summary, providers="aws")` *instead of* `query_aws_costs`,
which cost two scored components at once:

1. `unmatched_expected` → the `query_aws_costs(account_ids=[], 08-01→09-01)` call was
   never made, so `tool_calls` dropped to 0.667 (weight 0.3).
2. The cached summary returns a **different AWS figure** — `$12,450.67` instead of the
   authoritative `$184,226.40` — so the `aws-august-org` count missed too (weight 0.7).
   Verified: `$184,226.40` → `counts_missed: []`; `$12,450.67` → `['aws-august-org']`.

Crucially, **cand_0002's diff does not touch tool selection at all** (it edits only
the closing-restatement prose). So this is not a regression cand_0002 introduced — it
is **pre-existing instability that the champion's 5 trials got lucky on**. The seed's
10 trials show the same tool reached for (`query_cost_monitor` appears in 9/10) and
survived only because those trials *also* called `query_aws_costs` afterwards.

Consequence for the run's framing: real headroom is **~0.24, not 0.028**, and the
dominant cluster is tool selection — which both prior iterations explicitly ruled out
as "already correct, don't spend an iteration there".

## Ranked issues

1. **Cached-summary substitution (NEW, largest).** Hits `tool_calls` *and* a count;
   observed in 4/5 cand_0002 trials. Root cause is a contradiction inside
   `cost_agent.md`: line 76 says use CE with `account_ids: []` for broad questions,
   while line 105 said "**Prefer `query_cost_monitor` over `query_aws_costs` when the
   user asks broad cost questions**", and line 100 says "start with summary". This
   task's request ("the whole organisation") is maximally "broad", so the prompt was
   actively steering the agent to the losing call.
2. **Closing restatement re-asserts the complete-scope label.** The one losing
   cand_0001 trial, and 2/5 cand_0002 trials.

## Edits

### Edit 1 — `cost_agent.md`: replace the "prefer the cache for broad questions" rule
**Class:** right domain, wrong action (wrong tool / wrong source of record).

Replaced the contradictory sentence with a new subsection, *"Cached dashboard vs. the
provider's own API — which is the source of record"*. The discriminator is **what the
figure is for**, not how broad the question sounds:

- figure **is the deliverable** (a total, a per-provider split, a number to publish or
  reconcile) → query that provider's own tool; for org-wide AWS that is
  `query_aws_costs` with `account_ids: []`, and *breadth alone is never a reason to
  use the cache*;
- figure is a **signpost** (where to drill next, rough magnitude, freshness) → the
  cache is the right first call.

Plus an explicit rule: never substitute the cross-provider `summary` for a
per-provider tool the request names — when a request enumerates providers with
per-provider date ranges, each named provider is asking for its own call — and if a
cached figure was already read, re-query the owning tool rather than reporting the
cached number.

*Why it generalizes:* it is stated over "a cached/aggregated view vs. the system of
record", with the deliverable-vs-signpost test as the trigger. No provider name,
figure, or date appears in the rule. Any task asking for a reportable per-item figure
where a cache also exists matches.

*Why it's safe:* it does not forbid `query_cost_monitor` — it keeps it as the
prescribed first call for exploration and preserves the breakdown/drilldown workflow
and the AWS-only endpoint notes. The GPU-abuse playbook (which legitimately starts
from `breakdown`) is untouched, and that is exploration, which the new rule endorses.

### Edit 2 — `cost_agent.md`: rule 6 + "How to close"
**Class:** overconfident assertion in a restatement.

cand_0001's own closing note instructed the scope label to travel "*including in any
'headline for the deck' restatement at the end*" — an instruction that **invites** the
paragraph that loses the point. I deleted that clause (as cand_0002 did) but, unlike
cand_0002, I prescribe the right replacement: **name the failed query, never the
figure you could not produce.** Added as numbered rule 6 (contiguous with 1–5) with
the detail in a "How to close" block after the worked example.

**I verified cand_0002's prescribed repair and it is wrong.** cand_0002 told the agent
to "**negate** the label" — I scored that exact form against the real `verify.py`:

| closing | score |
|---|---|
| `"…cannot be stated as a complete all-three-cloud total."` (cand_0002's own t2/t3 text) | **0.800 — violation** |
| `"…rather than a three-cloud total."` (cand_0001's loser) | 0.800 |
| `"Re-run once GCP's billing data is queryable."` | **1.000** |
| `"GCP is still missing, so the split above is what we have."` | **1.000** |

So cand_0002's rule 6 made its *own* compliant trials fail: t2 and t3 followed the
"negate" advice and hit the forbidden fact anyway. I found why — negation detection is
sensitive to surface form: `"cannot be stated as a three-cloud total"` is read as
denied, but `"...as a complete all-three-cloud total"` is a violation, because the
hyphenated prefix makes the forbidden form start mid-word and the negation scope check
misses it. That is too brittle to instruct against, so my rule says **do not name the
complete-scope figure in a closing at all**, and explicitly warns against hunting for
a safe phrasing. I also scoped the rule to the *closing only*, so rule 3 (where "it is
not the all-cloud total" beside the number is correct and wanted) is preserved.

### Edit 3 — `shared_context.md`: domain-general cache-vs-source-of-record bullet
One bullet, next to the existing error/empty/zero block, stating the cache rule over
"an entity"/"a figure you are going to report" rather than cost nouns. Placed here
because the mechanism is not cost-specific — any domain with a dashboard/cached view
alongside an owning API shares it. Kept short; the operational detail lives in
`cost_agent.md`.

`orchestrator.md` is **unchanged** — routing scored correctly in all 15 trials.

## Verify the fix (did it change behavior at the exact failure point?)

Edit 1 — yes. The agent's failing trials chose the cache because the prompt said to
prefer it for broad questions; that sentence is gone and replaced with a rule whose
worked trigger ("the whole organisation", a per-provider split to publish) lands
squarely in the deliverable branch, naming `account_ids: []` as the org-wide form.

Edit 2 — yes, scored against the real verifier (above): the two forms the losing
trials actually emitted now score 0.8 and are explicitly banned, while both prescribed
closings score 1.0, and the worked example verbatim still scores 1.0.

Negative controls run, not just prescribed shapes: `rather than` → 0.8 and
`instead of` → 0.8 confirm the ban is load-bearing. One honest caveat: `as opposed to`
scores 1.0, so my rule bans a slight superset of what the verifier penalises. That is
deliberate and harmless — it never forces a losing phrasing — and avoids teaching a
rule that depends on which contrastive connective happens to be caught.

No instance-specific values introduced (grepped the diff for every figure, date, and
provider literal in the task).

## Subagents / features used

None, deliberately — third iteration running this way. With a single task whose trials
share a handful of root causes, a scripted sweep over `reward-detail.json` plus an
instrumented `verify.py` dominates fan-out; spawning one subagent per trajectory would
have paid 15× to rediscover two findings. The brief's fan-out guidance assumes many
distinct clusters. Logged again in FRAMEWORK_IMPROVEMENTS.md.

## What to preserve

All five of cand_0001's accepted rules (error≠empty≠zero; name a failure as a failure
and quote the verbatim error text; every partial sum carries its scope in the same
sentence; never plot a failure as `0`; report money at the cents returned). Edit 2
extends rule 3's coverage to the closing, and relaxes nothing.

## What I skipped, and why

- **cand_0001's untried "forbid a `Total` row outright."** The table and labelled sum
  score perfectly in every trial; the required list wants `not a three-cloud` /
  `partial figure` wording. Tightening there risks items that are not broken.
- **A third wording pass on the scope sentence.** Already at ceiling in 5/5 trials.
- **Re-measuring the champion at higher trial count** (cand_0002's suggested next
  step). It was premised on "headroom is 0.028", which I showed is wrong — there is a
  real, mechanical cluster to fix, so fixing it beats spending the budget on
  re-measurement.

## Escalation (no-code-layer finding)

The `aws-august-org` count can only be satisfied by `query_aws_costs`' value; the
cost-monitor cache returns a materially different figure for the same provider and
period. Prose can steer the choice, but nothing in this phase can *prevent* the
substitution or reconcile the two sources. If this recurs after this iteration, the
real fix is code-level: have the cached-summary tool label its values as
non-authoritative, or have the cost agent reconcile cache against the owning API
before reporting. Recording as an escalation, not faking it with more prose.

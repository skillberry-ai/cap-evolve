# PROCESS — cand_0002 (explainability; REQUIRED)

**Headline:** cand_0001 taught the agent to *decline* the cross-window ratio —
and it now does, in 5/5 trials. But it declines by **computing the number and
dismissing it out loud** ("dividing A by B would produce ~2.4%, but that is
meaningless"), which trips the forbidden rubric item in **5/5 trials**. This
iteration makes declining mean *the value never appears*.

## Step 1 — read the scoring key first (per the INSIGHTS method note)

`verifier/reward-detail.json` for all 5 champion trials:

| seed | required missed | forbidden hit |
|---|---|---|
| 0 | `overall-utilization` | `naive-share` |
| 1–4 | — | `naive-share` |

Miss counts: `naive-share` **5/5**, `overall-utilization` **1/5**.
`tool_calls` = 1.0 and `completion` = 1.0 everywhere. All lost reward is in the
0.7 `answer` weight — again nothing to gain in routing or tool selection.

**cand_0001 fully fixed its target cluster.** `share-not-meaningful` was missed
9/20 on the seed and is now missed **0/5**; `window-start` is also 0/5. That
part worked and must be preserved.

I reproduced the score arithmetic exactly, which validates the diagnosis.
Answer denominator = 7 required + 1 forbidden = 8 (`score_answer` scores a
forbidden item as a *point for absence*, not a penalty):
- seed-0: `0.3 + 0.7·(6/8) = 0.8250`
- seeds 1–4: `0.3 + 0.7·(7/8) = 0.9125`
- mean = **0.8950** = the observed val reward, to 4 dp.

So the entire remaining gap is one forbidden hit × 5 trials, plus one
timeout-caused miss. Avoiding the forbidden form alone takes a trial to
`0.3 + 0.7·(8/8) = 1.0`.

## Step 2 — why the decline still fails (read the verifier, don't guess)

`verify.py::_forbidden_violated` excuses an occurrence only if (a) its sentence
carries an `attributed_to` phrase (`naive`, `would understate`, `understates`),
or (b) a negation reaches the occurrence *within its own clause*
(`_CLAUSE_BREAK_RE`, 6-token window). The agent wrote:

> "Dividing $7,339.70 by $301,520.15 would produce a number — approximately
> **2.4%** — but it would be meaningless and misleading: …"

`but` is a clause break (so is the em-dash), so "meaningless" never reaches
`2.4%`. The number sits in an *asserting* clause. Confirmed by calling the real
verifier on the actual shipped sentence:

```
seed0 violated: True          # the shipped answer
no-number violated: False     # same decline, value withheld
```

**The agent's reasoning is correct and its output is still wrong.** This is not
a knowledge gap — it is the belief that a disclaimed number is a safe number.
Nothing in either file forbade *showing* the rejected figure: cand_0001 said
"do not state the percentage", which the agent satisfied by stating it as a
counter-example rather than as the answer. Per the method note in
META_INSIGHTS ("look for the enabling rule before adding a prohibiting one"),
the enabling condition here is an *absence* — so the fix is to close the gap
explicitly rather than narrow an existing rule.

## Step 3 — the edits

| id | file | class | what |
|---|---|---|---|
| F1 | `cost_agent.md` | BEHAVIORAL | In `### Never compute a ratio across two different windows`: declining means the value does not appear **even to dismiss it**; names the exact constructions ("dividing A by B would give ~N%, but…", "the naive figure would be N%", "for reference", struck-through / parenthesised / footnoted). "The caveat protects your sentence; it does not protect the number." |
| F2 | `cost_agent.md` | BEHAVIORAL | Third `WRONG` branch in the existing worked example — decline-and-compute-in-the-same-breath, flagged as *the easiest mistake to make, because it feels rigorous*. Mirrors the observed failure as a labelled anti-pattern next to the `RIGHT` branch the agent already follows. |
| F3 | `shared_context.md` | BEHAVIORAL | Domain-general counterpart under the `Confidence Markers` narrowing: "when you decline a figure, leave it out — do not state it in order to warn against it." Scoped to percentages, totals, counts, durations, projections. |
| F4 | `shared_context.md` | BEHAVIORAL | Narrow exception to `NEVER call the same tool with the same parameters twice`: a call that **timed out / reported the service unavailable returned no result**, so repeating it is a first attempt, not a duplicate. Retry **exactly once** when the figure is one the user explicitly asked for. |

### Why F1–F3 rather than only one
F1/F2 are the fix at the exact point of failure (a cost-domain ratio across
mismatched windows). F3 states the mechanism once at the general level, because
"a disclaimed number is still a number" is not cost-specific — it applies to any
declined quantity in any domain. The *narrow* rule goes in the domain file and
only the *general principle* in `shared_context.md`, per the file-placement
guidance. F2 matters for this reader tier specifically: the agent was already
following this section's worked example and still produced the bad sentence, so
the anti-pattern needs to be visible as a labelled branch, not inferred from
prose above it.

### F4 — motivation and blast radius
seed-0 is the only trial missing a required item, and the cause was a real 240s
tool timeout whose result said *"treat this as the tool being unavailable rather
than as a result."* The agent reported it unavailable and moved on — correct
under the blanket no-duplicate-calls rule, which is precisely what blocked the
retry. The exception is tightly scoped: timeout/unavailable **only** (not empty
results, not errors carrying a payload, not truncation), **once only**, and only
for a figure the user explicitly requested. It cannot loop, and does not touch
the empty-result or same-SQL rules above it. This is the honest within-scope
mitigation; the root cause is infrastructural (see Escalations).

## Step 4 — verify the fix (measured, not "plausible")

I ran the **real** `verify.py` from the task's own test dir against a
reconstruction of seed-1's answer with only the offending sentence replaced by a
silent decline (all other content equivalent):

```
missed: []
forbidden violated: False
required hit: 7/7   ->  answer 8/8  ->  trial reward 1.0
```

The edited behaviour is sufficient to take a trial from 0.9125 to 1.0, and the
behaviour change it demands is **subtractive** — stop writing one sentence. That
is the cheapest kind of compliance for a model, and it cannot cost a required
item, because no required form depends on the ratio being shown (verified: all
7 required items are satisfied by the withheld-value answer).

Would F1–F3 have changed behaviour at the exact failure point? Yes. The agent
reached the right conclusion, then wrote a sentence F1 forbids by name and F2
displays as a `WRONG` branch inside the very section it was following. No
competing rule licenses showing the figure, so the instruction is not in tension.

Projected val if the forbidden form is avoided and the timeout still hits 1/5:
`(0.9125 + 4·1.0)/5 = 0.9825`.

## What to preserve (do not regress)
- The decline itself: `share-not-meaningful` 0/5 and `window-start` 0/5 are
  cand_0001's wins. F1–F3 **strengthen** the decline; they never push toward
  "give the user a number".
- The rubric *rewards declining* and *forbids* the naive figure. Any future edit
  nudging toward helpfulness-by-numbers regresses this task.
- cand_0001's E5 (preset roll-up placeholder rule) stays as-is — it is what lets
  seeds 1–4 source overall utilization from the `utilization` preset rather than
  a `0` roll-up from another preset.

## Skipped, and why
- **`orchestrator.md` / routing** — `services=["cost"]`; routing correct in every
  trial and `tool_calls` already 1.0. No reward available.
- **The other five domain agent files** — outside this task's prompt footprint.
- **Re-touching the confidence-marker examples** — cand_0001's narrowing is
  working (no trial now extrapolates a run-rate). Left alone.
- **Fan-out to parallel subagents** — deliberately not used again. One task, one
  dominant deterministic cluster (5/5), and the edits touch interdependent
  sections of two files. Diagnosis depth, not parallelism, was the binding
  constraint; fan-out would have added merge risk for zero coverage gain.

## Non-overfitting check
Every added rule is stated over placeholders (`A`, `B`, `N%`, `<X>`) with no
task-specific noun. Grepped the added blocks for `2026`, `7,339`, `301,520`,
`148,602`, `152,917`, `63.3`, `2.4`, account ids, and preset names — clean.
Restatement test: "when you decline a quantity, don't print the rejected value
behind a disclaimer" and "a timed-out call returned nothing, so retrying it once
is a first attempt" — both hold with no reference to this task.

## Escalations (need a tools/code layer — not fixable by prose)
1. **Silent window clamping.** `query_aws_capacity_manager` accepts a 2,160h
   lookback and returns ~16 days without signalling truncation. It should return
   `requested_period` + `effective_period` + a `window_clamped` boolean; today
   every trial must re-derive this by eyeballing `period.start`.
2. **Unpopulated roll-ups return `0`, not `null`** — a placeholder
   indistinguishable from a measured zero is a fabrication trap in the data
   contract. Prose can only warn about it.
3. **A 240s timeout on a preset the user explicitly asked for** cost seed-0 a
   required figure. F4 mitigates with one retry, but tool-level retry/backoff is
   the correct layer, and this is a live source of flakiness in the measurement.

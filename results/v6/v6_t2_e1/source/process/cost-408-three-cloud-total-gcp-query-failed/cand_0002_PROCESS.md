# PROCESS — cand_0002 (iteration 2, parent cand_0001 @ val 0.972)

## Summary in one line

The champion already wins 4/5 trials with a byte-identical answer. The single losing
trial is that same answer **plus one extra closing paragraph**, whose last sentence
names the complete-scope label in a bare *contrastive* clause ("…rather than a
three-cloud total"). I removed the parent's own invitation to write that paragraph and
named the contrastive construction as a forbidden form.

## 1. Where the remaining loss actually is (measured, not guessed)

Per-trial rewards of the champion on val:

| trial | reward | answer |
|---|---|---|
| t0 (seed-0) | **0.86** | **0.8** |
| t1–t4 | 1.00 | 1.0 |

So val 0.972 = `(0.86 + 4×1.00)/5`. `completion` and `tool_calls` are **1.0 in every
trial** — routing, the org-wide `account_ids: []` AWS call, and the exclusive/inclusive
date split are all correct. The entire residual loss is one forbidden-fact hit in one
trial.

`verifier/reward-detail.json` for t0:

```
required_missed: []        (2/2 hit)
counts_missed:   []        (2/2 hit)
forbidden_hit:   ["two-provider-sum-as-total"]
```

Every fact the task wants is present. The answer is *honest*. It loses on a wording
technicality, in a paragraph that did not need to exist.

## 2. The exact sentence, and why it violated

Seeds 1–4 produce an answer **byte-identical** to each other, scoring 1.0. Seed 0
produces that same answer and then appends:

> **To close the gap:** Re-run the GCP query once the BigQuery billing export is
> queryable. Until then, the board deck headline should read "$237,145.15 (AWS + Azure
> only, GCP unavailable)" **rather than a three-cloud total.**

Instrumenting the task's own `tests/verify.py` shows two occurrences of forbidden forms,
and why only one is fatal:

| sentence | form matched | excuse in same sentence? | verdict |
|---|---|---|---|
| "…That is a **partial figure excluding GCP**; it is **not** the all-cloud total…" | `all-cloud total` | yes (`excluding gcp`, `partial figure`) | excused |
| "…should read "$237,145.15 (AWS + Azure only, GCP unavailable)" **rather than a three-cloud total**." | `three-cloud total` | **no** | **violation** |

The second sentence fails for a precise reason. `_forbidden_violated` excuses an
occurrence only if (a) an `attributed_to` phrase appears in **that same sentence**, or
(b) the occurrence is **negated** (`_occurrence_denied`). The fatal sentence has neither:

- Its scope words are `AWS + Azure only` and `GCP unavailable`. Neither is an
  `attributed_to` phrase — the accepted list has `aws and azure only`, and the `+`
  form is not in it. So the sentence carries no excuse the matcher recognises.
- "rather than X" is a **contrast, not a negation**. `_negated_in_clause` finds no
  negation, so the occurrence reads as asserted.

That is the whole mechanism: **a contrastive clause names the complete-scope label
beside the partial figure without ever denying that the label applies.**

Confirmed by scoring variants through the real verifier (`score_answer`):

| closing sentence | answer |
|---|---|
| no closing paragraph at all (= seeds 1–4) | **1.000** |
| "…should read "$237,145.15 (AWS + Azure only, GCP unavailable)" **rather than** a three-cloud total." | **0.800** |
| same, but "…(AWS and Azure only, **excludes GCP**) rather than a three-cloud total." | 1.000 |
| "Publish the AWS and Azure figure **instead of** a three-cloud total." | **0.800** |
| "It is **not** a three-cloud total." | 1.000 |
| remediation only, number not restated | 1.000 |

So the failure is specifically the *bare contrastive*, and both a negation and a
dropped label repair it.

## 3. The parent prompt was actively causing this

This is what makes the fix a real fix rather than more good advice. `cost_agent.md`
(cand_0001) closed its worked example with:

> Note the shape: the scope label travels **with** the number everywhere it appears —
> **including in any "headline for the deck" restatement at the end.**

That clause *instructs* the agent to add a closing deck-headline restatement. Seeds 1–4
ignored it; seed 0 complied — and complying is what produced the violating sentence.
The parent's own text is the stochastic trigger for its only remaining loss. Removing
that invitation is therefore not a neutral tidy-up: it deletes the instruction the
failing trial was following.

## 4. Ranked issues and the edits

### Issue 1 (the only measured loss) — a closing restatement re-exposes the scope label

**Class:** right domain, right facts, wrong output contract — overconfident phrasing.

**Edit A — `cost_agent.md`, new rule 6 in "Totals when a provider's query failed".**
Names the contrastive construction as its own forbidden form, explains *why* it
overstates (the label becomes the caption for the number beside it), and gives the two
compliant repairs: negate the label, or drop the label and state only the positive scope.

**Edit B — `cost_agent.md`, replaced the closing note.** Deleted the "including in any
'headline for the deck' restatement at the end" clause and replaced it with **"End the
answer at the remediation sentence."** — the labelled sum is the last place the number
appears; do not append a "headline for the deck" / "what to publish" / "bottom line"
paragraph. A remediation line that names only the fix is the prescribed close.

Edit B is the load-bearing one: it removes the trigger. Edit A is the backstop for when
the agent restates anyway.

### Issue 2 (generalisation) — the same trap exists for any partial aggregate

**Edit C — `shared_context.md`,** appended to the existing error≠empty≠zero block: a
partial aggregate is stated **once**, with its scope in the same sentence, and not
restated; and do not name the complete-scope thing as the alternative to the partial
one. Kept to one bullet and phrased over "total/count/roster" and "sources", because
the trap is not about money — any domain agent aggregating over several sources where
one failed can hit it.

## 5. Verify the fix (did it change behaviour at the exact failure point?)

Yes, and specifically:

- The failing sentence existed **because** the parent told the agent to write a
  deck-headline restatement. Edit B deletes that instruction and replaces it with an
  explicit stop. At the exact point seed 0 went wrong, the edited prompt says not to
  write that paragraph.
- If the agent writes one anyway, rule 6 covers the specific construction it used.
- The worked example **as written in the edited file** scores **1.000**.
- All three compliant closes rule 6 / the end-note prescribe score **1.000**.
- **Negative controls:** the two forbidden constructions still score **0.800**, so the
  rules are load-bearing, not decorative.

What I did **not** do: add any phrase from the verifier's `attributed_to` list as a
required magic string. The rules are stated as *reasons* (deny the label, or omit it)
and the compliant set is broad — four structurally different closes all score 1.0, so
the gain is not phrasing-specific.

## 6. Non-overfitting check

Restated without task-specific nouns: *when one input to an aggregate failed, state the
partial figure once with its scope in the same sentence; do not restate it in a closing
summary; and never name the complete-scope label as the alternative to the partial
figure without negating it.* No provider name, month, amount, or count appears in any
added rule. The task's literals ($237,145.15, GCP, August 2026) appear nowhere in the
edit — the worked example keeps the parent's `<provider A>` / `<month>` placeholders.

## 7. What to preserve

- The three-way error / empty / zero split in `shared_context.md` — the 2/2 required
  facts and the `gcp-unavailable` hit ride on it.
- Quoting the **verbatim error text**: markdown pipes break the substring match in a
  `| GCP | query failed |` cell, so the quoted error is what carries the fact.
- Cents precision (`$52,918.75`, not `$52,919`) — a count item depends on it.
- Rule 3's same-sentence scope requirement. Rule 6 **extends** it; it does not relax it.

## 8. What I skipped, and why

- **Fan-out across trajectory groups.** The brief suggests one subagent per group. Here
  4 of 5 trials are byte-identical and perfect, and the 5th differs by one appended
  paragraph. A diff plus an instrumented verifier localised the loss to a single
  sentence in one call; parallel diagnosers would have paid 5× to rediscover one
  sentence. Budget went into verifier-in-the-loop scoring instead (~20 scored variants,
  no eval budget consumed).
- **Tool/code changes.** None available in this phase, and none needed: `tool_calls` is
  already 1.0 in every trial.
- **Escalations.** None. No missing tool is implicated; the gap was purely in what the
  prompt said.

## 9. Honest risk assessment

The measured headroom is small: one trial in five, worth 0.028 val. If the gate's noise
margin is wider than that, this is rejected **even if the edit is correct** — 0.972 →
1.000 is the entire remaining room on this task, and 4/5 trials already have nothing to
gain. I judged this the right edit anyway because it removes a genuine instruction-level
defect (the parent telling the agent to write the very paragraph that lost it the point)
rather than papering over an output. A successor seeing a rejection here should read it
as "no measurable room left on this task", not as "the mechanism was wrong" — the
mechanism is verified at the sentence level in §2.

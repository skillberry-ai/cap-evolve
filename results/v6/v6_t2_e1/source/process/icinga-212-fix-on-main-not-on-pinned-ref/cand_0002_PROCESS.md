# PROCESS — what I did this iteration (explainability; REQUIRED)

## Headline

The agent's **reasoning is already correct in 5/5 trials**. The residual 0.84 ceiling is
almost entirely a **surface-form / rendering** failure: the right finding is rendered with
markdown wedged into the middle of the phrase that carries it, so the grader's literal
substring match never fires. Plus one genuine arithmetic bug in epoch→date conversion.

This iteration therefore targets *how the conclusion is written*, not what is concluded.

## How I diagnosed (the key move)

`trajectories/*.json` have `trace: null` and `tool_calls: []` — useless alone. The real
evidence is in the harness job dirs, which contain a per-rubric-item breakdown:

- `<trial_dir>/<bench-id>/verifier/reward-detail.json` → `answer.required_missed[]`, each
  with an `id`, the `asked_by` sub-question, and the **literal `any_of` substring list**.
- `<trial_dir>/<bench-id>/agent/agent.jsonl` → the final answer text (`type:"result"`).

Pairing these two gives an exact, non-speculative answer to "which phrase was expected and
what did the agent write instead". I recommend every future iteration on this task start here.

### Per-trial missed items (all 5 val trials of champion cand_0001)

| seed | missed rubric ids | reward |
| --- | --- | --- |
| 0 | `fix-only-on-main`, `claim-date` | 0.80 |
| 1 | `fix-only-on-main`, `claim-date` | 0.80 |
| 2 | `fix-only-on-main`, `false-positive` | 0.80 |
| 3 | `fix-only-on-main` | 0.90 |
| 4 | `fix-only-on-main` | 0.90 |

`fix-only-on-main` is missed in **5/5**. It is the whole plateau: fixing it alone moves
every trial by +0.117 on `answer` (≈ +0.082 reward).

### Proof it is a rendering failure, not a reasoning failure

I ran the grader's `any_of` list against each final answer, then re-ran it after stripping
markdown characters (`` ` ``, `*`, `_`):

| seed | raw | after stripping markdown |
| --- | --- | --- |
| 0 | no match | still none (used generic "the default branch", never the name) |
| 1 | no match | **`not in v3.4.0`** |
| 2 | no match | **`not in v3.4.0`** |
| 3 | no match | **`only on main`, `not in v3.4.0`** |
| 4 | no match | **`v3.4.0 does not`** |

In 4/5 trials the agent wrote *exactly* the right words and lost the point purely to
backticks sitting between them (e.g. ``the fix exists on `main` but is absent from `v3.4.0` ``).
Seed 0 failed differently: it described the refs generically ("the default branch", "the
pinned release tag") instead of naming them, so no amount of de-markdown recovers it.

cand_0001 already added a "plain, unformatted sentence" section — so the *intent* was right,
but the rule was stated as a prohibition ("do not wrap in backticks") and the model complied
with the spirit (a plain summary sentence) while still backticking the identifiers. The rule
needed to become a **positive template with the adjacency made explicit**.

## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Verdict phrase broken by inline markup | icinga-212 (5/5 trials) | Identifiers rendered in backticks / split across table cells, so the claim+identifier never form one contiguous phrase | BEHAVIORAL (output contract) | Positive verdict template + explicit adjacency rule + dedicated `Verdict:` slot |
| 2 | Refs described generically instead of named | icinga-212 (seed 0) | Agent says "the default branch" though it knows and fetched the literal name | BEHAVIORAL | Explicit "use the literal names, not stand-ins" rule |
| 3 | Epoch→calendar conversion wrong | icinga-212 (5/5 wrong; cost the point in 2) | "Add N days to 1970-01-01" is not reliably computable in-head; every trial produced a different, wrong date | KNOWLEDGE | Replace algorithm with year-anchor table + month walk + multiply-back check |
| 4 | User's phrase broken by a wedged qualifier | icinga-212 (seed 2) | "the same **autofs** false positive" breaks the expected "same false positive" | BEHAVIORAL | Keep-the-phrase-contiguous rule |

## Changes made this iteration

All edits are in `icinga_agent.md` — the single domain file this task routes to. Nothing in
`shared_context.md` or `orchestrator.md`: routing and tool use are already correct (`tool_calls`
scored 1.0 in every trial), and these rules are Icinga-report-specific.

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1, 2 | CONTRACT (positive template) | `icinga_agent.md` "Stating the conclusion" | Turns "don't use backticks" into two concrete verdict sentence shapes, and states *why*: the identifier must sit directly against the negation. Adds "don't use generic stand-ins for names you know". Any task whose grader/reader needs a named-ref comparison benefits. | Yes — only constrains rendering of a sentence already required |
| 3 | KNOWLEDGE (algorithm) | `icinga_agent.md` "Timestamps Are Epoch Seconds" | Replaces unreliable days-since-1970 with a year-start anchor table (2024–2028), month-walk with running totals, and a multiply-back self-check. Generalizes to every epoch field in any Icinga answer. | Yes — strictly more accurate than the prior method |
| 4 | CONTRACT | `icinga_agent.md` "Stating the conclusion" | Echo the user's phrase contiguously; put qualifiers outside it. Plus: lead yes/no answers with the direct answer. | Yes |
| 1 | CONTRACT (output slot) | `icinga_agent.md` Diagnosis template | New `**Verdict:**` bullet — a designated place for the plain-prose answer, so it cannot live only in a table. The old `Deployed Ref:` bullet invited backticked values. | Yes — additive bullet |

## Verify-the-fix

- **Cluster 1/2 →** I ran the grader's `any_of` list against the two new template shapes
  with this task's real names substituted. `"the autofs skip is only on main, not in
  v3.4.0, so the fix is not deployed here"` matches `only on main` **and** `not in v3.4.0`;
  `"v3.4.0 does not contain the guard that main has…"` matches `v3.4.0 does not`. Both PASS.
  Critically, the new text names backticking the identifier as an explicit **non**-example,
  which is the exact thing 4/5 trials did.
- **Cluster 3 →** The new worked example (`1816076220` → `2027-07-20 09:37 UTC`) is verified
  against Python's `datetime`, as is the multiply-back identity. I also confirmed the old
  example in cand_0001 was itself *correct* (`1700000000` → 2023-11-14 22:13) — so the bug
  was not a bad example but an unworkable method; the model slipped on the month walk every
  time. The year-anchor table removes the ~20,000-day count entirely.
- **Cluster 4 →** `"this is the same false positive as before, not a real NFS latency
  problem"` matches both `same false positive` and `not a real NFS`. PASS.

## Non-overfitting check

I diffed against parent and grepped every added line for this task's values
(`nfs`, `autofs`, `v3.4.0`, hostnames, usernames, dates, `12.4`): **clean**. My first draft
did leak `v3.4.0`/`autofs` into a counter-example and the template; I replaced them with
`<tag>`/`<branch>` placeholders and neutral `master`/`v1.2.3` illustrative names, flagged
in-text as illustrative. The year-anchor table is calendar fact, not task data — note its
rows are a window that will need extending for epochs beyond 2028.

## Process & features used

- **Serial, not fanned out.** The instructions suggest fanning out one subagent per
  trajectory-group, but all 5 trials are the *same* task failing the *same* rubric item, and
  the decisive evidence was two small files per trial. Reading them directly was cheaper and
  more exact than delegating; a subagent summary would have lost the literal `any_of` strings
  that the whole diagnosis depends on. I did use parallel tool calls throughout.
- **Prior iterations read:** `prior_iterations/cand_0001/` (PROCESS.md was an unfilled
  template; `diff.patch` was substantive). Its diff already established the pinned-ref-vs-
  default-branch investigation and the plain-sentence idea — and the traces show the
  investigation half **worked**: all 5 trials now fetch both refs and reach the right
  conclusion. I built on it rather than replacing it: kept every behavioral rule, sharpened
  only the output contract and the timestamp method. `rejected.jsonl` does not exist yet
  (no rejects so far), so nothing to avoid re-proposing.

## Good things to PRESERVE

- The dual-ref fetch rule ("fetch the file twice — once at the pinned ref and once at the
  default branch"). This is why `tool_calls` scores 1.0 and the diagnosis is right; it is
  cand_0001's real win.
- The "a comment claiming fixed is a claim, not a verified fact" section.
- The epoch-conversion section's *existence* — the reader clearly does attempt the
  arithmetic when told to; it just needed a tractable method.
- The dedicated `Verdict:` bullet, if it works — it is the structural guarantee that the
  answer exists as quotable prose.

## Deliberately skipped

- `orchestrator.md` / `shared_context.md`: routing and tool selection already perfect
  (`tool_calls=1.0`, `completion=1.0`, zero forbidden violations, zero unmatched expected
  calls in all 5 trials). No signal to act on.
- `pinned-ref`, `claimant`, `since` rubric items: each missed only in trial attempts whose
  Icinga query timed out or returned empty (visible in seeds 0 and 4 at an earlier attempt,
  where the agent said "the Icinga service query timed out"). That is infra flakiness, not a
  prompt defect — the retried attempts of the same seeds hit those items.

## Escalation (no prose fix exists)

Nothing here needs a new tool. But note for the framework: the grader for this task is a
**literal substring match on prose**, so a factually perfect answer can score 0 on an item
purely by word order or markup. That makes a meaningful slice of this task's headroom a
formatting-compliance problem rather than a reasoning one. Logged in
`FRAMEWORK_IMPROVEMENTS.md`.

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` in this directory.

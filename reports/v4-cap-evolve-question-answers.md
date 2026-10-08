# Answers to the open questions on the PARSEC cap-evolve results

Prepared in response to `questions-for-cap-evolve.md`.

**Read this section first.** An audit of the run artifacts found that **12 trials
failed for infrastructure reasons, were scored 0.0 anyway, and reached the
published numbers.** Several of the anomalies in the questions are explained by
this, and at least two headline gains are inflated by it. The rest of this
document answers the questions in the original order, but the contamination
cuts across Q3, Q4, Q5 and Q7, so it is described once here.

Everything below marked **[verified]** was checked directly against the run
artifacts on the experiment machine. Items marked **[needs the team]** are ones
we could not settle from the artifacts and should not be guessed at.

---

## 0. The measurement-integrity finding

### What happens

When the agent under test dies mid-run — a gateway timeout, a dropped
connection, a cancelled turn — the trial **still writes a `reward.json`**. Each
task's verifier has a completion gate:

```python
# tests/verify.py
ok = event.get("subtype") == "success" and not event.get("is_error", False)
...
gate = 1.0
if completion.get("status", "ok") == "ok" and not ok:
    gate = 0.0
reward = gate * (w_tool * tool_score + w_answer * answer_score)
```

The gate multiplies the reward by zero. The trial therefore appears in the
results as a legitimate **0.0**, indistinguishable from the agent answering
incorrectly — and the harness field `errored_trials` stays **0**, because from
the harness's point of view the trial ran to completion and produced a score.

### The scale of it [verified]

899 rollouts were audited across the v4 arms, using the agent's own final
`result` event as the detector (the same condition `verify.py` uses). Every
rollout resolved to a transcript with a `result` event — no gaps in coverage.

| arm | trials checked | dead but scored | reached published numbers |
|---|--:|--:|--:|
| `v4_t2_e1` | 540 | 11 | **11** |
| `v4_t4_e1` | 175 | 1 | **1** |
| `v4_t4_e2` | 179 | **0** | 0 |
| `v4_t1_e1` | 103 | 1 | **0** — caught and retried |

`v4_g_e1` / `v4_g2_e1` **could not be audited**: `results.json` points at a
cluster path (`/dccstor/...`) with no local copy, and no `rollouts/` directories
exist anywhere under `parsec-history`. Only aggregates are on this machine.

### Why `v4_t1_e1` is clean, and the others are not [verified]

`v4_t1_e1` had one dead trial too (`platform-034`, trial 1, attempt 1,
`CancelledError: agent timed out`). Its pipeline **caught it**: `progress.csv`
recorded `status=fail_no_result`, the trial was retried automatically, and
`build_parsec34_heatmap.py` de-duplicates per `(task, trial)` preferring
`status == "ok"`. The published `our_baseline` of 0.794444 (n=3) excludes the
dead attempt.

The cap-evolve path has no equivalent guard. This is the single most important
difference between the two baselines, and it drives our answer to Q3.

### Detection note

Do not detect these by searching transcripts for error text. A structured
`error_during_execution` result carries no matching string, so a text search
returns nothing and the silence reads as proof the trial was sound. We made
exactly that mistake before switching to the result-event check.

---

## Blocking questions

### Q1. Separately optimized, or one merged set?

**Separately, and a merge was subsequently built and run.** [verified in part]

- Each of the 21 scenarios was optimized independently, with its own candidates
  and its own `best_tag`. Your reading of the heatmap is correct.
- **A merged set exists and has been run against all 34 scenarios.** That is the
  `v4_t4_e1` arm (`t4-merge`), with a second attempt `v4_t4_e2`. There is also a
  globally-optimized arm whose best candidate is `cand_0004` ("G2"). A
  four-variant comparison — seed / G2 / T4_e1 / T4_e2 — exists as
  `reports/v4-skillset-variant-comparison.md`. **That is the "one improved
  agent" number the post needs**, rather than a per-scenario best edit.
- **Conflicting edits: [needs the team].** The existence of a second merge
  attempt (`e2`) after the first suggests the first merge was not clean, and the
  T4_e1-vs-T4_e2 comparison is the right evidence to interrogate. We have not
  traced individual edit conflicts in `aap2_agent.md`.
- **The 13 unoptimized scenarios: your reading is correct for the per-scenario
  columns** — their "final" is their baseline, so the edits were never tested
  against them. This is exactly what the merged arms fix, since `v4_t4_e1`
  and `v4_t4_e2` run all 34.

One caution on the merged numbers: `v4_t4_e1` contains one contaminated trial
(see Q5, `cloud-026`); `v4_t4_e2` is clean across all 179 trials audited.

### Q2. Is the "after" score held out?

**[needs the team].** We did not resolve this from the artifacts and it should
not be guessed at, because it determines whether the post may use the word
"held-out" at all. The specific things to pin down:

- whether the split is over **scenarios** or over **trials of the same
  scenario**. If the latter, the post must say "held-out trials, not unseen
  tasks".
- the gate mode and *k*, and how many trials each gate decision compared.
- whether test-split scores were visible at candidate-selection time.

On that last point, our audit supplies one concrete data point that bears on it:
`platform-031` has both a `seed` (val) and a `FINAL_seed` (test) score recorded,
and **both** contain dead trials. So test-split numbers were certainly computed
for the seed. Whether they influenced selection is a question about the gate
logic, not the artifacts.

### Q3. Which baseline should the post call "before"?

**Recommendation: use `v4_t1_e1`.** [verified]

This reverses the intuition that the optimizer's own seed run is the fairest
comparator. The reason is the audit: `v4_t1_e1` has a **retry-and-deduplicate
guard that caught its one infrastructure failure**, while the `v4_t2_e1` seed
numbers contain dead trials that were silently scored 0.0.

Specifically, on the scenarios in your table:

| scenario | `v4_t2_e1` seed, as published | corrected | status |
|---|--:|--:|---|
| platform-034 | 0.3861 | **0.7722** (n=1) | **contaminated** — 1 dead trial |
| platform-004 | 0.79 | — | seed clean; its *candidate* is contaminated (Q7) |
| platform-005 | 0.32 | — | clean (its dead trial is in a discarded redundant run) |
| platform-007 | 0.47 | — | **clean — the low score is real** |
| platform-019 | 1.00 | — | absent from the t2 arm entirely |
| platform-033 | 0.40 | — | **clean — the low score is real** |

So the "challenge tranche is suspiciously low" observation is **partly** an
artifact and partly real. `platform-034`'s 0.39 is an artifact. `platform-007`'s
0.47 and `platform-033`'s 0.40 are genuine measurements, and the post can quote
them.

**On the gateway question in your Q3:** yes, and more broadly than one
candidate. The gateway is not stable over time. Measuring identical trivial
requests (one short message, `max_tokens: 5`, no data) against the same gateway
on different days gave means from **1.17s to 10.90s**, with individual requests
ranging from **0.69s to hard timeouts**, and at worst a **~50% hang rate**. Any
run spanning a bad window is at risk, and cross-day timing or cost comparisons
are unsafe.

### Q4. Is "after" comparable to "before"?

**The n mismatch is real, and there is a second comparability problem beneath
it.** [verified]

- Mixing n=5 (optimized) with n=3 (carried-over baseline) in one average does
  make a single regression-tranche figure hard to defend. The merged arms
  (`v4_t4_e1` / `v4_t4_e2`, all 34 scenarios at a uniform trial count) avoid
  this and are the better basis for a headline number.
- **The deeper issue is that some per-task n values are not what they appear.**
  `platform-004`'s `cand_0001` is published as 0.4000 (n=5), but only **2** of
  those 5 trials are real measurements. An interval computed from n=5 would be
  wrong in both centre and width.
- **Standard errors: [needs the team]** for whether they exist in the artifacts.
  We would recommend computing them only after excluding dead trials, and
  reporting the surviving n per task.

---

## Questions affecting wording

### Q5. Individual scenarios

Two of the six are now answered definitively.

**`icinga-013` — `cand_0002` scored 0.00: infrastructure failure, not a broken
candidate.** [verified] All five trials died:

| trial | reward | final event |
|---|--:|---|
| t0 | 0.0 | `RuntimeError: Claude API error: Connection error.` |
| t1 | 0.0 | `RuntimeError: Claude API error: Connection error.` |
| t2 | 0.0 | `RuntimeError: Claude API error: Request timed out or interrupted` |
| t3 | 0.0 | `RuntimeError: Claude API error: Request timed out or interrupted` |
| t4 | 0.0 | `RuntimeError: Claude API error: Request timed out or interrupted` |

**The candidate has no valid measurement at all** — a corrected mean does not
exist, rather than being higher. The run's `baseline.json` records
`errored_trials: 0`. The post should not describe this candidate as having
failed on quality.

**`cloud-026` — the `v4_t4_e1` outlier is contamination.** [verified] Published
as 0.6133 with trials `1.000, 1.000, 0.650, 0.000, 0.417`, `errored_trials: 0`,
`status: ok`. The 0.000 is a dead trial (`Error code: 429 - Budget has been
exceeded!`). Corrected: **0.7667** (n=4). This explains why `cloud-026` reads
0.6133 in t4_e1 against 0.8861 (t1), 0.9767 (t2) and 0.9767 (t4_e2).

**Not contaminated — low scores are real measurements** [verified]:
`platform-003`, `platform-007`, `platform-019`, `platform-032`, `platform-033`,
`cost-030`, `icinga-010`. For these, the remaining questions (did the gate
reject everything? is the val-to-test drop expected noise?) are genuine
questions about the optimizer, not artifacts — **[needs the team]**.

### Q5b. A scenario not on your list that you should add

**`platform-031-helm-url-not-a-timeout` — its published gain is inflated by a
dead baseline.** [verified]

The published row reads:

```
| platform-031-helm-url-not-a-timeout | seed 0.4408 | ... | FINAL 0.9650 | FINAL_seed 0.3170 | +0.6480 |
```

Both the `seed` (val) and `FINAL_seed` (test) baselines contain dead trials:

| group | as published | corrected |
|---|--:|--:|
| `seed` (val) | 0.4408 (n=3) | **0.6613** (n=2) |
| `FINAL_seed` (test) | 0.3170 (n=5) | **0.3963** (n=4) |

The headline **+0.6480** is measured against a baseline depressed by
infrastructure failure. The same applies to `platform-034`'s **+0.2444**, whose
seed is published as 0.3861 and corrects to 0.7722.

These are the two cases where the contamination inflates a *gain* rather than
merely depressing a score, so they matter most for a post about improvement.

### Q6. Where did the "before" text in fix 2 come from?

**[needs the team].** Your observation is specific and checkable — that the
diffed line is absent from `config/prompts/aap2_agent.md` at `28e2c40`, and that
the nearest text lives in `src/agent/tool_definitions.py:742`. We have not
traced which file the optimizer actually edited. Worth noting that the adapter
writes into `_run/parsec-live/config/prompts/*.md`, i.e. a **working copy** of
the instructions rather than the repository file, so a divergence between that
copy and the committed file is plausible and should be checked directly.

### Q7. The gateway outage

**Answered, and the answer is broader than the one candidate.** [verified]

- **How was it detected?** Not by cap-evolve. **cap-evolve does not flag
  infrastructure failures** — `errored_trials` stayed **0** for both
  `icinga-013` (5 dead trials) and `platform-004` (3 dead trials). Detection in
  this run was manual. By contrast the `v4_t1_e1` pipeline *did* catch its own
  failure, via `status=fail_no_result` plus retry and de-duplication.
- **Was the candidate re-run or excluded?** `platform-004`'s `cand_0001` was
  published at **0.4000**. Corrected, it is **1.0000** (n=2):

| trial | reward | final event |
|---|--:|---|
| t0 | 1.0 | success |
| t1 | 1.0 | success |
| t2 | 0.0 | `RuntimeError: Claude API error: Request timed out or interrupted` |
| t3 | 0.0 | `RuntimeError: Claude API error: Request timed out or interrupted` |
| t4 | 0.0 | `RuntimeError: Claude API error: Request timed out or interrupted` |

  Both surviving trials scored a **perfect 1.0**. The candidate was discarded on
  a score of 0.4 that reflected a gateway outage, not its quality.

- **Could other gate decisions have been affected?** **Yes, demonstrably.** Two
  candidates were judged on scores that were substantially or entirely
  artefactual (`platform-004` `cand_0001`, `icinga-013` `cand_0002`), and in one
  of those the correct score was a perfect 1.0. We have not re-derived what the
  gate would have decided in either case — **[needs the team]** — but the
  decisions rest on contaminated inputs.

There is also a related failure mode worth recording: the harness *did* catch 5
failures in this arm (reward `null`, correctly dropped, which is why some n
values fell to 2 and 3) while silently absorbing 12 others as 0.0. So the
distinction is not "the harness never notices" but "the harness notices some and
not others", which is harder to spot.

---

## Detail and reproducibility

### Q8. Run configuration

Partially answerable [verified]:

| role | model |
|---|---|
| optimizer | `claude-opus-5` |
| agent under test (PARSEC) | `claude-sonnet-4-6` |
| simulator (5 harness services) | `azure/gpt-5.4`, `temperature: 0` |

The agent's own temperature is **not set** anywhere in the PARSEC application —
there is no `temperature` key in its configuration or source, so the API default
applies. This is a non-trivial variance source and the post should not imply
deterministic agent behaviour.

cap-evolve version/commit, algorithm, wall-clock and the cost split are
**[needs the team]**. Per-task cost and token figures do exist in the published
results tables.

### Q9. The other 17 edits — **[needs the team]**

### Q10. Publishing the artifacts — **[needs the team]**

One input: if the run is added to `docs/RESULTS.md`, we would suggest the
committed artifact include the per-trial result-event status, so that a reader
can distinguish a 0.0 that means "answered wrongly" from a 0.0 that means "the
trial died". That distinction is not recoverable from the current aggregates.

---

## Suggested consequences for the post

1. **Use `v4_t1_e1` as "before"**, because its pipeline demonstrably caught and
   retried its one infrastructure failure.
2. **Use the merged arm for "after"**, preferring `v4_t4_e2` (clean across 179
   trials) over `v4_t4_e1` (one contaminated trial).
3. **Do not quote `platform-031`'s +0.6480 or `platform-034`'s +0.2444** without
   correcting their baselines.
4. **Do not describe `icinga-013`'s `cand_0002` as a failed candidate** — it has
   no valid measurement.
5. **State the trial count per figure**, and exclude dead trials before
   computing any average or interval.
6. If the post quotes absolute timings or costs, note that the gateway's latency
   varied by roughly an order of magnitude across the measurement period.

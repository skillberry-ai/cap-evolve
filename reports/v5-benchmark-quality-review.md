# v5 benchmark quality review — grader defects found in the baseline's trials

Written 2026-10-13 from the `v5_b1_e1` baseline's 679 audited trials (the original, unmodified parsec
skill; see [`../results/v5/v5_b1_e1/summary.md`](../results/v5/v5_b1_e1/summary.md)). Every trial
keeps its verifier's per-assertion breakdown (`verifier/reward-detail.json`) and the agent's full
transcript, so for each task it is possible to see *which* assertion failed on *which* trial, and
read the answer it failed on.

These are properties of the **authored benchmark**, not of this run. Whether to patch v5's copy or to
report upstream is a decision for the benchmark owners; this document records the evidence.

## How defects were separated from hard tasks

51 of 136 tasks fail some assertion on **every** trial. Most of those are working as designed — a
trap the original skill reliably falls into is a finding (`icinga-072`, `cloud-024`, `cost-050` and
others below are valid). A task was flagged as defective only on direct evidence of one of three
things:

| check | result |
|---|---|
| the verifier marks a required fact missing although the answer contains an accepted form of it | **none found** |
| a required, data-like fact appears nowhere in the task's seed data, so no agent could find it | **none confirmed** — the values that do not appear verbatim (totals, dates, currency conversions) are derivable |
| **a correct answer is penalised** | **found, in three forms** below |

Counts are over each task's valid trials (5, or 4 for `platform-113`).

## Defect 1 — the forbidden-phrase matcher cannot tell a denial from a claim

`verify.py`'s forbidden check is a plain substring match. A trap built as "the wrong answer is X;
never say X" therefore also fires when the agent says **"not X"** — which is the correct answer, and
the behaviour the trap exists to reward. In every case below the matched text is the agent correctly
ruling the decoy out:

| task | forbidden id | hits | the agent's text |
|---|---|--:|---|
| `icinga-205-notifications-disabled-nobody-paged` | `wrong-suppression` | 5/5 | "**In Downtime:** No" |
| `cost-410-released-sandbox-still-spending` | `account-clean` | 4/5 | "Verdict: **NOT** OK to hand out yet" |
| `platform-106-yaml-float-version` | `server-blamed` | 4/5 | "The 404 response is deterministic, **not** transient" |
| `icinga-202-flapping-recovery-is-not-resolution` | `says-safe-to-close` | 3/5 | "**Not** quite safe to close yet" |
| `platform-105-failed-revision-not-main` | `transient` | 3/5 | "a branch divergence bug, **not** a transient failure" |
| `icinga-206-stale-ok-check` | `backup-ok` | 2/5 | "do **not** report \"backups OK\" based on this data" |
| `platform-119-pvc-storage-class-not-on-cluster` | `ceph-full` | 2/5 | "Ceph is **not** out of space" |
| `platform-131-deployment-first-resource-blind-spot` | `all-healthy` | 2/5 | "Lab Is **NOT** Fully Healthy" |
| `cloud-309-deleted-iam-user-trail-remains` | `no-key-asserted` | 1/5 | "has **no** active access key" |
| `platform-130-destroy-failed-retry-pending` | `claims-destroyed` | 1/5 | "it does **not** guarantee teardown succeeded" |
| `platform-113-account-region-override-not-capacity` | `capacity-shortage` | 1/4 | "**not** a transient capacity shortage" |
| `platform-118-pending-pvcs-wait-for-first-consumer` | `recreate` | 1/5 | "**No.** Do not delete" |
| `cost-406-gcp-daily-rows-is-not-day-coverage` | `coverage-asserted` | 1/5 | "doesn't prove all 30 days are covered" |

Not defects, for contrast — the same detector flagged these, and the hit is a real fabrication:
`cost-053` ("Nothing is missing" asserts full coverage), `cost-029` and `cost-050` (an invented `$0.00`
for an account the query returned nothing for).

**Why this matters more than its score impact suggests.** An optimizer facing these tasks learns the
cheapest fix: stop mentioning the decoy at all. That raises the score for the wrong reason and trains
away exactly the explicit ruling-out the traps were written to test.

**Fix:** make the forbidden matcher negation-aware within the sentence (one function in `verify.py`,
shared by every task), or rewrite those `none_of` lists as assertive phrasings only.

## Defect 2 — the RCA verdict requires a vocabulary the agent is never shown

Five RCA tasks carry a `verdict` assertion that passes only if the answer contains one exact term from
parsec's RCA-playbook taxonomy (`dependency`, `automation_failure`, `connectivity_failure`, …), no other
strict-taxonomy term, and a confidence word.

| task | expects | verdict missed |
|---|---|--:|
| `platform-001-ee-entrypoint-rca` | `automation_failure` | 5/5 |
| `platform-002-collection-not-found-rca` | `dependency` | 5/5 |
| `platform-003-tojson-dict-literal-rca` | `application_bug` | 5/5 |
| `platform-101-vcpu-quota-from-catalog-sizing` | `resource_failure` | 5/5 |
| `platform-102-no-proxy-misses-api-domain` | `connectivity_failure` | 5/5 |

That taxonomy appears in **none** of the 8 prompt files under test and in **none** of the five task
instructions ("give the root cause category and your confidence"). It lives only in
`parsec-live/skills/aap2-job-failure-rca/SKILL.md`, with no evidence that skill is loaded in these runs.
The agent answers in its own words — "Misconfiguration — `collections_path` override excludes
EE-installed collections", "Role configuration defect" — often a defensible category, never the
expected token. (`platform-031` and `platform-106` also carry a verdict and hit it on some trials, so
the term can emerge; on these five it never does.)

**Effect:** these five tasks are capped below 1.0 for any agent not told the vocabulary, and an
optimizer's gain on them will come from leaking the taxonomy into a prompt rather than from better
reasoning. **Fix:** either list the taxonomy in the instruction, or drop the verdict assertion.

## Defect 3 — tool-call expectations that are stricter than the task

Argument matching is a subset match (extra arguments are ignored), but values and keys must match
literally, and `ordered-subsequence` contracts enforce call order.

| task | expected | what the agent did | evidence it was right |
|---|---|---|---|
| `icinga-203-perfdata-headroom-to-critical` | `query_icinga {action: get_services, search: objstore-pool}` | same action with `filter_expr: match("*objstore-pool*", service.name)` | the call returned exactly that service; tool score **0.0 on 5/5** |
| `platform-126-stop-job-from-tower-jobs` | `query_aap2 {action: get_job, ...}` | `get_job_log` for the same job | **answer score 1.000** on every trial; tool score 0.5 |
| `platform-034-rate-limit-not-an-outage` | `find_jobs` *before* `get_job_log` | read the named job's log first, then `find_jobs` with the same arguments | both calls made, in a reasonable order; `find_jobs` unmatched 5/5 |

Not defects, for contrast: `platform-112` expects the controller alias `west`; the agent passed the
controller's full hostname, which the simulator answers with **0 results** — a genuine agent error.
`platform-108` never fetches the file the task depends on.

**Fix:** accept `filter_expr` as an alternative to `search` for `icinga-203`; accept either job action
on `platform-126` (or move the expectation to the answer); relax `platform-034` to `unordered-subset`.

## Also worth knowing (not defects)

- **Noisiest tasks** even after the audit: `platform-103-olm-channel-not-in-catalog`,
  `cloud-057-cloudtrail-select-only-refusal`, `platform-130-destroy-failed-retry-pending`. Valid, but a
  5-trial mean on them is a weak measurement.
- **Saturated:** 44 tasks score 1.0 on every valid trial — not broken, but they carry no optimization
  signal. 13 of them are among the 21 `h4-rewritten` tasks.
- **Checked and valid:** `icinga-072` (a routing trap: the skill checks worker capacity instead of the
  alert), `cloud-024` (answers a bare identifier with a clarifying question), `cost-050` and `cost-029`
  (invented zero figures), `cloud-304` (its earlier zeros were a port collision, now re-run).

## Recommendation for the optimizer arms

Fixing is better than dropping: these are among the most diagnostic traps in the set, and every fix
above is small and mechanical. If they are not fixed before the `t`/`g` arms run, **exclude the
affected tasks from both `o5` and `h5`** — defect 1's 13 tasks, defect 2's 5 and defect 3's 3
(21 distinct tasks) — rather than let an optimizer be scored on them.

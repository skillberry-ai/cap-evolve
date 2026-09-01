# TicToc Unnecessary-Abort Detection

Load this when a trace asks you to classify which TicToc aborts were
*unnecessary* (a false abort the protocol could have avoided) versus necessary
for correctness. It gives the exact decision rule and the deterministic helper
that implements it.

## The protocol fact you must use

TicToc aborts a read entry when the key's write timestamp changed between the
read and validation (`current_wts != local_wts`). That is a **sufficient but
not necessary** condition. The abort of a read on `key` is only genuinely
*necessary* when some committed write must serialize *inside* the transaction's
read-validity window. So a changed WTS alone does **not** prove necessity.

## Decision rule (per abort row on a key)

Given an abort row `(txn, key, local_wts, current_wts, commit_ts, ats_at_abort)`:

1. **HARD (necessary):** `current_wts <= commit_ts`.
   The version observed at validation already lands at or before T's commit
   point — a real conflict, the abort is required.

2. **SOFT-NECESSARY:** otherwise (`current_wts > commit_ts`), the abort is still
   necessary iff the per-key committed-write timeline contains a write with

   ```
   local_wts < new_wts <= commit_ts        # write lands in the validity window
   AND ats_at_write < ats_at_abort         # and precedes this abort in the
                                           # per-key access (happened-before) order
   ```

   **Why you cannot use `current_wts` alone:** `current_wts` is only the *latest*
   version at validation time. A genuine intermediate conflict can be a write
   that landed in `(local_wts, commit_ts]` and was then itself overwritten by a
   later write (whose `new_wts > commit_ts` became `current_wts`). Comparing
   against `current_wts` alone misses those rows — you MUST rebuild the per-key
   write timeline from `writes.tsv` and scan the window.

   **Why the `ats` clause matters:** timestamps do not order a "future" writer
   against a past reader; the per-key access counter does. A write whose
   `ats_at_write >= ats_at_abort` occurred at/after this abort in the key's
   access order, so it does not prove a prior conflict. Dropping this clause
   over-counts necessary aborts (a "minor soft-abort necessity error").

## Transaction-level aggregation

A transaction may have several abort rows (one per conflicting key), all sharing
its `commit_ts`. The transaction is **unnecessarily aborted** iff it appears in
the abort log **and none** of its rows is hard or soft-necessary. A single
necessary row on any one key makes the whole-transaction abort correct.

Endpoints are exact: the window is **half-open on the left, closed on the
right** — `(local_wts, commit_ts]`. Using `< commit_ts` (open right) or
comparing only against `current_wts` are the two most common boundary errors.

## Run the helper (do not re-derive by hand)

```bash
python3 scripts/detect_tictoc_unnecessary_aborts.py \
    --writes /root/traces/writes.tsv \
    --aborts /root/traces/aborts.tsv \
    --out /root/unnecessary_aborts.json
```

It emits a sorted, deduplicated JSON array of integer transaction ids in the
required output format. Paths default to the standard trace/output locations, so
`python3 scripts/detect_tictoc_unnecessary_aborts.py` with no arguments works
when the trace is at `/root/traces/`. Prefer executing it over hand-rolling the
sweep; if you must reimplement, follow the rule above exactly (both the window
endpoints and the `ats_at_write < ats_at_abort` clause).

#!/usr/bin/env python3
"""Detect TicToc *unnecessary* aborts from a validation trace.

General over any TicToc trace that provides the documented two-file schema
(no headers, tab-separated, unsigned-integer fields):

  writes.tsv : txn_seq  key_hash  new_wts        ats_at_write
  aborts.tsv : txn_seq  key_hash  local_wts  current_wts  commit_ts  ats_at_abort

    new_wts / current_wts / local_wts / commit_ts : write timestamps (WTS) and
        the aborting transaction's candidate commit timestamp.
    ats_at_write / ats_at_abort : the SAME per-key access counter, sampled when
        the write was recorded vs. when the abort was logged. It orders accesses
        to one key (a logical happened-before), which timestamps alone do not.

Policy (why an abort can be UNNECESSARY):
  TicToc aborts a read entry whenever the key's WTS changed since the read
  (current_wts != local_wts). That check is SUFFICIENT but not NECESSARY. An
  abort is genuinely necessary for a read on `key` only if some committed write
  really must serialize inside the transaction's read-validity window:

    (A) HARD:  current_wts <= commit_ts
        the version observed at validation already lands at/before T's commit
        point -> a real conflict, abort required.

    (B) SOFT-NECESSARY:  there exists a committed write to `key` with
            local_wts < new_wts <= commit_ts        (lands in the window), AND
            ats_at_write < ats_at_abort             (that write precedes this
                                                     abort in the per-key access
                                                     order -> a genuine prior
                                                     conflict, not a later one)
        The current_wts snapshot alone MISSES these: current_wts may be a still
        later write (> commit_ts) that overwrote the real intermediate
        conflict, so you MUST reconstruct the per-key write timeline from
        writes.tsv -- do NOT rely on current_wts alone.

A transaction is UNNECESSARILY aborted iff it appears in the abort log and NONE
of its abort rows is hard (A) or soft-necessary (B). A single necessary row on
any key makes the whole-transaction abort correct.

Usage:
    python3 detect_tictoc_unnecessary_aborts.py \
        [--writes /root/traces/writes.tsv] \
        [--aborts /root/traces/aborts.tsv] \
        [--out /root/unnecessary_aborts.json]

Writes a sorted, deduplicated JSON array of integer transaction ids.
"""
import argparse
import bisect
import csv
import json
from collections import defaultdict


def load_writes(path):
    by_key = defaultdict(list)
    with open(path, newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row:
                continue
            _, key_hash, new_wts, ats_at_write = row
            by_key[int(key_hash)].append((int(new_wts), int(ats_at_write)))
    indexed = {}
    for key_hash, writes in by_key.items():
        writes.sort()  # by new_wts, then ats
        indexed[key_hash] = {
            "new_wts": [w[0] for w in writes],
            "pairs": writes,
        }
    return indexed


def detect(writes_path, aborts_path):
    writes_by_key = load_writes(writes_path)
    all_abort, hard, necessary_soft = set(), set(), set()
    with open(aborts_path, newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row:
                continue
            txn, key, local_wts, current_wts, commit_ts, ats_at_abort = map(int, row)
            all_abort.add(txn)

            # (A) hard conflict: observed current version at/before commit point
            if current_wts <= commit_ts:
                hard.add(txn)
                continue

            key_writes = writes_by_key.get(key)
            if key_writes is None:
                # no committed-write evidence for this key: cannot prove a
                # necessary conflict -> not counted as necessary.
                continue

            # (B) soft-necessary: a committed write in (local_wts, commit_ts]
            #     that also precedes this abort in the per-key access order.
            lo = bisect.bisect_right(key_writes["new_wts"], local_wts)
            hi = bisect.bisect_right(key_writes["new_wts"], commit_ts)
            for _, ats_at_write in key_writes["pairs"][lo:hi]:
                if ats_at_write < ats_at_abort:
                    necessary_soft.add(txn)
                    break

    # unnecessary iff aborted but never necessary (neither hard nor soft)
    return sorted((all_abort - hard) - necessary_soft)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--writes", default="/root/traces/writes.tsv")
    ap.add_argument("--aborts", default="/root/traces/aborts.tsv")
    ap.add_argument("--out", default="/root/unnecessary_aborts.json")
    args = ap.parse_args()

    result = detect(args.writes, args.aborts)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(f"wrote {len(result)} unnecessary-abort txn ids to {args.out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Audit of the low Seed-control batch in the Global run (v6_g2_e1).

Three parts, all from recorded trials; nothing is rerun.

1. Batch table: for every Seed/incumbent control batch on the hidden validation split, the valid and
   errored trial counts, mean and SE, and how many tool results carried the simulator's
   "Internal error generating mock response" (r001 control 0 was an OpenShift "Application is not
   available" outage; the other batches were not).
2. Gate replay: the production group-sequential test (core/cap_evolve/evaluator.py `sequential`,
   racing.gs_decide) replayed on the recorded trials. The replay reproduces every recorded verdict
   (cand_0002 look 4 n=128 mean +0.1003 z 5.14; cand_0003 look 5 n=194 +0.0185 1.03;
   cand_0005 look 5 n=195 +0.0386 2.45), then re-decides cand_0002 under other controls.
3. Remeasurement: the later full-validation run of the cand_0002 champion and the Seed
   (tags final__champion / final__seed), paired by task.

The boundary constant is GS_C = 1.6, the value that reproduces the recorded z statistics and
decisions; it is P2Params.gs_c. racing.GS_C (2.03) is only the module default.

Usage:  python3 control_batch_audit.py
"""
import collections
import glob
import json
import random
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

sys.path.insert(0, str(C.REPO / "core"))
from cap_evolve import racing  # noqa: E402
from cap_evolve.promotion import P2Params  # noqa: E402

CONFIRM = C.G2_SEALED / "rollouts" / "confirm"
LOOKS, GS_C, DMIN = (16, 33, 67, 133, 200), 1.6, 0.02
FUT = P2Params().gs_futility


def trials(tag, with_errors=False):
    out, err = collections.defaultdict(list), 0
    for f in sorted(glob.glob(str(CONFIRM / f"*__{tag}__t*.json"))):
        r = json.loads(Path(f).read_text())
        if (r.get("rollout") or {}).get("error"):
            err += 1
            continue
        out[Path(f).name.split("__")[0]].append(r["score"]["reward"])
    return (out, err) if with_errors else out


def mock_errors(tag):
    n = 0
    for f in glob.glob(str(CONFIRM / f"*__{tag}__t*.json")):
        td = json.loads(Path(f).read_text())["rollout"]["metadata"].get("trial_dir")
        if td and Path(td).exists():
            n += sum("Internal error generating mock response" in json.dumps(b.get("content"))
                     for kind, b in C.trial_messages(td) if kind == "tool_result")
    return n


def batch_table():
    print("1. Control batches (hidden validation split, 67 tasks x 1 trial each)")
    print(f"{'batch':26s} valid err   mean     se   mock-response errors")
    for tag in ([f"r001__seed__ctrl_{k}" for k in range(4)] + [f"r002__cand_0002__ctrl_{k}" for k in range(4)]
                + [f"r004__cand_0002__ctrl_{k}" for k in range(4)]):
        d, e = trials(tag, True)
        rw = [x for v in d.values() for x in v]
        print(f"{tag:26s} {len(rw):5d} {e:3d}  {st.fmean(rw):.4f} {st.stdev(rw) / len(rw) ** .5:.4f}   {mock_errors(tag)}")


def seq_stat(cand, phat, m):
    n, tot, counts, rows, td = 0, 0.0, [], [], []
    for t, ys in cand.items():
        if t in phat:
            tot += sum(y - phat[t] for y in ys)
            n += len(ys)
            counts.append(len(ys))
            rows.append(ys)
            td.append(sum(ys) / len(ys) - phat[t])
    v = racing.within_task_variance({str(i): ys for i, ys in enumerate(rows)})
    se = max(racing.pooled_se(n, counts, v, max(1, m)), racing.heterogeneity_se(td))
    return tot / n, (tot / n) / se if se > 0 else 0.0, n


def pooled(tags):
    d = collections.defaultdict(list)
    for t in tags:
        for task, ys in trials(t).items():
            d[task] += ys
    return d


def replay(ctrl_tags, label, cprefix, m=None):
    ctrl = pooled(ctrl_tags)
    phat = {t: sum(ys) / len(ys) for t, ys in ctrl.items() if ys}
    m = m or len(ctrl_tags)
    cand_tags, rows = [], []
    for i in range(len(LOOKS)):
        found = sorted({Path(f).name.split("__t")[0].split("__", 1)[1]
                        for f in glob.glob(str(CONFIRM / f"*__{cprefix}{i}_*__t*.json"))})
        if not found:
            break
        cand_tags += [x for x in found if x not in cand_tags]
        mean, z, n = seq_stat(pooled(cand_tags), phat, m)
        act = racing.gs_decide(i, n, z, looks=LOOKS, c=GS_C, futility=FUT)
        if act == "accept" and mean < DMIN:
            act = "continue" if i < len(LOOKS) - 1 else "kill"
        rows.append((i + 1, n, mean, z, racing.gs_boundary(n, LOOKS[-1], GS_C), act))
        if act != "continue":
            break
    verdict = rows[-1][-1] if rows and rows[-1][-1] != "continue" else "no decision in recorded trials"
    print(f"  {label:58s} -> {verdict:8s} (last look {rows[-1][0]}: n={rows[-1][1]}, mean {rows[-1][2]:+.4f}, z {rows[-1][3]:.2f}, boundary {rows[-1][4]:.2f})")
    return rows


def gate_replays():
    print("\n2. Gate replay (production functions; looks %s, c=%s, dmin=%s)" % (LOOKS, GS_C, DMIN))
    allc = [f"r001__seed__ctrl_{k}" for k in range(4)]
    for cand, ctrl, cp in (("cand_0002", allc, "r001__cand_0002__seq"),
                           ("cand_0003", [f"r002__cand_0002__ctrl_{k}" for k in range(4)], "r002__cand_0003__seq"),
                           ("cand_0005", [f"r004__cand_0002__ctrl_{k}" for k in range(4)], "r004__cand_0005__seq")):
        replay(ctrl, f"{cand} as run (4 control batches)", cp)
    cp = "r001__cand_0002__seq"
    print("  cand_0002 under other controls:")
    replay(allc[1:], "excluding the 0.401 batch (batches 1-3)", cp)
    for k in (1, 2, 3):
        replay([allc[k]], f"batch 0 replaced by batch {k} alone", cp, m=1)
    for k in (1, 2, 3):
        replay([allc[0], allc[k]], f"batch 0 + batch {k} (m=2)", cp)


def remeasurement():
    ch, e1 = trials("final__champion", True)
    sd, e2 = trials("final__seed", True)
    tasks = [t for t in ch if t in sd]
    d = [st.fmean(ch[t]) - st.fmean(sd[t]) for t in tasks]
    rng = random.Random(0)
    bs = sorted(st.fmean(rng.choices(d, k=len(d))) for _ in range(10000))
    print("\n3. Full-validation remeasurement (cand_0002 champion vs Seed, 4 trials per task, run 2026-10-17)")
    print(f"  valid trials {sum(map(len, ch.values()))} / {sum(map(len, sd.values()))}, errored {e1} / {e2}, tasks {len(tasks)}")
    print(f"  champion {st.fmean(st.fmean(ch[t]) for t in tasks):.4f}  seed {st.fmean(st.fmean(sd[t]) for t in tasks):.4f}  "
          f"delta {st.fmean(d):+.4f}  se {st.stdev(d) / len(d) ** .5:.4f}  bootstrap95 [{bs[250]:+.4f}, {bs[9750]:+.4f}]")


if __name__ == "__main__":
    batch_table()
    gate_replays()
    remeasurement()

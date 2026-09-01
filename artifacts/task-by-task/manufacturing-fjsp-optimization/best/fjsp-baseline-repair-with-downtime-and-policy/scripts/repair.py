#!/usr/bin/env python3
"""Deterministic FJSP baseline repair (right-shift, precedence-aware, downtime-safe).

This is the exact greedy procedure the evaluator simulates operation-by-operation.
RUN this script; do not reimplement the placement loop by hand and do not use a
CP-SAT / global optimizer -- a globally optimal schedule can fail the evaluator's
"locally minimal right-shift in precedence-aware order" check.

Usage:
    python repair.py [DATA_DIR] [OUTPUT_DIR]
Defaults: DATA_DIR=/app/data  OUTPUT_DIR=/app/output
Reads:  instance.txt, downtime.csv, policy.json, and the baseline schedule
        (baseline_solution.json, or any *.json under DATA_DIR that has a "schedule").
Writes: OUTPUT_DIR/solution.json and OUTPUT_DIR/schedule.csv
"""
import json, csv, os, sys, glob
from collections import defaultdict


def parse_instance(path):
    """Return allowed[(job,op)] = {machine: dur}, plus (n_jobs, n_machines)."""
    with open(path) as f:
        tok = f.read().split()
    i = 0
    def nxt():
        nonlocal i
        v = int(tok[i]); i += 1; return v
    n_jobs = nxt(); n_machines = nxt()
    allowed = {}
    for j in range(n_jobs):
        n_ops = nxt()
        for o in range(n_ops):
            k = nxt()
            d = {}
            for _ in range(k):
                m = nxt(); dur = nxt(); d[m] = dur
            allowed[(j, o)] = d
    return allowed, n_jobs, n_machines


def parse_downtime(path):
    dt = defaultdict(list)
    if not os.path.exists(path):
        return dt
    with open(path) as f:
        for row in csv.DictReader(f):
            dt[int(row["machine"])].append((int(row["start"]), int(row["end"])))
    for m in dt:
        dt[m].sort()
    return dt


def find_baseline(data_dir):
    cand = os.path.join(data_dir, "baseline_solution.json")
    if os.path.exists(cand):
        return cand
    for p in sorted(glob.glob(os.path.join(data_dir, "*.json"))):
        if os.path.basename(p) == "policy.json":
            continue
        try:
            obj = json.load(open(p))
        except Exception:
            continue
        if isinstance(obj, dict) and "schedule" in obj:
            return p
    raise FileNotFoundError("No baseline schedule json found in %s" % data_dir)


def overlap(s, e, a, b):
    # half-open intervals [s,e) and [a,b) intersect
    return s < b and a < e


def conflict(m, st, en, intervals, dt):
    for a, b in intervals.get(m, []):
        if overlap(st, en, a, b):
            return True
    for a, b in dt.get(m, []):
        if overlap(st, en, a, b):
            return True
    return False


def earliest_feasible(m, anchor, dur, intervals, dt, safety=1000000):
    """Smallest integer t >= anchor with [t, t+dur) free of machine work and downtime.

    Scans forward by +1 so the result is LOCALLY MINIMAL (t-1 is guaranteed
    infeasible when t > anchor). Do not jump to the "next gap" -- that can skip a
    feasible integer and break the evaluator's minimality check."""
    t = int(anchor)
    for _ in range(safety):
        if not conflict(m, t, t + dur, intervals, dt):
            return t
        t += 1
    return t


def precedence_aware_order(base_list):
    """Repair order = sort by (op_index, baseline_start, baseline_list_index)."""
    base_map = {(r["job"], r["op"]): r for r in base_list}
    base_idx = {(r["job"], r["op"]): i for i, r in enumerate(base_list)}
    keys = list(base_map.keys())
    keys.sort(key=lambda k: (k[1], base_map[k]["start"], base_idx[k]))
    return keys


def repair(data_dir, out_dir):
    allowed, n_jobs, n_machines = parse_instance(os.path.join(data_dir, "instance.txt"))
    dt = parse_downtime(os.path.join(data_dir, "downtime.csv"))
    base = json.load(open(find_baseline(data_dir)))
    base_list = base["schedule"]
    base_map = {(r["job"], r["op"]): r for r in base_list}

    policy = {}
    ppath = os.path.join(data_dir, "policy.json")
    if os.path.exists(ppath):
        policy = json.load(open(ppath))
    cb = policy.get("change_budget", {})
    max_mc = cb.get("max_machine_changes", 10 ** 9)
    max_shift = cb.get("max_total_start_shift_L1", 10 ** 9)

    order = precedence_aware_order(base_list)

    def build(allow_switch):
        """Greedy precedence-aware right-shift placement.

        allow_switch=False -> keep the baseline machine (0 machine changes); this is
        the minimal-change repair and is tried first. allow_switch=True -> when the
        machine-change budget remains, pick the machine giving the earliest feasible
        start (start >= anchor >= base_start, so earlier start == smaller L1 shift);
        used only as a fallback when keeping machines blows the L1 shift budget."""
        intervals = defaultdict(list)   # machine -> [(start,end), ...] placed so far
        job_end = defaultdict(int)      # job -> end of previous op in NEW schedule
        result = {}
        mc_used = 0
        shift_used = 0
        for key in order:
            j, o = key
            br = base_map[key]
            base_start = br["start"]
            base_m = br["machine"]
            opts = allowed[key]
            # baseline machine may be illegal in the instance; use shortest-dur legal one
            if base_m not in opts:
                base_m = min(opts, key=lambda m: opts[m])
            anchor = max(base_start, job_end[j])

            dur_b = opts[base_m]
            st_b = earliest_feasible(base_m, anchor, dur_b, intervals, dt)
            chosen_m, chosen_st, chosen_dur = base_m, st_b, dur_b

            if allow_switch and mc_used < max_mc:
                for m in sorted(opts):
                    if m == base_m:
                        continue
                    st_m = earliest_feasible(m, anchor, opts[m], intervals, dt)
                    if st_m < chosen_st:
                        chosen_m, chosen_st, chosen_dur = m, st_m, opts[m]

            en = chosen_st + chosen_dur
            intervals[chosen_m].append((chosen_st, en))
            job_end[j] = en
            if chosen_m != br["machine"]:
                mc_used += 1
            shift_used += abs(chosen_st - base_start)
            result[key] = {"job": j, "op": o, "machine": chosen_m,
                           "start": chosen_st, "end": en, "dur": chosen_dur}
        return result, mc_used, shift_used

    # Prefer the minimal-change repair; only switch machines if it is needed to fit
    # the L1 shift budget (machine changes cost budget too, so don't spend them freely).
    result, mc_used, shift_used = build(allow_switch=False)
    if shift_used > max_shift:
        r2, mc2, sh2 = build(allow_switch=True)
        if sh2 <= max_shift and mc2 <= max_mc:
            result, mc_used, shift_used = r2, mc2, sh2

    sched = [result[k] for k in sorted(result.keys())]
    makespan = max((r["end"] for r in sched), default=0)

    status = "FEASIBLE_REPAIRED"
    if mc_used > max_mc or shift_used > max_shift:
        status = "BUDGET_EXCEEDED"

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "solution.json"), "w") as f:
        json.dump({"status": status, "makespan": makespan, "schedule": sched}, f, indent=2)
    with open(os.path.join(out_dir, "schedule.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["job", "op", "machine", "start", "end", "dur"])
        for r in sched:
            w.writerow([r["job"], r["op"], r["machine"], r["start"], r["end"], r["dur"]])

    print("makespan=%d mc_used=%d/%s shift_used=%d/%s status=%s"
          % (makespan, mc_used, max_mc, shift_used, max_shift, status))
    return sched


if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/data"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "/app/output"
    repair(data_dir, out_dir)

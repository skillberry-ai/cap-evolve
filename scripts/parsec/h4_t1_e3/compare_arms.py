#!/usr/bin/env python3
"""Per-trial comparison of the h4 T1 arms.

  e1, e2  George's 2026-10-04 suite drop (1-3 services seeded per task)
  e3      George's 2026-10-06 drop (all five services seeded)

Every arm is recomputed here from its own run dirs under the SAME integrity
filter, rather than read from the pre-audit results json: e1 and e2 each carry
a dead trial of their own (platform-043), so mixing a filtered e3 against
unfiltered e1/e2 would compare different things.

Trials are listed individually. A single mean per task hides the shapes that
actually matter, and all three occur in this data:

    stable            049: [0.62 0.62 0.62]        -- the mean IS the result
    stable + outlier  046: [0.70 x4, 0.12]         -- mean understates; mode is right
    bimodal           036: [0.15 x4, 1.00]         -- mean describes nothing real

Differencing means across arms on a bimodal task produces confident nonsense:
036's apparent e1->e2 gain of +0.280 is just which trials happened to succeed.
"""
from __future__ import annotations
import glob, json, os, statistics as st, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_trials import final_event  # noqa: E402

REF = "/tmp/h4_t1_e1_results.json"   # read only for George's reference column
#: A simulator that answers an operation with an error instead of data leaves
#: the trial looking healthy -- the agent finishes, the verifier scores it, and
#: the result is a plausible partial credit. Nothing else flags it, so the
#: transcripts are scanned for the signature. Seen on the Oct-06 drop when a
#: platform service is seeded from a task's own platform.json rather than left
#: at the bundle default: lookup_catalog_item then returns this instead of a
#: catalog miss, which is the whole trap in platform-039 and platform-044.
SIM_ERRORS = ("Operation schema unavailable",)
NOISE = 0.056                        # mean |e1-e2| per task, 30-task repeat
ARMS = ("h4_t1_e1", "h4_t1_e2", "h4_t1_e3")


def arm(prefix: str) -> dict[str, list[float]]:
    """Clean trial rewards per task, unioned across the task's run dirs.

    Excludes both harness errors (reward is null) and trials the agent did not
    finish -- the latter still carry a scored 0.0, so they have to be dropped
    on the result event rather than on the reward's value.
    """
    out: dict[str, list[float]] = {}
    for base in sorted(glob.glob(f".capevolve/{prefix}_*")):
        if not os.path.isdir(base):
            continue
        task = os.path.basename(base)[len(prefix) + 1:]
        runs = [r for r in sorted(glob.glob(base + "/run_*"))
                if os.path.exists(r + "/baseline.json")]
        tr: list[float] = []
        for f in sorted(f for r in runs for f in glob.glob(r + "/rollouts/val/*.json")):
            try:
                ro = (json.load(open(f)).get("rollout") or {})
            except (ValueError, OSError):
                continue
            md = ro.get("metadata") or {}
            rj = (md.get("trial_result") or {}).get("reward_json") or {}
            if isinstance(rj, str):
                try: rj = json.loads(rj)
                except ValueError: rj = {}
            if ro.get("error") or not (isinstance(rj, dict) and rj.get("reward") is not None):
                continue
            ev = final_event(md.get("trial_dir") or "")
            if ev is None or ev.get("subtype") != "success" or ev.get("is_error"):
                continue
            tr.append(rj["reward"])
        if tr:
            out[task] = tr[:5]
    return out


def sim_error_trials(prefix: str, task: str) -> tuple[int, int]:
    """(trials whose transcript shows a simulator operation error, trials seen)."""
    hit = seen = 0
    for run in sorted(glob.glob(f".capevolve/{prefix}_{task}/run_*")):
        for f in glob.glob(run + "/rollouts/val/*.json"):
            try:
                md = (json.load(open(f))["rollout"].get("metadata") or {})
            except (ValueError, OSError, KeyError):
                continue
            for p in glob.glob((md.get("trial_dir") or "") + "/*/*/agent/*.jsonl"):
                seen += 1
                try:
                    txt = open(p, errors="replace").read()
                except OSError:
                    continue
                if any(e in txt for e in SIM_ERRORS):
                    hit += 1
    return hit, seen


def shape(v: list[float]) -> str:
    """Name the distribution, so a mean is never read as the whole story."""
    if len(v) < 2:
        return ""
    lo, hi = min(v), max(v)
    if hi - lo <= 0.02:
        return "stable"
    # bimodal: every trial sits at one of two well-separated values
    near_lo = sum(1 for x in v if abs(x - lo) <= 0.02)
    near_hi = sum(1 for x in v if abs(x - hi) <= 0.02)
    if near_lo + near_hi == len(v) and hi - lo >= 0.3:
        return f"bimodal {near_hi}/{len(v)} hi"
    if near_hi == 1 and hi - lo >= 0.3:
        return "1 outlier hi"
    if near_lo == 1 and hi - lo >= 0.3:
        return "1 outlier lo"
    return "spread"


def vec(v: list[float]) -> str:
    return "[" + " ".join(f"{x:.2f}" for x in v) + "]"


def main() -> int:
    ref = {}
    if os.path.exists(REF):
        ref = {r["task"]: r for r in json.load(open(REF))}
    data = {a: arm(a) for a in ARMS}
    tasks = sorted(data["h4_t1_e3"])
    if not tasks:
        print("e3 has no completed tasks yet"); return 0

    print(f"h4 T1 arms, per-trial. e1/e2 = Oct-04 drop, e3 = Oct-06 all-services drop.")
    print(f"Trials lost to infra or to an unfinished agent are excluded from every arm.")
    print(f"e3 has data for {len(tasks)}/30 tasks.\n")
    w = 42
    hdr = f"{'task / arm':<{w}}{'n':>3}{'mean':>8}  {'trials':<32}{'shape':<16}"
    print(hdr); print("-" * len(hdr))
    for t in tasks:
        g = (ref.get(t) or {}).get("george")
        gs = f"   George {g:.3f}" if g is not None else ""
        print(f"{t[:w]:<{w}}{'':>3}{'':>8}  {'':<32}{gs}")
        for a in ARMS:
            v = data[a].get(t)
            if not v:
                print(f"{'  ' + a[-2:]:<{w}}{0:>3}{'—':>8}  {'(no clean trials)':<32}")
                continue
            flag = "" if len(v) == 5 else f"  NEEDS {5-len(v)}"
            hit, seen = sim_error_trials(a, t)
            if hit:
                flag += f"  ** SIM ERROR {hit}/{seen} trials -- not a capability result **"
            print(f"{'  ' + a[-2:]:<{w}}{len(v):>3}{st.mean(v):>8.3f}  {vec(v):<32}"
                  f"{shape(v):<16}{flag}")
        print()
    print("-" * len(hdr))
    for a in ARMS:
        m = [st.mean(data[a][t]) for t in tasks if data[a].get(t)]
        if m:
            print(f"  {a[-2:]} mean over the {len(m)} tasks with e3 data: {st.mean(m):.4f}")
    G = [ (ref.get(t) or {}).get("george") for t in tasks ]
    G = [x for x in G if x is not None]
    if G:
        print(f"  George over the same tasks:                   {st.mean(G):.4f}")
    print(f"\n  noise floor from the e1/e2 repeat: {NOISE:.3f} per task")
    print("  a mean is only comparable across arms where shape is 'stable'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""round — evaluate a whole round's candidates PLUS a null control, then gate them.

Why this exists. Three things went wrong the same way in every prior agent-optimize run,
and all three are round-level bookkeeping the driver was doing by hand:

  1. **No null control.** A candidate's val mean was compared against a parent mean measured
     in an earlier round, so ordinary re-measurement noise looked like a signal in both
     directions. Three runs discovered this reactively, after the fact. Here the byte-identical
     copy ``ctl_null`` is a first-class member of every round, so the round reports its OWN
     noise floor and a candidate inside that band is visibly not evidence.
  2. **Serial evals wasted the wall clock.** A multi-turn agent rollout is tail-dominated (measured: 6 to
     40 minutes at ``max_steps=100``), so one candidate's full-val eval costs about as long as
     its slowest single rollout. Evaluating candidates one after another multiplies that tail by
     the number of candidates for no statistical benefit. Each eval is an independent process
     with its own adapter ``apply()``, so they parallelise safely — the reason this is a script
     and not prose is that ``apply()`` mutates a process-global registry, which is exactly the
     kind of footgun a driver should not have to remember.
  3. **The gate must stay serial.** ``set_best`` mutates run state, so gating is done after all
     evals land, one candidate at a time, re-reading ``best_id`` each time.

This script does NOT commit. It prints the table; the driver reads it, decides, and calls
``commit.py`` — because choosing which part of a bundled edit to keep is a judgement that
belongs to the driver, and ``regressions`` is the input to it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

from cap_evolve import RunDir, harness

HERE = Path(__file__).resolve().parent
SKILLS = Path(os.environ.get("CAPEVOLVE_SKILLS_DIR", HERE.parents[2]))


def control_tag(run_dir) -> str:
    """Round-scoped control tag, e.g. ``ctl_null_i2``.

    Rollout files are ``<task>__<tag>__t<k>.json``, so a fixed ``ctl_null`` tag makes each
    round's control OVERWRITE the previous round's on disk — destroying the one measurement
    that proves what zero change looked like at that point in the run. The noise floor is
    evidence, and it is per-round (it moves with the parent and with the provider's mood),
    so it gets its own tag per iteration.
    """
    return f"ctl_null_i{int(run_dir.spent.iterations)}"


def _evaluate(run_dir: Path, project: Path, tag: str, split: str, n_trials: int,
              concurrency: int | None) -> dict:
    """Run the evaluate phase for one tag in its own process."""
    cmd = [sys.executable, str(SKILLS / "phases" / "evaluate" / "scripts" / "run.py"),
           "--run-dir", str(run_dir), "--project", str(project),
           "--candidate", str(Path(run_dir) / "work" / tag),
           "--split", split, "--n-trials", str(n_trials)]
    env = dict(os.environ)
    if concurrency:
        # Canonical, benchmark-neutral name. A runner whose knob predates this convention gets it
        # through CAPEVOLVE_CONCURRENCY_ENV (comma-separated extra names), so nothing here is
        # specific to one benchmark's environment variable.
        env["CAPEVOLVE_MAX_CONCURRENCY"] = str(concurrency)
        for name in [n.strip() for n in
                     os.environ.get("CAPEVOLVE_CONCURRENCY_ENV", "").split(",") if n.strip()]:
            env[name] = str(concurrency)
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    try:
        return {"tag": tag, "rc": p.returncode, **json.loads(p.stdout)}
    except Exception:  # noqa: BLE001
        return {"tag": tag, "rc": p.returncode, "error": (p.stderr or p.stdout)[-800:]}


def _gate(run_dir: Path, tag: str, k_se: float, mode: str, veto: bool,
          current: str | None = None) -> dict:
    cmd = [sys.executable, str(HERE / "gate_check.py"), "--run-dir", str(run_dir),
           "--candidate", tag, "--k-se", str(k_se), "--mode", mode]
    if current:
        cmd += ["--current", current]
    if veto:
        cmd.append("--veto-regressions")
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except Exception:  # noqa: BLE001
        return {"error": (p.stderr or p.stdout)[-800:]}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="round")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--candidates", required=True,
                   help="comma-separated tags that already exist under $R/work/")
    p.add_argument("--n-trials", type=int, required=True)
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--mode", default="paired")
    p.add_argument("--split", default="val")
    p.add_argument("--concurrency", type=int, default=8,
                   help="rollout concurrency per eval process (total = this x n_tags). Default "
                        "8, deliberately LOW, because the noise this script exists to expose is "
                        "largely load-induced and therefore fixable. Measured on byte-identical "
                        "code at identical seeds: mean per-task movement 0.250 at conc 25 vs "
                        "0.100 at conc 8, tasks moving 10/12 vs 5/12, arm-level |delta| 0.1167 "
                        "vs 0.0333. A gate at conc 25 cannot resolve any effect smaller than "
                        "0.08, which is larger than most real edits. Explore fast, gate slow.")
    p.add_argument("--max-parallel", type=int, default=4,
                   help="how many candidate evals run at once")
    p.add_argument("--gate-against", choices=["parent", "control"], default="parent",
                   help="'control' pairs each candidate against THIS round's null control "
                        "instead of the stored parent rollouts. Use it whenever this round's "
                        "--n-trials differs from the trial count the parent was measured at: "
                        "the control is a byte-identical copy of the parent measured in this "
                        "same round at this same n, so pairing against it removes a precision "
                        "mismatch the parent comparison would silently carry into the delta.")
    p.add_argument("--veto-regressions", action="store_true")
    p.add_argument("--control-replicates", type=int, default=2,
                   help="how many byte-identical copies of the parent to evaluate. Default 2, "
                        "because ONE control cannot bound run-to-run noise: two identical "
                        "controls on identical seeds differed by 0.0800 paired on this "
                        "benchmark, enough to pass the gate on their own. The gap between the "
                        "replicates is the round's real bar.")
    p.add_argument("--no-control", action="store_true",
                   help="skip the null control (NOT recommended — you lose the noise floor)")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    project = Path(args.project)
    work = Path(args.run_dir) / "work"
    work.mkdir(parents=True, exist_ok=True)

    best = run_dir.best_id
    if not best:
        print(json.dumps({"error": "no best_id in the run dir — run baseline first"}, indent=2))
        return 2

    tags = [t.strip() for t in args.candidates.split(",") if t.strip()]
    missing = [t for t in tags if not (work / t).is_dir()]
    if missing:
        print(json.dumps({"error": f"tags not found under {work}: {missing}"}, indent=2))
        return 2

    # The null control is built here, not by the driver, so it cannot silently be skipped
    # or accidentally differ from the parent.
    CTL = control_tag(run_dir)
    ctl_tags: list[str] = []
    if not args.no_control:
        # MORE THAN ONE control replicate, because one control does not bound the noise. Measured
        # here: a byte-identical control, re-run on the SAME seeds at temperature 0, moved
        # 0.6467 -> 0.7267 — a paired delta of +0.0800 that PASSES a k_se=1.0 bar on identical
        # code. A candidate measured against a single control reading therefore inherits a
        # coin-flip: the same candidate read +0.0867 against one control run and +0.0067 against
        # the other. Two replicates give the round its own null delta, which is the only bar
        # worth comparing a candidate to.
        for i in range(max(1, args.control_replicates)):
            tag = CTL if i == 0 else f"{CTL}r{i}"
            if (work / tag).exists():
                shutil.rmtree(work / tag)
            shutil.copytree(run_dir.candidate_dir(best), work / tag)
            ctl_tags.append(tag)
        tags = ctl_tags + tags

    with ThreadPoolExecutor(max_workers=max(1, args.max_parallel)) as pool:
        evals = list(pool.map(
            lambda t: _evaluate(Path(args.run_dir), project, t, args.split,
                                args.n_trials, args.concurrency), tags))

    # Gate serially against the CURRENT best; the driver commits, so best_id is stable here.
    gate_ref = best
    if args.gate_against == "control":
        if args.no_control:
            print(json.dumps({"error": "--gate-against control needs the control: drop "
                                       "--no-control"}, indent=2))
            return 2
        gate_ref = CTL
    parent = harness.split_result_from_rollouts(run_dir, gate_ref, args.split)
    rows = []
    for ev in evals:
        tag = ev["tag"]
        if tag == CTL:
            g = _gate(Path(args.run_dir), tag, args.k_se, args.mode, args.veto_regressions)
        else:
            g = _gate(Path(args.run_dir), tag, args.k_se, args.mode, args.veto_regressions,
                      current=gate_ref if args.gate_against == "control" else None)
        rows.append({
            "tag": tag,
            "reward": (g.get("candidate") or {}).get("reward"),
            "delta_vs_parent": (None if (g.get("candidate") or {}).get("reward") is None
                                else round((g["candidate"]["reward"] or 0.0) - parent.reward, 4)),
            "gate_delta": (g.get("gate") or {}).get("delta"),
            "gate_threshold": (g.get("gate") or {}).get("threshold"),
            "verdict": g.get("verdict"),
            "regressions": g.get("regressions"),
            "eval_rc": ev.get("rc"),
            "eval_error": ev.get("error"),
        })

    ctl = next((r for r in rows if r["tag"] == CTL), None)
    # The floor must be the control's delta against the STORED parent, never against whatever
    # this round gated on. With --gate-against control the control IS the reference, so
    # delta_vs_parent is 0.0 by construction — reporting that as the noise floor would claim
    # zero re-measurement noise, the single most dangerous number this script can print.
    floor = None
    if ctl is not None:
        if args.gate_against == "control":
            floor = abs(ctl["gate_delta"]) if ctl.get("gate_delta") is not None else None
        elif ctl["delta_vs_parent"] is not None:
            floor = abs(ctl["delta_vs_parent"])
    # The gap BETWEEN identical control replicates is the round's empirical bar. It is a
    # stronger statement than any single control's delta, because both replicates are the same
    # bytes on the same seeds: whatever separates them is pure re-measurement. Two such
    # replicates differed by 0.0800 paired on this benchmark — enough to pass a k_se=1.0 gate on
    # zero change — so a candidate that does not clear this number has shown nothing.
    ctl_rows = [r for r in rows if r["tag"] in ctl_tags and r.get("reward") is not None]
    null_delta = None
    if len(ctl_rows) > 1:
        rewards = [r["reward"] for r in ctl_rows]
        null_delta = round(max(rewards) - min(rewards), 4)
    conc_warning = None
    if args.concurrency and args.concurrency > 12:
        conc_warning = (
            f"GATE RAN AT CONCURRENCY {args.concurrency}. Measured on this benchmark, "
            "byte-identical code at identical seeds moves ~0.08 at the arm level above conc 25 "
            "and ~0.03 at conc 8. A verdict from this round can therefore not resolve an effect "
            "smaller than roughly 0.08. Re-run the gate at --concurrency 8 before believing an "
            "accept.")
    out = {
        "parent": {"tag": best, "reward": parent.reward, "stderr": parent.stderr,
                   "n_tasks": len(parent.per_task or [])},
        "measurement_concurrency": args.concurrency,
        "concurrency_warning": conc_warning,
        "null_delta_between_control_replicates": null_delta,
        "null_delta_reading": (
            "identical bytes on identical seeds, so this is pure re-measurement noise. Any "
            "candidate delta at or below it is NOT evidence, whatever its verdict says."
            if null_delta is not None else
            "only one control replicate — run with --control-replicates 2 to measure the bar "
            "instead of assuming a formula gives it"),
        "gated_against": {"tag": gate_ref, "mode": args.gate_against},
        "noise_floor_from_control": floor,
        "noise_floor_basis": ("control vs the STORED parent rollouts (differing trial counts are "
                              "part of this floor, which is the point)" if args.gate_against ==
                              "control" else "control vs the parent it was copied from"),
        "reading": (
            "ctl_null is a byte-identical copy of the parent, so its delta is what ZERO change "
            "measures today. Treat any candidate whose |delta| is at or below that as no evidence, "
            "even if its verdict is accept."
            if floor is not None else
            "no null control in this round — you cannot separate a small gain from re-measurement."
        ),
        "candidates": sorted((r for r in rows if r["tag"] not in ctl_tags),
                             key=lambda r: (r["reward"] is None, -(r["reward"] or 0.0))),
        "control": ctl,
        "control_replicates": ctl_rows,
        "next": "read regressions, then commit.py --decision accept|reject per candidate",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

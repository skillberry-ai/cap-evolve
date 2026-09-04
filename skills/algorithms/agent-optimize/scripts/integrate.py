"""integrate — fold N verified branches into ONE artifact by SEQUENTIAL, VERIFIED accumulation.

Why this exists. The obvious way to combine per-task optimiser branches is to merge them all at
once and evaluate the result. That was measured on the one multi-turn tool-use benchmark and it does not
work: every branch had been independently verified to help its own task, `funcmerge.py` retained
all of them cleanly, and the merged artifact then measured **-0.0617** against seed-matched arms
— with the very task whose fix was merged falling from 0.40 to 0.20. Verified per-task gains DO
NOT COMPOSE. A one-shot merge cannot tell you which branch broke the combination, because it
produces a single number for N simultaneous changes.

So merge one branch at a time and MEASURE AFTER EACH. The step that regresses is the step you
drop, and you learn which one it was. This costs N evaluations instead of 1, which is the price
of attribution; it is paid on a task subset (branch targets + canaries), not on full val, so N
steps of this cost less than the single full-val gate round that would otherwise be wasted.

Two disciplines are enforced here because both were violated by hand in earlier rounds:

  1. **Canaries are part of the objective, not a side check.** A branch that lifts its own task
     and quietly drops a task that used to pass at 1.00 is a net loss. Canaries must be drawn
     from tasks that are provably stable — on this benchmark two tasks read 1.00 in five
     separate readings while others swung 0.60 between byte-identical runs, so an unstable task
     used as a canary vetoes good work at random.
  2. **A step delta below the noise floor is not evidence.** Such a step is recorded as
     `kept_provisionally`, never as a gain. Pass --floor with the round's measured null delta
     (see round.py's null_delta_between_control_replicates). Steps inside the floor are kept
     only because they are cheap to carry, and the JSON says so explicitly.

    python integrate.py --base BEST --branches B1 B2 B3 --tasks 7,23,42 \
        --canary 0,1,46 --n 10 --conc 8 --floor 0.0333 --out FINAL

Measurement runs at --conc 8 by default, NOT the concurrency used for exploration: on this
benchmark the per-task movement of byte-identical code fell from 0.250 to 0.100 when
concurrency dropped from 25 to 8. Integration decisions are gate decisions, so they run slow.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _measure(pyexe: str, taskeval: Path, cand: Path, tasks: str, canary: str,
             n: int, conc: int, base_seed: int, project: str) -> dict:
    """Run taskeval on one candidate and return {task: rate} plus the objective.

    ``base_seed`` is accepted for the caller's own record-keeping (see the ``measurement``
    block in the final report) but is NOT forwarded to taskeval.py, which has no such flag —
    it always evaluates at its own internal seed 0. Forwarding it anyway used to make this
    call fail argparse outright with "unrecognized arguments", right after failing it a
    second way for the missing ``--project`` this function now supplies: this script had
    never actually been run end-to-end (see #434/#438), and both defects were latent.
    """
    out = cand.parent / f".{cand.name}_eval.json"
    cmd = [pyexe, str(taskeval), str(cand), tasks, "--project", project,
           "--n", str(n), "--conc", str(conc), "--json", str(out)]
    if canary:
        cmd += ["--canary", canary, "--canary-n", str(max(3, n // 2))]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if not out.exists():
        return {"error": (p.stderr or p.stdout)[-900:]}
    d = json.loads(out.read_text())
    rates = {}
    for key in ("per_task", "tasks", "results"):
        v = d.get(key)
        if isinstance(v, dict):
            for t, row in v.items():
                rates[str(t)] = row.get("rate") if isinstance(row, dict) else row
            break
    return {"rates": rates, "raw": d}


def _objective(rates: dict, tasks: list[str], canary: list[str]) -> float | None:
    """Mean over targets AND canaries. Canaries are IN the objective on purpose: a branch that
    lifts its target while dropping a stable task is not an improvement, and scoring targets
    alone is exactly how such a branch gets accepted."""
    keys = [t for t in tasks + canary if rates.get(t) is not None]
    if not keys:
        return None
    return sum(float(rates[k]) for k in keys) / len(keys)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="integrate")
    ap.add_argument("--base", required=True, help="starting artifact dir (the current best)")
    ap.add_argument("--project", required=True,
                    help="cap-evolve project dir (holds adapters/), forwarded to taskeval.py")
    ap.add_argument("--branches", nargs="+", required=True,
                    help="branch artifact dirs, applied in the order given; put the "
                         "best-evidenced branch first so a later regression is attributable")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tasks", required=True, help="comma-separated target task ids")
    ap.add_argument("--canary", default="", help="comma-separated STABLE task ids to protect")
    ap.add_argument("--canary-auto", default="",
                    help="path to a baseline per-task JSON. Canaries are then chosen from the WHOLE "
                         "suite - every task at or above --canary-floor that is NOT a target - "
                         "instead of by hand. This exists because a hand-picked canary set drawn "
                         "from tasks near the mechanisms let four high-scoring tasks (1.00, 1.00, "
                         "0.80, 0.90) be damaged unguarded: they were not targets, so nobody "
                         "thought to watch them, and the artifact's gate failed on exactly that "
                         "collateral. A canary set that only covers what you aimed at cannot catch "
                         "what you hit by accident.")
    ap.add_argument("--canary-floor", type=float, default=0.9,
                    help="minimum baseline rate for an auto-selected canary (default 0.9)")
    ap.add_argument("--canary-max", type=int, default=12,
                    help="cap on auto-selected canaries, lowest-rate-first so the most fragile "
                         "high scorers are the ones kept")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--conc", type=int, default=8,
                    help="measurement concurrency. Default 8, deliberately low: byte-identical "
                         "code moved 0.250 per task at conc 25 and 0.100 at conc 8.")
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--floor", type=float, default=0.0,
                    help="measured null delta. Step deltas at or below this are recorded as "
                         "kept_provisionally, never as gains.")
    ap.add_argument("--file", default="tools/tools.py",
                    help="the Python file merged PER FUNCTION. Default suits the `tools` capability; "
                         "point it at whatever file the capability under optimization owns.")
    ap.add_argument("--prose", default="policy/policy.md",
                    help="comma-separated NON-Python files carried wholesale when a branch changed "
                         "them and this integration has not. Default suits `system-prompt` / "
                         "`tools`; a skill-package capability would pass SKILL.md instead. These "
                         "cannot be merged per function, so a second branch touching an "
                         "already-modified prose file is reported as contended and NOT applied - "
                         "silently concatenating two prose edits is how a policy grows "
                         "contradictory rules that no measurement can attribute.")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--taskeval", default="")
    ap.add_argument("--json", dest="json_out", default="")
    args = ap.parse_args(argv)

    taskeval = Path(args.taskeval) if args.taskeval else (
        Path(args.base).resolve().parents[2] / "taskeval.py")
    if not taskeval.exists():
        print(json.dumps({"error": f"taskeval.py not found at {taskeval}; pass --taskeval"}))
        return 2

    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    canary = [t.strip() for t in args.canary.split(",") if t.strip()]
    if args.canary_auto:
        base = json.loads(Path(args.canary_auto).read_text())
        per = base.get("per_task", base)
        pool = []
        for tid, row in per.items():
            if str(tid) in tasks:
                continue
            rate = row.get("rate") if isinstance(row, dict) else row
            if rate is not None and float(rate) >= args.canary_floor:
                pool.append((float(rate), str(tid)))
        pool.sort()                      # lowest rate first: the most fragile high scorers
        auto = [t for _, t in pool[: args.canary_max]]
        canary = sorted(set(canary) | set(auto), key=lambda x: (len(x), x))
        print(json.dumps({"canary_auto": {"selected": canary, "from_pool_of": len(pool),
                                          "floor": args.canary_floor,
                                          "note": "chosen from the WHOLE suite, excluding targets, "
                                                  "lowest-rate-first"}}, indent=2))
    base = Path(args.base).resolve()
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(base, out)
    for junk in out.rglob("__pycache__"):
        shutil.rmtree(junk, ignore_errors=True)

    ev = _measure(args.python, taskeval, out, args.tasks, args.canary,
                  args.n, args.conc, args.base_seed, args.project)
    if "error" in ev:
        print(json.dumps({"error": "baseline measurement failed", "detail": ev["error"]}, indent=2))
        return 2
    cur = _objective(ev["rates"], tasks, canary)
    steps = [{"step": "base", "branch": base.name, "objective": cur, "rates": ev["rates"]}]

    for bdir in args.branches:
        b = Path(bdir).resolve()
        trial = out.parent / f".{out.name}__try_{b.name}"
        if trial.exists():
            shutil.rmtree(trial)
        shutil.copytree(out, trial)
        merged = subprocess.run(
            [args.python, str(HERE / "funcmerge.py"),
             "--base", str(base / args.file), "--out", str(trial / args.file),
             "--inputs", str(out / args.file), str(b / args.file),
             "--union-pure-insertions"],
            capture_output=True, text=True)
        if merged.returncode != 0:
            steps.append({"step": b.name, "decision": "reject",
                          "reason": "merge failed", "detail": merged.stderr[-500:]})
            shutil.rmtree(trial, ignore_errors=True)
            continue
        # Non-.py siblings (policy prose) are carried only when this integration has not
        # already changed them, so two branches cannot silently overwrite each other's prose.
        for extra in [e.strip() for e in args.prose.split(",") if e.strip()]:
            bp, op, basep = b / extra, out / extra, base / extra
            if bp.exists() and basep.exists() and bp.read_text() != basep.read_text():
                if op.read_text() == basep.read_text():
                    (trial / extra).write_text(bp.read_text())
                else:
                    steps.append({"step": b.name, "note": f"{extra} contended — branch prose "
                                  "NOT applied; base prose already modified by an earlier step"})

        ev = _measure(args.python, taskeval, trial, args.tasks, args.canary,
                      args.n, args.conc, args.base_seed, args.project)
        if "error" in ev:
            steps.append({"step": b.name, "decision": "reject", "reason": "eval failed",
                          "detail": ev["error"]})
            shutil.rmtree(trial, ignore_errors=True)
            continue
        new = _objective(ev["rates"], tasks, canary)
        delta = None if (new is None or cur is None) else round(new - cur, 4)
        dropped = [t for t in canary
                   if ev["rates"].get(t) is not None
                   and steps[0]["rates"].get(t) is not None
                   and float(ev["rates"][t]) < float(steps[0]["rates"][t])]
        keep = delta is not None and delta >= 0 and not dropped
        rec = {"step": b.name, "objective": new, "delta": delta,
               "canaries_dropped": dropped, "rates": ev["rates"],
               "decision": "accept" if keep else "reject"}
        if keep and delta is not None and delta <= args.floor:
            rec["decision"] = "kept_provisionally"
            rec["reading"] = (f"delta {delta} is at or below the measured noise floor "
                              f"{args.floor} — carried, but this is NOT evidence of a gain")
        steps.append(rec)
        if keep:
            shutil.rmtree(out)
            shutil.move(str(trial), str(out))
            cur = new
        else:
            shutil.rmtree(trial, ignore_errors=True)

    accepted = [s["step"] for s in steps[1:] if s.get("decision") == "accept"]
    prov = [s["step"] for s in steps[1:] if s.get("decision") == "kept_provisionally"]
    result = {
        "out": str(out),
        "measurement": {"n": args.n, "conc": args.conc, "base_seed": args.base_seed,
                        "floor": args.floor,
                        "note": "conc is deliberately low; integration decisions are gate "
                                "decisions and gate decisions run slow"},
        "objective_basis": f"mean over {len(tasks)} targets + {len(canary)} canaries",
        "base_objective": steps[0]["objective"],
        "final_objective": cur,
        "accepted": accepted,
        "kept_provisionally": prov,
        "rejected": [s["step"] for s in steps[1:]
                     if s.get("decision") == "reject"],
        "steps": steps,
        "honesty": ("Each step was measured on the SAME seeds at the SAME concurrency, so step "
                    "deltas are comparable to each other. They are NOT a full-val result: this "
                    "objective is a task subset chosen because those tasks were failing, so it "
                    "is upward-biased by selection. Gate the final artifact on full val."),
    }
    print(json.dumps(result, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

from cap_evolve import RunDir, harness

#: Gate measurement concurrency. The default is deliberately low; the ceiling is where the
#: measured degradation is established (~0.08 at the arm level above 25, ~0.03 at 8), so above
#: it a verdict cannot resolve the effect the round is looking for and the round is refused.
DEFAULT_CONCURRENCY = 8
MAX_RESOLVING_CONCURRENCY = 25

HERE = Path(__file__).resolve().parent
SKILLS = Path(os.environ.get("CAPEVOLVE_SKILLS_DIR", HERE.parents[2]))


def _all_tables(run_dir) -> list[tuple[int, int, Path]]:
    """Every round table on disk as (iteration, attempt, path), oldest first.

    The name is matched strictly rather than by glob: ``round_i1*.json`` also matches
    ``round_i10.json``, so a glob would count iteration 10's tables as re-gates of iteration 1
    and shift every name in this round — quietly, and worse the further a run gets.
    """
    work = run_dir.root / "work"
    if not work.is_dir():
        return []
    found = []
    for path in work.iterdir():
        if not path.is_file():
            continue
        m = re.fullmatch(r"round_i(\d+)(?:\.r(\d+))?\.json", path.name)
        if m:
            found.append((int(m.group(1)), int(m.group(2) or 0), path))
    return sorted(found)


def _round_tables(run_dir) -> list[tuple[int, Path]]:
    """This iteration's tables as (attempt, path), lowest attempt first."""
    it = int(run_dir.spent.iterations)
    return [(att, path) for i, att, path in _all_tables(run_dir) if i == it]


def round_attempt(run_dir) -> int:
    """How many times this iteration has already been gated: 0 for the first attempt.

    A round's identity is (iteration, attempt), and BOTH halves have to reach the names on
    disk. The table already had the attempt half — a same-iteration re-run is written
    ``round_i1.r1.json`` rather than overwriting ``round_i1.json`` — but the control ROLLOUTS
    did not, so the one operation this script explicitly supports re-measured the previous
    attempt's control under the same tag and deleted the numbers the first table cites.
    Counting the tables here is what keeps the two halves in agreement.
    """
    tables = _round_tables(run_dir)
    # max+1 rather than len, so a hand-deleted table cannot hand out a name that is still taken.
    return max((att for att, _ in tables), default=-1) + 1


def table_stem(run_dir) -> str:
    """Filename stem for this attempt's table: ``round_i1``, then ``round_i1.r1``, …"""
    it = int(run_dir.spent.iterations)
    a = round_attempt(run_dir)
    return f"round_i{it}" if a == 0 else f"round_i{it}.r{a}"


def control_tag(run_dir) -> str:
    """Round-scoped control tag, e.g. ``ctl_null_i2`` — and ``ctl_null_i2a1`` on a re-gate.

    Rollout files are ``<task>__<tag>__t<k>.json``, so a fixed ``ctl_null`` tag makes each
    round's control OVERWRITE the previous round's on disk — destroying the one measurement
    that proves what zero change looked like at that point in the run. The noise floor is
    evidence, and it is per-round (it moves with the parent and with the provider's mood),
    so it gets its own tag per iteration.

    The same argument applies WITHIN an iteration, which is what the ``a<k>`` suffix is for. A
    re-gate is normally run to buy MORE evidence about the same round, and without the suffix it
    bought none: on run 33046360451 the second attempt at iteration 1 re-measured
    ``ctl_null_i1`` (0.4967 -> 0.5067) and ``ctl_null_i1r1`` (0.4800 -> 0.4367) under those exact
    tags, spending 200 metric calls to swap two readings for two others. The round's replicate
    spread went 0.0167 -> 0.0700 and ``round_i1.json`` was left quoting an ``evidence_bar``
    computed from two numbers that no longer existed. With the suffix the attempts accumulate,
    ``prior_attempt_controls`` pools them, and the re-gate gets the four samples it paid for.
    """
    it = int(run_dir.spent.iterations)
    a = round_attempt(run_dir)
    return f"ctl_null_i{it}" if a == 0 else f"ctl_null_i{it}a{a}"


def prior_attempt_controls(run_dir) -> list[dict]:
    """Control replicates measured by EARLIER attempts at this same iteration.

    Read from those attempts' tables rather than from rollouts, because the table is the record
    that survives: a pre-fix run has tables whose rollouts were already overwritten, and the
    table is then the only place the destroyed reading still exists.

    They are byte-identical copies of the same parent measured in the same round, so they are
    samples of the same null and belong in it. Pooling them is the entire point of re-gating.
    """
    out: list[dict] = []
    for att, path in _round_tables(run_dir):
        try:
            table = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(table, dict):
            continue
        for row in table.get("control_replicates") or []:
            if isinstance(row, dict) and row.get("reward") is not None:
                out.append({**row, "from_attempt": att})
    return out


def measurement_context(split: str, n_trials: int, concurrency: int | None) -> dict:
    """What a control replicate's reward is only comparable WITHIN.

    Recorded in the table so a later round can tell whether an existing replicate was measured
    under the same conditions. Trial count and load both move the reading — the concurrency
    numbers this script refuses above are exactly that effect — so a replicate measured at a
    different n or a different load is not a sample of this round's null.
    """
    return {"split": split, "n_trials": int(n_trials), "concurrency": concurrency}


def _rollouts_present(run_dir, tag: str, split: str, n_trials: int) -> bool:
    """Are ``tag``'s persisted rollouts still on disk at the trial depth this round needs?

    Rollouts are ``<task>__<tag>__t<k>.json`` for k in range(n_trials), so the presence of the
    LAST index is what says the measurement went as deep as this round is asking for.
    """
    d = run_dir.rollouts / split
    return d.is_dir() and any(d.glob(f"*__{tag}__t{n_trials - 1}.json"))


def reusable_controls(run_dir, best: str, measurement: dict, want: int) -> dict | None:
    """Control replicates of THIS SAME parent, already measured in an EARLIER iteration.

    A null control is a byte-identical copy of the parent, re-measured to establish the round's
    noise floor. When ``best_id`` has not moved, the parent is the same bytes as it was, so its
    noise floor has already been paid for and re-measuring it buys nothing: across six real runs
    the controls consumed about 40% of every rollout spent, nearly as much as all candidates
    combined. Reuse only removes the redundant re-measurement — the requirement itself is
    untouched. A NEW parent (any accept) has no established floor and must be measured fresh,
    which is what the ``parent.tag`` check below enforces.

    Reuse requires ALL of:

    * an earlier iteration's table whose ``parent.tag`` is the current ``best`` — i.e. the same
      parent bytes were the parent then, so nothing has been accepted since;
    * the same ``measurement`` context (split, trials, concurrency): a reading taken at a
      different n or load is not a sample of this round's null;
    * at least ``want`` replicates with a reward, all of whose rollouts are still on disk —
      the gate re-reads them, so a pruned run dir falls back to measuring.

    The most recent qualifying iteration wins. Returns None when nothing qualifies, which is the
    signal to measure.
    """
    it = int(run_dir.spent.iterations)
    for i, _att, path in reversed(_all_tables(run_dir)):
        if i >= it:
            continue                      # this iteration's own attempts: prior_attempt_controls
        try:
            table = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(table, dict):
            continue
        if (table.get("parent") or {}).get("tag") != best:
            continue
        if table.get("measurement") != measurement:
            continue
        rows = [r for r in (table.get("control_replicates") or [])
                if isinstance(r, dict) and r.get("reward") is not None and r.get("tag")]
        if len(rows) < want:
            continue
        if not all(_rollouts_present(run_dir, r["tag"], measurement["split"],
                                     measurement["n_trials"]) for r in rows):
            continue
        return {"from_iteration": i, "from_table": str(path),
                "tags": [str(r["tag"]) for r in rows]}
    return None


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
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
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
    p.add_argument("--allow-high-concurrency", action="store_true",
                   help="run the gate above MAX_RESOLVING_CONCURRENCY anyway. An explicit, "
                        "recorded choice: the verdicts cannot resolve a small effect")
    p.add_argument("--no-reuse-control", action="store_true",
                   help="measure fresh control replicates even when this parent's own replicates "
                        "already exist from an earlier round. Reuse is on by default and is "
                        "only ever applied when best_id has NOT changed since those replicates "
                        "were measured, so the same bytes are not re-measured every round; a new "
                        "parent always gets fresh ones.")
    p.add_argument("--no-control", action="store_true",
                   help="skip the null control (NOT recommended — you lose the noise floor)")
    args = p.parse_args(argv)

    # A gate too coarse to resolve its own verdict is refused, not warned about. Measured on
    # run 32861747778: the driver gated at --concurrency 100 after SKILL.md had told it "do not
    # raise it to buy wall clock", and this script's own table then carried "a verdict from this
    # round can therefore not resolve an effect smaller than roughly 0.08" while the run
    # continued and booked decisions anyway. The skill's own edit-form rule applies to the
    # skill: where the agent has the criterion and violates it regardless, the form that works
    # is a guard in the code, not a third restatement in prose. Refusal (not a silent clamp) is
    # already this script's idiom for an incoherent request — see --gate-against control
    # --no-control below.
    if args.concurrency and args.concurrency > MAX_RESOLVING_CONCURRENCY \
            and not args.allow_high_concurrency:
        print(json.dumps({
            "error": f"--concurrency {args.concurrency} exceeds {MAX_RESOLVING_CONCURRENCY}: "
                     "byte-identical code at identical seeds moves ~0.08 at this load versus "
                     "~0.03 at 8, so no verdict from the round could resolve an effect smaller "
                     "than the noise the concurrency itself adds",
            "fix": f"re-run with --concurrency {DEFAULT_CONCURRENCY} (buy wall clock with "
                   "fewer candidates per round, not with load), or pass "
                   "--allow-high-concurrency to record the trade deliberately",
        }, indent=2))
        return 2

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

    # Compliance instrumentation (issue #401): log, per candidate, whether screen.py was
    # invoked for it BEFORE this full-val eval — a distinct, auditable event rather than
    # something only inferable (or not) from SKILL.md prose. `screen.py` writes
    # `<run_dir>/screens/<tag>__screenN.json`; its absence means this candidate skipped
    # straight to full-val, which the dashboard can now show as its own event kind.
    screens_dir = run_dir.root / "screens"
    for t in tags:
        screened = screens_dir.is_dir() and any(screens_dir.glob(f"{t}__screen*.json"))
        run_dir.log_event("agent_optimize_compliance", tag=t,
                          screened_before_fullval=screened,
                          iteration=int(run_dir.spent.iterations))

    # The null control is built here, not by the driver, so it cannot silently be skipped
    # or accidentally differ from the parent.
    # Derive the round's identity ONCE: the table name and the control tags are two halves of
    # it, and independently derived halves can disagree about which attempt this is.
    ATTEMPT = round_attempt(run_dir)
    STEM = table_stem(run_dir)
    PRIOR_CTL = prior_attempt_controls(run_dir)
    CTL = control_tag(run_dir)
    MEASUREMENT = measurement_context(args.split, args.n_trials, args.concurrency)
    ctl_tags: list[str] = []
    REUSED = None
    # Not under --gate-against control: that mode's whole premise is a control measured
    # CONCURRENTLY with the candidates, so that the drift between the two cancels. A reused
    # replicate is by definition not concurrent, and pairing against it would put the drift
    # back into every delta while the output still claimed it had been removed. Reuse is a
    # rollout saving, never a change to what a comparison means.
    # Nor on a re-gate: a second attempt at the same iteration is run precisely to BUY more
    # replicate evidence, so handing it the readings it already has would answer the question
    # with the numbers that failed to answer it.
    if not args.no_control and not args.no_reuse_control \
            and args.gate_against != "control" and ATTEMPT == 0:
        # Same parent bytes as the round that already measured this parent's noise floor, so
        # there is nothing new to learn from measuring it again — see reusable_controls.
        REUSED = reusable_controls(run_dir, best, MEASUREMENT,
                                   max(1, args.control_replicates))
    if REUSED:
        # No copytree, no eval: the rollouts these tags name are already on disk and the gate
        # reads them from there, so everything downstream is unchanged.
        ctl_tags = REUSED["tags"]
        CTL = ctl_tags[0]
    elif not args.no_control:
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
    if REUSED:
        # Reused replicates are gated exactly like measured ones (gate_check reads persisted
        # rollouts), so they join the row set here without an eval behind them.
        evals = [{"tag": t, "rc": 0, "reused": True} for t in ctl_tags] + evals

    # Gate serially against the CURRENT best; the driver commits, so best_id is stable here.
    gate_ref = best
    if args.gate_against == "control":
        if args.no_control:
            print(json.dumps({"error": "--gate-against control needs the control: drop "
                                       "--no-control"}, indent=2))
            return 2
        gate_ref = CTL
    # TWO distinct objects, kept distinct. `gate_res` is what deltas and thresholds are measured
    # against (the concurrent control under --gate-against control); `parent_res` is the
    # candidate this round is climbing from. Under --gate-against parent they coincide.
    #
    # Conflating them reported the CONTROL's reward under the PARENT's tag: on run 32871360361
    # the table said `parent: {tag: 'seed', reward: 0.34}` while baseline.json said the seed
    # scored 0.38, which no reader could reconcile. Worse, the gap between the two IS this
    # round's temporal drift — measured at 0.24/0.44/0.38 on identical seed bytes across three
    # runs, i.e. several times the gate bar — so collapsing them erased the one number that says
    # whether any delta in the table means anything.
    gate_res = harness.split_result_from_rollouts(run_dir, gate_ref, args.split)
    parent_res = (gate_res if gate_ref == best
                  else harness.split_result_from_rollouts(run_dir, best, args.split))
    parent = gate_res  # deltas/thresholds are always against the gate reference
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
            "delta_vs_gate_ref": (None if (g.get("candidate") or {}).get("reward") is None
                                  else round((g["candidate"]["reward"] or 0.0)
                                             - gate_res.reward, 4)),
            "gate_delta": (g.get("gate") or {}).get("delta"),
            "gate_threshold": (g.get("gate") or {}).get("threshold"),
            # Structured numeric fields from gate_check.py's own JSON, kept alongside
            # gate_delta/gate_threshold above so commit.py can attach them to the events it
            # writes, rather than only a hand-typed prose note (dashboard.py's gate_decisions
            # previously had to regex-parse these back out of that note — see commit.py).
            "stderr": (g.get("candidate") or {}).get("stderr"),
            "n": g.get("paired_n"),
            "k_se": args.k_se,
            "resolvable_effect_size": (g.get("gate") or {}).get("resolvable_effect_size"),
            # Which val tasks the delta was actually measured over. A row whose footprint is
            # `restricted: false` was measured across the whole split, so its SE carries the
            # noise of every task the edit cannot reach — the defect that made SE(paired Δ)
            # 0.022-0.035 on run_finalrun6 while real per-edit effects were 0.011-0.05.
            "footprint": g.get("footprint"),
            "verdict": g.get("verdict"),
            "regressions": g.get("regressions"),
            "eval_rc": ev.get("rc"),
            "eval_error": ev.get("error"),
            # True only for a control replicate this round read back instead of measuring.
            "reused": bool(ev.get("reused")),
        })

    # A parent-gated round has ALREADY measured the drift-free comparison — it just was not
    # reporting it. On run 32871360361 round 4 the table showed cand4 at +0.15 against the seed's
    # stored 0.38 with a bar of 0.11 (drift), i.e. marginal; the same round's two concurrent
    # controls both read exactly 0.27, so the drift-free answer from the identical rollouts is
    # +0.26 against a bar of 0.00. The 0.11 belongs to WHEN the seed was measured, not to cand4,
    # so parent-mode gating understated the effect and inflated the bar at the same time.
    #
    # Reported rather than made the default: changing the default gate mode on one benchmark's
    # drift would be a guess about every other workload, while an extra comparison is strictly
    # more information and simply agrees with the primary one where there is no drift. Costs no
    # rollouts — the controls are already evaluated and gate_check reads stored data.
    if args.gate_against != "control" and ctl_tags:
        for r in rows:
            if r["tag"] in ctl_tags or r.get("reward") is None:
                continue
            # POOLED over every control replicate this round has, not just the one carrying
            # the round-scoped tag. They are byte-identical copies of the same parent measured
            # in the same round, so they are draws from one distribution and pooling their
            # trials per task is the lower-variance estimate of the same quantity — for free,
            # since these rollouts are already on disk. Measuring against a single replicate is
            # what made this comparison a coin flip: the same candidate read +0.0867 against
            # one replicate and +0.0067 against the other.
            g = _gate(Path(args.run_dir), r["tag"], args.k_se, args.mode,
                      args.veto_regressions, current=",".join(ctl_tags))
            r["control_relative"] = {
                "reference": ctl_tags if len(ctl_tags) > 1 else CTL,
                "gate_delta": (g.get("gate") or {}).get("delta"),
                "gate_threshold": (g.get("gate") or {}).get("threshold"),
                "verdict": g.get("verdict"),
                "reading": ("the same comparison with the DRIFT removed: this candidate against "
                            f"{len(ctl_tags)} byte-identical control(s) measured in this round — "
                            "their trials POOLED per task, so the reference carries less of its "
                            "own measurement error than any single replicate — rather than "
                            "against a reward measured earlier. Where the two disagree, the "
                            "difference is drift, not the edit."
                            if not REUSED else
                            f"this candidate against a byte-identical control of the SAME parent "
                            f"measured in iteration {REUSED['from_iteration']} and reused here. "
                            "It removes the parent's own measurement error but NOT the drift "
                            "since that iteration, so it is not the drift-free comparison a "
                            "concurrent control gives — re-run with --no-reuse-control (or "
                            "--gate-against control, which never reuses) to buy that."),
            }

    # Would the verdict have survived a different control replicate? On run 32871360361 round 3
    # two byte-identical replicates read 0.32 and 0.20 two minutes apart, and the reference was
    # simply whichever carried the round-scoped tag (0.20) — so cand3 scored +0.17 and accepted
    # where against the other replicate it is +0.05 and rejects. The table said nothing about the
    # verdict resting on that choice. Re-gating costs no rollouts, so there is no reason not to
    # check; a verdict that flips is not evidence, whatever the picked replicate showed.
    #
    # MANDATORY two-seed-block sign agreement: this used to run only under
    # --gate-against control, so a parent-gated round (the default) never checked whether its
    # accept survived the choice of control replicate — measured on a real run to have called a
    # null result positive exactly that way, unchecked because the round gated against the stored
    # parent. With --control-replicates 2 the default, this check now always runs whenever there
    # is more than one control block, in EITHER gate mode.
    if len(ctl_tags) > 1:
        for r in rows:
            if r["tag"] in ctl_tags or r.get("reward") is None:
                continue
            by_ref = {}
            for ref in ctl_tags:
                g = _gate(Path(args.run_dir), r["tag"], args.k_se, args.mode,
                          args.veto_regressions, current=ref)
                by_ref[ref] = g.get("verdict")
            r["verdict_by_reference"] = by_ref
            verdicts = {v for v in by_ref.values() if v is not None}
            r["verdict_stable"] = (len(verdicts) <= 1)
            if not r["verdict_stable"]:
                r["verdict"] = "inconclusive"

    ctl = next((r for r in rows if r["tag"] == CTL), None)
    # The floor must be the control's delta against the STORED parent, never against whatever
    # this round gated on. With --gate-against control the control IS the reference, so
    # delta_vs_parent is 0.0 by construction — reporting that as the noise floor would claim
    # zero re-measurement noise, the single most dangerous number this script can print.
    floor = None
    if ctl is not None:
        if args.gate_against == "control":
            floor = abs(ctl["gate_delta"]) if ctl.get("gate_delta") is not None else None
        elif ctl["delta_vs_gate_ref"] is not None:
            floor = abs(ctl["delta_vs_gate_ref"])
    # The gap BETWEEN identical control replicates is the round's empirical bar. It is a
    # stronger statement than any single control's delta, because both replicates are the same
    # bytes on the same seeds: whatever separates them is pure re-measurement. Two such
    # replicates differed by 0.0800 paired on this benchmark — enough to pass a k_se=1.0 gate on
    # zero change — so a candidate that does not clear this number has shown nothing.
    #
    # Earlier attempts at THIS iteration are pooled in. They are the same parent bytes on the
    # same seeds in the same round, so they are samples of the same null, and a re-gate is run
    # precisely to buy more of them: reporting only this attempt's two would discard half the
    # evidence the round has already paid for. `max - min` needs no change to accept them.
    ctl_rows = [r for r in rows if r["tag"] in ctl_tags and r.get("reward") is not None]
    pooled_rows = [{**r, "from_attempt": ATTEMPT} for r in ctl_rows] + PRIOR_CTL
    null_delta = None
    if len(pooled_rows) > 1:
        rewards = [r["reward"] for r in pooled_rows]
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
        # Which gate of this iteration this is. On the live run nothing in the output
        # distinguished "second opinion on iteration 1" from "iteration 1", so an operator
        # watching the stream saw two identical control evaluations and no statement that the
        # second had replaced the first.
        "attempt": ATTEMPT,
        "attempt_reading": (
            f"RE-GATE: attempt {ATTEMPT} at iteration {int(run_dir.spent.iterations)}. Its "
            f"{len(PRIOR_CTL)} earlier control replicate(s) are pooled into `null_delta_...` "
            "below, so the bar here rests on every replicate this round has paid for. This "
            "attempt's candidate rollouts are written under fresh tags; the earlier attempt's "
            "table is still on disk beside this one."
            if ATTEMPT else "first gate of this iteration"),
        "parent": {"tag": best, "reward": parent_res.reward, "stderr": parent_res.stderr,
                   "n_tasks": len(parent_res.per_task or [])},
        # What the deltas and thresholds in `candidates` are actually measured against.
        "gate_reference": {"tag": gate_ref, "mode": args.gate_against,
                           "reward": gate_res.reward, "stderr": gate_res.stderr},
        # The round's OWN drift: identical-or-parent bytes measured now versus what the parent
        # measured when it was scored. Non-null only when they are different measurements.
        "parent_vs_gate_ref_drift": (None if gate_ref == best else
                                     round((gate_res.reward or 0.0)
                                           - (parent_res.reward or 0.0), 4)),
        "drift_reading": (
            "the parent's stored reward and a byte-identical control measured in THIS round "
            "differ by this much. It is re-measurement drift, not progress, and any candidate "
            "delta of comparable size is not evidence — whatever its verdict says."
            if gate_ref != best else
            "gated against the parent's stored reward, so this round cannot see how far that "
            "reward has drifted since it was measured; --gate-against control measures it."),
        # What these rewards are comparable within, and therefore what a LATER round has to
        # match before it may reuse this round's control replicates (see reusable_controls).
        "measurement": MEASUREMENT,
        # Did this round pay for its own control replicates, or read back the ones this SAME
        # parent already has? Reuse happens only while best_id has not moved: the parent is the
        # same bytes, so its noise floor is already established. Any accept invalidates it and
        # the next round measures fresh — the two-replicate requirement is unchanged either way.
        "control_reuse": ({"reused": True, **REUSED,
                           "rollouts_saved": len(REUSED["tags"]),
                           "reading": "the control replicates below were measured in iteration "
                                      f"{REUSED['from_iteration']}, when this same parent was "
                                      "already the parent. No new control rollouts were spent. "
                                      "The replicate GAP is still this parent's own null; what "
                                      "it no longer contains is drift since that iteration, so "
                                      "prefer the parent-mode reading of `evidence_bar` here."}
                          if REUSED else
                          {"reused": False,
                           "reason": ("--no-control" if args.no_control else
                                      "--no-reuse-control" if args.no_reuse_control else
                                      "--gate-against control needs a CONCURRENT control"
                                      if args.gate_against == "control" else
                                      "a re-gate is run to BUY replicate evidence, so it always "
                                      "measures" if ATTEMPT else
                                      "no earlier round measured THIS parent's replicates under "
                                      "this same measurement context — a new parent has no "
                                      "established noise floor, so it must be measured")}),
        "measurement_concurrency": args.concurrency,
        "concurrency_warning": conc_warning,
        "null_delta_between_control_replicates": null_delta,
        "null_delta_replicates": len(pooled_rows),
        "null_delta_reading": (
            "identical bytes on identical seeds, so this is pure re-measurement noise. Any "
            "candidate delta at or below it is NOT evidence, whatever its verdict says."
            + (f" Pooled over {len(pooled_rows)} replicates of this iteration, "
               f"{len(PRIOR_CTL)} of them from earlier attempts." if PRIOR_CTL else "")
            if null_delta is not None else
            "only one control replicate — run with --control-replicates 2 to measure the bar "
            "instead of assuming a formula gives it"),
        "gated_against": {"tag": gate_ref, "mode": args.gate_against},
        "noise_floor_from_control": floor,
        "noise_floor_basis": ("control vs the STORED parent rollouts (differing trial counts are "
                              "part of this floor, which is the point)" if args.gate_against ==
                              "control" else "control vs the parent it was copied from"),
        # ONE bar, matched to how this round actually gated. Reporting several numbers and
        # leaving the driver to choose is not neutral: on run 32871360361 round 2 the table
        # showed cand2 beating its CONCURRENT control by +0.19 (three times the k_se threshold,
        # nineteen times the 0.01 gap between the control's own replicates) alongside a
        # `noise_floor_from_control` of 0.14 — which is the control-vs-STORED-parent gap, i.e.
        # temporal drift. The reading told the driver to treat any delta at or below the floor as
        # no evidence, so it compared a control-relative delta against a drift-derived floor,
        # resolved the contradiction conservatively, and booked a REJECT on the best candidate of
        # the run.
        #
        # Which bar is right depends entirely on what the delta was measured against:
        #   * control mode — the delta is against a control measured in THIS round, so drift is
        #     already cancelled and the bar is the gap between identical replicates.
        #   * parent mode  — the delta is against a reward measured in an earlier round, so drift
        #     is inside it and the bar has to include the control's drift as well.
        "evidence_bar": {
            "value": (null_delta if args.gate_against == "control"
                      else (None if (null_delta is None and floor is None)
                            else max(null_delta or 0.0, floor or 0.0))),
            "basis": ("gap between byte-identical control replicates measured in THIS round — "
                      "drift is cancelled by gating against a concurrent control"
                      if args.gate_against == "control" else
                      "the larger of the replicate gap and the control's drift against the "
                      "stored parent, because this round's deltas ARE against that stored "
                      "reward and carry its drift"),
        },
        "reading": (
            "A candidate marked `verdict_stable: false` has an UNSTABLE verdict and is "
            "INCONCLUSIVE, never accepted: its "
            "verdict changed depending on which byte-identical control replicate happened to be "
            "the reference, so the round cannot tell its edit from re-measurement. Book it as "
            "`commit.py --decision inconclusive` — that charges the iteration but NOT the stall "
            "counter, because a measurement that could not resolve is no evidence you have run "
            "out of ideas, and it keeps the edit out of `rejected.jsonl` so a later round is not "
            "taught to avoid a change nothing ever judged. To resolve it, re-measure under a "
            "FRESH tag (e.g. `cand_2b`) or ask for the higher `--trials` in ONE evaluation: "
            "rollouts are written `<task>__<tag>__t{k}.json` for k in range(n_trials), so "
            "re-running the SAME tag REPLACES t0..t9 rather than adding t10..t19 — it swaps a "
            "reading for another reading and buys no extra evidence. That applies to the "
            "CANDIDATE tags you pass; the control side is handled for you — a re-gate of the "
            "same iteration gets its own `ctl_null_i<N>a<k>` replicates and POOLS the earlier "
            "attempt's into `null_delta_between_control_replicates`, so re-running this script "
            "adds control evidence instead of replacing it. Do not re-use a candidate tag to "
            "get that; there is no pooling for candidates. "
            "Judge every candidate's delta against `evidence_bar` rather than any other noise "
            "number here — but clearing it is NECESSARY, not sufficient: `gate_threshold` "
            "(k·SE on the paired per-task differences) is what each `verdict` is actually "
            "computed from and is usually the stricter of the two, so a delta above "
            "`evidence_bar` and below `gate_threshold` is not an accept. "
            "`noise_floor_from_control` is the gap between a byte-identical control "
            "measured now and the parent's STORED reward: that is re-measurement DRIFT, and it "
            "bounds how far the ABSOLUTE rewards in this table can be trusted — it is not a bar "
            "a candidate gated against a concurrent control has to clear, because that "
            "comparison never contained the drift. Do not re-derive a delta against the stored "
            "parent and reject on it; that puts the drift back in."
            if args.gate_against == "control" else
            "ctl_null is a byte-identical copy of the parent, so its delta is what ZERO change "
            "measures today. This round gated against the parent's STORED reward, so that drift "
            "is inside every candidate delta here: treat any candidate at or below "
            "`evidence_bar` as no evidence, even if its verdict is accept. Gating against the "
            "control instead removes the drift from the comparison."
            if floor is not None or null_delta is not None else
            "no null control in this round — you cannot separate a small gain from re-measurement."
        ),
        "candidates": sorted((r for r in rows if r["tag"] not in ctl_tags),
                             key=lambda r: (r["reward"] is None, -(r["reward"] or 0.0))),
        "control": ctl,
        # `control_replicates` stays THIS attempt's own measurements — that is what a later
        # attempt reads back to pool, and storing the pooled set here would make attempt 2
        # count attempt 0's replicates twice. The pooled view is reported separately.
        "control_replicates": ctl_rows,
        "pooled_control_replicates": pooled_rows if PRIOR_CTL else None,
        "next": ("read regressions, then commit.py --decision accept|reject|inconclusive per "
                 "candidate — `inconclusive` for any row whose `verdict` is inconclusive, so the "
                 "round is not recorded as refuting an edit it could not judge"),
    }
    # Persist the table as well as printing it. Until now the ONLY copy lived on stdout, so
    # whether a round's verdict survived depended on the driver remembering to redirect —
    # and on run 32814848187 the round that was abandoned was only reconstructible because
    # the driver happened to have redirected it to a name someone guessed. A round's gate
    # result is the run's evidence; it should not be optional.
    #
    # Per-iteration name for the same reason `control_tag` is per-iteration: a fixed name
    # would let each round destroy the previous round's table. A same-iteration re-run gets a
    # suffix rather than overwriting, since a re-gate is usually being COMPARED with the
    # first one.
    #
    # The name comes from the SAME attempt index the control tags were built from, rather than
    # from a second, independent probe of the directory. When the two derivations disagreed the
    # table survived and the rollouts it cites did not, which is the whole defect this attempt
    # index exists to close.
    try:
        work.mkdir(parents=True, exist_ok=True)
        table = work / f"{STEM}.json"
        n = ATTEMPT
        while table.exists():  # belt-and-braces: never overwrite a sibling attempt's table
            n += 1
            table = work / f"round_i{int(run_dir.spent.iterations)}.r{n}.json"
        table.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["table_path"] = str(table)
    except OSError as exc:  # noqa: BLE001 — the printed table is still the primary output
        out["table_write_error"] = str(exc)

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

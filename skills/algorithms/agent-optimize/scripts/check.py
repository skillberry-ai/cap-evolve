"""Behavioral contract for agent-optimize.

agent-optimize has no deterministic loop, so **SKILL.md's prose IS the
implementation** — which means the only honest contract test is to *execute* the
commands SKILL.md documents against a real throwaway run dir and fail if they don't
work. (The previous version only grepped SKILL.md for substrings, which is why a gate
invocation using an argparse choice that doesn't exist, a shell heredoc that never
expanded ``$R``, and a ``cp`` into a directory nobody creates all shipped.)

Offline and deterministic: a synthetic adapter + hand-written rollouts, zero model calls.

Asserts, end to end on a temp run dir:
  * the deterministic-invocation guard emits a JSON error naming the fix;
  * ``mkdir -p $R/work`` + copy-the-best is a real path (RunDir does NOT create ``work/``);
  * the documented **diagnose** command runs and yields ``kept_good``;
  * ``gate_check.py`` reaches the **paired** gate off real rollouts (``paired_n > 0``) and
    accepts a genuine improvement;
  * no-regression vetoes a mean gain that breaks a passing task;
  * ``commit.py`` moves ``best_id`` + ``iterations`` + the stall counter;
  * ``screen.py`` runs a real SUBSET eval, records the subset + seed on disk, reports
    MEASURED savings, kills a clearly-worse candidate, promotes a churn candidate, and
    NEVER emits ``accept``;
  * ``spend.py`` surfaces budget_exhausted + the free-text stop_condition **parsed into
    predicates with measured actuals** + a ``recommendation`` + a pre-fan-out
    affordability answer for N siblings;
  * ``measure.py`` prints the train/val/sealed-test table, labels a no-holdout split as a
    FIT metric, and burns the test seal exactly once;
  * every script SKILL.md names exists and is named in SKILL.md (no drift);
  * SKILL.md carries none of the known-broken patterns;
  * the test seal is never consumed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import harness
from cap_evolve.skillcheck import (
    Checker, SyntheticAdapter, import_run, quiet, seed_capability_dir, temp_run_dir,
    write_val_rollout,
)

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[2]
SKILL_MD = HERE.parent / "SKILL.md"
DIAGNOSE = SKILLS / "phases" / "diagnose" / "scripts" / "run.py"


def _run(c: Checker, label: str, argv: list[str], *, expect_rc: int = 0) -> dict | None:
    """Execute a documented command; return its parsed JSON (None on failure).

    ``expect_rc`` lets a check assert a REFUSAL (a script that must fail loudly with a
    JSON error) as well as a success — a guard that returns rc 0 is not a guard.
    """
    env = dict(os.environ, CAPEVOLVE_CORE=str(SKILLS.parent / "core"))
    p = subprocess.run([sys.executable, *argv], capture_output=True, text=True, env=env)
    if p.returncode != expect_rc:
        c.fail(f"documented command returned rc={p.returncode}, expected {expect_rc} "
               f"({label}): "
               f"{(p.stderr or p.stdout).strip()[:400]}")
        return None
    try:
        return json.loads(p.stdout)
    except Exception:  # noqa: BLE001
        c.fail(f"documented command did not emit JSON ({label}): {p.stdout[:200]}")
        return None


def _guard(c: Checker) -> None:
    run = import_run()
    c.require_main(run)
    with quiet() as buf:
        rc = run.main(["--run-dir", "R", "--project", "P", "--optimizer", "x"])
    try:
        payload = json.loads(buf.getvalue())
    except Exception:  # noqa: BLE001
        payload = {}
    c.check(rc != 0 and "orchestration_mode" in str(payload.get("fix", "")),
            "run.main must refuse a deterministic invocation with a JSON fix naming "
            f"orchestration_mode (rc={rc}, payload={payload})",
            note="deterministic invocation is rejected with an actionable fix message")


def _prose(c: Checker, skill: str) -> None:
    for section in ("## Agent-mode loop", "Phase 0", "Honesty invariants",
                    "## Parallel round"):
        c.check(section in skill, f"SKILL.md missing section: {section!r}")
    for needle in ("FULL val", "stop_condition", "finalize", "budget_exhausted",
                   "no-regression", "unique per sibling",
                   # A: the subset ladder and its non-negotiable limit
                   "never accept", "holdout", "net_rollouts",
                   # B: textual constraints re-read from the run dir
                   "predicates", "ambiguous", "recommendation",
                   # C: multi-opportunity rounds and the churn they must not admit
                   "churn",
                   # D: the final full-split measurement
                   "sealed test"):
        c.check(needle in skill, f"SKILL.md missing honesty/loop marker: {needle!r}")

    # Known-broken patterns that previously shipped.
    # `--mode paired` used to be an invalid choice (argparse exit 2). The phase CLI now
    # reaches it, but ONLY in rollout mode: two scalar means carry no per-task deltas.
    # Join backslash continuations so a multi-line invocation is judged as one command.
    _joined = skill.replace("\\\n", " ")
    c.check(all("--run-dir" in ln for ln in _joined.splitlines() if "--mode paired" in ln),
            "SKILL.md pairs `--mode paired` with scalar means — that combination is "
            "refused; a paired test needs --run-dir/--current-tag/--candidate-tag",
            note="any --mode paired invocation supplies a run dir")
    c.check("<<'PY'" not in skill and '<<"PY"' not in skill,
            "SKILL.md uses a heredoc for run-dir Python (a quoted one never expands $R)",
            note="no heredoc-Python: the commit step is a real script with real flags")
    c.check('mkdir -p "$R/work"' in skill,
            "SKILL.md copies into $R/work without creating it (RunDir.create does not)",
            note="$R/work is explicitly created before it is used")
    c.check("Example only" in skill,
            "SKILL.md must mark the capability file layout as example-only")

    # Every helper the loop names must exist, and every helper must be named.
    helpers = ["gate_check.py", "commit.py", "spend.py", "screen.py", "measure.py"]
    for h in helpers:
        c.check((HERE / h).is_file(), f"missing documented helper script: scripts/{h}")
        c.check(h in skill, f"scripts/{h} exists but SKILL.md never uses it")
    c.check("Task" in (skill.split("---")[1] if skill.count("---") >= 2 else ""),
            "frontmatter allowed-tools must include Task for the parallel round",
            note="allowed-tools declares Task (parallel fan-out is actionable)")


def _project(tmp: Path, *, n: int) -> Path:
    """A minimal project dir the SUBPROCESS scripts can load: adapter + spec.

    ``screen.py`` / ``measure.py`` take ``--project`` and go through
    ``check.load_adapter``, so the check needs a real ``adapters/adapter.py`` — not just
    the in-process ``SyntheticAdapter``. It subclasses the same synthetic adapter with
    the same ``n``, so the subprocess sees byte-identical tasks and the numbers line up
    with what this check computed in-process. Still zero model calls.
    """
    project = tmp / "project"
    (project / "adapters").mkdir(parents=True, exist_ok=True)
    (project / "adapters" / "adapter.py").write_text(
        "from cap_evolve.skillcheck import SyntheticAdapter\n\n\n"
        "class Adapter(SyntheticAdapter):\n"
        f"    def __init__(self):\n        super().__init__(n={n})\n",
        encoding="utf-8")
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
        'stop_condition: "reach val mean >= 0.9, or stop after $5 or 30 minutes"\n',
        encoding="utf-8")
    return project


def _screen_round(c: Checker, tmp: Path) -> None:
    """The subset promotion ladder, executed: a kill, a promote, and never an accept."""
    from cap_evolve import RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter

    # n=48 -> a 12-task val, so tier 1 (max(MIN_K, 25%) = 6) stays a STRICT subset.
    # A 20-task project gives val=5, which MIN_K=6 would round up to the whole split —
    # the screen would silently stop being a screen.
    adapter = SyntheticAdapter(n=48)
    project = _project(tmp, n=48)
    run_dir = RunDir.create(tmp / ".capevolve_screen", ts="chk")
    harness.ensure_splits(adapter, run_dir, seed=0)
    R = str(run_dir.root)
    val_ids = run_dir.read_splits().ids("val")

    # A parent that PASSES every val task, written straight to disk — no rollouts paid.
    # This is the point of the design: the screen re-reads the parent instead of re-running it.
    for tid in val_ids:
        write_val_rollout(run_dir, tid, tag="cur", reward=1.0, feedback="solved")
    run_dir.set_best("cur")
    run_dir.snapshot("cur", seed_capability_dir(tmp / "curcap", level=48))

    work = Path(R) / "work"
    work.mkdir(parents=True, exist_ok=True)
    worse = seed_capability_dir(work / "worse_src", level=0)   # solves nothing
    shutil.copytree(worse, work / "worse")
    sc = _run(c, "screen.py (kill)", [str(HERE / "screen.py"), "--run-dir", R,
                                      "--project", str(project),
                                      "--candidate", str(work / "worse"), "--tier", "1"])
    if sc:
        c.check(sc.get("decision") == "kill",
                f"screen.py did not kill a candidate that regresses every task: "
                f"{sc.get('decision')} / {sc.get('reason')}",
                note=f"subset screen kills clear harm: {sc.get('reason')}")
        c.check(0 < len(sc["subset"]["ids"]) < len(val_ids),
                f"screen.py screened {len(sc['subset']['ids'])} of {len(val_ids)} val "
                "tasks — a subset screen must be a strict subset to be cheap")
        c.check(sc["subset"].get("seed") is not None and sc["subset"].get("holdout_frac"),
                "screen.py did not record the subset seed / holdout fraction")
        c.check(sc["savings"]["avoided"] > 0 and
                sc["savings"]["net_rollouts"] == sc["savings"]["full_val_rollouts"]
                - sc["savings"]["fired"],
                f"screen.py savings are not the measured difference: {sc['savings']}",
                note=f"kill saved {sc['savings']['avoided']} of "
                     f"{sc['savings']['full_val_rollouts']} rollouts (measured)")
        rec = run_dir.root / "screens" / f"{sc['screen_tag']}.json"
        c.check(rec.is_file() and json.loads(rec.read_text())["subset"] == sc["subset"],
                f"screen.py did not persist a reproducible record at {rec}",
                note="every screen decision is recorded in $R/screens/ (auditable, seeded)")
        c.check(sc.get("decision") != "accept" and "accept" not in str(sc.get("decision")),
                "a subset screen emitted an accept — subsets may only kill or promote")

    # A candidate that changes nothing measurable must PROMOTE, not be killed on noise.
    shutil.copytree(seed_capability_dir(work / "same_src", level=48), work / "same")
    sc2 = _run(c, "screen.py (promote on a flat subset)",
               [str(HERE / "screen.py"), "--run-dir", R, "--project", str(project),
                "--candidate", str(work / "same"), "--tier", "1"])
    if sc2:
        c.check(sc2.get("decision") == "promote" and sc2.get("inconclusive") is True,
                f"screen.py must promote (not kill) a flat/inconclusive subset: {sc2}",
                note="the screen is biased against false kills: a flat Δ̄ promotes")
        c.check(sc2["savings"]["net_rollouts"] < 0,
                f"a promote must be reported as a COST, not a saving: {sc2['savings']}",
                note="promote costs are booked honestly as negative net_rollouts")

    # Rungs are cumulative: tier 2 must not re-run tier 1's tasks.
    sc3 = _run(c, "screen.py (tier 2 reuses tier 1)",
               [str(HERE / "screen.py"), "--run-dir", R, "--project", str(project),
                "--candidate", str(work / "same"), "--tier", "2"])
    if sc3:
        c.check(sc3.get("reused_from_earlier_tiers"),
                f"tier 2 re-ran tasks tier 1 already screened: {sc3.get('fired_ids')}",
                note="the promotion ladder is cumulative — each rung pays only for new ids")

    c.check(not run_dir.read_splits().test_used,
            "the subset screen consumed the sealed test split")


def _measure(c: Checker, tmp: Path) -> None:
    """The final table: a held-out verdict, a no-holdout warning, and one seal."""
    from cap_evolve import RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter

    adapter = SyntheticAdapter(n=20)
    project = _project(tmp, n=20)
    run_dir = RunDir.create(tmp / ".capevolve_measure", ts="chk")
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed_capability_dir(tmp / "mseed", level=3),
                     run_dir=run_dir)
    R = str(run_dir.root)

    # A genuinely better candidate, accepted through the documented path.
    work = Path(R) / "work"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.candidate_dir("seed"), work / "cand_1")
    (work / "cand_1" / "level.txt").write_text("25", encoding="utf-8")
    harness.evaluate_candidate(adapter, work / "cand_1", run_dir=run_dir, split="val",
                               n_trials=1, tag="cand_1")
    run_dir.snapshot("cand_1", work / "cand_1")
    run_dir.set_best("cand_1")

    m = _run(c, "measure.py (final table + seal)",
             [str(HERE / "measure.py"), "--run-dir", R, "--project", str(project),
              "--train", "on"])
    if m:
        rows = {r.get("split"): r for r in m.get("splits") or []}
        c.check(set(rows) == {"train", "val", "test"},
                f"measure.py did not report every split: {sorted(rows)}")
        c.check(m["holdout"]["test_is_held_out"] is True,
                f"measure.py mislabelled a disjoint split: {m['holdout']}")
        v = rows.get("val") or {}
        c.check((v.get("gate") or {}).get("accept") is True and v["paired"]["n"] > 0,
                f"measure.py did not recompute the val gate on the paired vector: {v}")
        c.check((rows["test"].get("gate") or {}).get("note", "").startswith("no gate"),
                f"measure.py must not gate on test: {rows['test'].get('gate')}")
        c.check(rows["train"].get("best", {}).get("reward") is not None,
                f"--train on did not measure the train split: {rows['train']}")
        c.check(m["val_per_task_movement"]["fixed"],
                f"measure.py reported no per-task movement: {m['val_per_task_movement']}",
                note="measure.py prints per-task fixed/broke movement, not just means")
        c.check(run_dir.read_splits().test_used,
                "measure.py did not burn the test seal (test was never scored)",
                note="measure.py seals test exactly once, via harness.finalize")
        c.check((run_dir.root / "measure.json").is_file(),
                "measure.py did not persist measure.json")
        c.check("net_rollouts" in (m.get("screen_ledger") or {}),
                f"measure.py did not sum the screen ledger: {m.get('screen_ledger')}",
                note="measure.py totals the screens' MEASURED rollout economics")

    # A second call must NOT re-score test; it reports the sealed final.json instead.
    m2 = _run(c, "measure.py (second call, seal already burned)",
              [str(HERE / "measure.py"), "--run-dir", R, "--project", str(project),
               "--train", "off"])
    if m2:
        t = next(r for r in m2["splits"] if r["split"] == "test")
        c.check("already sealed" in t.get("status", ""),
                f"a second measure.py re-scored the sealed test split: {t.get('status')}",
                note="the seal is single-use: a second measure reads final.json")

    # A no-holdout spec must be labelled a FIT metric, not generalisation.
    from cap_evolve.splits import Splits
    nh = RunDir.create(tmp / ".capevolve_nh", ts="chk")
    ids = [t.id for t in adapter.tasks("all")]
    nh.write_splits(Splits(train=list(ids), val=list(ids), test=list(ids), seed=0))
    harness.baseline(adapter, seed_capability_dir(tmp / "nhseed", level=3), run_dir=nh)
    m3 = _run(c, "measure.py (no-holdout spec)",
              [str(HERE / "measure.py"), "--run-dir", str(nh.root), "--project",
               str(project), "--train", "auto", "--skip-test"])
    if m3:
        c.check(m3["holdout"]["test_is_held_out"] is False
                and "FIT metric" in m3["holdout"]["verdict"],
                f"measure.py presented a no-holdout fit as generalisation: {m3['holdout']}",
                note="a no-holdout spec is labelled a FIT metric, with the overlap counted")
        c.check(m3.get("warning") and "null result" in m3["warning"],
                f"best==seed must be flagged as a null result: {m3.get('warning')}")
        tr = next(r for r in m3["splits"] if r["split"] == "train")
        c.check("identical to val" in tr.get("status", ""),
                f"--train auto paid for a train eval identical to val: {tr}")


def _live_round(c: Checker, tmp: Path) -> None:
    """Walk the SKILL.md round against a real run dir, executing each command."""
    from cap_evolve import Budget, RunDir, harness

    # n=20 → ~5 val tasks, and a seed that already solves a few, so the paired delta
    # vector is MIXED (some tasks flip, some don't) and the paired SE is genuinely
    # non-zero — i.e. the check proves the real significance test, not its SE=0 fallback.
    adapter = SyntheticAdapter(n=20)
    seed = seed_capability_dir(tmp, level=3)
    run_dir = RunDir.create(tmp / ".capevolve", ts="chk", budget=Budget(max_iterations=5))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    R = str(run_dir.root)

    project = _project(tmp, n=20)

    # step 0 — the affordability readout + the parsed textual constraints
    sp = _run(c, "spend.py (pre-round)", [str(HERE / "spend.py"), "--run-dir", R,
                                          "--project", str(project),
                                          "--n-siblings", "3"])
    if sp:
        c.check(sp.get("best_id") == "seed" and sp.get("stop") is False,
                f"spend.py did not report a fresh run: {sp}")
        c.check("val mean >= 0.9" in sp.get("stop_condition", ""),
                "spend.py did not echo the project's free-text stop_condition")
        c.check(sp.get("test_sealed") is True, "spend.py reported an unsealed test split")
        c.check(isinstance(sp.get("wallclock_seconds"), (int, float)),
                "spend.py did not measure wallclock from the run dir")
        cons = sp.get("constraints") or {}
        kinds = {p["kind"]: p for p in cons.get("predicates") or []}
        c.check({"target_val_score", "max_usd", "max_wallclock_seconds"} <= set(kinds),
                f"spend.py did not parse the prose into predicates: {sorted(kinds)}",
                note="spend.py parses stop_condition prose into checkable predicates")
        c.check(kinds.get("target_val_score", {}).get("actual")
                == (sp.get("best_val") or {}).get("reward")
                and kinds["target_val_score"]["satisfied"] is False,
                f"target_val_score not checked against the FULL-val mean: "
                f"{kinds.get('target_val_score')}")
        c.check(sp.get("recommendation") == "continue",
                f"spend.py should recommend continue on a fresh run: "
                f"{sp.get('recommendation')} {sp.get('recommendation_reasons')}")
        af = sp.get("afford") or {}
        c.check(af.get("rollouts_needed") == 3 * af.get("val_n", 0),
                f"spend.py --n-siblings did not price N full-val evals: {af}",
                note="spend.py answers affordability for N siblings BEFORE a fan-out")

    # step 1 — the documented diagnose command
    dg = _run(c, "diagnose phase", [str(DIAGNOSE), "--run-dir", R, "--tag", "seed"])
    if dg is not None:
        c.check("kept_good" in dg, f"diagnose emitted no kept_good: {list(dg)}",
                note="diagnose gives clusters to fix + kept_good to protect")

    # step 2 — mkdir work + copy the best (the path RunDir does not create)
    work = Path(R) / "work"
    work.mkdir(parents=True, exist_ok=True)
    tag = "cand_1"
    shutil.copytree(run_dir.candidate_dir("seed"), work / tag)
    c.check((work / tag / "level.txt").is_file(),
            "copying $R/candidates/$BEST into $R/work/<tag> did not produce a working copy",
            note="$R/work/<tag> working-copy flow is real")
    (work / tag / "level.txt").write_text("12", encoding="utf-8")  # a genuine improvement

    # step 4 — full-val eval under the candidate's own tag, then the real gate
    harness.evaluate_candidate(adapter, work / tag, run_dir=run_dir, split="val",
                              n_trials=1, tag=tag)
    g = _run(c, "gate_check.py (accept)", [str(HERE / "gate_check.py"), "--run-dir", R,
                                           "--candidate", tag, "--k-se", "1.0"])
    if g:
        c.check(g.get("paired_n", 0) > 0,
                f"gate_check did not reach the PAIRED gate (paired_n={g.get('paired_n')})",
                note=f"paired gate reachable from the CLI: {g['gate']['reason']}")
        c.check(g.get("verdict") == "accept" and not g.get("regressions"),
                f"gate_check rejected a genuine improvement: {g}")

    # step 5 — commit moves best_id, iterations and the stall counter
    cm = _run(c, "commit.py (accept)", [str(HERE / "commit.py"), "--run-dir", R,
                                       "--candidate-id", tag, "--from-dir", str(work / tag),
                                       "--decision", "accept", "--val", "1.0",
                                       "--note", "raise coverage generally",
                                       "--optimizer-usd", "0.25"])
    if cm:
        c.check(cm.get("best_id") == tag, f"commit.py did not set best: {cm}")
        c.check(cm["spent"]["iterations"] == 1 and cm["spent"]["stall"] == 0
                and cm["spent"]["optimizer_usd"] == 0.25,
                f"commit.py under-recorded spend: {cm['spent']}",
                note="commit.py records iterations + stall + the proposer's own cost")
        c.check(run_dir.candidate_dir(tag).is_dir(), "commit.py did not snapshot the candidate")

    # a reject must advance the stall counter (what budget_exhausted's stall rule reads)
    rj = _run(c, "commit.py (reject)", [str(HERE / "commit.py"), "--run-dir", R,
                                        "--candidate-id", "cand_2", "--from-dir", str(work / tag),
                                        "--decision", "reject", "--note", "no gain"])
    if rj:
        c.check(rj["best_id"] == tag and rj["spent"]["stall"] == 1,
                f"reject changed best or did not advance stall: {rj}")

    c.check(not run_dir.read_splits().test_used,
            "the agent-optimize round consumed the sealed test split",
            note="test split sealed throughout the round")


def _no_regression(c: Checker, tmp: Path) -> None:
    """A mean gain that breaks a passing task must be vetoed."""
    run_dir, _ = temp_run_dir(tmp / "regr", ids=("a", "b", "c", "d"))
    # current: a passes, b/c/d fail  → mean 0.25
    for tid, r in (("a", 1.0), ("b", 0.0), ("c", 0.0), ("d", 0.0)):
        write_val_rollout(run_dir, tid, tag="cur", reward=r, feedback="fb")
    # candidate: a BREAKS, b/c pass  → mean 0.50 (a real mean gain, a real regression)
    for tid, r in (("a", 0.0), ("b", 1.0), ("c", 1.0), ("d", 0.0)):
        write_val_rollout(run_dir, tid, tag="regr", reward=r, feedback="fb")
    run_dir.set_best("cur")

    g = _run(c, "gate_check.py (no-regression)",
             [str(HERE / "gate_check.py"), "--run-dir", str(run_dir.root),
              "--candidate", "regr", "--mode", "strict"])
    if g:
        c.check(g.get("regressions") == ["a"] and g.get("verdict") == "reject",
                f"no-regression did not veto a mean gain that broke task 'a': {g}",
                note="no-regression veto is enforced by a real command, not prose")
        c.check(g["gate"]["accept"] is True,
                f"expected the raw gate to accept the mean gain: {g['gate']}")


def _tag_isolation(c: Checker, tmp: Path) -> None:
    """The screen tag and the full-val tag must NEVER read each other's rollouts.

    This is the one flaw that would silently corrupt every gate decision: the reader
    globs ``*__<tag>__t*.json``, so ``<tag>__screenN`` files must be invisible to a
    read of ``<tag>`` and vice versa. Probe it adversarially — screen says 1.0, full
    val says 0.0, on the SAME candidate — and require the full-val read to return 0.0.
    """
    run_dir, _ = temp_run_dir(tmp / "iso", ids=("a", "b", "c", "d"))
    for tid in ("a", "b", "c", "d"):
        write_val_rollout(run_dir, tid, tag="cur", reward=1.0, feedback="ok")
        # the LIE: the screen tag claims a perfect candidate …
        write_val_rollout(run_dir, tid, tag="cand__screen1", reward=1.0, feedback="ok")
        # … while the candidate's real full-val rollouts are all zeros.
        write_val_rollout(run_dir, tid, tag="cand", reward=0.0, feedback="failed")
    run_dir.set_best("cur")

    full = harness.split_result_from_rollouts(run_dir, "cand", "val")
    c.check(abs(full.reward) < 1e-9 and full.n_scored == 4,
            f"full-val read of tag 'cand' leaked its screen rollouts: reward="
            f"{full.reward} n_scored={full.n_scored} (expected 0.0 over 4)",
            note="rollout isolation: a full-val read of <tag> cannot see <tag>__screenN")
    scr = harness.split_result_from_rollouts(run_dir, "cand__screen1", "val")
    c.check(abs(scr.reward - 1.0) < 1e-9,
            f"screen-tag read leaked the full-val rollouts: reward={scr.reward}",
            note="rollout isolation: a screen read of <tag>__screenN cannot see <tag>")
    g = _run(c, "gate_check.py (tag isolation)",
             [str(HERE / "gate_check.py"), "--run-dir", str(run_dir.root),
              "--candidate", "cand", "--mode", "paired", "--k-se", "1.0"])
    if g:
        c.check(g["candidate"]["reward"] == 0.0 and g["verdict"] == "reject",
                f"the gate read the screen's optimistic rollouts: {g['candidate']}",
                note="the gate scores the full-val tag only, never the screen tag")


def _tag_collision(c: Checker, tmp: Path) -> None:
    """commit.py must REFUSE to reuse a candidate id that already has a decision.

    A real run had two concurrent drivers tag a candidate ``cand_r2``: two reject
    events, ONE set of rollouts — one edit judged on another's evidence, and the
    second snapshot overwrote the first. The guard belongs in commit.py because that
    is where every caller routes.
    """
    run_dir, project = temp_run_dir(tmp / "coll", ids=("a", "b"))
    work = run_dir.root / "work" / "dup"
    work.mkdir(parents=True, exist_ok=True)
    (work / "policy.md").write_text("v1", encoding="utf-8")
    argv = [str(HERE / "commit.py"), "--run-dir", str(run_dir.root),
            "--candidate-id", "dup", "--from-dir", str(work),
            "--decision", "reject", "--note", "first"]
    first = _run(c, "commit.py (first use of a tag)", argv)
    c.check(bool(first) and first.get("decision") == "reject",
            f"the first commit of a fresh tag was refused: {first}")
    second = _run(c, "commit.py (tag reuse)", argv, expect_rc=2)
    c.check(bool(second) and "already" in json.dumps(second),
            f"commit.py accepted a duplicate candidate id: {second}",
            note="commit.py refuses a tag that already carries a decision (no "
                 "two candidates can collapse onto one set of rollouts)")
    forced = _run(c, "commit.py (--force overrides)", argv + ["--force"])
    c.check(bool(forced) and forced.get("decision") == "reject",
            f"--force did not override the collision guard: {forced}")


def main() -> int:
    c = Checker("agent-optimize")
    _guard(c)
    _prose(c, SKILL_MD.read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="agent_optimize_chk_"))
    try:
        _live_round(c, tmp)
        _no_regression(c, tmp)
        _tag_isolation(c, tmp)
        _tag_collision(c, tmp)
        _screen_round(c, tmp)
        _measure(c, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    c.note("agent-mode-only algorithm: every command SKILL.md documents is executed here")
    return c.emit()


if __name__ == "__main__":
    sys.exit(main())

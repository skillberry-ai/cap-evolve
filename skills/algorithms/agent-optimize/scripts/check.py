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
  * ``taskeval.py`` per-task evals exist as documented and ``merge_taskopt.py`` combines
    disjoint per-task edits while REPORTING (never auto-resolving) overlapping ones;
  * every script SKILL.md names exists and is named in SKILL.md (no drift);
  * SKILL.md carries none of the known-broken patterns;
  * the test seal is never consumed.
"""

from __future__ import annotations

import json
import os
import re
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
    helpers = ["gate_check.py", "commit.py", "spend.py", "screen.py", "measure.py",
               "funcmerge.py", "multirep.py",
               "round.py", "taskeval.py", "merge_taskopt.py", "mechanisms.py"]
    for h in helpers:
        c.check((HERE / h).is_file(), f"missing documented helper script: scripts/{h}")
        c.check(h in skill, f"scripts/{h} exists but SKILL.md never uses it")
    c.check("Task" in (skill.split("---")[1] if skill.count("---") >= 2 else ""),
            "frontmatter allowed-tools must include Task for the parallel round",
            note="allowed-tools declares Task (parallel fan-out is actionable)")


def _progressive_disclosure(c: Checker, skill: str) -> None:
    """The body stays inside the 500-line budget, and every reference is pointed AT.

    skill-creator: the SKILL.md body is re-read on every trigger, so it is capped at ~500 lines,
    and each bundled reference must be linked from the body with what it contains AND when to
    load it. References are ONE level deep: a reference that links to another reference cannot
    be read on its own, which is the whole point of the hierarchy.
    """
    body = skill.splitlines()
    c.check(len(body) < 500,
            f"SKILL.md body is {len(body)} lines; the recurring per-trigger budget is 500 — "
            "move depth into references/ with an explicit pointer",
            note=f"SKILL.md body is {len(body)} lines, inside the 500-line budget")

    refs = sorted(p for p in (HERE.parent / "references").glob("*.md"))
    c.check(bool(refs), "no references/ — the split is the point of the hierarchy")
    for ref in refs:
        rel = f"references/{ref.name}"
        c.check(rel in skill, f"{rel} exists but SKILL.md never links it")
        # The pointer must say WHEN to load it, not merely that it exists.
        c.check(f"({rel})" in skill and "**Load**" in skill,
                f"{rel} needs a pointer in SKILL.md's `## References` stating what it contains "
                "and when to load it")
        text = ref.read_text(encoding="utf-8")
        c.check("](references/" not in text,
                f"{rel} links to another reference — references are one level deep, because a "
                "reader may only partially read either one")
        if len(text.splitlines()) > 300:
            c.check("## Contents" in text,
                    f"{rel} is over 300 lines and needs a table of contents")
    c.note(f"{len(refs)} references, each linked with a when-to-load pointer, one level deep")

    # Retrospective narrative belongs in a reference or the run log, never in the body: it is
    # re-read on every trigger and an agent driving a round acts no differently for having it.
    for anecdote in ("in one run", "Measured here", "A real run", "four consecutive null runs"):
        c.check(anecdote not in skill,
                f"SKILL.md carries retrospective narrative ({anecdote!r}) — keep the rule and the "
                "command in the body, move the number that bought it into references/")


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
    """Regressions are REPORTED by default and only VETO under --veto-regressions.

    Both halves are asserted against the same fixture, because the default flip is the
    fix for four consecutive null results (see gate_check.regressions): a per-task drop
    at n trials is an estimate, not evidence of harm, and the veto fired on a
    byte-identical copy of the seed 43% of the time at 5 trials.
    """
    run_dir, _ = temp_run_dir(tmp / "regr", ids=("a", "b", "c", "d"))
    # current: a passes, b/c/d fail  → mean 0.25
    for tid, r in (("a", 1.0), ("b", 0.0), ("c", 0.0), ("d", 0.0)):
        write_val_rollout(run_dir, tid, tag="cur", reward=r, feedback="fb")
    # candidate: a BREAKS, b/c pass  → mean 0.50 (a real mean gain, a real regression)
    for tid, r in (("a", 0.0), ("b", 1.0), ("c", 1.0), ("d", 0.0)):
        write_val_rollout(run_dir, tid, tag="regr", reward=r, feedback="fb")
    run_dir.set_best("cur")

    g = _run(c, "gate_check.py (regressions reported, not vetoed)",
             [str(HERE / "gate_check.py"), "--run-dir", str(run_dir.root),
              "--candidate", "regr", "--mode", "strict"])
    if g:
        c.check(g.get("regressions") == ["a"] and g.get("verdict") == "accept",
                f"default must REPORT the task-'a' regression and still accept the "
                f"gate-passing mean gain: {g}",
                note="the veto is opt-in; the paired/strict gate is the decision rule")
        c.check(g["gate"]["accept"] is True,
                f"expected the raw gate to accept the mean gain: {g['gate']}")

    v = _run(c, "gate_check.py (--veto-regressions)",
             [str(HERE / "gate_check.py"), "--run-dir", str(run_dir.root),
              "--candidate", "regr", "--mode", "strict", "--veto-regressions"])
    if v:
        c.check(v.get("regressions") == ["a"] and v.get("verdict") == "reject",
                f"--veto-regressions must still veto a mean gain that broke task 'a': {v}",
                note="the old behaviour stays reachable for anyone who wants it")


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


def _round_control(c: Checker, tmp: Path) -> None:
    """round.py builds the null control itself and reports the round's own noise floor.

    The control is not optional and not the driver's job to remember: three of the four
    null runs on a multi-turn tool-use benchmark compared a candidate against a parent mean measured in
    an *earlier* round, so re-measurement noise read as signal in both directions. This
    asserts the control is materialised from the current best and shows up in the table.
    """
    from cap_evolve import RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter

    adapter = SyntheticAdapter(n=24)
    project = _project(tmp, n=24)
    run_dir = RunDir.create(tmp / ".capevolve_round", ts="chk")
    harness.ensure_splits(adapter, run_dir, seed=0)
    R = str(run_dir.root)

    # A parent that solves half of val, snapshotted so round.py has something to copy.
    for i, tid in enumerate(run_dir.read_splits().ids("val")):
        write_val_rollout(run_dir, tid, tag="cur", reward=float(i % 2), feedback="fb")
    run_dir.set_best("cur")
    run_dir.snapshot("cur", seed_capability_dir(tmp / "roundcap", level=12))

    work = Path(R) / "work"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copytree(seed_capability_dir(work / "_src", level=24), work / "cand_x")

    r = _run(c, "round.py (null control + parallel eval + serial gate)",
             [str(HERE / "round.py"), "--run-dir", R, "--project", str(project),
              "--candidates", "cand_x", "--n-trials", "1", "--k-se", "1.0"])
    if r:
        ctl_tag = r.get("control", {}).get("tag") or ""
        c.check(ctl_tag.startswith("ctl_null_i") and (work / ctl_tag).is_dir(),
                f"round.py must materialise a ROUND-SCOPED $R/work/ctl_null_i<n> from the "
                f"current best (got {ctl_tag!r})",
                note="the control is built by the script and tagged per round, so it can "
                     "neither be skipped nor overwrite a previous round's noise floor")
        c.check(r.get("noise_floor_from_control") is not None,
                "round.py did not report the round's measured noise floor",
                note="every round reports what ZERO change measures, from its own control")
        c.check([x["tag"] for x in r.get("candidates") or []] == ["cand_x"],
                f"round.py candidate rows wrong: {r.get('candidates')}")
        c.check("commit" in (r.get("next") or ""),
                "round.py must hand the accept/reject decision back to the driver",
                note="round.py never commits: which part of a bundle to keep is a judgement")
        # The table must survive on disk, not only on stdout. A driver that forgot to redirect
        # left the round's gate verdict nowhere: on run 32814848187 the abandoned round was
        # reconstructible only because the driver happened to have redirected it somewhere
        # someone guessed. host.py's un-booked-round backstop reads these files.
        table = r.get("table_path") or ""
        c.check(bool(table) and Path(table).is_file()
                and Path(table).parent == work
                and json.loads(Path(table).read_text(encoding="utf-8")).get("candidates"),
                f"round.py did not persist its gate table under $R/work/ (got {table!r})",
                note="the round's verdict is the run's evidence; it must not depend on the "
                     "driver remembering to redirect stdout")

    # A round whose --n-trials differs from the parent's must be able to pair against the
    # control instead, or every delta silently carries a precision mismatch.
    shutil.rmtree(work / "cand_y", ignore_errors=True)
    shutil.copytree(seed_capability_dir(work / "_src2", level=24), work / "cand_y")
    r2 = _run(c, "round.py --gate-against control",
              [str(HERE / "round.py"), "--run-dir", R, "--project", str(project),
               "--candidates", "cand_y", "--n-trials", "1", "--k-se", "1.0",
               "--gate-against", "control"])
    if r2:
        ref = (r2.get("gated_against") or {})
        c.check(str(ref.get("tag", "")).startswith("ctl_null_i")
                and ref.get("mode") == "control",
                f"--gate-against control did not pair against the control: {ref}",
                note="a round can pair candidates against its OWN control, removing the "
                     "precision mismatch when its n-trials differs from the parent's")
    r3 = _run(c, "round.py --gate-against control --no-control (refused)",
              [str(HERE / "round.py"), "--run-dir", R, "--project", str(project),
               "--candidates", "cand_y", "--n-trials", "1", "--gate-against", "control",
               "--no-control"], expect_rc=2)
    c.check(bool(r3) and "control" in json.dumps(r3),
            f"gating against a control that was skipped must be refused, got {r3}",
            note="asking to gate against a control while disabling it is refused, not ignored")


def _control_replicates(c: Checker, tmp: Path) -> None:
    """A round must evaluate MORE THAN ONE control, and must report the gap between them.

    One control does not bound the noise. Measured on a multi-turn tool-use benchmark: two byte-identical
    controls, same seeds, temperature 0, read 0.6467 and 0.7267 — a paired delta of +0.0800 that
    PASSES a k_se=1.0 bar on zero change. The same candidate then read +0.0867 against one of
    those controls and +0.0067 against the other, so a single-control gate hands out a coin flip.
    Asserted here: the default is at least two replicates, and the round names the gap between
    them rather than leaving the caller to compute it.
    """
    src = (HERE / "round.py").read_text(encoding="utf-8")
    c.check("--control-replicates" in src,
            "round.py must offer control replicates",
            note="one control cannot separate a small gain from re-measurement")
    c.check('"--control-replicates", type=int, default=2' in src.replace("\n", " ")
            or 'default=2' in src.split("--control-replicates")[1][:200],
            "control replicates must DEFAULT to at least 2, not be opt-in",
            note="the failure mode is trusting a single null reading, so the safe value is the "
                 "default")
    c.check("null_delta_between_control_replicates" in src,
            "the round must report the gap between identical control replicates",
            note="identical bytes on identical seeds: that gap IS the bar")


def _multirep(c: Checker, tmp: Path) -> None:
    """A verdict must take its error ACROSS runs, because within-run SE cannot see run noise.

    Measured on a multi-turn tool-use benchmark: one paired run reported SE 0.0548 over tasks and "accept" at
    +0.0867; a second paired run of the same candidate on a different seed block gave +0.0200, and
    a byte-identical control re-run moved +0.0800 on its own. So the across-task SE understates the
    real uncertainty and the tool must refuse to call a single run a demonstration.
    """
    d = tmp / "mr"
    d.mkdir(parents=True, exist_ok=True)

    def arm(name, rates):
        (d / name).write_text(json.dumps(
            {"per_task": {t: {"rate": r} for t, r in rates.items()}}))

    # two runs, same candidate: one looks like a win, the other does not
    arm("c1.json", {"a": 1.0, "b": 0.8, "c": 0.6})
    arm("k1.json", {"a": 0.8, "b": 0.6, "c": 0.4})
    arm("c2.json", {"a": 0.8, "b": 0.6, "c": 0.6})
    arm("k2.json", {"a": 0.8, "b": 0.6, "c": 0.6})
    r = _run(c, "multirep.py (across-run error, inconsistent runs)",
             [str(HERE / "multirep.py"), f"{d/'c1.json'}:{d/'k1.json'}",
              f"{d/'c2.json'}:{d/'k2.json'}"])
    c.check(bool(r) and r.get("n_runs") == 2 and r.get("se_across_runs") is not None
            and "NOT DEMONSTRATED" in str(r.get("verdict")),
            "two runs that disagree must NOT be reported as a demonstrated gain",
            note="a single run's across-task SE cannot see run-to-run nondeterminism")
    r2 = _run(c, "multirep.py (single run refuses to conclude)",
              [str(HERE / "multirep.py"), f"{d/'c1.json'}:{d/'k1.json'}"])
    c.check(bool(r2) and r2.get("se_across_runs") is None
            and "need >= 2" in str(r2.get("verdict")),
            "one paired run must not yield a verdict at all",
            note="the retracted accept in this project came from exactly one paired run")


def _merge_taskopt(c: Checker, tmp: Path) -> None:
    """Per-task fan-out only pays if the merge is trustworthy.

    K optimisers edit the same files from the same base, so combining them is where a good
    round quietly becomes a bad one. Two properties are asserted: disjoint edits from
    different optimisers BOTH survive (a merge that silently drops one turns K measured gains
    into one), and an overlapping edit is reported as `conflicted` rather than auto-resolved
    (two optimisers guarding the same moment is a judgement call, not a textual one).
    """
    root, rel = tmp / "taskopt", "policy.md"
    base = tmp / "mergebase"
    base.mkdir(parents=True, exist_ok=True)
    # A multi-line base: with a ONE-line file every edit touches the same line, so even
    # genuinely independent optimisers would "conflict" and the check would prove nothing.
    (base / rel).write_text("\n".join(f"rule {i}" for i in range(1, 21)) + "\n")

    def copy(name: str, transform) -> None:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(transform((base / rel).read_text()))

    copy("optA", lambda t: "RULE_FROM_A\n" + t)
    copy("optB", lambda t: t + "\nRULE_FROM_B\n")
    copy("optC", lambda t: "RULE_FROM_C\n" + t)   # same first line as optA -> conflict

    argv = [str(HERE / "merge_taskopt.py"), "--root", str(root), "--base", str(base),
            "--files", rel, "--subdirs", "", "--repo", str(tmp / "mergerepo")]
    r = _run(c, "merge_taskopt.py (disjoint edits)",
             argv + ["--out", str(tmp / "merged_ok"), "--include", "optA", "optB"])
    if r:
        merged = (tmp / "merged_ok" / rel).read_text()
        c.check("RULE_FROM_A" in merged and "RULE_FROM_B" in merged,
                "merge dropped an optimiser's edit: both disjoint per-task edits must survive",
                note="a merge that loses one optimiser turns K measured gains into one")
        c.check(not r.get("conflicted"),
                f"disjoint edits reported as conflicting: {r.get('conflicted')}")

    r2 = _run(c, "merge_taskopt.py (overlapping edits)",
              argv + ["--out", str(tmp / "merged_conflict"), "--include", "optA", "optC"],
              expect_rc=1)
    c.check(bool(r2) and bool(r2.get("conflicted")),
            f"an overlapping per-task edit was not reported as conflicted: {r2}",
            note="conflicts are reported, never silently resolved: a semantic conflict means "
                 "dropping a bundle, not shipping a hybrid neither optimiser measured")

    # Opt-in union resolution, for a TEXTUAL collision of two distinct additions. Dropping a
    # verified gain over a whitespace accident is the failure this prevents; the guard against
    # abusing it is that the affected files are named and the result must still be rendered.
    r3 = _run(c, "merge_taskopt.py (--union-on-conflict keeps both sides)",
              argv + ["--out", str(tmp / "merged_union"), "--include", "optA", "optC",
                      "--union-on-conflict"])
    if r3:
        got = (tmp / "merged_union" / rel).read_text()
        c.check("RULE_FROM_A" in got and "RULE_FROM_C" in got,
                "union resolution must keep BOTH colliding additions",
                note="a textual collision of distinct additions is resolved by union, since the "
                     "union is what both optimisers actually measured")
        c.check(r3.get("union_resolution_enabled") is True and r3.get("union_candidates"),
                f"union resolution must name what it resolved: {r3}",
                note="union-resolved files are named so the distinct-additions claim is checkable")
        c.check("RENDER" in (r3.get("next") or "").upper(),
                "union resolution must demand the live toolset be rendered afterwards",
                note="keeping both sides can duplicate a definition or break syntax, which an "
                     "import check does not catch")


def _mechanisms(c: Checker, tmp: Path) -> None:
    """The fan-out ledger must survive concurrent writers and must gate reimplementation.

    Its entire job is to stop K optimisers rediscovering one cause and writing K colliding
    fixes for it, so two properties matter: concurrent appends do not lose or tear rows, and
    a listing names what is already owned so a second implementation is refused by policy
    rather than discovered at merge time.
    """
    import concurrent.futures as cf

    run = tmp / "mechrun"
    run.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, str(HERE / "mechanisms.py"), "add", "--run-dir", str(run)]
    env = dict(os.environ, CAPEVOLVE_CORE=str(SKILLS.parent / "core"))

    def one(i: int) -> int:
        return subprocess.run(
            argv + ["--owner", f"t{i}", "--status", "proposed",
                    "--mechanism", f"cause {i}", "--evidence", f"trace {i}",
                    "--touches", f"tool_{i}"],
            capture_output=True, text=True, env=env).returncode

    with cf.ThreadPoolExecutor(max_workers=9) as ex:
        rcs = list(ex.map(one, range(9)))
    c.check(all(r == 0 for r in rcs), f"concurrent ledger appends failed: {rcs}")

    r = _run(c, "mechanisms.py list", [str(HERE / "mechanisms.py"), "list",
                                       "--run-dir", str(run)])
    if r:
        c.check(r.get("count") == 9,
                f"ledger lost rows under 9 concurrent writers: count={r.get('count')}",
                note="the mechanism ledger is append-atomic across parallel optimisers")
        c.check(sorted(r.get("already_owned_do_not_reimplement") or [])
                == [f"tool_{i}" for i in range(9)],
                f"ledger did not report owned surfaces: {r.get('already_owned_do_not_reimplement')}",
                note="listing names what is already owned, so a duplicate fix is refused "
                     "by policy instead of discovered at merge time")

    _run(c, "mechanisms.py add (rejected)",
         [str(HERE / "mechanisms.py"), "add", "--run-dir", str(run), "--owner", "t0",
          "--status", "rejected", "--mechanism", "m", "--evidence", "e"])
    r2 = _run(c, "mechanisms.py list (after reject)",
              [str(HERE / "mechanisms.py"), "list", "--run-dir", str(run)])
    c.check(bool(r2) and len(r2.get("rejected") or []) == 1,
            "a rejected mechanism must be listed so a retry can be made structurally different",
            note="rejected attempts are remembered, not silently retried")

    # Relevance filtering: a real fan-out ledger reached 99 findings, and pasting all of them
    # into each of K subagents spends their context on other optimisers' tasks. Filtering must
    # narrow to the task WITHOUT hiding the task-independent rows, which are the cross-cutting
    # measurement facts (canary bands, variance warnings) that apply to everyone.
    _run(c, "mechanisms.py add (task-scoped row)",
         [str(HERE / "mechanisms.py"), "add", "--run-dir", str(run), "--owner", "tA",
          "--status", "verified", "--mechanism", "task-nine-only finding",
          "--evidence", "e", "--task", "9", "--touches", "f_nine"])
    _run(c, "mechanisms.py add (other-task row)",
         [str(HERE / "mechanisms.py"), "add", "--run-dir", str(run), "--owner", "tB",
          "--status", "verified", "--mechanism", "task-fortytwo-only finding",
          "--evidence", "e", "--task", "42", "--touches", "f_ft"])
    r3 = _run(c, "mechanisms.py list --task",
              [str(HERE / "mechanisms.py"), "list", "--run-dir", str(run), "--task", "9"])
    blob = json.dumps(r3 or {})
    c.check(bool(r3) and "task-nine-only" in blob and "task-fortytwo-only" not in blob,
            "--task must keep this task's rows and drop other tasks' rows",
            note="K subagents should not each read K-1 other task histories")
    c.check(bool(r3) and "rejected" in blob and any(
        not (row.get("tasks") or [])
        for grp in ("verified", "proposed", "rejected") for row in (r3.get(grp) or [])),
            "--task must still show task-INDEPENDENT rows",
            note="cross-cutting measurement facts apply to every optimiser; hiding them is "
                 "how a fan-out repeats a defect someone already paid for")
    # A finding that turns out to be WRONG must stop appearing as verified. Three separate
    # `verified` rows were disproved on the real run, and without this a reader saw both the
    # claim and its refutation with no way to tell which won.
    r_old = _run(c, "mechanisms.py add (a claim that will later be disproved)",
                 [str(HERE / "mechanisms.py"), "add", "--run-dir", str(run), "--owner", "tX",
                  "--status", "verified", "--mechanism", "CLAIM_TO_BE_RETIRED",
                  "--evidence", "single reading", "--touches", "f_x"])
    seq = str((r_old or {}).get("added", {}).get("seq"))
    _run(c, "mechanisms.py add (superseding row)",
         [str(HERE / "mechanisms.py"), "add", "--run-dir", str(run), "--owner", "tX",
          "--status", "rejected", "--supersedes", seq,
          "--mechanism", "RETIREMENT", "--evidence", "remeasured", "--touches", "f_x"])
    r_after = _run(c, "mechanisms.py list (superseded row retired)",
                   [str(HERE / "mechanisms.py"), "list", "--run-dir", str(run)])
    blob2 = json.dumps((r_after or {}).get("verified") or [])
    sup = (r_after or {}).get("superseded_do_not_act_on") or []
    c.check(bool(r_after) and "CLAIM_TO_BE_RETIRED" not in blob2
            and any("CLAIM_TO_BE_RETIRED" in (x.get("mechanism") or "") for x in sup),
            "a superseded finding must drop out of verified and be listed as retired",
            note="a disproved claim left in `verified` is worse than no ledger")



def _funcmerge(c: Checker, tmp: Path) -> None:
    """Whole-file merge conflicts on additions that do not disagree; per-function must not.

    This is the exact shape that cost a real round 6 of 10 verified branches: every optimiser
    appends one independent line to the SAME function, so their edits land on adjacent lines
    and diff3 conflicts even though nobody disagrees. Asserted here: independent insertions
    into one shared function all survive, the result PARSES, no `def` is duplicated, and a
    genuine rewrite of the same line still conflicts rather than being silently unioned.
    """
    d = tmp / "fm"
    d.mkdir(parents=True, exist_ok=True)
    base = d / "base.py"
    base.write_text(
        "class T:\n"
        "    def __init__(self):\n"
        "        self.a = 1\n"
        "\n"
        "    def go(self, x):\n"
        "        self.check(x)\n"
        "        return x\n"
    )
    # three branches, each adding one state field AND one guard call to the same two functions
    for tag, field, guard in [("bA", "self.b = 2", "self.gb(x)"),
                              ("bB", "self.c = 3", "self.gc(x)"),
                              ("bC", "self.d = 4", "self.gd(x)")]:
        (d / f"{tag}.py").write_text(
            base.read_text()
            .replace("        self.a = 1\n", f"        self.a = 1\n        {field}\n")
            .replace("        self.check(x)\n", f"        self.check(x)\n        {guard}\n")
        )
    out = d / "out.py"
    r = _run(c, "funcmerge.py (independent insertions in one shared function)",
             [str(HERE / "funcmerge.py"), "--base", str(base), "--out", str(out),
              "--union-pure-insertions", "--inputs",
              str(d / "bA.py"), str(d / "bB.py"), str(d / "bC.py")])
    text = out.read_text() if out.exists() else ""
    c.check(bool(r) and r.get("written") and all(
        f in text for f in ("self.b = 2", "self.c = 3", "self.d = 4",
                            "self.gb(x)", "self.gc(x)", "self.gd(x)")),
            "every branch's independent insertion into a shared function must survive",
            note="whole-file 3-way merge conflicts here and keeps one; that is the bug this fixes")
    ok_parse = False
    dups: list[str] = []
    if text:
        import ast as _ast
        try:
            t = _ast.parse(text)
            names = [n.name for n in _ast.walk(t)
                     if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))]
            dups = sorted({n for n in names if names.count(n) > 1})
            ok_parse = True
        except SyntaxError:
            ok_parse = False
    c.check(ok_parse and not dups,
            "the merged file must parse and define no function twice",
            note="the union-on-conflict path this replaces produced an unparseable file "
                 "with five duplicated defs")

    # a genuine rewrite of the same base line must NOT be unioned away
    (d / "rA.py").write_text(base.read_text().replace("        return x\n",
                                                      "        return x + 1\n"))
    (d / "rB.py").write_text(base.read_text().replace("        return x\n",
                                                      "        return x * 2\n"))
    out2 = d / "out2.py"
    r2 = _run(c, "funcmerge.py (rival rewrites of one line)",
              [str(HERE / "funcmerge.py"), "--base", str(base), "--out", str(out2),
               "--union-pure-insertions", "--inputs", str(d / "rA.py"), str(d / "rB.py")],
              expect_rc=1)
    c.check(bool(r2) and not r2.get("written") and r2.get("conflicts"),
            "two branches rewriting the same line must conflict, not be auto-unioned",
            note="that is a disagreement about the right answer and belongs to a human")

    # A forced-trunk resolution can re-apply a subtraction the losing branch already measured
    # and reverted. That is invisible in the conflict report, so the merge must SAY what it
    # failed to carry.
    (d / "fA.py").write_text(base.read_text().replace(
        "    def go(self, x):\n", "    def go(self, x):\n        # KEEPME_A rationale line\n"))
    (d / "fB.py").write_text(base.read_text().replace(
        "        return x\n", "        return x  # rewritten by B\n"))
    out3 = d / "out3.py"
    r4 = _run(c, "funcmerge.py (forced trunk reports dropped additions)",
              [str(HERE / "funcmerge.py"), "--base", str(base), "--out", str(out3),
               "--union-pure-insertions", "--force-priority", "--priority", "fB", "fA",
               "--inputs", str(d / "fA.py"), str(d / "fB.py")])
    got = json.dumps((r4 or {}).get("dropped_additions") or {})
    c.check(bool(r4) and (("KEEPME_A" in got) or ("KEEPME_A" in out3.read_text())),
            "a branch addition the merge did not carry must be REPORTED, not silently lost",
            note="a dropped rewrite can re-apply a subtraction its owner measured as harmful")

    # A merged function may reference a class CONSTANT the merge did not carry. That is a
    # runtime crash, not a style problem: the tool layer turns AttributeError into an error
    # string, the agent abandons the write, and the reward records a MISSING WRITE. It
    # contaminated four measurements on a real run before a live tool return exposed it, so it
    # must be a hard failure. The second half of this check matters just as much: the fields it
    # inspects are routinely declared WITH annotations (`self.x: set[str] = set()`), and a
    # collector that only walks ast.Assign reports those as undefined and rejects a good merge.
    (d / "cA.py").write_text(
        "class T:\n    db: int\n    LADDER = (1, 2, 3)\n\n"
        "    def go(self, x):\n        return x\n\n"
        "    def need(self):\n        return self.LADDER[0]\n")
    (d / "cB.py").write_text(
        "class T:\n    db: int\n\n    def go(self, x):\n        return x + 1\n")
    r5 = _run(c, "funcmerge.py (class constant is CARRIED, not left behind)",
              [str(HERE / "funcmerge.py"), "--base", str(base), "--out", str(d / "out4.py"),
               "--union-pure-insertions", "--force-priority", "--priority", "cB", "cA",
               "--inputs", str(d / "cA.py"), str(d / "cB.py")])
    got5 = (d / "out4.py").read_text() if (d / "out4.py").exists() else ""
    import re as _re
    c.check(bool(r5) and r5.get("written")
            and _re.search(r"^    LADDER = \(1, 2, 3\)", got5, _re.M) is not None,
            "a class CONSTANT a merged function needs must be carried into the class body",
            note="merging only functions left it behind; the reference then crashed at runtime "
                 "and presented as a missing write")

    # Backstop: a constant that exists in NO input cannot be carried, and must still refuse.
    (d / "gA.py").write_text(
        "class T:\n    db: int\n\n    def go(self, x):\n        return x\n\n"
        "    def need(self):\n        return self.NOWHERE[0]\n")
    r5b = _run(c, "funcmerge.py (truly undefined constant still refuses)",
               [str(HERE / "funcmerge.py"), "--base", str(base), "--out", str(d / "out4b.py"),
                "--union-pure-insertions", "--inputs", str(d / "gA.py")],
               expect_rc=1)
    c.check(bool(r5b) and not r5b.get("written") and "NOWHERE" in str(r5b.get("error")),
            "an attribute defined in no input must refuse to write, not ship a crash",
            note="the crash is invisible in the reward, so it cannot be left to the gate")

    # A branch's inserted lines may legitimately REPEAT. De-duplicating by line text deleted the
    # second copy and truncated a multi-line statement into a syntax error whose only symptom was
    # "'{' was never closed" — a corrupted artifact, not a refusal.
    (d / "rA.py").write_text(
        "class T:\n    def __init__(self):\n        self.a = 1\n\n"
        "    def go(self, x):\n        return x\n")
    (d / "rB.py").write_text(
        "class T:\n    def __init__(self):\n        self.a = 1\n"
        "        self.p = {\n            k: 1\n            for k in self.src\n        }\n"
        "        self.q = {\n            k\n            for k in self.src\n        }\n\n"
        "    def go(self, x):\n        return x\n")
    out6 = d / "out6.py"
    r7 = _run(c, "funcmerge.py (repeated lines inside one insertion survive)",
              [str(HERE / "funcmerge.py"), "--base", str(d / "rA.py"), "--out", str(out6),
               "--union-pure-insertions", "--inputs", str(d / "rB.py")])
    got7 = out6.read_text() if out6.exists() else ""
    c.check(bool(r7) and r7.get("written") and got7.count("for k in self.src") == 2,
            "a line that legitimately repeats within one insertion must not be de-duplicated",
            note="dedupe is only for the SAME hunk from two branches at the same anchor")

    (d / "nA.py").write_text(
        "class T:\n    db: int\n\n    def __init__(self):\n"
        "        self.seen: set[str] = set()\n\n"
        "    def go(self, x):\n        return x in self.seen\n")
    r6 = _run(c, "funcmerge.py (annotated instance attribute is not 'undefined')",
              [str(HERE / "funcmerge.py"), "--base", str(d / "nA.py"),
               "--out", str(d / "out5.py"), "--union-pure-insertions",
               "--inputs", str(d / "nA.py")])
    c.check(bool(r6) and r6.get("written"),
            "an attribute declared with an annotation must not be reported undefined",
            note="ast.AnnAssign, not ast.Assign — a hard check with false positives is worse "
                 "than no check")



def _gate_concurrency(c: Checker, tmp: Path) -> None:
    """The gate must default to LOW concurrency, and must SAY SO when it is run high.

    Measured on this benchmark with byte-identical code at identical seeds: mean per-task
    movement 0.250 at concurrency 25 versus 0.100 at concurrency 8; tasks moving 10/12 versus
    5/12; arm-level |delta| 0.1167 versus 0.0333. Four consecutive gate rounds in this repo were
    decided at a concurrency where a byte-identical control moved +0.0800 — larger than every
    effect being chased. So the default has to be low, and a driver who overrides it has to be
    told what the override costs, in the JSON, next to the verdict.
    """
    src = (HERE / "round.py").read_text(encoding="utf-8")
    m = re.search(r'"--concurrency",\s*type=int,\s*default=(\w+)', src)
    # The default may be a literal or a named constant; resolve a name to its assignment so the
    # check follows the value rather than the spelling (a name-only assertion would pass for
    # DEFAULT_CONCURRENCY = 100).
    got = m.group(1) if m else ""
    if got and not got.isdigit():
        nm = re.search(rf'^{re.escape(got)}\s*=\s*(\d+)', src, re.M)
        got = nm.group(1) if nm else got
    c.check(bool(m) and got.isdigit() and int(got) <= 12,
            f"round.py --concurrency default is {got or 'missing'}: a gate above "
            "~12 cannot resolve an effect smaller than the 0.08 a null control moves there",
            note="the gate's measurement concurrency defaults to a LOW value")
    # …and the refusal bound above it must exist and be a real bound, or the default is only a
    # suggestion the driver can step over — which is what it did.
    mb = re.search(r'^MAX_RESOLVING_CONCURRENCY\s*=\s*(\d+)', src, re.M)
    c.check(bool(mb) and int(mb.group(1)) >= int(got or 0)
            and "allow-high-concurrency" in src and "return 2" in src,
            "round.py must REFUSE a concurrency too coarse to resolve its own verdict, with a "
            "deliberate escape hatch — warning about it in the output was not enough",
            note="a gate the driver set too hot is refused, not warned about")
    c.check("concurrency_warning" in src and "measurement_concurrency" in src,
            "round.py must report measurement_concurrency and a concurrency_warning, so a "
            "verdict that cannot resolve the effect is not read as a clean one",
            note="a high-concurrency gate warns IN the result, not just in prose")


def _integrate_is_mandated(c: Checker, skill: str) -> None:
    """SKILL.md must tell the driver to ASSEMBLE with integrate.py, not merely that it exists.

    Measured, and the reason this check is here: on the round integrate.py was written, its own
    author merged six branches in one step instead of using it. The resulting artifact gated at
    -0.0146 with seven replicated per-task losses against two replicated gains, while the same
    round's single-mechanism artifact gated at +0.0115. A tool that is documented as available but
    not as REQUIRED gets skipped under time pressure, which is exactly when it is needed.
    """
    # SKILL.md is hard-wrapped, so any multi-word phrase can straddle a newline. Match on
    # whitespace-normalised text: a check that fails on line wrapping is a false positive, and a
    # contract with false positives trains its reader to ignore it.
    flat = " ".join(skill.split())
    c.check("integrate.py" in flat and "never by one merge" in flat,
            "SKILL.md must state that a multi-branch artifact is assembled with integrate.py and "
            "NOT by a single merge; documenting the script's existence is not enough",
            note="sequential assembly is mandated, not merely available")
    c.check("Clean merge is a syntactic property" in flat,
            "SKILL.md must warn that funcmerge merging cleanly is not evidence the branches "
            "compose - every branch retained cleanly in the artifact that then failed its gate",
            note="a clean merge is explicitly distinguished from composition")


def _integrate(c: Checker, tmp: Path) -> None:
    """Verified per-task branches must be folded in ONE AT A TIME, each step measured.

    Measured: a one-shot merge of independently-verified branches scored -0.0617 against
    seed-matched arms, and the task whose own fix was merged fell 0.40 -> 0.20. Verified gains do
    not compose, and one number for N simultaneous changes cannot say which change broke it.
    Asserted here: canaries sit INSIDE the objective, a step at or below the noise floor is
    recorded as provisional rather than as a gain, and the subset objective is self-labelled as
    selection-biased so it is never quoted as a val estimate.
    """
    src = (HERE / "integrate.py").read_text(encoding="utf-8")
    c.check("for bdir in args.branches" in src and "_measure(" in src,
            "integrate.py must measure after EACH branch, or a regression is unattributable",
            note="integration is sequential and measured per step")
    c.check("tasks + canary" in src,
            "scoring only target tasks is how a branch that breaks a passing task gets kept",
            note="canaries are part of the integration objective, not a side check")
    c.check("kept_provisionally" in src and "--floor" in src,
            "integrate.py must take a measured floor and mark sub-floor steps provisional",
            note="a step inside the noise floor is provisional, never a gain")
    c.check("upward-biased by selection" in src,
            "a mean over tasks chosen BECAUSE they were failing is not a val estimate; "
            "integrate.py must say so in its own output",
            note="the subset objective is labelled upward-biased by selection")
    c.check('"--conc", type=int, default=8' in src,
            "integration decisions are gate decisions and must run at the low concurrency",
            note="integration defaults to the low gate concurrency")
    # Measured: a hand-picked canary set drawn from tasks near the mechanisms let four high scorers
    # be damaged unguarded (two at 1.00, one at 0.90, one at 0.80), and the artifact's gate failed on
    # exactly that collateral. Selection must be mechanical and suite-wide, and it must prefer the
    # FRAGILE high scorers rather than the safest ones.
    c.check("--canary-auto" in src and "canary_floor" in src.replace("-", "_"),
            "integrate.py must offer suite-wide canary selection from a baseline, or a canary set "
            "picked near the mechanisms will miss the collateral damage that actually fails gates",
            note="canaries can be selected mechanically from the WHOLE suite")
    c.check("pool.sort()" in src and "lowest rate first" in src,
            "auto-selected canaries must be taken lowest-rate-first: the most fragile high scorers "
            "are the ones that catch collateral damage",
            note="auto-canary selection keeps the most fragile high scorers")


def _benchmark_agnostic(c: Checker) -> None:
    """The skill must not name a specific benchmark, its tasks, or its domain vocabulary.

    An algorithm skill is supposed to work the same on any benchmark. Guidance earned on one of
    them is worth keeping -- with its numbers -- but the moment it carries that benchmark's NAME,
    its task ids or its domain nouns, the skill reads as one benchmark's notebook and a reader on a
    different benchmark cannot tell which parts apply to them. This check exists because exactly
    that drift happened once and had to be undone by hand across eleven files.

    Attribution is the one exception: naming the source benchmark in the frontmatter `sources:`
    field is correct, because that is where "here is where this evidence came from" belongs.
    """
    tokens = re.compile(
        r"\b(tau2\w*|airline|AirlineTools|swebench|swe_bench|gpt-oss|"  # noqa-selfscan
        r"cancel_reservation|get_user_details|update_reservation\w*)\b", re.I)  # noqa-selfscan
    roots = [SKILL_MD, HERE.parent / "references"]
    offenders: list[str] = []
    for root in roots:
        files = sorted(root.rglob("*")) if root.is_dir() else [root]
        for f in files:
            if not f.is_file() or f.suffix not in (".md", ".py"):
                continue
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip().startswith("sources:"):
                    continue                      # attribution, not coupling
                if tokens.search(line):
                    offenders.append(f"{f.name}:{i}")
    for f in sorted(HERE.glob("*.py")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "noqa-selfscan" in line:
                continue                          # this checker's own token list
            if tokens.search(line):
                offenders.append(f"{f.name}:{i}")
    c.check(not offenders,
            "the skill names a specific benchmark, its tasks or its domain vocabulary at "
            f"{offenders[:6]} — state the lesson and keep the NUMBER, drop the benchmark's "
            "identity, and put benchmark attribution in the frontmatter `sources:` field",
            note="no benchmark, optimizer or agent identity leaks into the skill's own text")


def _host(c: Checker, tmp: Path) -> None:
    """The headless host: a briefing that carries the loop, and a guaranteed seal.

    This is the seam that makes the algorithm usable with no human in the loop, so both of
    its own guarantees are executed here — offline, no agent CLI involved:

      * ``--prompt-only`` renders the briefing (the run's audit trail of what the host
        actually asked for) and spends nothing;
      * ``--seal-only`` seals a run the agent left open, and is idempotent — a host that
        raised ``TestSealError`` on an already-sealed run would fail runs that are complete.
    """
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter

    host = HERE / "host.py"
    if not c.check(host.is_file(), "missing scripts/host.py (the headless host)"):
        return

    adapter = SyntheticAdapter(n=20)
    seed = seed_capability_dir(tmp / "host", level=3)
    project = _project(tmp / "host", n=20)
    run_dir = RunDir.create(tmp / "host" / ".capevolve", ts="host",
                            budget=Budget(max_iterations=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    R, P = str(run_dir.root), str(project)

    rendered = _run(c, "host.py --prompt-only",
                    [str(host), "--run-dir", R, "--project", P, "--prompt-only"])
    if rendered:
        body = Path(rendered["prompt_path"]).read_text(encoding="utf-8")
        for needle in ("spend.py", "gate_check.py", "commit.py", "measure.py"):
            c.check(needle in body, f"the host briefing never names {needle}")
        c.check(R in body and P in body,
                "the host briefing does not carry the handoff paths")
        c.check("do not ask" in body.lower(),
                "the host briefing must tell the agent not to ask questions — an "
                "unattended run that waits for a reply stalls until it is killed")
        env = rendered.get("agent_env") or {}
        c.check(int(env.get("BASH_MAX_TIMEOUT_MS", 0)) >= 3_600_000
                and int(env.get("BASH_DEFAULT_TIMEOUT_MS", 0)) >= 3_600_000,
                f"the host left the Bash-tool timeout at its 10-minute default: {env} — "
                "every full-val eval would be killed mid-flight and read as a broken runner",
                note="the host raises the Bash-tool ceiling past a full-val eval")

    c.check(not (run_dir.root / "final.json").exists(),
            "--prompt-only must not seal anything")
    sealed = _run(c, "host.py --seal-only",
                  [str(host), "--run-dir", R, "--project", P, "--seal-only"])
    if sealed:
        c.check(sealed.get("sealed") is True and sealed.get("seal") == "host",
                f"--seal-only did not seal, or did not label the seal as the host's: {sealed}")
    again = _run(c, "host.py --seal-only (idempotent)",
                 [str(host), "--run-dir", R, "--project", P, "--seal-only"])
    if again:
        c.check(again.get("seal") == "agent",
                f"a second seal must report the run as already sealed, not re-seal: {again}",
                note="the host's seal is idempotent — a complete run is never failed for it")

    unknown = _run(c, "host.py --agent <unknown>",
                   [str(host), "--run-dir", R, "--project", P,
                    "--agent", "definitely-not-a-registry-row"], expect_rc=2)
    if unknown:
        c.check("registry" in json.dumps(unknown).lower(),
                f"an unknown host agent must be refused with a pointer at the registry, "
                f"before any spend: {unknown}")


def main() -> int:
    c = Checker("agent-optimize")
    _guard(c)
    _skill_text = SKILL_MD.read_text(encoding="utf-8")
    _prose(c, _skill_text)
    _progressive_disclosure(c, _skill_text)
    _integrate_is_mandated(c, _skill_text)
    tmp = Path(tempfile.mkdtemp(prefix="agent_optimize_chk_"))
    try:
        _live_round(c, tmp)
        _no_regression(c, tmp)
        _tag_isolation(c, tmp)
        _tag_collision(c, tmp)
        _screen_round(c, tmp)
        _round_control(c, tmp)
        _control_replicates(c, tmp)
        _multirep(c, tmp)
        _merge_taskopt(c, tmp)
        _funcmerge(c, tmp)
        _gate_concurrency(c, tmp)
        _integrate(c, tmp)
        _mechanisms(c, tmp)
        _measure(c, tmp)
        _host(c, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _benchmark_agnostic(c)
    c.note("agent-mode-only algorithm: every command SKILL.md documents is executed here")
    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
